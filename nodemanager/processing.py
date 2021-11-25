import os
import re
import logging
import glob
import time
import shutil
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
        self.footer_lay.setStretch(1, 0)

    def connect_ui(self):
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.process_view.restarted.connect(self.reset_progress)

    def accept(self):
        # super(ProcessingDialog, self).accept()
        for row in range(self.model.rowCount()):
            processing_item = self.model.item(row, 0).data()
            processing_item.stop()

    def reject(self):
        try:
            self.status_bar.showMessage('Waiting for all running processes to exit...')
            self.status_bar.repaint()

            # if self.model:
            #     for row in range(self.model.rowCount()):
            #         logging.debug(row)
            #         item = self.model.item(row, 0)
            #         logging.debug(item)


                    # processing_item = item.data()
                    # logging.debug(processing_item)
            # for item in self.items:
            #     logging.debug(item.node)
                # item.stop()

            self.threadpool.waitForDone()
        except Exception as e:
            logging.critical(e, exc_info=True)
        super(ProcessingDialog, self).reject()

    def set_nodes(self, nodes):
        self.nodes = nodes

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

            processing_item.started.connect(partial(self.item_started, item))
            processing_item.finished.connect(partial(self.item_finished, item))
            self.item_created(item)

    def item_created(self, item):
        self.update_item(item)
        self.runnable_count += 1
        self.status_bar.showMessage('Processing {} items.'.format(self.runnable_count))
        self.update_progress()

        # start the runnable
        processing_item = item.data()
        processing_item.start()
        self.threadpool.start(processing_item.runnable)

    def item_started(self, item):
        self.update_item(item)

    def item_finished(self, item):
        self.update_item(item)
        self.runnable_completed += 1
        self.update_progress()

    def update_item(self, item):
        item = self.model.item(item.row(), 0)
        processing_item = item.data()
        item.setData(processing_item.state.value, QtCore.Qt.DisplayRole)
        item.setData(self.icon(processing_item.state), QtCore.Qt.DecorationRole)

        item = self.model.item(item.row(), 1)
        item.setData(processing_item.display_text(), QtCore.Qt.DisplayRole)

    def update_progress(self):
        self.main_prgbar.setValue(self.runnable_completed / self.runnable_count * 100)

    def reset_progress(self):
        self.runnable_count = self.runnable_count - self.runnable_completed
        self.runnable_completed = 0

    def finished(self):
        return
        self.accept()

    @classmethod
    def process(cls, nodes, runnable_cls):
        dialog = cls(nodes, runnable_cls)
        result = dialog.exec_()

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
        action.triggered.connect(partial(self.restart, index))
        action = menu.addAction('Show log')
        action.triggered.connect(partial(self.show_log, index))

        menu.popup(event.globalPos())

    def restart(self, index):
        if not self.model():
            return

        self.restarted.emit()

        # Sometimes the right click happens on not selected row
        indexes = [index]
        if self.selectionModel():
            indexes.extend(self.selectionModel().selectedRows(index.column()))
        indexes = list(set(indexes))

        for item_index in indexes:
            processing_item = self.model().itemFromIndex(item_index).data()
            processing_item.restart()

    def show_log(self, index):
        item = self.model().itemFromIndex(index)
        processing_item = item.data()

        dialog = QtWidgets.QDialog()
        dialog.setLayout(QtWidgets.QVBoxLayout())
        text_edit = QtWidgets.QTextEdit()
        text_edit.setText(processing_item.log_stream.getvalue())
        text_edit.setReadOnly(True)
        dialog.layout().addWidget(text_edit)
        dialog.exec_()


class ProcessingModel(QtGui.QStandardItemModel):
    # def data(self, index, role=QtCore.Qt.DisplayRole):
    #     # override to enable deferred loading of items
    #     data = super(ProcessingModel, self).data(index, role)
    #     if role == QtCore.Qt.DisplayRole and callable(data):
    #         data = data()
    #     return data

    # def setData(self, index, value, role):
    #     super(ProcessingModel, self).setData(index, value, role)

    #     if isinstance(value, ProcessingState):
    #         icon = self.icon(value)
    #         super(ProcessingModel, self).setData(index, icon, QtCore.Qt.DecorationRole)

    @property
    def items(self):
        items = [self.item(row, 0).data() for row in range(self.rowCount())]
        return items


class ProcessingRunnable(QtCore.QRunnable):
    def __init__(self, item):
        super(ProcessingRunnable, self).__init__()
        self.item = item
        self.node = item.node
        self.logger = item.logger
        self.running = False

        # implement this bad boi or refer to item state?
        self.cancelled = False

    def run(self):
        # todo: can this be reorganized a bit simpler?
        self.running = True
        # shouldn't be here...
        self.item.started.emit()
        self.item.state = ProcessingState.INPROGRESS

        try:
            result = self.process()
            if not result:
                return
        except Exception as e:
            self.item.error(e)
            return
        finally:
            self.running = False

        self.item.finish()

    def stop(self):
        self.running = False

    def process(self):
        # example code
        for i in range(4):
            self.logger.debug(self.running)
            if not self.running:
                return False
            time.sleep(1)
            self.logger.debug(i)
        return True

    @staticmethod
    def display_text(node):
        return node.name


@unique
class ProcessingState(Enum):
    OPEN = 'Open'
    PENDING = 'Pending'
    INPROGRESS = 'In Progress'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'
    FAILED = 'Failed'


class ProcessingItem(QtCore.QObject):
    started = QtCore.Signal()
    finished = QtCore.Signal()

    def __init__(self, node, runnable_cls, parent=None):
        super(ProcessingItem, self).__init__(parent)
        self.node = node
        self.runnable = None
        self.runnable_cls = runnable_cls

        self.state = ProcessingState.OPEN

        self.log_stream = StringIO()
        self.logger = logging.getLogger(str(hash(self)))
        # self.logger.propagate = False
        self.logger.addHandler(logging.StreamHandler(self.log_stream))

    def start(self):
        self.logger.info('Process started')
        self.runnable = self.runnable_cls(self)
        self.state = ProcessingState.PENDING

    def restart(self):
        if self.state not in (ProcessingState.PENDING, ProcessingState.OPEN):
            self.runnable.stop()
            self.start()

    def stop(self):
        if self.state != ProcessingState.COMPLETED:
            self.state = ProcessingState.CANCELLED
            self.runnable.stop()
            self.logger.error('Process cancelled by the user')
        self.finished.emit()

    def finish(self):
        self.state = ProcessingState.COMPLETED
        self.logger.info('Process finished succesfully')
        self.finished.emit()

    def error(self, exception):
        self.logger.critical(exception, exc_info=True)
        self.finished.emit()

    def display_text(self):
        return self.runnable_cls.display_text(self.node)
