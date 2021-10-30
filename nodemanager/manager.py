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
        self.model.setHorizontalHeaderLabels(self.attributes)

        for node_item in self.node_items():
            items = []
            for attribute, value in node_item.attributes.items():
                item = QtGui.QStandardItem()

                text = str(value)
                if isinstance(value, QtGui.QColor):
                    text = '({}, {}, {})'.format(value.redF(), value.greenF(), value.blueF())
                elif isinstance(value, bool):
                    text = ''

                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(QtCore.Qt.Checked if value else QtCore.Qt.Unchecked)

                item.setText(text)
                item.setData(node_item)
                items.append(item)
            self.model.appendRow(items)


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


