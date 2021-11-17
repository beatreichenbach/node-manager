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
        action = QtWidgets.QAction(text)
        action.triggered.connect(lambda: func(self.selected_nodes()))
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
            for selected_index in self.table_view.selectionModel().selectedRows():
                index = self.table_view.model().mapToSource(selected_index)
                node = self.model.data(index, role=QtCore.Qt.UserRole + 1)
                if node:
                    nodes.append(node)

        return nodes


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


if __name__ == '__main__':
    pass
