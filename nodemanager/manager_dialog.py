import os
import re
import glob
import logging
import shutil

from PySide2 import QtWidgets, QtCore, QtGui

try:
    from . import gui_utils
    from . import plugin_utils
    from . import utils
    from .utils import NotFoundException, NoSelectionException
    from . import setup
    from . import manager_widget
except ImportError:
    import gui_utils
    import plugin_utils
    import utils
    from utils import NotFoundException, NoSelectionException
    import setup
    import manager_widget


class ManagerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, dcc=''):
        super(ManagerDialog, self).__init__(parent)

        self.setObjectName('ManagerDialog')
        self.dcc = dcc
        self.settings = utils.Settings()

        self.context = None
        self.manager_widget = None

        self.init_ui()

        self.connect_ui()
        self.context_changed()
        self.load_settings()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_dialog.ui')

        self.resize(800, 600)

        self.update_context()

        # Menu Bar
        menu_bar = QtWidgets.QMenuBar(self)
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

        self.main_prgbar.setVisible(False)
        size_policy = self.main_prgbar.sizePolicy()
        # size_policy.setRetainSizeWhenHidden(True)
        self.main_prgbar.setSizePolicy(size_policy)

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
        self.context_cmb.currentTextChanged.connect(self.context_changed)

    def reject(self):
        self.save_settings()
        super(ManagerDialog, self).reject()

    def closeEvent(self, event):
        logging.debug('closeEvent')
        self.save_settings()
        event.accept()

    def save_settings(self):
        logging.debug('save_settings')
        self.settings.setValue('manager_dialog/pos', self.pos())
        self.settings.setValue('manager_dialog/size', self.size())

        manager_widget = self.manager_tab.currentWidget()
        self.settings.setValue('manager_widget/splitter', manager_widget.splitter.sizes())

    def load_settings(self):
        logging.debug('load_settings')
        if self.settings.value('manager_dialog/pos'):
            self.move(self.settings.value('manager_dialog/pos'))
        if self.settings.value('manager_dialog/size'):
            self.resize(self.settings.value('manager_dialog/size'))

        if self.settings.list('manager_widget/splitter'):
            manager_widget = self.manager_tab.currentWidget()
            manager_widget.splitter.setSizes(self.settings.list('manager_widget/splitter'))

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

    def open_configs_dir(self):
        os.startfile(self.settings.configs_path)

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
        self.context = self.context_cmb.currentData()
        self.update_tabs()

    def update_context(self):
        for context in sorted(plugin_utils.contexts(self.dcc)):
            self.context_cmb.addItem(context.title(), context)

    def update_tabs(self):
        self.manager_tab.clear()
        logging.debug('update_tabs')
        for node in sorted(plugin_utils.node_plugins(self.dcc, self.context)):
            widget = manager_widget.ManagerWidget(self, self.dcc, self.context, node)
            self.manager_tab.addTab(widget, node.title())

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    gui_utils.show(ManagerDialog)
