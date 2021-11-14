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

    def __init__(self):
        self.settings = utils.Settings()
        self.init_settings()

        self.actions = OrderedDict()
        self.filters = []
        self.model = nodes_table.NodesModel()
        self.table_view = None

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
        # action = Action(text, func, group)
        action = QtWidgets.QAction(text)
        action.triggered.connect(func)
        actions = self.actions.get(group, set())
        actions.add(action)
        self.actions[group] = actions

    def addFilter(self, attribute):
        if attribute not in self.filters:
            self.filters.append(attribute)

    def load(self):
        try:
            self.load_plugin()
        except RuntimeError:
            QtWidgets.QMessageBox.warning(
                self,
                'Plugin Load Error',
                'Unable to load plugin: {}'.format(self.plugin_name),
                QtWidgets.QMessageBox.Ok)
            return

        self.model.set_nodes(self.nodes())

    def nodes(self):
        return []

    def selected_nodes(self):
        nodes = []
        if self.table_view:
            for row in self.table_view.selectionModel().selectedRows():
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
    node = None
    locked_attributes = []

    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return 'Node({})'.format(self.name)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return str(self.node)


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
