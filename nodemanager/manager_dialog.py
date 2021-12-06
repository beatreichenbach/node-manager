import os
import logging

from PySide2 import QtWidgets, QtCore, QtGui

from . import gui_utils
from . import plugin_utils
from . import utils
from . import setup
from . import manager_widget


class ManagerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, dcc=''):
        super(ManagerDialog, self).__init__(parent)

        self.setWindowTitle('Node Manager')
        self.dcc = dcc
        self.settings = utils.Settings()

        self.manager_widget = None

        self.init_ui()
        self.connect_ui()
        self.load_settings()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_dialog.ui')

        self.resize(800, 600)

        # menu bar
        menu_bar = QtWidgets.QMenuBar(self)

        menu = QtWidgets.QMenu('File')
        action = menu.addAction('Open Script Directory')
        action.triggered.connect(self.open_scripts_dir)
        menu_bar.addMenu(menu)

        menu = QtWidgets.QMenu('Settings')
        action = menu.addAction('Edit Settings')
        action.triggered.connect(self.edit_settings)

        action = menu.addAction('Reset Settings')
        action.triggered.connect(self.reset_settings)
        menu_bar.addMenu(menu)

        menu = QtWidgets.QMenu('Help')
        action = menu.addAction('Documentation')
        action.triggered.connect(self.documentation)

        action = menu.addAction('Update')
        action.triggered.connect(self.update)
        menu_bar.addMenu(menu)
        self.layout().setMenuBar(menu_bar)

        # init tabs
        self.update_context()

    def connect_ui(self):
        self.context_cmb.currentTextChanged.connect(self.context_changed)
        self.manager_tab.currentChanged.connect(self.tab_changed)

    def reject(self):
        self.save_settings()
        super(ManagerDialog, self).reject()

    def closeEvent(self, event):
        logging.debug('closeEvent')
        self.save_settings()
        self.manager_widget.close()
        event.accept()

    def save_settings(self):
        logging.debug('save_settings')
        self.settings.setValue('manager_dialog/pos', self.pos())
        self.settings.setValue('manager_dialog/size', self.size())

        self.settings.setValue('manager_dialog/context', self.context_cmb.currentText())

        tab = self.manager_tab.tabText(self.manager_tab.currentIndex())
        self.settings.setValue('manager_dialog/tab', tab)

    def load_settings(self):
        logging.debug('load_settings')
        value = self.settings.value('manager_dialog/pos')
        if value:
            self.move(value)

        value = self.settings.value('manager_dialog/size')
        if value:
            self.resize(value)

        value = self.settings.value('manager_dialog/context')
        if value:
            self.context_cmb.setCurrentText(value)
        else:
            self.context_cmb.setCurrentIndex(0)

        value = self.settings.value('manager_dialog/tab')
        if value:
            for i in range(self.manager_tab.count()):
                if self.manager_tab.tabText(i) == value:
                    self.manager_tab.setCurrentIndex(i)
                    break

    def edit_settings(self):
        os.startfile(self.settings.fileName())

    def reset_settings(self):
        result = QtWidgets.QMessageBox.question(
            self,
            'Reset Settings',
            'Are you sure you want to reset the settings?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.Yes:
            self.settings.clear()

    def open_scripts_dir(self):
        os.startfile(os.path.dirname(__file__))

    def update(self):
        result = setup.Installer.update(self.dcc)
        if result:
            QtWidgets.QMessageBox.information(
                self,
                'Update',
                'Update successful.',
                QtWidgets.QMessageBox.Ok)
        else:
            QtWidgets.QMessageBox.information(
                self,
                'Update',
                'Update failed. Please see log.',
                QtWidgets.QMessageBox.Ok)
        self.close()

    def documentation(self):
        import webbrowser
        webbrowser.open('https://github.com/beatreichenbach/node-manager')

    def context_changed(self):
        logging.debug('context_changed')
        self.update_tabs()

    def update_context(self):
        for context in sorted(plugin_utils.contexts(self.dcc)):
            self.context_cmb.addItem(context.title(), context)
        self.context_cmb.setCurrentIndex(-1)

    def update_tabs(self):
        logging.debug('update_tabs')
        self.manager_tab.clear()

        self.manager_tab.blockSignals(True)

        context = self.context_cmb.currentData()
        if not context:
            return
        for node_cls in sorted(plugin_utils.node_plugins(self.dcc, context)):
            widget = manager_widget.ManagerWidget(self, self.dcc, context, node_cls)
            self.manager_tab.addTab(widget, node_cls.title())
        self.manager_widget = self.manager_tab.currentWidget()

        self.manager_tab.blockSignals(False)

    def tab_changed(self):
        logging.debug('tab_changed')
        if self.manager_widget:
            self.manager_widget.save_settings()
        self.manager_widget = self.manager_tab.currentWidget()
        self.manager_widget.load_settings()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    gui_utils.show(ManagerDialog)
