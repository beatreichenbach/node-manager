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
        return
        header = self.horizontalHeader()
        for i in range(self.manager.model.columnCount()):
            item = self.manager.model.horizontalHeaderItem(i)

            action = QtWidgets.QAction(item.text(), self)
            action.setCheckable(True)
            action.setChecked(not self.isColumnHidden(i))
            action.triggered.connect(self.update_header)
            header.addAction(action)

    def update_header(self):
        return
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
        for i in range(self.model().columnCount()):
            logging.debug(i)
            attribute = self.model().sourceModel().headerData(i, QtCore.Qt.Horizontal, QtCore.Qt.UserRole)
            item = self.model().sourceModel().horizontalHeaderItem(i)
            attribute = item.data()
            if not attribute:
                continue
            delegate = Delegate.fromAttribute(attribute, parent=self)
            self.setItemDelegateForColumn(i, delegate)

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


class NodesModel(QtGui.QStandardItemModel):
    # def __init__(self):
    #     super(NodesModel, self).__init__()

    def setData(self, index, value, role):
        # super(NodesModel, self).setData(index, value, role)

        if role == QtCore.Qt.EditRole:
            node = self.itemFromIndex(index).data()
            item = self.horizontalHeaderItem(index.column())
            attribute = item.data()
            setattr(node, str(attribute), value)

        return True


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
        # still don't know what source_parent is
        # logging.debug([source_row, source_parent.column()])
        index = self.sourceModel().index(source_row, 0, source_parent)
        # index = self.sourceModel().index(source_row, 0)
        node = self.sourceModel().data(index, QtCore.Qt.UserRole)

        item = self.sourceModel().item(source_row, 0)
        node = item.data()

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
        logging.debug('update_filters')
        self.filters = filters
        self.setFilterRegExp('')


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

    @classmethod
    def fromAttribute(cls, attribute, parent=None):
        type_ = attribute.type
        if type_ == utils.Enum:
            delegate = EnumDelegate(parent, enum=attribute.enum)
        elif type_ == utils.FileSize:
            delegate = FileSizeDelegate(parent)
        elif type_ == QtGui.QColor:
            delegate = ColorDelegate(parent)
        elif type_ == bool:
            delegate = BoolDelegate(parent)
        else:
            delegate = cls(parent)
        return delegate


class FileSizeDelegate(Delegate):
    def displayText(self, value, locale):
        return str(value)


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
        editor.setCurrentIndex(value.current)

    def setModelData(self, editor, model, index):
        value = bool(editor.currentIndex())

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
