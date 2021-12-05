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


class AttributeTableView(QtWidgets.QTableView):
    def __init__(self, parent=None):
        super(AttributeTableView, self).__init__(parent)

        # self._header_state = {}
        self.init_ui()

    @property
    def _model(self):
        model = super(AttributeTableView, self).model()
        if model and isinstance(model, QtCore.QAbstractProxyModel):
            model = model.sourceModel()
        return model

    def init_ui(self):
        self.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSortingEnabled(True)

        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsMovable(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().hide()

        header = self.horizontalHeader()
        header.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)

    def update_requested(self):
        header_state = self.header_state
        if header_state:
            self._header_state = header_state

    def update(self):
        logging.debug('update_nodes_view')
        # self.update_header_actions()
        self.update_delegates()
        self.header_state = self._header_state

    def update_header_actions(self):
        header = self.horizontalHeader()
        for action in header.actions():
            header.removeAction(action)

        logging.debug('update_header_actions')
        for i in range(header.count()):
            item = self._model.horizontalHeaderItem(i)

            action = QtWidgets.QAction(item.text(), self)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(i))
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
            if state and not header.sectionSize(i):
                header.resizeSection(i, 100)
            header.setSectionHidden(i, not state)

        # prevent all columns to be hidden
        if not any(states):
            header.actions()[0].setChecked(True)
            header.setSectionHidden(0, False)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())

        if not self.model():
            return

        model_index = self.model().mapToSource(index)

        if not self._model.itemFromIndex(model_index).isEditable():
            return

        menu = QtWidgets.QMenu(self)
        action = menu.addAction('Edit')
        action.triggered.connect(lambda: self.edit(index))

        # todo: add other required actions
        menu.popup(event.globalPos())

    @property
    def header_state(self):
        header = self.horizontalHeader()
        headers = {}
        for i in range(header.count()):
            attribute = self._model.horizontalHeaderItem(i).data()
            visibility = not header.isSectionHidden(i)
            width = header.sectionSize(i)
            visual_index = header.visualIndex(i)
            headers[attribute] = {
                'width': width,
                'visibility': visibility,
                'visual_index': visual_index
            }
        logging.debug(['get_header', headers])

        return headers

    @header_state.setter
    def header_state(self, headers):
        if headers:
            # cache state
            self._header_state = headers
        else:
            # set s tate from cache
            headers = self._header_state

        logging.debug(['set_header', headers])
        header = self.horizontalHeader()
        for i in range(header.count()):
            attribute = self._model.horizontalHeaderItem(i).data()
            values = headers.get(attribute)
            if values:
                visibility = values.get('visibility', True)
                width = values.get('width', 100)
                if width == 0:
                    visibility = False
                header.setSectionHidden(i, not visibility)
                header.resizeSection(i, width)
                header.moveSection(header.visualIndex(i), values.get('visual_index', i))
        self.update_header_actions()


class AttributeItemModel(QtGui.QStandardItemModel):
    updated = QtCore.Signal()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        # override to enable deferred loading of items
        data = super(AttributeItemModel, self).data(index, role)
        if data is None and role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            attribute_item = self.attribute_item_from_index(index)
            attribute = self.attribute_from_index(index)
            data = getattr(attribute_item, attribute)
            super(AttributeItemModel, self).setData(index, data, role)
        return data

    def setData(self, index, value, role):
        result = super(AttributeItemModel, self).setData(index, value, role)

        if role == QtCore.Qt.EditRole:
            attribute_item = self.attribute_item_from_index(index)
            attribute = self.attribute_from_index(index)
            try:
                setattr(attribute_item, attribute, value)
            except AttributeError:
                return False

        return True and result

    def attribute_item_from_index(self, index):
        return self.item(index.row(), 0).data()

    def attribute_from_index(self, index):
        return self.horizontalHeaderItem(index.column()).data()

    def set_items(self, attribute_items):
        self.clear()
        for attribute_item in attribute_items:
            items = []
            for i, attribute in attribute_item.attributes:
                item = QtGui.QStandardItem()

                if attribute in attribute_item.locked_attributes:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

                if i == 0:
                    item.setData(attribute_item)

            if items:
                items[0].append(attribute_item)
                self.appendRow(items)

        self.set_headers(attribute_items)
        self.updated.emit()

    def update(self):
        for row in range(self.rowCount()):
            self.update_index(self.index(row, 0))

    def update_items(self, attribute_items):
        for row in range(self.rowCount()):
            attribute_item = self.item(row, 0).data()
            if attribute_item in attribute_items:
                self.update_index(self.index(row, 0))
                attribute_items.remove(attribute_item)
                if not attribute_items:
                    break

    def update_index(self, index):
        for column in range(self.columnCount()):
            item = self.item(index.row(), column)
            item.setData(None, QtCore.Qt.DisplayRole)

    def set_headers(self, attribute_items):
        logging.debug('set_headers')
        if attribute_items:
            node = attribute_items[0]
            self.attributes = node.attributes
            for i, attribute in enumerate(self.attributes):
                item = QtGui.QStandardItem()
                item.setText(utils.title(attribute))
                item.setData(attribute)
                self.setHorizontalHeaderItem(i, item)


class AttributeSortModel(QtCore.QSortFilterProxyModel):
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

        # Sometimes the right click happens on not selected row
        indexes = [index]
        if self.parent() and self.parent().selectionModel():
            indexes.extend(self.parent().selectionModel().selectedRows(index.column()))
        indexes = list(set(indexes))

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
        # editor.setFocusPolicy(QtCore.Qt.StrongFocus)
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
        # editor.setFocusPolicy(QtCore.Qt.StrongFocus)
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
        editor.color = None
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
        if value and value.isValid():
            super(ColorDelegate, self).setModelData(editor, model, index, value)

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        if value:
            option.rect.adjust(5, 5, -5, -5)
            painter.setBrush(value)
            painter.drawRect(option.rect)
