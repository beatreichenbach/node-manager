import logging
from collections import OrderedDict

from PySide2 import QtCore

from . import plugin_utils


class Action(QtCore.QObject):
    UPDATE_MODEL = 0
    IGNORE_UPDATE = 1
    RELOAD_MODEL = 2

    triggered = QtCore.Signal(list, int)

    def __init__(self, label, func, update):
        super(Action, self).__init__()
        self.label = label
        self.func = func
        self.update = update

    def __repr__(self):
        return 'Action({})'.format(self.label)

    def __str__(self):
        return self.label

    def trigger(self, nodes):
        logging.debug('trigger')
        # todo: try except would be faster
        nodes = [node for node in nodes if node.exists]
        if not nodes:
            return
        self.func(nodes)
        logging.debug([self.label, self.update, self.func])
        self.triggered.emit(nodes, self.update)


class Manager(object):
    display_name = 'General'
    plugin_name = ''

    def __init__(self):
        self.actions = OrderedDict()
        self.filters = []

    @classmethod
    def from_plugin(cls, plugin):
        cls = plugin_utils.plugin_class(cls, plugin)
        return cls()

    def load_plugin(self):
        pass

    def addAction(self, group, label, func, update=Action.UPDATE_MODEL):
        action = Action(label, func, update)

        actions = self.actions.get(group, [])
        if action not in actions:
            actions.append(action)
        self.actions[group] = actions

    def runAction(self, func, update_model):
        nodes = [node for node in self.selected_nodes() if node.exists]
        if not nodes:
            return
        func(nodes)
        if update_model:
            self.model.update()

    def addFilter(self, attribute):
        if attribute not in self.filters:
            self.filters.append(attribute)

    def nodes(self, options={}):
        return []


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
