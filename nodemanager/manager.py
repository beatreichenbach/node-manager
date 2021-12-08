import logging
import os
import re
import shutil
from collections import OrderedDict
from enum import Enum

from PySide2 import QtCore

from . import plugin_utils
from . import utils
from . import processing
from . import util_dialog


class FileStatus(Enum):
    EXISTS = 1
    NOT_FOUND = 2
    NOT_SET = 3


class Action(QtCore.QObject):
    UPDATE_MODEL = 0
    IGNORE_UPDATE = 1
    RELOAD_MODEL = 2

    triggered = QtCore.Signal(list, int)

    def __init__(self, label, func, update):
        super(Action, self).__init__()
        self.label = label
        self.func = func
        self.update = update

    def __repr__(self):
        return 'Action({})'.format(self.label)

    def __str__(self):
        return self.label

    def trigger(self, nodes):
        logging.debug('trigger')
        # todo: try except would be faster
        nodes = [node for node in nodes if node.exists]
        if not nodes:
            return
        self.func(nodes)
        logging.debug([self.label, self.update, self.func])
        self.triggered.emit(nodes, self.update)


class Manager(object):
    display_name = 'General'
    plugin_name = ''

    def __init__(self):
        self.actions = OrderedDict()
        self.filters = []

    @classmethod
    def from_plugin(cls, plugin):
        cls = plugin_utils.plugin_class(cls, plugin)
        return cls()

    def load_plugin(self):
        pass

    def addAction(self, group, label, func, update=0):
        # update=0 will use the default defined in Action class
        action = Action(label, func, update)

        actions = self.actions.get(group, [])
        if action not in actions:
            actions.append(action)
        self.actions[group] = actions

    def runAction(self, func, update_model):
        nodes = [node for node in self.selected_nodes() if node.exists]
        if not nodes:
            return
        func(nodes)
        if update_model:
            self.model.update()

    def addFilter(self, attribute):
        if attribute not in self.filters:
            self.filters.append(attribute)

    def nodes(self, options={}):
        return []


class Node(object):
    node = None
    locked_attributes = []

    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return 'Node({})'.format(self.name)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return str(self.node)


class FileNode(Node):
    _file_sequence_tags = ['<udim>', '<frameNum>', '<uvtile>']

    def __init__(self, node):
        super(FileNode, self).__init__(node)

        self.locked_attributes.extend(['status', 'file_size'])

    @property
    def filepath(self):
        return ''

    @filepath.setter
    def filepath(self, value):
        pass

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
        # to match escaped filename escape the escaped tags
        tags = '|'.join(map(re.escape, map(re.escape, self._file_sequence_tags)))
        file_pattern = re.sub(tags, r'\d+', re.escape(self.filename), re.IGNORECASE)
        regex = re.compile(file_pattern)
        return regex

    @property
    def real_filepath(self):
        return next(self.file_sequence, '')

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


class TiledRunnable(processing.ProcessingRunnable):
    processing = []

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
                self.logger.info('Skipping... File already exists.')
                continue

            command_args = [
                maketx_path,
                '-v',
                '--oiio',
                '--checknan',
                '--filter',  'lanczos3',
                input_path,
                '-o',  output_path
                ]

            command = ' '.join(command_args)
            # py 2.7
            command = str(command)

            self.logger.info(command)

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


def generate_tiled(nodes):
    runnable_cls = TiledRunnable
    processing.ProcessingDialog.process(nodes, runnable_cls)


def switch_raw(nodes):
    extensions = ['jpg', 'png', 'tif', 'tiff', 'exr']
    for node in nodes:
        raw_dir = re.sub(r'[\\/]tiled[\\/]', 'raw', node.directory)

        pattern = node.file_sequence_regex.pattern
        base, ext = os.path.splitext(pattern)
        for extension in extensions:
            file_pattern = '{}.{}'.format(base, extension)

            for filename in os.listdir(raw_dir):
                if re.match(file_pattern, filename):
                    base, ext = os.path.splitext(node.filename)
                    raw_filename = '{}.{}'.format(base, extension)
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

        pattern = node.file_sequence_regex.pattern
        base, ext = os.path.splitext(pattern)

        file_pattern = '{}.tx'.format(base)

        for filename in os.listdir(tiled_dir):
            if re.match(file_pattern, filename):
                node.filename = tiled_filename
                node.directory = tiled_dir
                break
