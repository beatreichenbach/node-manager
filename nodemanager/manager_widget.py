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


        self.nodes_view.setModel(self.manager.model)

        self.action_widget.updateActions()
        self.connect_ui()

        self.load_settings()


        self.filter = QtWidgets.QLineEdit()
        self.layout().addWidget(self.filter)
        self.filter.textChanged.connect(self.filter_changed)

    def filter_changed(self):
        text = self.filter.text()
        for i in range(self.manager.model.rowCount()):
            item = self.manager.model.item(i, 0)
            match = text.lower() in item.data().name.lower()
            self.nodes_view.setRowHidden(i, not match)

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
        self.manager.load()

        self.load_settings()

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

        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsMovable(True)
        self.verticalHeader().hide()

        header = self.horizontalHeader()
        header.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)

    def update_header_actions(self):
        header = self.horizontalHeader()
        for i in range(self.manager.model.columnCount()):
            item = self.model().horizontalHeaderItem(i)

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
        item = self.model().item(0, 0)
        if not item:
            return

        node = item.data()
        for i, attribute in enumerate(self.manager.attributes):
            value = getattr(node, attribute)

            delegate = None
            if isinstance(value, str):
                pass
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
            elif isinstance(value, utils.Enum):
                delegate = EnumDelegate(self, enum=value)
            elif isinstance(value, utils.FileSize):
                delegate = FileSizeDelegate(self)
            elif isinstance(value, QtGui.QColor):
                delegate = ColorDelegate(self)

            if delegate:
                self.setItemDelegateForColumn(i, delegate)

    def contextMenuEvent(self, event):
        item_index = self.indexAt(event.pos())

        if not self.manager.model.itemFromIndex(item_index).isEditable():
            return

        menu = QtWidgets.QMenu(self)
        action = menu.addAction('Edit Selected')
        action.triggered.connect(lambda: self.edit(item_index))

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

    def updateActions(self):
        self.clear()
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
    def __init__(self, parent):
        super(DisplayWidget, self).__init__(parent)

        self.parent = parent
        self.manager = parent.manager


        self.init_ui()

    def init_ui(self):
        self.setLayout(QtWidgets.QVBoxLayout())

        self.filter_grp = QtWidgets.QGroupBox('Filter')
        self.layout().addWidget(self.filter_grp)




# class Delegate(QtWidgets.QStyledItemDelegate):
#     def closeEditor(self, editor, hint):
#         logging.debug(['closeEditor', editor.text()])
#         super(Delegate, self).closeEditor(editor, hint)

class FileSizeDelegate(QtWidgets.QStyledItemDelegate):
    def displayText(self, value, locale):
        return str(value)

class BoolDelegate(QtWidgets.QStyledItemDelegate):

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QCheckBox(parent)
        editor.stateChanged.connect(lambda: self.commitData.emit(editor))
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        editor.setChecked(value)

    def setModelData(self, editor, model, index):
        value = editor.isChecked()
        model.setData(index, value, QtCore.Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        if isinstance(self.parent(), QtWidgets.QAbstractItemView):
            self.parent().openPersistentEditor(index)

class SpinBoxDelegate(QtWidgets.QStyledItemDelegate):
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

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class DoubleSpinBoxDelegate(QtWidgets.QStyledItemDelegate):
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

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class EnumDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, *args, enum):
        super(EnumDelegate, self).__init__(*args)
        self.enum = enum

    def displayText(self, value, locale):
        return value.enums.get(value.current)

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        editor.setFocusPolicy(QtCore.Qt.StrongFocus)
        editor.addItems(self.enum.enums.values())
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
        value.current = editor.currentIndex()
        # model.setData(index, value, QtCore.Qt.EditRole)

        # self.parent() unclean?
        for item_index in self.parent().selectionModel().selectedRows(index.column()):
            model.setData(item_index, value, QtCore.Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class ColorDelegate(QtWidgets.QStyledItemDelegate):
    def displayText(self, value, locale):
        return ''

    def createEditor(self, parent, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        self.dialog = QtWidgets.QColorDialog(value, parent)

        editor = QtWidgets.QWidget()

        self.dialog.colorSelected.connect(lambda: self.colorSelected(editor))
        # dialog.colorSelected.connect(lambda: editor.color = dialog.selectedColor())
        # dialog.colorSelected.connect(lambda: self.commitData.emit(editor))
        # dialog.colorSelected.connect(lambda: self.closeEditor.emit(editor, self.NoHint))

        # dialog.open()

        # color = QtWidgets.QColorDialog.getColor(value, parent)
        # editor.color = color
        # editor.setVisible(False)
        self.closeEditor.connect(lambda: logging.debug('closeEditor'))
        self.commitData.connect(lambda: logging.debug('commitData'))
        # self.setModelData(editor, index.model(), index)

        # logging.debug('createEditor')
        # self.closeEditor.emit(editor, self.NoHint)
        # self.commitData.emit(editor)

        # self.closeEditor.connect(lambda: self.commitData.emit(editor))

        # self.setModelData(editor, index.model(), index)
        return editor


    def colorSelected(self, editor):
        logging.debug('colorSelected')
        # editor.color = self.dialog.selectedColor()
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, self.NoHint)

    def setModelData(self, editor, model, index):
        value = self.dialog.selectedColor()

        if index.row() == 4:
            logging.debug(('setModelData', value))

        if not value.isValid():
            return


        for item_index in self.parent().selectionModel().selectedRows(index.column()):
            model.setData(item_index, value, QtCore.Qt.EditRole)

    def setEditorData(self, editor, index):
        logging.debug('setEditorData')
        value = index.model().data(index, QtCore.Qt.EditRole)
        self.dialog.setCurrentColor(value)
        self.dialog.open()

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.EditRole)

        if index.row() == 4:
            logging.debug(('paint', value))

        option.rect.adjust(5, 5, -5, -5)
        painter.setBrush(value)
        painter.drawRect(option.rect)
