from __future__ import absolute_import

import os
import logging
from enum import Enum

from maya import cmds
from PySide2 import QtGui

from . import maya
from .. import utils


class Manager(maya.Manager):
    display_name = 'Image'
    plugin_name = 'mtoa.mll'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

    @property
    def attributes(self):
        '''
        texture_node = cmds.shadingNode('aiImage', asTexture=True)
        attrs = cmds.listAttr(texture_node, write=True, connectable=True)
        attrs = [attr for attr in attrs if attr[-1] not in ['R', 'G', 'B', 'X', 'Y', 'Z']]
        print(attrs)
        cmds.delete(texture_node)
        '''

        attrs = [
            # 'filename',
            'colorSpace',
            'filter',
            # 'mipmapBias',
            # 'singleChannel',
            # 'startChannel',
            # 'swrap',
            # 'twrap',
            # 'sscale',
            # 'tscale',
            # 'sflip',
            # 'tflip',
            # 'soffset',
            # 'toffset',
            # 'swapSt',
            # 'uvcoords',
            # 'uvset',
            'multiply',
            # 'offset',
            'ignoreMissingTextures',
            # 'missingTextureColorA',
            # 'missingTextureColor',
            # 'aiUserOptions',
            'autoTx',
            # 'colorManagementConfigFileEnabled',
            # 'colorManagementConfigFilePath',
            # 'colorManagementEnabled',
            # 'colorProfile',
            'colorSpace',
            # 'workingSpace',
            # 'useFrameExtension',
            # 'frame',
            # 'ignoreColorSpaceFileRules'
            ]

        # set custom attributes:
        attrs = [
            'name',
            'status',
            'colorSpace',
            'filter',
            'file_size',
            'filename',
            'directory',
            'autoTx',
            'multiply',
            'channels'
        ]

        return attrs

    def setActions(self):
        logging.debug('imageactions')
        self.addAction('File', 'Set Directory', None)
        self.addAction('File', 'Find and Replace', None)
        self.addAction('File', 'Relocate', None)
        self.addAction('File', 'Find Files', None)
        self.addAction('File', 'Open', None)
        self.addAction('File', 'Open Directory', self.open_directory)

        self.addAction('Parameters', 'Auto Color Space', None)
        self.addAction('Parameters', 'Auto Filter', None)

        self.addAction('Tiled', 'Generate TX', None)
        self.addAction('Tiled', 'Switch to Raw', None)
        self.addAction('Tiled', 'Switch to TX', None)

        self.addAction('Node', 'Convert', None)
        self.addAction('Node', 'Remove', None)
        self.addAction('Node', 'Show', None)
        self.addAction('Node', 'Select Dependent Objects', None)

    def setFilters(self):
        self.addFilter('name')
        self.addFilter('status')
        self.addFilter('colorSpace')
        self.addFilter('filter')
        self.addFilter('directory')

    def node_items(self):
        node_items = []
        for node in cmds.ls(type='aiImage'):
            node_items.append(self.node_item(node))
        return node_items

    def node_item(self, node):
        return Node(node)

    def open_directory(self):
        os.startfile(self.selected_nodes()[-1].directory)

class Node(object):
    node = ''
    read_only_attrs = []

    _file_size = None

    def __init__(self, node):
        self.node = node

        self.read_only_attrs.extend([
            # 'status',
            'file_size',
            'channels'
            ])

    def __repr__(self):
        return 'Node({})'.format(self.name)

    def __str__(self):
        return self.name

    def __getattr__(self, name):
        return self.get_node_attr(name)

    def __setattr__(self, name, value):
        if name not in Node.__dict__:
            self.set_node_attr(name, value)
        else:
            object.__setattr__(self, name, value)

    def attr(self, name):
        return '{}.{}'.format(self.node, name)

    def has_node_attr(self, name):
        return cmds.attributeQuery(name, node=self.node, exists=True)

    def get_node_attr(self, name):
        attr = self.attr(name)
        try:
            attr_type = cmds.getAttr(attr, type=True)
            value = cmds.getAttr(attr)

            if attr_type == 'float3':
                value = QtGui.QColor.fromRgbF(*value[0])
            elif attr_type == 'double3':
                value = list(*value[0])
            elif attr_type == 'enum':
                enums = cmds.attributeQuery(name, node=self.node, listEnum=True)
                value = utils.Enum(enums[0].split(':'), value)
            return value
        except ValueError:
            raise AttributeError('No attribute matches name: {}'.format(attr))

    def set_node_attr(self, name, value):
        attr = self.attr(name)
        try:
            if isinstance(value, str):
                value = value.replace('\\', '/')
                cmds.setAttr(attr, value, type='string')
            elif isinstance(value, utils.Enum):
                cmds.setAttr(attr, value.current)
            elif isinstance(value, QtGui.QColor):
                cmds.setAttr(attr, *value.getRgbF(), type='double3')
            else:
                cmds.setAttr(attr, value)

        except ValueError:
            raise AttributeError('No attribute matches name: {}'.format(attr))

    @property
    def name(self):
        return self.node.rsplit('|')[-1]

    @name.setter
    def name(self, value):
        self.node = cmds.rename(self.node, value)

    @property
    def filepath(self):
        return self.get_node_attr('filename')

    @filepath.setter
    def filepath(self, value):
        self._file_size = None
        self.set_node_attr('filename', value)

    @property
    def filename(self):
        return os.path.basename(self.filepath)

    @filename.setter
    def filename(self, value):
        path = os.path.join(self.directory, value)
        self.filepath = path

    @property
    def directory(self):
        return os.path.dirname(self.filepath)

    @directory.setter
    def directory(self, value):
        dirpath = os.path.abspath(value)
        path = os.path.join(dirpath, self.filename)
        self.filepath = path

    @property
    def status(self):
        return 1.01


    @status.setter
    def status(self, value):
        pass

    @property
    def file_size(self):
        if self._file_size is None:
            self._file_size = utils.FileSize.from_file(self.filepath)

        return self._file_size

    @property
    def channels(self):
        connections = []
        out_connections = cmds.listConnections(
                    self.node, destination=True, source=False, connections=True, plugs=True)

        for i in range(0, len(out_connections), 2):
            source = out_connections[i]
            destination = out_connections[i + 1]

            destination_node = destination.split('.')[0]
            if not cmds.objExists(destination_node):
                continue
            cls = cmds.nodeType(destination_node)
            ignore_classes = [
                'shadingEngine',
                'defaultShaderList',
                'materialInfo',
                'nodeGraphEditorInfo']
            if cls in ignore_classes:
                continue

            valid_attr = source.split('.')[-1] not in ('message', 'partition')
            if valid_attr:
                connections.append(destination.split('.')[-1])

        return ', '.join(set(connections))
