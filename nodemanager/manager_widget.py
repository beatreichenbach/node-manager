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
        # fix ugh
        self.manager.parent = self

        self.init_ui()

        sort_model = nodes_table.SortModel(self)
        sort_model.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        sort_model.setSourceModel(self.manager.model)

        # self.nodes_view.setModel(self.manager.model)
        self.nodes_view.setModel(sort_model)

        self.display_widget.filter_changed.connect(sort_model.update_filters)

        self.action_widget.update_actions()
        self.connect_ui()

        self.load_settings()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_widget.ui')

        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(self.display_scroll)
        self.splitter.addWidget(self.list_scroll)
        self.layout().addWidget(self.splitter)

        self.display_widget = DisplayWidget(self)
        self.display_lay.layout().addWidget(self.display_widget)

        self.nodes_view = nodes_table.NodesView(self)
        self.list_lay.addWidget(self.nodes_view)
        self.action_widget = ActionWidget(self)
        self.list_lay.addWidget(self.action_widget)

        self.setStyleSheet('QTableView::item {border: 0px; padding: 0px 10px;}')

    def connect_ui(self):
        self.load_btn.clicked.connect(self.load)

    def closeEvent(self, event):
        logging.debug('manager_widget closeEvent')
        self.save_settings()
        event.accept()

    def save_settings(self):
        self.settings.setValue('manager_widget/splitter', self.splitter.sizes())

        value = self.nodes_view.horizontalHeader().saveState()
        self.settings.setValue('plugins/{}_colums'.format(self.plugin), value)

    def load_settings(self):
        value = self.settings.list('manager_widget/splitter')
        if value:
            self.splitter.setSizes(value)

        value = self.settings.value('plugins/{}_colums'.format(self.plugin))
        if value:
            self.nodes_view.horizontalHeader().restoreState(value)

    def load(self):
        logging.debug('load')
        self.save_settings()
        self.manager.load()

        self.load_settings()

        # pure vomit
        item = self.manager.model.item(0, 0)
        if item:
            node = item.data()
            filters = {}
            for i, attribute in enumerate(self.manager.attributes):
                filters[attribute] = getattr(node, str(attribute))

            self.display_widget.update_filters(filters)

        # fix this!!!
        self.nodes_view.update_header_actions()


class ActionWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ActionWidget, self).__init__(parent)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.group_boxes = {}
        self.parent = parent

    def clear(self):
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.group_boxes = {}

    def update_actions(self):
        self.clear()
        logging.debug(self.parent.manager.display_name)

        logging.debug(self.parent.manager.actions)
        for group, actions in self.parent.manager.actions.items():
            logging.debug([group, actions])
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

                # button.clicked.connect(action.func)
                group_box.layout().addWidget(button)

        self.layout().addStretch(1)


class DisplayWidget(QtWidgets.QWidget):
    filter_changed = QtCore.Signal(dict)

    def __init__(self, parent):
        super(DisplayWidget, self).__init__(parent)

        self.parent = parent
        self.manager = parent.manager
        self.filter_widgets = {}

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

    def update_filters(self, filters):
        self.clear()

        # as with the delegates this should probably not depend on the value but some sort of
        # attribute object that can hold enum.
        for attribute, value in filters.items():
            widget = None
            if isinstance(value, str):
                widget = QtWidgets.QLineEdit(self)
                widget.textChanged.connect(self.filter_input_changed)
            elif isinstance(value, bool):
                widget = QtWidgets.QComboBox(self)
                widget.addItems(('', 'Disabled', 'Enabled'))
                widget.currentTextChanged.connect(self.filter_input_changed)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            elif isinstance(value, utils.Enum):
                widget = QtWidgets.QComboBox(self)
                widget.addItem('')
                for i, enum in value.enums.items():
                    widget.addItem(enum, i)
                widget.currentTextChanged.connect(self.filter_input_changed)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

            if widget:
                self.filter_widgets[attribute] = widget
                # make title into func
                self.filter_lay.addRow(attribute.display_name, widget)

    def filter_input_changed(self):
        # i hate that name
        filters = {}

        for attribute, widget in self.filter_widgets.items():
            value = None
            if isinstance(widget, QtWidgets.QLineEdit):
                value = widget.text()
            if isinstance(widget, QtWidgets.QComboBox):
                # should be data?
                value = widget.currentData()
            if value is not None:
                filters[attribute] = value

        self.filter_changed.emit(filters)
        logging.debug(filters)
