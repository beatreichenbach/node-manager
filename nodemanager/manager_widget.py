import os
import re
import glob
import logging
import shutil

from PySide2 import QtWidgets, QtCore, QtGui

try:
    from . import gui_utils
    from . import utils
except ImportError:
    import gui_utils
    import utils


class ManagerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, dcc=''):
        super(ManagerWidget, self).__init__(parent)

        self.setObjectName('ManagerWidget')
        self.dcc = dcc
        self.init_ui()
        self.settings = utils.Settings()

        # self.connect_ui()
        self.load_settings()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_widget.ui')

        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(self.filter_scroll)
        self.splitter.addWidget(self.list_scroll)
        self.layout().insertWidget(2, self.splitter)

        self.list_lay.removeWidget(self.nodes_view)
        self.nodes_view = NodesView()
        self.node_model = NodesModel()
        self.nodes_view.setModel(self.node_model)
        self.list_lay.insertWidget(0, self.nodes_view)

        self.node_model.populate()

    def save_settings(self):
        logging.debug('save_settings')
        self.settings.setValue('manager_widget/pos', self.pos())
        self.settings.setValue('manager_widget/size', self.size())

    def load_settings(self):
        logging.debug('load_settings')
        if self.settings.value('manager_widget/pos'):
            self.move(self.settings.value('manager_widget/pos'))
        if self.settings.value('manager_widget/size'):
            self.resize(self.settings.value('manager_widget/size'))

    def reject(self):
        self.save_settings()
        super(ManagerDialog, self).reject()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def updateActions(self):
        self.

class NodesView(QtWidgets.QTableView):
    def __init__(self, parent=None):
        super(NodesView, self).__init__(parent)

        self.setSelectionBehavior(self.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)

        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().hide()


class ActionWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ActionWidget, self).__init__(parent)

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    gui_utils.show(ManagerWidget)
