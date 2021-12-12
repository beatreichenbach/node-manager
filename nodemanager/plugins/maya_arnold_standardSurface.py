from __future__ import absolute_import

from maya import cmds
from PySide2 import QtWidgets

from . import maya
from .. import manager


UPDATE_MODEL = manager.Action.UPDATE_MODEL
IGNORE_UPDATE = manager.Action.IGNORE_UPDATE
RELOAD_MODEL = manager.Action.RELOAD_MODEL


class Manager(maya.Manager):
    display_name = 'standardSurface'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

        # addAction(group, label, func, update=UPDATE_MODEL)
        self.addAction('Node', 'Select Dependent Objects', select_dependents, IGNORE_UPDATE)

        self.addFilter('name')

    def nodes(self, options={}):
        return super(Manager, self).nodes(options, Node, 'standardSurface')


class Node(maya.Node):

    def __init__(self, node):
        super(Node, self).__init__(node)

        '''
        texture_node = cmds.shadingNode('aiStandardSurface', asTexture=True)
        attrs = cmds.listAttr(texture_node, write=True, connectable=True)
        attrs = [attr for attr in attrs if attr[-1] not in ['R', 'G', 'B', 'X', 'Y', 'Z']]
        print(attrs)
        cmds.delete(texture_node)
        '''
        self.attributes.extend([
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
            ])


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
