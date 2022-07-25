from __future__ import absolute_import

from maya import cmds
from PySide2 import QtWidgets

from . import maya
from .. import manager


UPDATE_MODEL = manager.Action.UPDATE_MODEL
IGNORE_UPDATE = manager.Action.IGNORE_UPDATE
RELOAD_MODEL = manager.Action.RELOAD_MODEL


class Manager(maya.Manager):
    display_name = 'File'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

        # addAction(group, label, func, update=UPDATE_MODEL)
        self.addAction('File', 'Set Directory', manager.set_directory)
        self.addAction('File', 'Find and Replace', manager.find_and_replace)
        self.addAction('File', 'Relocate', maya.relocate)
        self.addAction('File', 'Locate', maya.locate)
        self.addAction('File', 'Open', manager.open_file, IGNORE_UPDATE)
        self.addAction('File', 'Open Directory', manager.open_directory, IGNORE_UPDATE)
        self.addAction('Parameters', 'Auto Color Space', auto_colorspace)
        self.addAction('Parameters', 'Auto Filter', auto_filter)
        self.addAction('Tiled', 'Generate Tiled', maya.generate_tiled)
        self.addAction('Tiled', 'Switch to Raw', manager.switch_raw)
        self.addAction('Tiled', 'Switch to Tiled', manager.switch_tiled)
        self.addAction('Node', 'Convert', convert, RELOAD_MODEL)
        self.addAction('Node', 'Select Dependent Objects', select_dependents, IGNORE_UPDATE)

        self.addFilter('name')
        self.addFilter('status')
        self.addFilter('colorSpace')
        self.addFilter('filter')
        self.addFilter('directory')
        self.addFilter('channels')

    def nodes(self, options={}):
        return super(Manager, self).nodes(options, Node, 'file')


class Node(manager.FileNode, maya.Node):

    def __init__(self, node):
        super(Node, self).__init__(node)

        '''
        texture_node = cmds.shadingNode('file', asTexture=True)
        attrs = cmds.listAttr(texture_node, write=True, connectable=True)
        attrs = [attr for attr in attrs if attr[-1] not in ['R', 'G', 'B', 'X', 'Y', 'Z']]
        print(attrs)
        cmds.delete(texture_node)
        '''
        self.attributes.extend([
            'uvTilingMode',
            'alphaIsLuminance',
            'colorGain',
            'colorOffset',
            'colorSpace',
            'filterType',
            'ignoreColorSpaceFileRules',
            'aiFilter',
            'channels',
        ])
        self.locked_attributes.extend(['channels'])

    @property
    def filepath(self):
        return self._get_node_attr('fileTextureName')

    @filepath.setter
    def filepath(self, value):
        self._set_node_attr('fileTextureName', value)

    @property
    def channels(self):
        channels = []

        shader_types = cmds.listNodeTypes('shader')
        future = cmds.listHistory(self.node, future=True)
        descendents = cmds.ls(*future, type=shader_types)

        for descendent in descendents:
            in_connections = cmds.listConnections(
                descendent,
                connections=True,
                source=True,
                destination=False)
            for i in range(0, len(in_connections), 2):
                source = in_connections[i + 1]
                destination = in_connections[i]

                source_node = source.split('.')[0]
                if not cmds.objExists(source_node):
                    continue
                history = cmds.listHistory(source_node)
                if self.node in history:
                    channels.append(destination.split('.')[-1])
        return channels


def select_dependents(nodes):
    objects = []

    for node in nodes:
        future = cmds.listHistory(node.node, future=True)
        shading_engines = cmds.ls(*future, type='shadingEngine')

        for shading_engine in shading_engines:
            set_members = cmds.sets(shading_engine, query=True)
            objects.extend(set_members)

    objects = list(set(objects))
    selection = cmds.select(objects, replace=True)

    return selection


def auto_filter(nodes):
    for node in nodes:
        node.filter = 0
        node.mipmapBias = 0


def auto_colorspace(nodes):
    for node in nodes:
        if any(['color' in channel.lower() for channel in node.channels]):
            node.colorSpace = 'sRGB'
        else:
            node.colorSpace = 'linear'


def convert(nodes):
    classes = ['aiImage']
    item, result = QtWidgets.QInputDialog.getItem(
        None,
        'Convert',
        'Convert nodes to:',
        classes,
        editable=False)

    if result:
        for node in nodes:
            convert_node(node, item)


def convert_node(node, cls):
    if cls == 'aiImage':
        replace_node = cmds.shadingNode('aiImage', asUtility=True)
        cmds.setAttr('{}.filename'.format(replace_node), node.filepath, type='string')
        cmds.setAttr('{}.filter'.format(replace_node), node.aiFilter.value)
        if node.colorSpace in ['sRGB', 'Raw']:
            cmds.setAttr('{}.colorSpace'.format(replace_node), node.colorSpace, type='string')

        cmds.setAttr('{}.multiply'.format(replace_node), *node.colorGain.getRgbF(), type='double3')
        cmds.setAttr('{}.offset'.format(replace_node), *node.colorOffset.getRgbF(), type='double3')

        name = node.name
        cmds.delete(node.node)
        cmds.rename(replace_node, name)
