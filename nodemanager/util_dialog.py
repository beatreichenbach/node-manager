import logging
import sys
import os
from PySide2 import QtWidgets, QtCore, QtGui

try:
    from . import gui_utils
except ImportError:
    import gui_utils


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
        values['case_sensitive'] = self.case_chk.isChecked()
        values['regex'] = self.regex_chk.isChecked()
        return values

    @classmethod
    def get_values(cls):
        dialog = cls()
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()


class RelocateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(RelocateDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()

    def init_ui(self):
        gui_utils.load_ui(self, 'relocate_dialog.ui')

    def connect_ui(self):
        self.path_btn.clicked.connect(self.browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def browse(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(dir=self.path_line.text())
        path = os.path.abspath(path)
        if path:
            self.path_line.setText(path)

    def values(self):
        values = {}
        values['path'] = self.path_line.text()
        values['copy'] = self.copy_radio.isChecked()
        values['update'] = self.update_chk.isChecked()
        values['parent'] = self.parent_chk.isChecked()
        return values

    @classmethod
    def get_values(cls):
        dialog = cls()
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()


class FindFilesDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FindFilesDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()

    def init_ui(self):
        gui_utils.load_ui(self, 'find_files_dialog.ui')

    def connect_ui(self):
        self.path_btn.clicked.connect(self.browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def browse(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(dir=self.path_line.text())
        path = os.path.abspath(path)
        if path:
            self.path_line.setText(path)

    def values(self):
        values = {}
        values['path'] = self.path_line.text()
        return values

    @classmethod
    def get_values(cls):
        dialog = cls()
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()


class SetDirectory(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SetDirectory, self).__init__(parent)
        self.init_ui()
        self.connect_ui()

    def init_ui(self):
        gui_utils.load_ui(self, 'set_directory_dialog.ui')

    def connect_ui(self):
        self.path_btn.clicked.connect(self.browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def browse(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(dir=self.path_line.text())
        path = os.path.abspath(path)
        if path:
            self.path_line.setText(path)

    def values(self):
        values = {}
        values['path'] = self.path_line.text()
        return values

    @classmethod
    def get_values(cls):
        dialog = cls()
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.values()


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    values = SetDirectory.get_values()
    logging.debug(values)
    sys.exit(app.exec_())
