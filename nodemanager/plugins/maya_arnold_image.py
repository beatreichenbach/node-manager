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
        return maya.Node(node)

    def open_directory(self):
        if self.selected_nodes():
            os.startfile(self.selected_nodes()[-1].directory)
