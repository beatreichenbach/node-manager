import os
import re
import logging
import glob
import time
import shutil
import random
import subprocess
from functools import partial
from enum import Enum, unique
from io import StringIO

from PySide2 import QtWidgets, QtGui, QtCore

from . import manager
from . import gui_utils


class ProcessingDialog(QtWidgets.QDialog):
    # on fail: ok

    def __init__(self, nodes, runnable_cls, parent=None):
        super(ProcessingDialog, self).__init__(parent)
        self.runnable_cls = runnable_cls
        self.runnable_completed = 0
        self.runnable_count = 0

        self.threadpool = QtCore.QThreadPool(self)
        self.threadpool.setMaxThreadCount(2)

        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(['State', 'Item'])

        self.init_ui()
        self.connect_ui()
        self.set_nodes(nodes)

    def init_ui(self):
        gui_utils.load_ui(self, 'process_dialog.ui')

        view = ProcessingView()
        self.layout().replaceWidget(self.process_view, view)
        self.process_view.setParent(None)
        self.process_view = view
        self.process_view.setModel(self.model)

        # status bar
        self.status_bar = QtWidgets.QStatusBar()
        palette = self.status_bar.palette()
        palette.setColor(palette.Window, palette.color(palette.AlternateBase))
        palette.setColor(palette.WindowText, palette.color(palette.HighlightedText))
        self.status_bar.setPalette(palette)
        self.status_bar.setAutoFillBackground(True)

        self.status_bar.setSizeGripEnabled(False)
        self.footer_lay.insertWidget(0, self.status_bar)
        self.footer_lay.setStretch(0, 1)
        self.footer_lay.setStretch(1, 0)

    def connect_ui(self):
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.process_view.restarted.connect(self.reset_progress)

    def reject(self):
        # todo: can this be put into a property?
        if self.runnable_count - self.runnable_completed:
            self.status_bar.showMessage('Waiting for all running processes to exit...')
            self.status_bar.repaint()

        try:
            self.threadpool.clear()
            for row in range(self.model.rowCount()):
                processing_item = self.model.item(row, 0).data()
                processing_item.stop()
            success = self.threadpool.waitForDone(30000)
            if not success:
                raise Exception(
                    'Could not exit all running threads. It is recommended to save and '
                    'restart the application.') from Exception
        except Exception as e:
            logging.critical(e, exc_info=True)
        finally:
            self.status_bar.clearMessage()

        super(ProcessingDialog, self).reject()

    def set_nodes(self, nodes):
        processing_items = []
        for node in nodes:
            items = []
            processing_item = ProcessingItem(node, self.runnable_cls, self)

            # icon item
            item = QtGui.QStandardItem()
            item.setData(processing_item)
            items.append(item)

            # text item
            item = QtGui.QStandardItem()
            item.setData(processing_item)
            items.append(item)

            self.model.appendRow(items)

            processing_item.queued.connect(partial(self.item_queued, item))
            processing_item.started.connect(partial(self.item_started, item))
            processing_item.finished.connect(partial(self.item_finished, item))

            processing_items.append(processing_item)

        random.shuffle(processing_items)
        for processing_item in processing_items:
            processing_item.start()

    def item_queued(self, item):
        # todo: only call when needed
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel)

        # start the runnable
        processing_item = item.data()
        self.threadpool.start(processing_item.runnable)
        self.update_item(item)

        self.runnable_count += 1
        self.status_bar.showMessage('Processing {} items.'.format(self.runnable_count))
        self.update_progress()

    def item_started(self, item):
        self.update_item(item)

    def item_finished(self, item):
        self.update_item(item)
        self.runnable_completed += 1
        if self.runnable_count == self.runnable_completed:
            self.finished()
        self.update_progress()

    def finished(self):
        self.status_bar.showMessage('Done', 1000)
        for row in range(self.model.rowCount()):
            processing_item = self.model.item(row, 0).data()
            if processing_item.state == ProcessingState.FAILED:
                return

        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Ok)

    def update_item(self, item):
        item = self.model.item(item.row(), 0)
        processing_item = item.data()
        item.setData(processing_item.state.value, QtCore.Qt.DisplayRole)
        item.setData(self.icon(processing_item.state), QtCore.Qt.DecorationRole)

        item = self.model.item(item.row(), 1)
        item.setData(processing_item.display_text(), QtCore.Qt.DisplayRole)

    def update_progress(self):
        self.main_prgbar.setValue(self.runnable_completed / self.runnable_count * 100)
        # todo: only call when needed
        self.main_prgbar.setVisible(self.main_prgbar.value() != 100)

    def reset_progress(self):
        self.runnable_count = self.runnable_count - self.runnable_completed
        self.runnable_completed = 0

    @classmethod
    def process(cls, nodes, runnable_cls):
        dialog = cls(nodes, runnable_cls)
        dialog.exec_()

    @staticmethod
    def icon(value):
        if isinstance(value, ProcessingState):
            # reuse cancelled icon
            if value == ProcessingState.FAILED:
                value = ProcessingState.CANCELLED
            filename = 'state_{}.svg'.format(value.name.lower())
        else:
            return QtGui.QIcon()

        icon_path = os.path.join(os.path.dirname(__file__), 'icons', filename)
        icon = QtGui.QIcon(icon_path)
        return icon


class ProcessingView(QtWidgets.QTableView):
    restarted = QtCore.Signal()

    def __init__(self, parent=None):
        super(ProcessingView, self).__init__(parent)

        self.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        # self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSortingEnabled(True)

        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsMovable(True)
        self.verticalHeader().hide()

        self.setFocusPolicy(QtCore.Qt.NoFocus)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())

        menu = QtWidgets.QMenu(self)
        action = menu.addAction('Restart')
        action.triggered.connect(partial(self.run_action, self.restart, index))
        action = menu.addAction('Restart (Verbose)')
        action.triggered.connect(partial(self.run_action, self.restart_verbose, index,))
        action = menu.addAction('Cancel')
        action.triggered.connect(partial(self.run_action, self.cancel, index))
        action = menu.addAction('Show log')
        action.triggered.connect(partial(self.run_action, self.show_log, index))

        menu.popup(event.globalPos())

    def run_action(self, func, index):
        if not self.model():
            return

        # Sometimes the right click happens on not selected row
        indexes = [index]
        if self.selectionModel():
            indexes.extend(self.selectionModel().selectedRows(index.column()))
        indexes = sorted(list(set(indexes)), key=lambda i: i.row())

        processing_items = []
        for item_index in indexes:
            processing_item = self.model().itemFromIndex(item_index).data()
            processing_items.append(processing_item)
        func(processing_items)

    def cancel(self, items):
        for processing_item in items:
            processing_item.stop()

    def restart_verbose(self, items):
        self.restarted.emit()
        for processing_item in items:
            processing_item.logger.setLevel(logging.DEBUG)
            processing_item.restart()

    def restart(self, items):
        self.restarted.emit()
        for processing_item in items:
            processing_item.logger.setLevel(logging.INFO)
            processing_item.restart()

    def show_log(self, items):
        if not items:
            return
        processing_item = items[-1]

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('Log')
        dialog.setLayout(QtWidgets.QVBoxLayout())
        text_edit = QtWidgets.QTextEdit()
        text_edit.setText(processing_item.log)
        text_edit.setReadOnly(True)

        font = QtGui.QFont('Monospace')
        font.setStyleHint(QtGui.QFont.Monospace)
        text_edit.setFont(font)
        dialog.text_edit = text_edit

        dialog.layout().addWidget(text_edit)

        processing_item.log_updated.connect(text_edit.setText)

        dialog.show()


class ProcessingRunnable(QtCore.QRunnable):
    def __init__(self, item):
        super(ProcessingRunnable, self).__init__()
        self.item = item
        self.node = item.node
        self.logger = item.logger
        self.running = False

        self._process = None

    def run(self):
        self.running = True
        self.item._started()

        completed = False
        try:
            completed = self.process()
        except Exception as e:
            self.item._failed(e)
            return
        finally:
            self.running = False

        if completed:
            self.item._completed()
        else:
            self.item._cancelled()

    def stop(self):
        if not self.running:
            self.item._cancelled()
        else:
            if self._process:
                self._process.kill()
            self.running = False

    def process(self):
        return True
        # example code

    def popen(self, args, **kwargs):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self._process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            text=True,
        )

        if self.logger.level == logging.DEBUG:
            while self._process.poll() is None:
                self.logger.info(self._process.stdout.readline(), extra={'raw': True})
            self._process.stdout.close()
        return_code = self._process.wait()

        if return_code:
            self.logger.error(subprocess.CalledProcessError(return_code, args))

        return return_code

    def display_text(self):
        return self.node.name


@unique
class ProcessingState(Enum):
    OPEN = 'Open'
    PENDING = 'Pending'
    INPROGRESS = 'In Progress'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'
    FAILED = 'Failed'


class Handler(logging.StreamHandler):
    def __init__(self, item, stream=None):
        super(Handler, self).__init__(stream)
        self.item = item

    def emit(self, record):
        if hasattr(record, 'raw') and record.raw:
            self.stream.write(record.getMessage())
        else:
            super(Handler, self).emit(record)
        self.item.log_updated.emit(self.stream.getvalue())


class ProcessingItem(QtCore.QObject):
    queued = QtCore.Signal()
    started = QtCore.Signal()
    finished = QtCore.Signal()

    log_updated = QtCore.Signal(str)

    def __init__(self, node, runnable_cls, parent=None):
        super(ProcessingItem, self).__init__(parent)
        self.node = node
        self.runnable_cls = runnable_cls
        self.runnable = None
        self.state = ProcessingState.OPEN

        self.logger = logging.getLogger(str(hash(self)))
        self.logger.propagate = False
        self.log_handler = Handler(self, StringIO())
        self.log_handler.setFormatter(logging.Formatter(fmt='{levelname}: {message}', style='{'))
        self.logger.addHandler(self.log_handler)

    def _started(self):
        self.state = ProcessingState.INPROGRESS
        self.logger.info('Process started')
        self.started.emit()

    def _completed(self):
        self.state = ProcessingState.COMPLETED
        self.logger.info('Process finished succesfully')
        self.finished.emit()

    def _cancelled(self):
        self.state = ProcessingState.CANCELLED
        self.logger.error('Process cancelled by the user')
        self.finished.emit()

    def _failed(self, exception):
        self.state = ProcessingState.FAILED
        self.logger.critical(exception, exc_info=True)
        self.finished.emit()

    def start(self):
        self.state = ProcessingState.PENDING
        self.runnable = self.runnable_cls(self)
        self.queued.emit()

    def restart(self):
        if self.state not in (ProcessingState.PENDING, ProcessingState.OPEN):
            if self.state == ProcessingState.INPROGRESS:
                self.runnable.stop()
            self.clear_log()
            self.start()

    def stop(self):
        if self.state in (ProcessingState.OPEN, ProcessingState.PENDING, ProcessingState.INPROGRESS):
            self.runnable.stop()

    def clear_log(self):
        self.log_handler.setStream(StringIO())

    @property
    def log(self):
        return self.log_handler.stream.getvalue()

    def display_text(self):
        return self.runnable.display_text()
