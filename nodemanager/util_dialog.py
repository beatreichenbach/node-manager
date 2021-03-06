import logging
import os
from PySide2 import QtWidgets, QtCore, QtGui

from . import gui_utils


class FindAndReplaceDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FindAndReplaceDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()

    def init_ui(self):
        gui_utils.load_ui(self, 'find_and_replace_dialog.ui')

    def connect_ui(self):
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def values(self):
        values = {}
        values['find'] = self.find_line.text()
        values['replace'] = self.replace_line.text()
        values['ignorecase'] = not self.case_sensitive_chk.isChecked()
        values['regex'] = self.regex_chk.isChecked()
        return values

    @classmethod
    def get_values(cls, path=''):
        dialog = cls()
        dialog.path = path
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()


class RelocateDialog(QtWidgets.QDialog):
    # todo: preserve hierarchy: specify common folder/level

    def __init__(self, parent=None):
        super(RelocateDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()
        self.path = ''

    def init_ui(self):
        gui_utils.load_ui(self, 'relocate_dialog.ui')

    def connect_ui(self):
        self.path_btn.clicked.connect(self.browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def browse(self):
        directory = self.path_line.text() or self.path
        path = QtWidgets.QFileDialog.getExistingDirectory(dir=directory)
        path = os.path.abspath(path)
        if path:
            self.path_line.setText(path)

    def values(self):
        values = {}
        values['path'] = self.path_line.text()
        values['copy'] = self.copy_radio.isChecked()
        values['ignore_update'] = self.ignore_update_chk.isChecked()
        values['parent'] = self.parent_chk.isChecked()
        return values

    @classmethod
    def get_values(cls, path=''):
        dialog = cls()
        dialog.path = path
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()


class FindFilesDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FindFilesDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()
        self.path = ''

    def init_ui(self):
        gui_utils.load_ui(self, 'find_files_dialog.ui')

    def connect_ui(self):
        self.path_btn.clicked.connect(self.browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def browse(self):
        directory = self.path_line.text() or self.path
        path = QtWidgets.QFileDialog.getExistingDirectory(dir=directory)
        path = os.path.abspath(path)
        if path:
            self.path_line.setText(path)

    def values(self):
        values = {}
        values['path'] = self.path_line.text()
        return values

    @classmethod
    def get_values(cls, path=''):
        dialog = cls()
        dialog.path = path
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()


class SetDirectoryDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SetDirectoryDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()
        self.path = ''

    def init_ui(self):
        gui_utils.load_ui(self, 'set_directory_dialog.ui')

    def connect_ui(self):
        self.path_btn.clicked.connect(self.browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def browse(self):
        directory = self.path_line.text() or self.path
        path = QtWidgets.QFileDialog.getExistingDirectory(dir=directory)
        path = os.path.abspath(path)
        if path:
            self.path_line.setText(path)

    def values(self):
        values = {}
        values['path'] = self.path_line.text()
        return values

    @classmethod
    def get_values(cls, path=''):
        dialog = cls()
        dialog.path = path
        dialog.path_line.setText(path)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()
