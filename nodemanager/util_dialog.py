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
        values['ignorecase'] = self.case_chk.isChecked()
        values['regex'] = self.regex_chk.isChecked()
        return values

    @classmethod
    def get_values(cls):
        dialog = cls()
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
        values['update'] = self.update_chk.isChecked()
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


class ProcessDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ProcessDialog, self).__init__(parent)
        self.init_ui()
        self.connect_ui()
        self.nodes = []
        self.runnable = None
        self.nodes_completed = 0

        self.threadpool = QtCore.QThreadPool(self)
        self.threadpool.setMaxThreadCount(4)

    def init_ui(self):
        gui_utils.load_ui(self, 'process_dialog.ui')

    def connect_ui(self):
        self.button_box.rejected.connect(self.reject)

    def set_nodes(self, nodes):
        self.nodes = nodes
        for node in nodes:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)

            item = QtWidgets.QTableWidgetItem(node.name)
            item.setData(QtCore.Qt.UserRole, node)
            self.items_table.setItem(row, 0, item)

            item = QtWidgets.QTableWidgetItem('Waiting')
            self.items_table.setItem(row, 1, item)

            runnable = self.runnable(node)
            runnable.finished.connect(self.node_finished)
            self.threadpool.start(runnable)
        runnable.finished.connect(self.finished)

    def node_finished(self, node):
        items = self.items_table.findItems(node.name, QtCore.Qt.MatchExactly)
        if items:
            self.items_table.item(items[0].row(), 1).setText('Done')
        self.nodes_completed = self.nodes_completed + 1

        self.main_prgbar.setValue(self.nodes_completed / len(self.nodes) * 100)

    def finished(self):
        self.accept()

    @classmethod
    def process(cls, nodes, runnable):
        dialog = cls()
        dialog.runnable = runnable
        dialog.set_nodes(nodes)

        # thread.start()
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.nodes


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    values = SetDirectoryDialog.get_values()
    logging.debug(values)
    sys.exit(app.exec_())
