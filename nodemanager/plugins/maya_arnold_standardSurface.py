from __future__ import absolute_import

import os
import logging
from enum import Enum

from maya import cmds
from PySide2 import QtGui

from . import maya
from .. import utils

class Manager(maya.Manager):
    display_name = 'Standard Surface'
    plugin_name = 'mtoa.mll'

    def __init__(self):
        super(Manager, self).__init__()

    @property
    def attributes(self):
        '''
        texture_node = cmds.shadingNode('aiStandardSurface', asTexture=True)
        attrs = cmds.listAttr(texture_node, write=True, connectable=True)
        attrs = [attr for attr in attrs if attr[-1] not in ['R', 'G', 'B', 'X', 'Y', 'Z']]
        print(attrs)
        cmds.delete(texture_node)
        '''

        attrs = [
            'normalCamera',
            # 'aiEnableMatte',
            # 'aiMatteColor',
            # 'aiMatteColorA',
            # 'base',
            'baseColor',
            # 'diffuseRoughness',
            # 'specular',
            'specularColor',
            'specularRoughness',
            # 'specularAnisotropy',
            # 'specularRotation',
            'metalness',
            # 'transmission',
            'transmissionColor',
            # 'transmissionDepth',
            # 'transmissionScatter',
            # 'transmissionScatterAnisotropy',
            # 'transmissionDispersion',
            # 'transmissionExtraRoughness',
            # 'transmitAovs',
            # 'subsurface',
            'subsurfaceColor',
            # 'subsurfaceRadius',
            # 'subsurfaceScale',
            # 'subsurfaceAnisotropy',
            # 'subsurfaceType',
            # 'sheen',
            # 'sheenColor',
            # 'sheenRoughness',
            # 'thinWalled',
            # 'tangent',
            # 'coat',
            # 'coatColor',
            # 'coatRoughness',
            # 'coatAnisotropy',
            # 'coatRotation',
            # 'coatNormal',
            # 'thinFilmThickness',
            # 'emission',
            'emissionColor',
            'opacity',
            # 'caustics',
            # 'internalReflections',
            # 'exitToBackground',
            # 'indirectDiffuse',
            # 'indirectSpecular',
            # 'aovId1',
            # 'id1',
            # 'aovId2',
            # 'id2',
            # 'aovId3',
            # 'id3',
            # 'aovId4',
            # 'id4',
            # 'aovId5',
            # 'id5',
            # 'aovId6',
            # 'id6',
            # 'aovId7',
            # 'id7',
            # 'aovId8',
            # 'id8'
            ]


        # extra attributes:
        attrs.insert(0, 'name')

        return attrs

    def setActions(self):
        pass

    def node_items(self):
        node_items = []
        for node in cmds.ls(type='aiStandardSurface'):
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

        # self.read_only_attrs.extend([
        #     # 'status',
        #     'file_size'
        #     ])

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
    def status(self):
        return 1.01


    @status.setter
    def status(self, value):
        pass
