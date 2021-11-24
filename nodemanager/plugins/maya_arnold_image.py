from __future__ import absolute_import

import os
import re
import logging
import glob
import time
import shutil

from enum import Enum

from maya import cmds, mel
from PySide2 import QtWidgets, QtGui, QtCore

from .. import processing
from . import maya
from .. import utils
from .. import manager
from .. import util_dialog


class Manager(maya.Manager):
    display_name = 'Image'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

        self.addAction('File', 'Set Directory', set_directory)
        self.addAction('File', 'Find and Replace', find_and_replace)
        self.addAction('File', 'Relocate', relocate)
        self.addAction('File', 'Find Files', find_files)
        self.addAction('File', 'Open', open_file)
        self.addAction('File', 'Open Directory', open_directory)
        self.addAction('Parameters', 'Auto Color Space', auto_colorspace)
        self.addAction('Parameters', 'Auto Filter', auto_filter)
        self.addAction('Tiled', 'Generate TX', generate_tx)
        self.addAction('Tiled', 'Switch to Raw', None)
        self.addAction('Tiled', 'Switch to TX', None)
        self.addAction('Node', 'Convert', None)
        self.addAction('Node', 'Remove', remove)
        self.addAction('Node', 'Graph Nodes', graph_nodes)
        self.addAction('Node', 'Select Dependent Objects', select_dependents)

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


class Node(maya.Node):
    '''
    since the node is using deferred loading in the table to get certain contents,
    all attributes should stay live?
    alternatively we store them on the node object and only refresh when the path attribute is being
    set on the pytthon object. it should probably be consistent but might not make sense to do so.
    in cations such as auto color space, we should cache that though.
    '''

    _file_size = None
    _file_sequence_tags = ['<udim>', '<frameNum>', '<uvtile>']

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
        return os.path.isfile(self.filepath)
        '''
        NO_PATH (really that's just missing file...)
        MISSING_FILE
        OK
        '''
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

    @property
    def is_file_sequence(self):
        is_file_sequence = any([tag in self.filename for tag in self._file_sequence_tags])
        return is_file_sequence


def open_file(nodes):
    node = nodes[-1]
    filepath = node.filepath
    if node.is_file_sequence:
        if not os.path.isdir(node.directory):
            return

        # todo: move into function
        tags = '|'.join(node._file_sequence_tags)
        file_pattern = re.sub(tags, r'\d+', re.escape(node.filename))
        regex = re.compile(file_pattern)

        for file in os.listdir(node.directory):
            if regex.search(file):
                filepath = os.path.join(node.directory, file)
                break

    if not os.path.isfile(filepath):
        return

    os.startfile(filepath)


def open_directory(nodes):
    if nodes:
        os.startfile(nodes[-1].directory)


def set_directory(nodes):
    path = nodes[-1].directory
    values = util_dialog.SetDirectoryDialog.get_values(path)

    if not values:
        return
    for node in nodes:
        node.directory = values['path']


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


def graph_nodes(nodes):
    cmds.select(nodes, replace=True)

    editor = mel.eval('getHypershadeNodeEditor()')
    if editor:
        for node in nodes:
            cmds.nodeEditor(editor, edit=True, frameAll=True, addNode=node)


def remove(nodes):
    for node in nodes:
        if node.exists:
            cmds.delete(node)


def relocate(nodes):
    # todo: add parent
    path = nodes[-1].directory
    values = util_dialog.RelocateDialog.get_values(path)

    for node in nodes:
        filepaths = []

        if node.is_file_sequence:
            tags = '|'.join(node._file_sequence_tags)
            file_pattern = re.sub(tags, r'\d+', re.escape(node.filename))
            regex = re.compile(file_pattern)

            for file in os.listdir(node.directory):
                if regex.search(file):
                    filepaths.append(os.path.join(node.directory, file))

        else:
            filepaths.append(node.filepath)

        for filepath in filepaths:
            if os.path.isfile(filepath):
                if values['copy']:
                    shutil.copy(node.filepath, path)
                else:
                    shutil.move(node.filepath, path)

        if values['update']:
            node.directory = path


def find_files(nodes):
    path = nodes[-1].directory
    values = util_dialog.FindFilesDialog.get_values(path)

    if not values or not os.path.isdir(values['path']):
        return

    for node in nodes:
        # todo: replace with actual status constant
        if node.status or not node.filename:
            continue

        file_pattern = re.escape(node.filename)

        # todo: move into function
        if node.is_file_sequence:
            tags = '|'.join(node._file_sequence_tags)
            file_pattern = re.sub(tags, r'\d+', re.escape(node.filename))

        logging.debug(file_pattern)
        file_sequence_regex = re.compile(file_pattern)

        # todo: cache directories with success
        for root, dirs, files in os.walk(values['path']):
            for file in files:
                filepath = os.path.join(root, file)
                if file_sequence_regex.search(filepath):
                    break
            else:
                continue

            break
        else:
            continue

        logging.debug(filepath)
        node.filepath = filepath



def find_and_replace(nodes):
    path = nodes[-1].directory
    values = util_dialog.FindAndReplaceDialog.get_values(path)

    if not values:
        return

    if values['regex']:
        pattern = values['find']
    else:
        pattern = re.escape(values['find'])

    flags = 0
    if values['ignorecase']:
        flags = flags | re.IGNORECASE

    regex = re.compile(pattern, flags)

    for node in nodes:
        filepath = regex.sub(values['replace'], node.filepath)
        node.filepath = filepath


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


def generate_tx(nodes, parent):
    runnable = TXRunnable

    processing.ProcessingDialog.process(nodes, runnable)


class TXRunnable(processing.ProcessingRunnable):
    def process(self):
        time.sleep(4)
        self.log('Success Bitch')

    def display_text(self):
        return self.node.filepath
