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
        self.set_delegates()

    def set_delegates(self):
        item = self.manager.model.item(0, 0)
        if not item:
            return

        node = item.data()
        for i, attribute in enumerate(self.manager.attributes):
            value = getattr(node, attribute)

            delegate = Delegate(self.nodes_view)
            if isinstance(value, str):
                pass
            elif isinstance(value, int):
                delegate = SpinBoxDelegate(self.nodes_view)
            elif isinstance(value, float):
                delegate = DoubleSpinBoxDelegate(self.nodes_view)
            elif isinstance(value, bool):
                pass
                # delegate = CheckboxDelegate()
            elif isinstance(value, list) and len(value) == 2:
                pass
            elif isinstance(value, list) and len(value) == 3:
                pass
            elif isinstance(value, QtGui.QColor):
                pass
                # delegate = ColorDelegate()
            elif isinstance(value, utils.Enum):
                delegate = EnumDelegate(self.nodes_view, enum=value)


            if delegate:
                self.nodes_view.setItemDelegateForColumn(i, delegate)


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




class Delegate(QtWidgets.QStyledItemDelegate):
    def closeEditor(self, editor, hint):
        logging.debug(['closeEditor', editor.text()])
        super(Delegate, self).closeEditor(editor, hint)


class SpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QtWidgets.SpinBox(parent)
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
        editor.showPopup()

    def setModelData(self, editor, model, index):
        value = utils.Enum(self.enum.enums)
        value.current = editor.currentIndex()
        # model.setData(index, value, QtCore.Qt.EditRole)

        for item_index in self.parent().selectionModel().selectedRows(index.column()):
            model.setData(item_index, value, QtCore.Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    gui_utils.show(ManagerWidget)
