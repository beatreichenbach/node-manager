from __future__ import absolute_import

import os
import logging
from enum import Enum

from maya import cmds
from PySide2 import QtGui

from . import maya
from .. import utils
from .. import manager


class Manager(maya.Manager):
    display_name = 'Image'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

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

        self.addFilter('name')
        self.addFilter('status')
        self.addFilter('colorSpace')
        self.addFilter('filter')
        self.addFilter('directory')
        self.addFilter('channels')

    def nodes(self, options={}):
        nodes = []
        maya_nodes = cmds.ls(type='aiImage')
        for maya_node in maya_nodes:
            node = Node(maya_node)
            nodes.append(node)
        return nodes

    def open_directory(self):
        if self.selected_nodes():
            os.startfile(self.selected_nodes()[-1].directory)


class Node(maya.Node):
    _file_size = None

    def __init__(self, node):
        super(Node, self).__init__(node)

        self.locked_attributes.extend([
            'status',
            'file_size',
            'channels'
            ])

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
            'name',
            'status',
            'colorSpace',
            'filter',
            'file_size',
            'filename',
            'directory',
            'autoTx',
            'multiply',
            'channels',
        ]

        # attrs = [
        #     'name',
        #     'channels',
        #     ]

        return attrs

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
        channels = []

        shader_types = cmds.listNodeTypes('shader')
        history = cmds.listHistory(self.node, future=True)
        descendents = cmds.ls(*history, type=shader_types)

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
