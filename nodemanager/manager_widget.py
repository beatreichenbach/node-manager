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
    message = QtCore.Signal(str)

    # todo: when actions are taller than table, bottom scroll disappears
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

        # is this good?
        self.manager.table_view = self.nodes_view

        self.action_widget.update_actions()

        self.connect_ui()
        self.load_settings()

        # for testing purposes only
        # todo: add setting for autoload
        # self.load()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_widget.ui')

        # table view
        self.nodes_view = nodes_table.NodesView(self.plugin, parent=self)
        self.sort_model = nodes_table.SortModel(parent=self)
        self.sort_model.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.sort_model.setSourceModel(self.manager.model)
        self.nodes_view.setModel(self.sort_model)

        # action widget
        self.action_scroll = VerticalScrollArea()
        self.action_widget = ActionWidget(self.manager)
        self.action_scroll.setWidget(self.action_widget)
        self.action_scroll.setMinimumSize(self.action_scroll.sizeHint())
        self.action_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        # display widget
        display_scroll = QtWidgets.QScrollArea()
        self.display_widget = DisplayWidget(self.nodes_view)
        display_scroll.setWidget(self.display_widget)
        display_scroll.setWidgetResizable(True)

        # nodes widget
        nodes_frame = QtWidgets.QFrame()
        nodes_frame.setFrameShape(display_scroll.frameShape())
        nodes_frame.setFrameStyle(display_scroll.frameStyle())
        nodes_frame.setLayout(QtWidgets.QHBoxLayout())
        nodes_frame.layout().addWidget(self.nodes_view)
        nodes_frame.layout().addWidget(self.action_scroll)
        nodes_frame.layout().setStretch(0, 1)

        # splitter
        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(display_scroll)
        self.splitter.addWidget(nodes_frame)
        self.layout().replaceWidget(self.nodes_widget, self.splitter)

        self.setStyleSheet('QTableView::item {border: 0px; padding: 0px 10px;}')

    def connect_ui(self):
        self.load_btn.clicked.connect(self.load)
        self.manager.model.update_requested.connect(self.nodes_view.update_requested)
        self.manager.model.updated.connect(self.nodes_view.update)
        self.manager.model.updated.connect(self.display_widget.update)
        self.display_widget.filter_changed.connect(self.sort_model.update_filters)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def save_settings(self):
        logging.debug('save_settings_widget')
        self.settings.setValue('manager_widget/splitter', self.splitter.sizes())

        self.settings.beginGroup(self.plugin)

        headers = self.nodes_view.header_state
        if headers:
            attributes = []
            widths = []
            visibilities = []
            for attribute, values in sorted(headers.items(), key=lambda i: i[1]['visual_index']):
                attributes.append(attribute)
                widths.append(values['width'])
                visibilities.append(values['visibility'])
            self.settings.setValue('header_attributes', attributes)
            self.settings.setValue('header_widths', widths)
            self.settings.setValue('header_visibilities', visibilities)

        self.settings.endGroup()

    def load_settings(self):
        logging.debug('load_settings_widget')
        value = self.settings.list('manager_widget/splitter')
        # setting splitter size when identical seems to cause it to reset
        if value and self.splitter.sizes() != value:
            self.splitter.setSizes(value)

        self.settings.beginGroup(self.plugin)

        attributes = self.settings.list('header_attributes')
        widths = self.settings.list('header_widths')
        visibilities = self.settings.list('header_visibilities')

        headers = {}
        for i, attribute in enumerate(attributes):
            headers[attribute] = {
                'width': widths[i],
                'visibility': visibilities[i],
                'visual_index': i
            }

        self.nodes_view.header_state = headers
        self.settings.endGroup()

    def _load(self):
        # self.save_settings()
        self.manager.load()
        # self.load_settings()
        self.message.emit('')

    def load(self):
        logging.debug('load')
        self.message.emit('Loading nodes...')
        threadpool = QtCore.QThreadPool(self)
        # runnable = Runnable(self._load)
        # threadpool.start(runnable)
        self._load()


class Runnable(QtCore.QRunnable):
    def __init__(self, func):
        super(Runnable, self).__init__()
        self.func = func

    def run(self):
        self.func()


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
        self.resize(self.sizeHint())


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
        self.filter_grp.setVisible(False)

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
                self.filter_grp.setVisible(True)

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


class VerticalScrollArea(QtWidgets.QScrollArea):
    def eventFilter(self, watched, event):
        if watched == self.verticalScrollBar():
            if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.Hide) and self.widget():
                min_width = self.widget().sizeHint().width()
                if event.type() == QtCore.QEvent.Show:
                    min_width += self.verticalScrollBar().sizeHint().width()
                self.setMinimumWidth(min_width)
        return super(VerticalScrollArea, self).eventFilter(watched, event)
