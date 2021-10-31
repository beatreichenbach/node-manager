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
            'multiply'
        ]

        return attrs

    def setActions(self):
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

    def __init__(self, node):
        self.node = node

        self.read_only_attrs.extend([
            # 'status',
            'file_size'
            ])

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
                logging.debug('cmds.setAttr('+attr+', '+value+', type=\'string\')')
            elif isinstance(value, utils.Enum):
                cmds.setAttr(attr, value.current)
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
        self.set_node_attr('filename', value)

    @property
    def filename(self):
        return os.path.basename(self.filepath)

    @filename.setter
    def filename(self, value):
        dirpath = os.path.abspath(self.filepath)
        path = os.path.join(dirpath, value)
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

    @property
    def file_size(self):
        if not os.path.isfile(self.filepath):
            return ''

        factors = {
            'GB': 1<<30,
            'MB': 1<<20,
            'KB': 1<<10
            }

        unit = 'KB'
        size = os.path.getsize(self.filepath)
        text = '{:,.0f} {}'.format(size / (factors[unit]), unit)
        return text


