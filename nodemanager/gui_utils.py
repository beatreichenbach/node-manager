import os
import sys
from PySide2 import QtUiTools, QtWidgets, QtCore
import logging


def load_ui(parent, file_name):
    """Loads the specified ui file and attaches them to the parent.

    Args:   parent: the object to load the ui elements into
            file_name: the file name of the ui file in the ui folder.
    """

    loader = QtUiTools.QUiLoader()
    ui_path = os.path.join(os.path.dirname(__file__), 'ui', file_name)
    widget = loader.load(ui_path)
    parent.setLayout(widget.layout())
    parent.__dict__.update(widget.__dict__)

    attrs = ['geometry', 'windowTitle', 'minimumSize']
    for attr in attrs:

        set_func = getattr(parent, 'set{}'.format(attr[0].upper() + attr[1:]))
        value = getattr(widget, attr).__call__()

        if attr == 'geometry':
            parent.resize(value.width(), value.height())
            continue
        set_func(value)

    return widget


def show(cls):
    """Helper function to show a window/dialog when no QApp is specified."""

    app = QtWidgets.QApplication(sys.argv)
    dialog = cls()
    dialog.show()
    sys.exit(app.exec_())
