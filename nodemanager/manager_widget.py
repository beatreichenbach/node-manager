import logging
import sys
from functools import partial
import traceback
try:
    from enum import Enum
except ImportError:
    from ..enum import Enum

from PySide2 import QtWidgets, QtCore, QtGui

from . import gui_utils
from . import utils
from . import manager
from . import attribute_table


# py 2.7
if sys.version_info[0] >= 3:
    unicode = str


class ManagerWidget(QtWidgets.QWidget):
    message = QtCore.Signal(str)

    def __init__(self, parent=None, dcc='', context='', node_cls=''):
        super(ManagerWidget, self).__init__(parent)

        self.settings = utils.Settings()
        self.dcc = dcc
        self.context = context
        self.node_cls = node_cls

        self.plugin = '_'.join((self.dcc, self.context, self.node_cls))
        self.manager = manager.Manager.from_plugin(self.plugin)

        self.init_ui()

        self.action_widget.update_actions()
        # self.action_scroll.setMinimumWidth(self.action_scroll.widget().sizeHint().width())

        self.connect_ui()
        self.load_settings()

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_widget.ui')

        # table view
        self.model = attribute_table.AttributeItemModel(parent=self)
        self.sort_model = attribute_table.AttributeSortModel(parent=self)
        self.sort_model.setSourceModel(self.model)
        self.sort_model.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.attribute_view = attribute_table.AttributeTableView(parent=self)
        self.attribute_view.setModel(self.sort_model)
        self.setStyleSheet('QTableView::item {border: 0px; padding: 0px 10px;}')

        # action widget
        self.action_scroll = VerticalScrollArea()
        self.action_widget = ActionWidget(self, self.manager, self.attribute_view)
        self.action_widget.updated.connect(self.action_scroll.update)
        self.action_scroll.setWidget(self.action_widget)
        self.action_scroll.setMinimumSize(self.action_scroll.sizeHint())
        self.action_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        # display widget
        display_scroll = QtWidgets.QScrollArea()
        self.display_widget = DisplayWidget(self.attribute_view)
        display_scroll.setWidget(self.display_widget)
        display_scroll.setWidgetResizable(True)

        # nodes widget
        nodes_frame = QtWidgets.QFrame()
        nodes_frame.setFrameShape(display_scroll.frameShape())
        nodes_frame.setFrameStyle(display_scroll.frameStyle())
        nodes_frame.setLayout(QtWidgets.QHBoxLayout())
        nodes_frame.layout().addWidget(self.attribute_view)
        nodes_frame.layout().addWidget(self.action_scroll)
        nodes_frame.layout().setStretch(0, 1)

        # splitter
        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(display_scroll)
        self.splitter.addWidget(nodes_frame)
        self.layout().replaceWidget(self.nodes_widget, self.splitter)
        self.nodes_widget.setParent(None)

        # progress and status bar
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

        # todo:
        self.visible_chk.setEnabled(False)

    def connect_ui(self):
        self.load_btn.clicked.connect(self.load)
        self.model.update_requested.connect(self.attribute_view.update_requested)
        self.model.updated.connect(self.attribute_view.update)
        self.model.updated.connect(self.display_widget.update)
        self.display_widget.filter_changed.connect(self.sort_model.update_filters)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def save_settings(self):
        self.settings.setValue('manager_widget/splitter', self.splitter.sizes())

        self.settings.beginGroup(self.plugin)

        self.settings.setValue('selection', self.selection_chk.isChecked())

        headers = self.attribute_view.header_state
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
        value = self.settings.list('manager_widget/splitter')
        # setting splitter size when identical seems to cause it to reset
        if value and self.splitter.sizes() != value:
            self.splitter.setSizes(value)

        self.settings.beginGroup(self.plugin)

        self.selection_chk.setChecked(self.settings.bool('selection'))
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

        self.attribute_view.header_state = headers
        self.settings.endGroup()

    def load(self):
        self.status_bar.showMessage('Loading nodes...')

        options = {
            'selection': self.selection_chk.isChecked(),
            'visible': self.visible_chk.isChecked(),
        }
        attribute_items = []
        try:
            attribute_items = self.manager.nodes(options=options)
            self.model.set_items(attribute_items)
        except RuntimeError as exception:
            message_box = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Warning,
                'RuntimeError',
                'RuntimeError: {}'.format(exception),
                QtWidgets.QMessageBox.Ok,
                self)
            message_box.setDetailedText(traceback.print_exc())
            message_box.exec_()

        self.status_bar.clearMessage()

        num_items = len(attribute_items)
        self.status_bar.showMessage(
            'Loaded {} item{}'.format(num_items, 's' if num_items != 1 else '')
            )


class ActionWidget(QtWidgets.QWidget):
    updated = QtCore.Signal()

    def __init__(self, manager_widget, manager, attribute_view, parent=None):
        super(ActionWidget, self).__init__(parent)
        self.manager_widget = manager_widget
        self.manager = manager
        self.attribute_view = attribute_view
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
                action.triggered.connect(self.action_triggered)
                button = QtWidgets.QPushButton(action.label)
                button.clicked.connect(partial(self.trigger_action, action))
                group_box.layout().addWidget(button)

        self.layout().addStretch(1)
        self.resize(self.sizeHint())
        self.updated.emit()

    def trigger_action(self, action):
        action.trigger(self.attribute_view.selected_attribute_items)

    def action_triggered(self, attribute_items, update):
        if update == manager.Action.UPDATE_MODEL:
            self.attribute_view._model.update_items(attribute_items)
        elif update == manager.Action.RELOAD_MODEL:
            self.manager_widget.load()


class IntEdit(QtWidgets.QLineEdit):
    pass


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
            try:
                value = getattr(node, str(attribute))
            except AttributeError:
                continue

            widget = None

            # py 2.7
            if isinstance(value, str) or isinstance(value, unicode) or isinstance(value, list):
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

            elif isinstance(value, int):
                widget = IntEdit(self)
                widget.setValidator(QtGui.QIntValidator())
                widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                signal = widget.textChanged

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

            if isinstance(widget, IntEdit):
                value = widget.text()
                value = int(value) if value else None
            elif isinstance(widget, QtWidgets.QLineEdit):
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

    def update(self):
        min_width = self.widget().sizeHint().width()
        self.setMinimumWidth(min_width)
