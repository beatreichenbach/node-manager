from __future__ import absolute_import

from maya import cmds
import logging
from . import maya


class Manager(maya.Manager):
    display_name = 'Image'
    plugin_name = 'mtoa.mll'

    def __init__(self):
        super(Manager, self).__init__()

    def setActions(self):
        self.addAction('File', 'Set Directory', None)
        self.addAction('File', 'Find and Replace', None)
        self.addAction('File', 'Relocate', None)
        self.addAction('File', 'Find Files', None)
        self.addAction('File', 'Open', None)
        self.addAction('File', 'Open Directory', None)

        self.addAction('Color Space', 'Auto', None)
        self.addAction('Color Space', 'Set Transfer Function', None)
        self.addAction('Color Space', 'Set RGB Primaries', None)

        self.addAction('Tiled', 'Generate TX', None)
        self.addAction('Tiled', 'Switch to Raw', None)
        self.addAction('Tiled', 'Switch to TX', None)

        self.addAction('Node', 'Set Parameters', None)
        self.addAction('Node', 'Convert', None)
        self.addAction('Node', 'Remove Selected', None)
        self.addAction('Node', 'Show Selected', None)
        self.addAction('Node', 'Select Dependent Objects', None)
