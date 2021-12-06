from __future__ import absolute_import

import logging
import os
import re
import shutil
import collections
try:
    from enum import Enum
except ImportError:
    from ..enum import Enum

from maya import cmds, mel, utils as maya_utils
from PySide2 import QtWidgets

from .. import processing
from . import maya
from .. import utils
from .. import manager
from .. import util_dialog


class Manager(maya.Manager):
    display_name = 'Image'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

        UPDATE_MODEL = manager.Action.UPDATE_MODEL
        IGNORE_UPDATE = manager.Action.IGNORE_UPDATE
        RELOAD_MODEL = manager.Action.RELOAD_MODEL

        # addAction(group, label, func, update=UPDATE_MODEL)
        self.addAction('File', 'Set Directory', set_directory)
        self.addAction('File', 'Find and Replace', find_and_replace)
        self.addAction('File', 'Relocate', relocate)
        self.addAction('File', 'Locate', locate)
        self.addAction('File', 'Open', open_file, IGNORE_UPDATE)
        self.addAction('File', 'Open Directory', open_directory, IGNORE_UPDATE)
        self.addAction('Parameters', 'Auto Color Space', auto_colorspace)
        self.addAction('Parameters', 'Auto Filter', auto_filter)
        self.addAction('Tiled', 'Generate Tiled', generate_tiled)
        self.addAction('Tiled', 'Switch to Raw', switch_raw)
        self.addAction('Tiled', 'Switch to Tiled', switch_tiled)
        self.addAction('Node', 'Convert', convert, RELOAD_MODEL)
        self.addAction('Node', 'Remove', remove, RELOAD_MODEL)
        self.addAction('Node', 'Graph Nodes', graph_nodes, IGNORE_UPDATE)
        self.addAction('Node', 'Select Dependent Objects', select_dependents, IGNORE_UPDATE)

        self.addFilter('name')
        self.addFilter('status')
        self.addFilter('colorSpace')
        self.addFilter('filter')
        self.addFilter('directory')
        self.addFilter('channels')

    def nodes(self, options={}):
        self.load_plugin()
        nodes = []
        maya_nodes = cmds.ls(type='aiImage')
        for maya_node in maya_nodes:
            node = Node(maya_node)
            nodes.append(node)
        return nodes


class Node(maya.Node):
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
        filepath = self.real_filepath

        if not filepath:
            return FileStatus.NOT_SET
        elif os.path.isfile(filepath):
            return FileStatus.EXISTS
        else:
            return FileStatus.NOT_FOUND

    @property
    def file_size(self):
        return utils.FileSize.from_file(self.real_filepath)

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
        file_pattern = re.sub(tags, r'\\d+', self.filename)
        file_pattern = re.sub(r'\.', r'\\.', file_pattern)
        return re.compile(file_pattern)

    @property
    def real_filepath(self):
        return next(self.file_sequence, '')


def open_file(nodes):
    node = nodes[0]
    filepath = node.filepath
    if node.is_file_sequence:
        filepath = node.real_filepath
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
    if cls == 'file':
        replace_node = cmds.shadingNode('file', asUtility=True)
        cmds.setAttr('{}.fileTextureName'.format(replace_node), node.filepath, type='string')
        cmds.setAttr('{}.aiFilter'.format(replace_node), node.filter.value)
        if node.colorSpace in ['sRGB', 'Raw']:
            cmds.setAttr('{}.colorSpace'.format(replace_node), node.colorSpace, type='string')

        cmds.setAttr('{}.colorGain'.format(replace_node), *node.multiply.getRgbF(), type='double3')
        cmds.setAttr('{}.colorOffset'.format(replace_node), *node.offset.getRgbF(), type='double3')

        name = node.name
        cmds.delete(node.node)
        cmds.rename(replace_node, name)


def switch_raw(nodes):
    extensions = ['jpg', 'png', 'tif', 'tiff', 'exr']
    for node in nodes:
        raw_dir = re.sub(r'[\\/]tiled[\\/]', 'raw', node.directory)
        base, ext = os.path.splitext(node.filename)

        for extension in extensions:
            raw_filename = '{}.{}'.format(base, extension)

            tags = '|'.join(node._file_sequence_tags)
            file_pattern = re.sub(tags, r'\\d+', raw_filename)
            file_pattern = re.sub(r'\.', r'\\.', file_pattern)
            for filename in os.listdir(raw_dir):
                if re.match(file_pattern, filename):
                    node.filename = raw_filename
                    node.directory = raw_dir
                    break
            else:
                continue

            break


def switch_tiled(nodes):
    for node in nodes:
        tiled_dir = re.sub(r'[\\/]raw[\\/]', 'tiled', node.directory)
        base, ext = os.path.splitext(node.filename)

        tiled_filename = '{}.tx'.format(base)

        tags = '|'.join(node._file_sequence_tags)
        file_pattern = re.sub(tags, r'\\d+', tiled_filename)
        file_pattern = re.sub(r'\.', r'\\.', file_pattern)

        for filename in os.listdir(tiled_dir):
            if re.match(file_pattern, filename):
                node.filename = tiled_filename
                node.directory = tiled_dir
                break


class TiledRunnable(processing.ProcessingRunnable):
    processing = []

    def __init__(self, item):
        super(TiledRunnable, self).__init__(item)

        self.node = ProcessingNode(self.node)

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
            # py 2.7
            try:
                raise FileNotFoundError(self.node.filepath)
            except NameError:
                raise OSError('File not found: {}'.format(self.node.filepath))

        for input_path in input_paths:
            if not self.running:
                return

            filename = os.path.basename(input_path)
            name, ext = os.path.splitext(filename)

            if ext == 'tx':
                raise Exception('File already has extension: {}'.format(ext))

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

            # py 2.7
            self.logger.info(str(' '.join(command_args)))

            # is the file being process by another runnable?
            if input_path in TiledRunnable.processing:
                self.logger.info('Skipping... File already being processed by a different thread.')
                continue
            TiledRunnable.processing.append(input_path)

            if self.popen(command_args):
                # any return code other than None means there was an error.
                return
        name, ext = os.path.splitext(self.node.filename)
        outout_filename = '{}.tx'.format(name)

        self.node.directory = output_dir
        self.node.filename = outout_filename

        return True

    def display_text(self):
        return self.node.filepath

    @staticmethod
    def reset():
        TiledRunnable.processing = []

    def get_attr(self, name):
        return maya_utils.executeInMainThreadWithResult(lambda: getattr(self.node, name))


class LocateRunnable(processing.ProcessingRunnable):
    cache = []

    def process(self):
        if not self.node.filename:
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
        target_dir = self.node.directory
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


class ProcessingNode(object):
    def __init__(self, node):
        self.node = node

        attrs = [
            'filepath',
            'filename',
            'directory',
            'file_sequence',
            'is_file_sequence',
            'real_filepath'
        ]
        for name in attrs:
            value = getattr(self.node, name)
            if isinstance(value, collections.Iterator):
                value = list(value)
            object.__setattr__(self, name, value)

    # def __getattribute__(self, name):
    #     if name == 'node':
    #         return object.__getattribute__(self, name)
    #     else:
    #         logging.debug(name)
    #         maya_utils.executeInMainThreadWithResult(lambda: getattr(self.node, name))
    #         return 'asd'
    #         result = maya_utils.executeInMainThreadWithResult(lambda: getattr(self.node, name))
    #         return result

    def __setattr__(self, name, value):
        if name == 'node':
            object.__setattr__(self, name, value)
        else:
            maya_utils.executeDeferred(lambda: setattr(self.node, name, value))
