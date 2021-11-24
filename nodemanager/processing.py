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

    def __init__(self, nodes, runnable, parent=None):
        super(ProcessingDialog, self).__init__(parent)
        self.runnable = runnable
        self.runnable_completed = 0
        self.runnable_count = 0

        self.init_ui()
        self.connect_ui()
        self.set_nodes(nodes)

        self.model = ProcessingModel()
        self.model.setHorizontalHeaderLabels(['State', 'Item'])
        self.process_view.setModel(self.model)

        self.threadpool = QtCore.QThreadPool(self)
        self.threadpool.setMaxThreadCount(2)

    def init_ui(self):
        gui_utils.load_ui(self, 'process_dialog.ui')

        view = ProcessingView(dialog=self)
        self.layout().replaceWidget(self.process_view, view)
        self.process_view.setParent(None)
        self.process_view = view

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
        self.button_box.rejected.connect(self.reject)
        self.process_view.restarted.connect(self.reset_progress)

    # def accept(self):
    #     super(ProcessingDialog, self).accept()

    def reject(self):
        self.status_bar.showMessage('Waiting for all running processes to exit...')
        self.status_bar.repaint()

        for item in self.items:
            item.stop()
        self.threadpool.waitForDone()

        super(ProcessingDialog, self).reject()

    def set_nodes(self, nodes):
        self.nodes = nodes

        for node in nodes:
            items = []
            processing_item = ProcessingItem(node, self.runnable, self.threadpool)
            processing_item.created.connect(partial(self.item_created, item))
            processing_item.started.connect(partial(self.item_started, item))
            processing_item.finished.connect(partial(self.item_finished, item))

            item = QtGui.QStandardItem()
            item.setData(processing_item.state, QtCore.Qt.DisplayRole)
            item.setData(processing_item)
            items.append(item)

            item = QtGui.QStandardItem()
            item.setData(processing_item.display_text(), QtCore.Qt.DisplayRole)
            item.setData(processing_item)
            items.append(item)

            self.model.appendRow(items)

    def item_created(self, item):
        self.update_item(item)
        self.runnable_count += 1
        self.status_bar.showMessage('Processing {} items.'.format(self.runnable_count))
        self.update_progress()

    def item_started(self, item):
        self.update_item(item)

    def item_finished(self, item):
        self.update_item(item)
        self.runnable_completed += 1
        self.update_progress()

    def update_item(self, item):
        item = self.model.item(item.row(), 0)
        processing_item = item.data()
        item.setData(processing_item.state)

    def update_progress(self):
        self.main_prgbar.setValue(self.runnable_completed / self.runnable_count * 100)

    def reset_progress(self):
        self.runnable_count = self.runnable_count - self.runnable_completed
        self.runnable_completed = 0

    def finished(self):
        return
        self.accept()

    @property
    def items(self):
        items = [self.model.item(row, 0).data() for row in self.model.rowCount()]
        return items

    @classmethod
    def process(cls, nodes, runnable):
        dialog = cls(nodes, runnable)

        result = dialog.exec_()

    @staticmethod
    def state_text(state):
        return str(Processingstate.value)



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
        action.triggered.connect(lambda: self.restart(index))
        action = menu.addAction('Show log')
        action.triggered.connect(lambda: self.show_log(index))

        menu.popup(event.globalPos())

    def restart(self, index):
        if not self.model():
            return

        index = self.model().index(index.row(), 0)

        # Sometimes the right click happens on not selected row
        indexes = [index]
        if self.selectionModel():
            indexes.extend(self.selectionModel().selectedRows(index.column()))
        indexes = list(set(indexes))

        self.restarted.emit()

        for item_index in indexes:
            item = self.model().itemFromIndex(item_index).data()
            item.restart()

    def show_log(self, index):
        model_item = self.model().itemFromIndex(index)
        item = model_item.data()

        dialog = QtWidgets.QDialog()
        dialog.setLayout(QtWidgets.QVBoxLayout())
        text_edit = QtWidgets.QTextEdit()
        text_edit.setText(item.log_stream.getvalue())
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

    def setData(self, index, value, role):
        super(NodesModel, self).setData(index, value, role)

        if isinstance(value, ProcessingState):
            icon = self.icon(value)
            super(NodesModel, self).setData(index, icon, QtCore.Qt.DecorationRole)

    @staticmethod
    def icon(value):
        if isinstance(value, State):
            # reuse cancelled icon
            if value == ProcessingState.FAILED:
                value = ProcessingState.CANCELLED
            filename = 'state_{}.svg'.format(value.name.lower())
        else:
            return QtGui.QIcon()

        icon_path = os.path.join(os.path.dirname(__file__), 'icons', filename)
        icon = QtGui.QIcon(icon_path)
        return icon

class ProcessingRunnable(QtCore.QRunnable):
    def __init__(self, item):
        super(ProcessingRunnable, self).__init__()
        self.item = item
        self.node = item.node
        self.logger = item.logger
        self.running = False

    def run(self):
        self.running = True
        try:
            self.process()
        except Exception as e:
            self.error(e)
        self.item.end()

    def stop(self):
        self.running = False

    def process(self):
        # example code
        for i in range(4):
            if not self.running:
                return
            time.sleep(1)

    def display_text(self):
        return self.item.node.name

@unique
class State(Enum):
    OPEN = 'Open'
    PENDING = 'Pending'
    INPROGRESS = 'In Progress'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'
    FAILED = 'Failed'


class ProcessingItem(object):
    created = QtCore.Signal()
    started = QtCore.Signal()
    finished = QtCore.Signal()

    def __init__(self, node, runnable):
        self.node = node
        self.runnable = runnable

        self._state = ProcessingState.OPEN

        self.log_stream = StringIO()
        self.logger = logging.getLogger(str(hash(self)))
        self.logger.addHandler(logging.StreamHandler(self.log_stream))

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        item = self.model.item(self.row, 0)
        item.setData(value)

    def start(self):
        runnable = self.runnable(self)
        self.state = ProcessingState.INPROGRESS
        self.started.emit()
        self.threadpool.start()


    def restart(self):
        if self.state not in (ProcessingState.PENDING, ProcessingState.OPEN):
            self.runnable.stop()
            self.start()

    def stop(self):
        self.item.state = ProcessingState.CANCELLED
        if runnable.running:
            self.logger.error('Process cancelled by the user')
            self.runnable.stop()

    def _finished(self):
        # internal signal called by runnable
        self.logger.info('Process finished succesfully')
        self.finished.emit()

    def error(exception):
        self.logger.critical(exception, exc_info=True)
