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
    from . import nodes_table
except ImportError:
    import plugin_utils
    import utils
    import nodes_table


class Manager(object):
    attributes = []

    display_name = ''
    plugin_name = ''

    settings_group = ''
    settings_defaults = {
        }

    def __init__(self, parent=None):
        self.settings = utils.Settings()
        self.init_settings()
        self.parent = parent
        self.actions = OrderedDict()
        self.filters = []

        # these shouldn't exist, just put in init
        self.setActions()
        self.setFilters()

        self.model = nodes_table.NodesModel()

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

    def addFilter(self, attribute):
        if attribute not in self.filters:
            self.filters.append(attribute)

    def load(self):
        self.model.clear()

        for i, attribute in enumerate(self.attributes):
            item = QtGui.QStandardItem()
            item.setText(attribute.display_name)
            item.setData(attribute)
            self.model.setHorizontalHeaderItem(i, item)

            # self.model.setHeaderData(i, QtCore.Qt.Horizontal, attribute.display_name, QtCore.Qt.DisplayRole)
            # self.model.setHeaderData(i, QtCore.Qt.Horizontal, attribute, QtCore.Qt.UserRole)

        # this probably shouldn't be in here
        self.parent.nodes_view.set_delegates()

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
                value = getattr(node_item, str(attribute))

                text = value
                if value is None:
                    text = ''

                if str(attribute) in node_item.read_only_attrs:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

                item.setData(text, QtCore.Qt.DisplayRole)
                item.setData(node_item)

                if isinstance(value, utils.Enum):
                    item.setData(value, role=QtCore.Qt.DisplayRole)
                items.append(item)
            self.model.appendRow(items)

    def setActions(self):
        pass

    def setFilters(self):
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
    def __init__(self, node):
        self.node = node
        self.read_only_attrs = []

    def __repr__(self):
        return 'Node({})'.format(self.name)

    def __str__(self):
        return self.name


class Attribute(object):
    def __init__(self, name, type_):
        self.name = name
        self.type = type_

    def __repr__(self):
        type_ = self.type.__name__ if hasattr(self.type, '__name__') else self.type
        return 'Attribute({}, {})'.format(self.name, type_)

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        return self.name.replace('_', ' ').title()


if __name__ == '__main__':
    attr = Attribute('count', None)
    print(repr(attr))
