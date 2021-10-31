import os
import re
import glob
import logging
import shutil
from collections import OrderedDict

from PySide2 import QtWidgets, QtCore, QtGui

try:
    from . import plugin_utils
    from . import utils
except ImportError:
    import plugin_utils
    import utils

class NodesModel(QtGui.QStandardItemModel):
    def __init__(self, manager):
        super(NodesModel, self).__init__()

        self.manager = manager

    def setData(self, index, value, role):

        super(NodesModel, self).setData(index, value, role)

        if role == QtCore.Qt.EditRole:
            node = self.itemFromIndex(index).data()
            attribute = self.manager.attributes[index.column()]
            setattr(node, attribute, value)

        return True


class Manager(object):
    attributes = []

    display_name = ''
    plugin_name = ''

    settings_group = ''
    settings_defaults = {
        }
    actions = OrderedDict()

    def __init__(self, parent=None):
        self.settings = utils.Settings()
        self.init_settings()
        self.parent = parent

        self.setActions()

        self.model = NodesModel(self)

    def init_settings(self):
        self.settings.beginGroup(self.settings_group)
        for setting, value in self.settings_defaults.items():
            if not self.settings.contains(setting):
                self.settings.setValue(setting, value)
        self.settings.endGroup()

    @classmethod
    def from_plugin(cls, plugin):
        cls = plugin_utils.plugin_class(cls, plugin)
        return cls()

    def load_plugin(self):
        pass

    def addAction(self, group, text, func):
        action = Action(text, func, group)

        self.actions[action.hash()] = action

    def load(self):
        self.model.clear()
        labels = [attribute.replace('_', ' ').title() for attribute in self.attributes]
        self.model.setHorizontalHeaderLabels(labels)

        try:
            self.load_plugin()
        except RuntimeError:
            QtWidgets.QMessageBox.warning(
                self,
                'Plugin Load Error',
                'Unable to load plugin: {}'.format(self.plugin_name),
                QtWidgets.QMessageBox.Ok)
            return


        for node_item in self.node_items():
            items = []
            for attribute in self.attributes:
                item = QtGui.QStandardItem()
                value = getattr(node_item, attribute)

                text = value
                if value is None:
                    text = ''
                # else:
                #     text = str(value)

                # if isinstance(value, QtGui.QColor):
                #     text = '({}, {}, {})'.format(value.redF(), value.greenF(), value.blueF())
                # elif isinstance(value, bool):
                    # text = ''

                    # item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                    # item.setCheckState(QtCore.Qt.Checked if value else QtCore.Qt.Unchecked)
                # elif isinstance(value, utils.Enum):
                #     text = value.enums.get(value.current)

                if attribute in node_item.read_only_attrs:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

                item.setData(text, QtCore.Qt.DisplayRole)
                item.setData(node_item)

                if isinstance(value, utils.Enum):
                    item.setData(value, role=QtCore.Qt.DisplayRole)
                items.append(item)
            self.model.appendRow(items)

    def setActions(self):
        pass

    def selected_nodes(self):
        nodes = []
        for row in self.parent.nodes_view.selectionModel().selectedRows():
            nodes.append(self.model.itemFromIndex(row).data())

        return nodes


class Action(object):
    def __init__(self, text, func, group='Node'):
        self.text = text
        self.group = group
        self.func = func

    def hash(self):
        return hash((self.text, self.group))

class Node(object):
    def __init__(self):
        pass


