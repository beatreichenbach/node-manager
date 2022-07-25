from __future__ import absolute_import

from maya import cmds
from PySide2 import QtWidgets

from . import maya
from .. import manager


UPDATE_MODEL = manager.Action.UPDATE_MODEL
IGNORE_UPDATE = manager.Action.IGNORE_UPDATE
RELOAD_MODEL = manager.Action.RELOAD_MODEL


class Node(maya.Node):

    def __init__(self, node):
        super(Node, self).__init__(node)

        self.attributes.extend([
            'smoothLevel',
            'osdVertBoundary',
            'osdFvarBoundary',
        ])


class Manager(maya.Manager):
    display_name = 'shape'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

        # addAction(group, label, func, update=UPDATE_MODEL)

    def nodes(self, options={}, maya_cls=Node):
        if options.get('selection'):
            transforms = cmds.ls(selection=True, type='transform', long=True)
            children = cmds.listRelatives(transforms, allDescendents=True, fullPath=True, type='transform') or []
            transforms.extend(children)
        else:
            transforms = cmds.ls(type='transform', long=True)

        maya_nodes = []

        for transform in transforms:
            shapes = cmds.listRelatives(transform, shapes=True, fullPath=True)
            if shapes and cmds.nodeType(shapes[0]) == 'mesh':
                maya_nodes.append(shapes[0])

        nodes = [maya_cls(maya_node) for maya_node in maya_nodes]

        return nodes
