import os
import re
import glob
import logging
import shutil
from enum import Enum

from PySide2 import QtWidgets, QtCore, QtGui

try:
    from . import gui_utils
    from . import utils
    from . import manager
    from . import nodes_table
except ImportError:
    import gui_utils
    import utils
    import manager
    import nodes_table


class ManagerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, dcc='', context='', node=''):
        super(ManagerWidget, self).__init__(parent)

        self.setObjectName('ManagerWidget')
        self.settings = utils.Settings()
        self.dcc = dcc
        self.context = context
        self.node = node

        self.plugin = '_'.join((self.dcc, self.context, self.node))
        self.manager = manager.Manager.from_plugin(self.plugin)

        self.init_ui()

        self.manager.table_view = self.nodes_view
        self.action_widget.update_actions()

        self.connect_ui()
        self.load_settings()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_widget.ui')

        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(self.display_scroll)
        self.splitter.addWidget(self.list_scroll)
        self.layout().addWidget(self.splitter)

        # table view
        self.nodes_view = nodes_table.NodesView(self)
        self.sort_model = nodes_table.SortModel(self)
        self.sort_model.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.sort_model.setSourceModel(self.manager.model)
        self.nodes_view.setModel(self.sort_model)
        self.list_lay.addWidget(self.nodes_view)

        # action widget
        self.action_widget = ActionWidget(self.manager)
        self.list_lay.addWidget(self.action_widget)

        # display widget
        self.display_widget = DisplayWidget(self.nodes_view)
        self.display_lay.layout().insertWidget(0, self.display_widget)

        self.setStyleSheet('QTableView::item {border: 0px; padding: 0px 10px;}')

    def connect_ui(self):
        self.load_btn.clicked.connect(self.load)
        self.manager.model.updated.connect(self.nodes_view.update)
        self.manager.model.updated.connect(self.display_widget.update)
        self.display_widget.filter_changed.connect(self.sort_model.update_filters)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def save_settings(self):
        self.settings.setValue('manager_widget/splitter', self.splitter.sizes())

        header = self.nodes_view.horizontalHeader()
        if header.count():
            value = header.saveState()
            self.settings.setValue('plugins/{}_columns'.format(self.plugin), value)

        value = header.count()
        if value:
            self.settings.setValue('plugins/{}_columncount'.format(self.plugin), value)

    def load_settings(self):
        value = self.settings.list('manager_widget/splitter')
        # setting splitter size when identical seems to cause it to reset
        if value and self.splitter.sizes() != value:
            self.splitter.setSizes(value)
        # logging.debug(['manager_widget', 'load_settings', self.plugin, value, self.splitter.sizes()])

        value = self.settings.value('plugins/{}_columns'.format(self.plugin))
        if value:
            header = self.nodes_view.horizontalHeader()
            column_count = self.settings.value('plugins/{}_columncount'.format(self.plugin))
            if int(column_count) == header.count():
                header.restoreState(value)
                self.nodes_view.update_header_actions()

    def load(self):
        logging.debug('load')
        # save settings to keep columns the same
        self.save_settings()
        self.manager.load()
        self.load_settings()


class ActionWidget(QtWidgets.QWidget):
    def __init__(self, manager, parent=None):
        super(ActionWidget, self).__init__(parent)
        self.manager = manager
        self.setLayout(QtWidgets.QVBoxLayout())

    def clear(self):
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.group_boxes = {}

    def update_actions(self):
        self.clear()
        for group, actions in self.manager.actions.items():
            group_box = self.group_boxes.get(group)
            if not group_box:
                group_box = QtWidgets.QGroupBox(group)
                group_lay = QtWidgets.QVBoxLayout()
                group_box.setLayout(group_lay)
                self.layout().addWidget(group_box)
                self.group_boxes[group] = group_box

            for action in actions:
                button = QtWidgets.QPushButton(action.text())
                button.clicked.connect(action.trigger)
                group_box.layout().addWidget(button)

        self.layout().addStretch(1)


class DisplayWidget(QtWidgets.QWidget):
    filter_changed = QtCore.Signal(dict)

    def __init__(self, table_view, parent=None):
        super(DisplayWidget, self).__init__(parent)
        self.table_view = table_view
        self.init_ui()

    def init_ui(self):
        self.setLayout(QtWidgets.QVBoxLayout())

        self.filter_grp = QtWidgets.QGroupBox('Filter')
        self.filter_lay = QtWidgets.QFormLayout(self.filter_grp)
        self.filter_grp.setLayout(self.filter_lay)

        self.layout().addWidget(self.filter_grp)
        self.layout().addStretch(1)

    def clear(self):
        self.filter_widgets = {}
        while self.filter_lay.count():
            child = self.filter_lay.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update(self):
        self.update_filters()

    def update_filters(self):
        self.clear()

        model = self.table_view._model
        node = model.data(model.index(0, 0), QtCore.Qt.UserRole + 1)
        if not node:
            return

        for attribute in node.attributes:
            value = getattr(node, str(attribute))

            widget = None
            if isinstance(value, str) or isinstance(value, list):
                widget = QtWidgets.QLineEdit(self)
                signal = widget.textChanged

            elif isinstance(value, bool):
                widget = QtWidgets.QComboBox(self)
                items = {'Disabled': False, 'Enabled': True}
                for text, value in items.items():
                    widget.addItem(text, value)
                widget.insertItem(0, '')
                widget.setCurrentIndex(0)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                signal = widget.currentTextChanged

            elif isinstance(value, Enum):
                widget = QtWidgets.QComboBox(self)
                for member in value.__class__:
                    widget.addItem(member.name, member)
                widget.insertItem(0, '')
                widget.setCurrentIndex(0)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                signal = widget.currentTextChanged

            if widget:
                signal.connect(self.filter_input_changed)
                self.filter_widgets[attribute] = widget
                self.filter_lay.addRow(utils.title(attribute), widget)

    def filter_input_changed(self):
        filters = {}

        for attribute, widget in self.filter_widgets.items():
            value = None
            if isinstance(widget, QtWidgets.QLineEdit):
                value = widget.text()
            elif isinstance(widget, QtWidgets.QComboBox):
                value = widget.currentData()
            if value is not None and value != '':
                filters[attribute] = value

        self.filter_changed.emit(filters)
