import os
import re
import glob
import logging
import shutil

from PySide2 import QtWidgets, QtCore, QtGui

try:
    from . import gui_utils
    from . import utils
    from . import manager
except ImportError:
    import gui_utils
    import utils
    import manager


class ManagerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, dcc='', context='', node=''):
        super(ManagerWidget, self).__init__(parent)

        self.setObjectName('ManagerWidget')
        self.dcc = dcc
        self.context = context
        self.node = node
        self.init_ui()

        plugin = '_'.join((self.dcc, self.context, self.node))
        self.manager = manager.Manager.from_plugin(plugin)

        self.nodes_view.setModel(self.manager.model)

        self.action_widget.updateActions()
        self.connect_ui()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_widget.ui')

        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(self.filter_scroll)
        self.splitter.addWidget(self.list_scroll)
        self.layout().insertWidget(2, self.splitter)

        self.list_lay.removeWidget(self.nodes_view)
        self.nodes_view = NodesView()
        self.list_lay.insertWidget(0, self.nodes_view)

        self.list_lay.removeWidget(self.action_widget)
        self.action_widget = ActionWidget(self)
        self.list_lay.insertWidget(1, self.action_widget)

        self.setStyleSheet('QTableView::item {border: 0px; padding: 0px 10px;}')

    def connect_ui(self):
        self.load_btn.clicked.connect(self.manager.load)


class NodesView(QtWidgets.QTableView):
    def __init__(self, parent=None):
        super(NodesView, self).__init__(parent)

        self.setSelectionBehavior(self.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSortingEnabled(True)

        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsMovable(True)
        self.verticalHeader().hide()


class ActionWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ActionWidget, self).__init__(parent)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.groups = {}
        self.parent = parent

    def clear(self):
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.groups = {}

    def updateActions(self):
        self.clear()
        for action in self.parent.manager.actions.values():
            group_grp = self.groups.get(action.group)
            if not group_grp:
                group_grp = QtWidgets.QGroupBox(action.group)
                group_lay = QtWidgets.QVBoxLayout()
                group_grp.setLayout(group_lay)
                self.layout().addWidget(group_grp)
                self.groups[action.group] = group_grp

            button = QtWidgets.QPushButton(action.text)
            button.clicked.connect(action.func)
            group_grp.layout().addWidget(button)

        self.layout().addStretch(1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    gui_utils.show(ManagerWidget)
