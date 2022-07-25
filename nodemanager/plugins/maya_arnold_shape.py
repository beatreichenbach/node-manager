from __future__ import absolute_import

from maya import cmds
from PySide2 import QtWidgets

from . import maya
from . import maya_native_shape
from .. import manager


UPDATE_MODEL = manager.Action.UPDATE_MODEL
IGNORE_UPDATE = manager.Action.IGNORE_UPDATE
RELOAD_MODEL = manager.Action.RELOAD_MODEL


class Node(maya_native_shape.Node):

    def __init__(self, node):
        super(Node, self).__init__(node)

        self.attributes.extend([
            'aiDispHeight',
            'aiSubdivIterations',
            'aiSubdivAdaptiveMetric',
            'aiSubdivType',
            ])


class Manager(maya_native_shape.Manager):
    display_name = 'shape'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

        # addAction(group, label, func, update=UPDATE_MODEL)

    def nodes(self, options={}, maya_cls=Node):
        return super(Manager, self).nodes(options=options, maya_cls=Node)
