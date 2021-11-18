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
except ImportError:
    import gui_utils
    import utils
    import manager


class NodesView(QtWidgets.QTableView):
    def __init__(self, parent):
        super(NodesView, self).__init__(parent)

        self.parent = parent
        self.manager = parent.manager
        self.menu = None

        self.init_ui()

    @property
    def _model(self):
        model = super(NodesView, self).model()
        if model and isinstance(model, QtCore.QSortFilterProxyModel):
            model = model.sourceModel()
        return model

    def init_ui(self):
        self.setSelectionBehavior(self.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSortingEnabled(True)

        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsMovable(True)
        self.verticalHeader().hide()

        header = self.horizontalHeader()
        header.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)

    def update(self):
        self.update_header_actions()
        self.update_delegates()

    def update_header_actions(self):
        header = self.horizontalHeader()
        for action in header.actions():
            header.removeAction(action)

        for i in range(self._model.columnCount()):
            item = self._model.horizontalHeaderItem(i)

            action = QtWidgets.QAction(item.text(), self)
            action.setCheckable(True)
            action.setChecked(not self.isColumnHidden(i))
            action.triggered.connect(self.update_header)
            header.addAction(action)

    def update_delegates(self):
        node = self._model.data(self._model.index(0, 0), QtCore.Qt.UserRole + 1)
        if node:
            for i in range(self._model.columnCount()):
                attribute = self._model.headerData(i, QtCore.Qt.Horizontal, QtCore.Qt.UserRole + 1)
                value = getattr(node, attribute)
                delegate = Delegate.fromValue(value, parent=self)
                self.setItemDelegateForColumn(i, delegate)

    def update_header(self):
        header = self.horizontalHeader()
        states = []
        for i, action in enumerate(header.actions()):
            state = action.isChecked()
            states.append(state)
            self.setColumnHidden(i, not state)

        # prevent all columns to be hidden
        if not any(states):
            header.actions()[0].setChecked(True)
            self.setColumnHidden(0, False)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())

        if not self.model():
            return

        model_index = self.model().mapToSource(index)

        if not self._model.itemFromIndex(model_index).isEditable():
            return

        menu = QtWidgets.QMenu(self)
        action = menu.addAction('Edit Selected')
        action.triggered.connect(lambda: self.edit(index))

        # todo: add other required actions
        menu.popup(event.globalPos())


class NodesModel(QtGui.QStandardItemModel):
    # todo: add function to invalidate loaded items, in case of generate tx/find files etc.
    updated = QtCore.Signal()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        # override to enable deferred loading of items
        data = super(NodesModel, self).data(index, role)
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole) and callable(data):
            data = data()
            super(NodesModel, self).setData(index, data, role)
        return data

    def setData(self, index, value, role):
        super(NodesModel, self).setData(index, value, role)

        if role == QtCore.Qt.EditRole:
            node = self.itemFromIndex(index).data()
            item = self.horizontalHeaderItem(index.column())
            attribute = item.data()
            setattr(node, attribute, value)

        return True

    def set_nodes(self, nodes):
        self.clear()

        for node in nodes:
            items = []
            for attribute in node.attributes:
                item = QtGui.QStandardItem()
                value = self.deferred_loading(node, attribute)

                if attribute in node.locked_attributes:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

                item.setData(value, QtCore.Qt.DisplayRole)
                item.setData(node)

                items.append(item)

            self.appendRow(items)

        self.set_headers(nodes)
        self.updated.emit()

    def set_headers(self, nodes):
        if nodes:
            node = nodes[0]
            self.attributes = node.attributes
            for i, attribute in enumerate(self.attributes):
                item = QtGui.QStandardItem()
                item.setText(utils.title(attribute))
                item.setData(attribute)
                self.setHorizontalHeaderItem(i, item)

    @staticmethod
    def deferred_loading(node, attribute):
        def wrapper():
            return getattr(node, attribute)
        return wrapper


class SortModel(QtCore.QSortFilterProxyModel):
    filters = {}

    def value(self, value):
        if isinstance(value, str):
            if self.sortCaseSensitivity() == QtCore.Qt.CaseInsensitive:
                return value.lower()
        elif isinstance(value, QtGui.QColor):
            return str(value)
        elif isinstance(value, Enum):
            return value.value
        return value

    def lessThan(self, left, right):
        # load requested item / override data
        left_value = self.value(self.sourceModel().data(left))
        right_value = self.value(self.sourceModel().data(right))
        return left_value < right_value

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()

        for attribute, filter_value in self.filters.items():
            try:
                column = model.attributes.index(attribute)
            except IndexError:
                continue
            index = model.index(source_row, column, source_parent)

            item_value = self.value(model.data(index))
            filter_value = self.value(filter_value)

            if isinstance(item_value, list):
                item_value = ''.join(item_value)

            if isinstance(filter_value, str):
                # todo: add support for expressions?
                if filter_value not in item_value:
                    break
            elif filter_value != item_value:
                break
        else:
            return True

        return False

    def update_filters(self, filters):
        self.filters = filters
        self.setFilterRegExp('')


class Delegate(QtWidgets.QStyledItemDelegate):
    def setModelData(self, editor, model, index, value=None):
        # Set ModelData on all selected rows

        indexes = [index]
        if self.parent() and self.parent().selectionModel():
            indexes.extend(self.parent().selectionModel().selectedRows(index.column()))

        for item_index in indexes:
            if value is not None:
                model.setData(item_index, value, QtCore.Qt.EditRole)
            else:
                super(Delegate, self).setModelData(editor, model, item_index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    @classmethod
    def fromValue(cls, value, parent=None):
        if isinstance(value, Enum):
            delegate = EnumDelegate(enum=value.__class__, parent=parent)
        elif isinstance(value, utils.FileSize):
            delegate = FileSizeDelegate(parent)
        elif isinstance(value, QtGui.QColor):
            delegate = ColorDelegate(parent)
        elif isinstance(value, bool):
            delegate = BoolDelegate(parent)
        elif isinstance(value, list):
            delegate = ListDelegate(parent)
        else:
            delegate = cls(parent)
        return delegate


class FileSizeDelegate(Delegate):
    def displayText(self, value, locale):
        return str(value)

    def initStyleOption(self, option, index):
        super(FileSizeDelegate, self).initStyleOption(option, index)
        option.displayAlignment = QtCore.Qt.AlignRight


class ListDelegate(Delegate):
    def displayText(self, value, locale):
        return ', '.join(value)


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
        editor.setCurrentIndex(value)

    def setModelData(self, editor, model, index):
        value = bool(editor.currentIndex())
        super(BoolDelegate, self).setModelData(editor, model, index, value)


class EnumDelegate(Delegate):
    def __init__(self, enum, parent=None):
        super(EnumDelegate, self).__init__(parent)
        self.enum = enum

    def displayText(self, value, locale):
        return value.name

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        editor.setFocusPolicy(QtCore.Qt.StrongFocus)
        for member in self.enum:
            editor.addItem(member.name, member.value)
        editor.currentIndexChanged.connect(lambda: self.commitData.emit(editor))
        editor.currentIndexChanged.connect(lambda: self.closeEditor.emit(editor, self.NoHint))
        return editor

    def setEditorData(self, editor, index):
        member = index.model().data(index, QtCore.Qt.EditRole)
        index = editor.findData(member.value)
        editor.setCurrentIndex(index)
        # editor.showPopup()

    def setModelData(self, editor, model, index):
        value = self.enum(editor.currentData())
        super(EnumDelegate, self).setModelData(editor, model, index, value)


class ColorDelegate(Delegate):
    def displayText(self, value, locale):
        return

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QWidget(parent)
        editor.dialog = QtWidgets.QColorDialog(editor)
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
        if value.isValid():
            super(ColorDelegate, self).setModelData(editor, model, index, value)

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        option.rect.adjust(5, 5, -5, -5)
        painter.setBrush(value)
        painter.drawRect(option.rect)
