from __future__ import absolute_import

import os
import re
import logging
import glob
import time
import shutil
import subprocess
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

        # addAction(group, label, func, update_model=True)
        self.addAction('File', 'Set Directory', set_directory)
        self.addAction('File', 'Find and Replace', find_and_replace)
        self.addAction('File', 'Relocate', relocate)
        self.addAction('File', 'Locate', locate)
        self.addAction('File', 'Open', open_file, False)
        self.addAction('File', 'Open Directory', open_directory, False)
        self.addAction('Parameters', 'Auto Color Space', auto_colorspace)
        self.addAction('Parameters', 'Auto Filter', auto_filter)
        self.addAction('Tiled', 'Generate Tiled', generate_tiled)
        self.addAction('Tiled', 'Switch to Raw', switch_raw)
        self.addAction('Tiled', 'Switch to Tiled', switch_tiled)
        self.addAction('Node', 'Convert', convert)
        self.addAction('Node', 'Remove', remove)
        self.addAction('Node', 'Graph Nodes', graph_nodes, False)
        self.addAction('Node', 'Select Dependent Objects', select_dependents, False)

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
        filepath = next(self.file_sequence, '')

        if not filepath:
            return FileStatus.NOT_SET
        elif os.path.isfile(filepath):
            return FileStatus.EXISTS
        else:
            return FileStatus.NOT_FOUND

    @property
    def file_size(self):
        if self._file_size is None:
            self._file_size = utils.FileSize.from_file(next(self.file_sequence, ''))

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

    @property
    def file_sequence(self):
        if self.is_file_sequence:
            regex = self.file_sequence_regex

            for filename in os.listdir(self.directory):
                if regex.search(filename):
                    yield os.path.join(self.directory, filename)
        else:
            yield self.filepath

    @property
    def file_sequence_regex(self):
        tags = '|'.join(self._file_sequence_tags)
        file_pattern = re.sub(tags, r'\\d+', re.escape(self.filename))
        return re.compile(file_pattern)


def open_file(nodes):
    node = nodes[0]
    filepath = node.filepath
    if node.is_file_sequence:
        filepath = next(node.file_sequence)
    if not os.path.isfile(filepath):
        return

    os.startfile(filepath)


def open_directory(nodes):
    if nodes:
        os.startfile(nodes[0].directory)


def set_directory(nodes):
    path = nodes[0].directory
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
    path = nodes[0].directory
    values = util_dialog.RelocateDialog.get_values(path)

    if not values or not os.path.isdir(values['path']):
        return

    runnable = RelocateRunnable
    runnable.kwargs = values

    processing.ProcessingDialog.process(nodes, runnable)


def locate(nodes):
    path = nodes[0].directory
    values = util_dialog.FindFilesDialog.get_values(path)

    if not values or not os.path.isdir(values['path']):
        return

    runnable = LocateRunnable
    runnable.kwargs = values

    processing.ProcessingDialog.process(nodes, runnable)


def find_and_replace(nodes):
    path = nodes[0].directory
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


def generate_tiled(nodes):
    runnable_cls = TiledRunnable
    processing.ProcessingDialog.process(nodes, runnable_cls)


def convert(nodes):
    classes = ['file']
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
    aiimage_file = {
        'path': 'filename'
    }
    if cls == 'file':
        logging.debug('file')


def switch_raw(nodes):
    extensions = ['jpg', 'png', 'tif', 'tiff', 'exr']
    for node in nodes:
        filepath = next(node.file_sequence, '')

        if not filepath:
            continue

        base, ext = os.path.splitext(os.path.basename(filepath))
        raw_dir = re.sub(r'[\\/]tiled[\\/]', 'raw', node.directory)

        for extension in extensions:
            for filename in os.listdir(raw_dir):
                if filename == '{}.{}'.format(base, extension):
                    break
            else:
                continue

            base, ext = os.path.splitext(node.filename)
            raw_filename = '{}.{}'.format(base, extension)
            node.filename = raw_filename
            node.directory = raw_dir
            break


def switch_tiled(nodes):
    for node in nodes:
        filepath = next(node.file_sequence, '')

        if not filepath:
            continue

        base, ext = os.path.splitext(os.path.basename(filepath))
        tiled_dir = re.sub(r'[\\/]raw[\\/]', 'tiled', node.directory)
        tiled_filepath = os.path.join(tiled_dir, '{}.tx'.format(base))
        if os.path.isfile(tiled_filepath):
            base, ext = os.path.splitext(node.filename)
            tiled_filename = '{}.tx'.format(base)
            node.filename = tiled_filename
            node.directory = tiled_dir


class TiledRunnable(processing.ProcessingRunnable):

    def process(self):
        maketx_path = r'C:\Program Files\Autodesk\Arnold\maya2022\bin\maketx.exe'

        output_dir = re.sub(r'[\\/]raw[\\/]', 'tiled', self.node.directory)

        input_paths = []
        if self.node.is_file_sequence:
            input_paths.extend(self.node.file_sequence)
        else:
            input_paths.append(self.node.filepath)

        input_paths = list(filter(os.path.isfile, input_paths))

        if not input_paths:
            raise FileNotFoundError

        for input_path in input_paths:
            if not self.running:
                return

            filename = os.path.basename(input_path)
            name, ext = os.path.splitext(filename)
            output_filename = '{}.tx'.format(name)
            output_path = os.path.join(output_dir, output_filename)

            input_path = os.path.abspath(input_path)
            output_path = os.path.abspath(output_path)

            # seems faster than maketx internal -u argument
            if (os.path.isfile(input_path) and os.path.isfile(output_path) and
                    os.path.getmtime(input_path) <= os.path.getmtime(output_path)):
                continue

            command_args = [
                maketx_path,
                '-v',
                # '-u',
                '--oiio',
                '--checknan',
                '--filter',  'lanczos3',
                input_path,
                '-o',  output_path
                ]

            self.logger.info(' '.join(command_args))

            if self.popen(command_args):
                return
        self.node.directory = output_dir
        name, ext = os.path.splitext(self.node.filename)
        self.node.filename = '{}.tx'.format(name)

        return True

    def display_text(self):
        return self.node.filepath


class LocateRunnable(processing.ProcessingRunnable):
    cache = []

    def process(self):
        # todo: replace with actual status constant
        if self.node.status or not self.node.filename:
            return True

        self.logger.info('Searching recursivly: {}'.format(self.kwargs['path']))

        regex = self.node.file_sequence_regex
        self.logger.info('Regex pattern: {}'.format(regex))

        # lock contents of cache
        cache = list(self.cache)
        for root in cache:
            for file in os.listdir(root):
                if not self.running:
                    return
                filepath = os.path.join(root, file)
                if regex.search(filepath):
                    self.set_directory(root)
                    return True

        for root, dirs, files in os.walk(self.kwargs['path']):
            if root in cache:
                continue
            for file in files:
                if not self.running:
                    return
                filepath = os.path.join(root, file)
                if regex.search(filepath):
                    # still check since other instances could have added it
                    if root not in self.cache:
                        LocateRunnable.cache.append(root)
                    self.set_directory(root)
                    return True

        raise FileNotFoundError

    def set_directory(self, root):
        self.logger.info('File found in: {}'.format(root))
        self.node.directory = root

    def display_text(self):
        return self.node.filename


class RelocateRunnable(processing.ProcessingRunnable):
    def process(self):
        for source_path in self.node.file_sequence:
            if not self.running:
                return
            target_path = os.path.join(self.kwargs['path'], os.path.basename(source_path))
            target_dir = os.path.dirname(target_path)
            if not os.path.exists(target_dir):
                self.logger.info('Directory created: {}'.format(target_dir))
                os.makedirs(target_dir)

            if os.path.isfile(source_path):
                if (os.path.isfile(target_path) and
                        os.path.getmtime(source_path) <= os.path.getmtime(target_path)):
                    self.logger.info('Target file already exists: {}'.format(target_path))
                    continue

                if self.kwargs['copy']:
                    self.logger.info('File copied: {}'.format(target_path))
                    shutil.copy(source_path, target_dir)
                else:
                    self.logger.info('File moved: {}'.format(target_path))
                    shutil.move(source_path, target_dir)

        if not self.kwargs['ignore_update']:
            self.node.directory = target_dir
        return True

    def display_text(self):
        return self.node.filepath


class FileStatus(Enum):
    EXISTS = 1
    NOT_FOUND = 2
    NOT_SET = 3
