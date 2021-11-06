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
except ImportError:
    import gui_utils
    import utils
    import manager


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

        sort_model = SortModel(self)
        sort_model.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        sort_model.setSourceModel(self.manager.model)

        # self.nodes_view.setModel(self.manager.model)
        self.nodes_view.setModel(sort_model)

        self.display_widget.filter_changed.connect(sort_model.update_filters)

        self.action_widget.update_actions()
        self.connect_ui()

        self.load_settings()

    #     self.filter = QtWidgets.QLineEdit()
    #     self.layout().addWidget(self.filter)
    #     self.filter.textChanged.connect(self.filter_changed)

    # def filter_changed(self):
    #     text = self.filter.text()
    #     for i in range(self.manager.model.rowCount()):
    #         item = self.manager.model.item(i, 0)
    #         match = text.lower() in item.data().name.lower()
    #         self.nodes_view.setRowHidden(i, not match)

    def init_ui(self):
        gui_utils.load_ui(self, 'manager_widget.ui')

        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(self.display_scroll)
        self.splitter.addWidget(self.list_scroll)
        self.layout().addWidget(self.splitter)

        self.display_widget = DisplayWidget(self)
        self.display_lay.layout().addWidget(self.display_widget)

        self.nodes_view = NodesView(self)
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
                filters[attribute] = getattr(node, attribute)

            self.display_widget.update_filters(filters)

        # fix this!!!
        self.nodes_view.update_header_actions()


        # this probably shouldn't be in here
        self.nodes_view.set_delegates()


class NodesView(QtWidgets.QTableView):
    def __init__(self, parent):
        super(NodesView, self).__init__(parent)

        self.parent = parent
        self.manager = parent.manager
        self.menu = None

        self.init_ui()

    def init_ui(self):
        self.setSelectionBehavior(self.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSortingEnabled(True)

        # self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsMovable(True)
        self.verticalHeader().hide()

        header = self.horizontalHeader()
        header.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)

    def update_header_actions(self):
        header = self.horizontalHeader()
        for i in range(self.manager.model.columnCount()):
            item = self.manager.model.horizontalHeaderItem(i)

            action = QtWidgets.QAction(item.text(), self)
            action.setCheckable(True)
            action.setChecked(not self.isColumnHidden(i))
            action.triggered.connect(self.update_header)
            header.addAction(action)



    def update_header(self):
        header = self.horizontalHeader()
        states = []
        for i, action in enumerate(header.actions()):
            state = action.isChecked()
            states.append(state)
            self.setColumnHidden(i, not state)
        if not any(states):
            # prevent all columns to be hidden
            header.actions()[0].setChecked(True)
            self.setColumnHidden(0, False)

    def set_delegates(self):
        item = self.manager.model.item(0, 0)
        if not item:
            return

        node = item.data()
        for i, attribute in enumerate(self.manager.attributes):
            value = getattr(node, attribute)

            delegate = Delegate(self)
            if isinstance(value, str):
                pass
            elif isinstance(value, utils.Enum):
                delegate = EnumDelegate(self, enum=value)
            elif isinstance(value, utils.FileSize):
                delegate = FileSizeDelegate(self)
            elif isinstance(value, QtGui.QColor):
                delegate = ColorDelegate(self)
            elif isinstance(value, bool):
                delegate = BoolDelegate(self)
            elif isinstance(value, int):
                pass
                # delegate = SpinBoxDelegate(self)
            elif isinstance(value, float):
                pass
                # delegate = DoubleSpinBoxDelegate(self)
            elif isinstance(value, list) and len(value) == 2:
                pass
            elif isinstance(value, list) and len(value) == 3:
                pass

            if delegate:
                self.setItemDelegateForColumn(i, delegate)


            # if isinstance(value, bool):
            #     for row in range(self.model().rowCount()):
            #         index = self.model().index(row, i)
            #         logging.debug(index)
            #         self.openPersistentEditor(index)


            # if isinstance(value, utils.FileSize):
            #     values = []
            #     for row in range(self.manager.model.rowCount()):
            #         item = self.manager.model.item(row, i)
            #         values.append(item.data(QtCore.Qt.EditRole))
            #     logging.debug(values[0] > values[2])
            #     logging.debug(values[2] > values[3])
            #     logging.debug(values[2] < values[3])
            #     logging.debug(values[2] > values[4])
            #     logging.debug(values)
            #     logging.debug(sorted(values))
            #     logging.debug([value.size for value in values])

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())

        # map index from proxy sort to model
        model_index = self.model().mapToSource(index)

        if not self.manager.model.itemFromIndex(model_index).isEditable():
            return

        menu = QtWidgets.QMenu(self)
        action = menu.addAction('Edit Selected')
        action.triggered.connect(lambda: self.edit(index))

        # add other required actions
        menu.popup(event.globalPos())



class ActionWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ActionWidget, self).__init__(parent)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.groups = {}
        self.parent = parent

    def clear(self):
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.groups = {}

    def update_actions(self):
        self.clear()
        logging.debug(self.parent.manager.display_name)
        for action in self.parent.manager.actions.values():
            group_grp = self.groups.get(action.group)
            if not group_grp:
                group_grp = QtWidgets.QGroupBox(action.group)
                group_lay = QtWidgets.QVBoxLayout()
                group_grp.setLayout(group_lay)
                self.layout().addWidget(group_grp)
                self.groups[action.group] = group_grp

            button = QtWidgets.QPushButton(action.text)

            button.clicked.connect(action.func)
            group_grp.layout().addWidget(button)

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

        # as with the delegates this should probably not depend on the value but some sort of attribute object that can hold enum.
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
                self.filter_widgets[attribute]  = widget
                # make title into func
                self.filter_lay.addRow(attribute.replace('_', ' ').title(), widget)

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



class SortModel(QtCore.QSortFilterProxyModel):
    filters = {}

    def value(self, value):
        if isinstance(value, str):
            if self.sortCaseSensitivity() == QtCore.Qt.CaseInsensitive:
                return value.lower()
        elif isinstance(value, QtGui.QColor):
            return str(value)
        return value

    def lessThan(self, left, right):
        left_value = self.value(self.sourceModel().data(left))
        right_value = self.value(self.sourceModel().data(right))
        return left_value < right_value

    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        index = self.sourceModel().index(source_row, 0)
        node = self.sourceModel().data(index, QtCore.Qt.UserRole)

        item = self.sourceModel().item(source_row, 0)
        node = item.data()

        logging.debug(node)

        for attribute, value in self.filters.items():
            if isinstance(value, str):
                if value.lower() not in getattr(node, attribute).lower():
                    break

            elif isinstance(value, int):
                if value != int(getattr(node, attribute)):
                    break
        else:
            return True

        return False

    def update_filters(self, filters):
        self.filters = filters
        self.setFilterRegExp('')
        logging.debug('update_filters')



class Delegate(QtWidgets.QStyledItemDelegate):
    def set_user_property(self, editor, name):
        def userProperty():
            return name

        metaobject = editor.metaObject()
        index = metaobject.indexOfProperty(name)
        metaobject.property(index)
        editor.metaObject().userProperty = lambda: metaobject.property(index)

        logging.debug(editor.metaObject().userProperty().name())

    def setModelData(self, editor, model, index):
        # Set ModelData on selection by default
        logging.debug(editor.metaObject().userProperty().name())

        # self.parent() unclean?
        indexes = self.parent().selectionModel().selectedRows(index.column())
        indexes.append(index)
        for item_index in indexes:
            super(Delegate, self).setModelData(editor, model, item_index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class FileSizeDelegate(Delegate):
    def displayText(self, value, locale):
        return str(value)

class BoolDelegate(Delegate):
    def displayText(self, value, locale):
        return 'Enabled' if value else 'Disabled'

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        editor.setFocusPolicy(QtCore.Qt.StrongFocus)
        editor.addItems(('Disabled', 'Enabled'))
        editor.currentIndexChanged.connect(lambda: self.commitData.emit(editor))
        editor.currentIndexChanged.connect(lambda: self.closeEditor.emit(editor, self.NoHint))
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        editor.setCurrentIndex(value.current)

    def setModelData(self, editor, model, index):
        value.current = bool(editor.currentIndex())

        # self.parent() unclean?
        for item_index in self.parent().selectionModel().selectedRows(index.column()):
            model.setData(item_index, value, QtCore.Qt.EditRole)


class SpinBoxDelegate(Delegate):
    def createEditor(self, parent, option, index):
        editor = QtWidgets.QSpinBox(parent)
        editor.setMinimum(-10000)
        editor.setMaximum(10000)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        editor.setValue(value)

    def setModelData(self, editor, model, index):
        editor.interpretText()
        value = editor.value()
        model.setData(index, value, QtCore.Qt.EditRole)

class DoubleSpinBoxDelegate(Delegate):
    def createEditor(self, parent, option, index):
        editor = QtWidgets.QDoubleSpinBox(parent)
        editor.setMinimum(-10000)
        editor.setMaximum(10000)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        editor.setValue(value)

    def setModelData(self, editor, model, index):
        editor.interpretText()
        value = editor.value()
        model.setData(index, value, QtCore.Qt.EditRole)


class EnumDelegate(Delegate):
    def __init__(self, *args, enum):
        super(EnumDelegate, self).__init__(*args)
        self.enum = enum

    def displayText(self, value, locale):
        return value.enums.get(value.current)

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        editor.setFocusPolicy(QtCore.Qt.StrongFocus)

        for i, enum in self.enum.enums.items():
            editor.addItem(enum, i)
        editor.setCurrentText(self.enum.enums.get(self.enum.current))
        editor.currentIndexChanged.connect(lambda: self.commitData.emit(editor))
        editor.currentIndexChanged.connect(lambda: self.closeEditor.emit(editor, self.NoHint))
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        editor.setCurrentIndex(value.current)
        # editor.showPopup()

    def setModelData(self, editor, model, index):
        value = utils.Enum(self.enum.enums)
        # should this be currentData since some enums might not be linear?
        value.current = editor.currentIndex()
        # model.setData(index, value, QtCore.Qt.EditRole)

        # self.parent() unclean?
        for item_index in self.parent().selectionModel().selectedRows(index.column()):
            model.setData(item_index, value, QtCore.Qt.EditRole)



class ColorDelegate(Delegate):
    def displayText(self, value, locale):
        return ''

    def createEditor(self, parent, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)

        editor = QtWidgets.QWidget(parent)
        editor.setWindowTitle('asdfasdfasdf')

        color = QtWidgets.QColorDialog.getColor(value, parent)
        editor.color = color

        # signals don't work so call to setModelData directly
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, self.NoHint)
        self.setModelData(editor, index.model(), index)

        return editor

    def setModelData(self, editor, model, index):
        value = editor.color
        if not value.isValid():
            return

        for item_index in self.parent().selectionModel().selectedRows(index.column()):
            model.setData(item_index, value, QtCore.Qt.EditRole)
        editor.deleteLater()

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        option.rect.adjust(5, 5, -5, -5)
        painter.setBrush(value)
        painter.drawRect(option.rect)

class ColorDelegate(Delegate):
    def displayText(self, value, locale):
        return ''

    def createEditor(self, parent, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)

        editor = QtWidgets.QWidget(parent)
        editor.dialog = QtWidgets.QColorDialog(value, editor)
        editor.dialog.colorSelected.connect(lambda color: setattr(editor, 'color', color))
        editor.dialog.colorSelected.connect(lambda: self.commitData.emit(editor))
        editor.dialog.colorSelected.connect(lambda: self.closeEditor.emit(editor, self.NoHint))

        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        editor.dialog.setCurrentColor(value)
        editor.dialog.open()

    def setModelData(self, editor, model, index):
        value = editor.color
        if not value.isValid():
            return

        for item_index in self.parent().selectionModel().selectedRows(index.column()):
            model.setData(item_index, value, QtCore.Qt.EditRole)

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        option.rect.adjust(5, 5, -5, -5)
        painter.setBrush(value)
        painter.drawRect(option.rect)

