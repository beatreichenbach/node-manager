import os
import re
import logging
import glob
import time
import shutil
from enum import Enum, unique

from PySide2 import QtWidgets, QtGui, QtCore

from . import manager
from . import gui_utils


class ProcessDialog(QtWidgets.QDialog):
    # todo:
    # sorting
    # restart item
    # show log
    # on fail: ok
    # cancel end all running runnables
    # progress bar, all nodes (but when restart, set new number)

    # model / item
    # item: state, log, display
    def __init__(self, parent=None):
        super(ProcessDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()
        self.nodes = []
        self.runnable = None
        self.nodes_completed = 0
        self.runnable_count = 0

        self.model = QtGui.QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['State', 'Item'])
        self.process_view.setModel(self.model)

        self.threadpool = QtCore.QThreadPool(self)
        self.threadpool.setMaxThreadCount(4)

    def init_ui(self):
        gui_utils.load_ui(self, 'process_dialog.ui')

        view = ProcessView(self)
        self.layout().replaceWidget(self.process_view, view)
        self.process_view = view

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
        self.button_box.rejected.connect(self.reject)

    def accept(self):
        super(ProcessDialog, self).accept()

    def reject(self):
        self.status_bar.showMessage('Waiting for all running processes to exit...')
        self.status_bar.repaint()
        # todo: call a stop function on all threads in the pool?
        self.threadpool.waitForDone()

        super(ProcessDialog, self).reject()

    def set_nodes(self, nodes):
        self.nodes = nodes

        self.runnable_count = len(nodes)
        self.status_bar.showMessage('Processing {} items.'.format(self.runnable_count))

        for node in nodes:
            items = []

            item = QtGui.QStandardItem()
            item.setData(self.state_text(ProcessState.PENDING), QtCore.Qt.DisplayRole)
            item.setData(self.state_icon(ProcessState.PENDING), QtCore.Qt.DecorationRole)
            items.append(item)

            runnable = self.runnable(node, item)

            item = QtGui.QStandardItem()
            item.setData(runnable.display_text(), QtCore.Qt.DisplayRole)
            item.setData(node)
            items.append(item)

            self.model.appendRow(items)

            runnable.started.connect(self.node_started)
            runnable.finished.connect(self.node_finished)

            self.threadpool.start(runnable)

    def node_started(self, node, item):
        state_item = self.model.item(item.row(), 0)
        state_item.setData(self.state_icon(ProcessState.INPROGRESS), QtCore.Qt.DecorationRole)
        state_item.setData(self.state_text(ProcessState.INPROGRESS), QtCore.Qt.DisplayRole)

    def node_finished(self, node, item):
        state_item = self.model.item(item.row(), 0)
        state_item.setData(self.state_icon(ProcessState.COMPLETED), QtCore.Qt.DecorationRole)
        state_item.setData(self.state_text(ProcessState.COMPLETED), QtCore.Qt.DisplayRole)

        self.nodes_completed = self.nodes_completed + 1

        self.main_prgbar.setValue(self.nodes_completed / self.runnable_count * 100)

    def finished(self):
        # self.accept()
        pass

    @classmethod
    def process(cls, nodes, runnable):
        dialog = cls()
        dialog.runnable = runnable
        dialog.set_nodes(nodes)

        # thread.start()
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.nodes

    @staticmethod
    def state_text(state):
        return str(state.value)

    @staticmethod
    def state_icon(state):
        # reuse cancelled icon
        if state == ProcessState.FAILED:
            state = ProcessState.CANCELLED
        filename = 'state_{}.svg'.format(state.name.lower())
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', filename)
        icon = QtGui.QIcon(icon_path)
        return icon


class ProcessView(QtWidgets.QTableView):
    def __init__(self, dialog, parent=None):
        super(ProcessView, self).__init__(parent)

        # feeling not great about this one chief
        self.dialog = dialog

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

        if not self.model():
            return

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

        # talk about this not belonging here
        self.dialog.nodes_completed = self.dialog.threadpool.activeThreadCount()
        logging.debug(self.dialog.threadpool.activeThreadCount())
        self.dialog.runnable_count = self.dialog.threadpool.activeThreadCount() + len(indexes)
        self.dialog.main_prgbar.setValue(self.dialog.nodes_completed / self.dialog.runnable_count * 100)
        self.dialog.status_bar.showMessage('Processing {} items.'.format(self.dialog.runnable_count))

        for item_index in indexes:
            item = self.model().itemFromIndex(item_index)
            item.setData(self.dialog.state_text(ProcessState.PENDING), QtCore.Qt.DisplayRole)
            item.setData(self.dialog.state_icon(ProcessState.PENDING), QtCore.Qt.DecorationRole)

            node = self.model().item(item_index.row(), 1).data()

            # lol we noticing some WET
            runnable = self.dialog.runnable(node, item)
            runnable.started.connect(self.dialog.node_started)
            runnable.finished.connect(self.dialog.node_finished)
            self.dialog.threadpool.start(runnable)

    def show_log(self, index):
        pass
        # dialog = QtWidgets.QDialog()
        # dialog.setLayout(QtWidgets.QVBoxLayout())
        # text_edit = QtWidgets.QTextEdit()

        # item = self.model().item(index.row(), 0)
        # log = item.data(QtCore.Qt.UserRole + 2)
        # text_edit.setText(log or '')
        # text_edit.setTextInteractionFlags(text_edit.textInteractionFlags() | ~QtCore.Qt.TextEditable)
        # dialog.layout().addWidget(text_edit)
        # dialog.exec_()


class NodeRunnable(QtCore.QRunnable):
    def __init__(self, node, model_item=None):
        super(NodeRunnable, self).__init__()
        self.node = node
        self.model_item = model_item
        self.signals = WorkerSignals()
        self.started = self.signals.started
        self.finished = self.signals.finished

    def run(self):
        self.started.emit(self.node, self.model_item)
        self.process()
        self.finished.emit(self.node, self.model_item)

    def process(self):
        time.sleep(1)

    def display_text(self):
        return self.node.name

    def log(self, text):
        log = self.model_item.data(QtCore.Qt.UserRole + 2) or ''
        if log:
            log += '\n'
        log += text
        self.model_item.setData(QtCore.Qt.UserRole + 2)
        logging.debug(self.model_item.data(QtCore.Qt.UserRole + 2))


class WorkerSignals(QtCore.QObject):
    started = QtCore.Signal(manager.Node, QtGui.QStandardItem)
    finished = QtCore.Signal(manager.Node, QtGui.QStandardItem)


@unique
class ProcessState(Enum):
    OPEN = 'Open'
    PENDING = 'Pending'
    INPROGRESS = 'In Progress'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'
    FAILED = 'Failed'
