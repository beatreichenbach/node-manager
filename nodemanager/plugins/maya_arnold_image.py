from __future__ import absolute_import

from maya import cmds
import logging
from . import maya

from PySide2 import QtGui

class Manager(maya.Manager):
    display_name = 'Image'
    plugin_name = 'mtoa.mll'

    def __init__(self):
        super(Manager, self).__init__()

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
            'filename',
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

        # extra attributes:
        attrs.insert(0, 'name')

        return attrs

    def setActions(self):
        self.addAction('File', 'Set Directory', None)
        self.addAction('File', 'Find and Replace', None)
        self.addAction('File', 'Relocate', None)
        self.addAction('File', 'Find Files', None)
        self.addAction('File', 'Open', None)
        self.addAction('File', 'Open Directory', None)

        self.addAction('Parameters', 'Set Parameters', None)
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
        name = node.rsplit('|')[-1]
        node_item = Node(node)
        for attribute in self.attributes:
            try:
                value = cmds.getAttr('{}.{}'.format(node, attribute))
            except ValueError:
                value = None

            if attribute == 'name':
                value = name

            if isinstance(value, list):
                color = QtGui.QColor.fromRgbF(*value[0])
                value = color

            node_item.attributes[attribute] = value
        return node_item




class Node(object):
    attributes = {}

    def __init__(self, node):
        self.node = node
