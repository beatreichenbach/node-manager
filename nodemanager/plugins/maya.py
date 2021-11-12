from __future__ import absolute_import
import sys
import logging
import os

from PySide2 import QtWidgets, QtGui
from maya import mel, cmds

from nodemanager import manager_dialog
from .. import manager
from .. import setup
from .. import utils


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    main_window = next(w for w in app.topLevelWidgets() if w.objectName() == 'MayaWindow')
    dialog = manager_dialog.ManagerDialog(main_window, dcc='maya')
    dialog.show()
    return main_window


class Manager(manager.Manager):
    plugin_name = 'mtoa.mll'
    settings_group = 'maya'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

    def load_plugin(self):
        if not self.plugin_name:
            raise RuntimeError
        if not (cmds.pluginInfo(self.plugin_name, query=True, loaded=True)):
            cmds.loadPlugin(self.plugin_name)


class Installer(setup.Installer):
    # def __init__(self):
    #     super(Installer, self).__init__()

    def create_button(self):
        shelf_name = 'Plugins'
        label = 'nodemanager'
        image_path = 'textureEditor.png'
        command = (
            'from nodemanager.plugins.maya import run\n'
            'main_window = run()')

        top_level_shelf = mel.eval('$gShelfTopLevel = $gShelfTopLevel;')

        if cmds.shelfLayout(shelf_name, exists=True):
            buttons = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
            for button in buttons:
                if cmds.shelfButton(button, label=True, query=True) == label:
                    cmds.deleteUI(button)
        else:
            mel.eval('addNewShelfTab "{}";'.format(shelf_name))

        cmds.shelfButton(label=label, command=command, parent=shelf_name, image=image_path)
        logging.info('Created button "{}"" on shelf "{}".'.format(label, shelf_name))
        return cmds.saveAllShelves(top_level_shelf)

    def install_package(self):
        maya_app_path = os.path.normpath(os.getenv('MAYA_APP_DIR'))
        if maya_app_path is None:
            if sys.platform.startswith('win32'):
                maya_app_path = os.path.join(os.path.expanduser("~"), 'Documents', 'Maya')
            elif sys.platform.startswith('linux'):
                maya_app_path = os.path.join(os.path.expanduser("~"), 'Maya')
            elif sys.platform.startswith('darwin'):
                maya_app_path = os.path.join(os.path.expanduser("~"), 'Library', 'Preferences', 'Autodesk', 'Maya')

        if not maya_app_path:
            logging.error('Could not find maya scripts directory.')
            return False

        scripts_path = os.path.join(maya_app_path, 'scripts')
        if not os.path.isdir(scripts_path):
            os.makedirs(scripts_path)

        if not self.copy_package(scripts_path):
            return False

        try:
            self.create_button()
        except ModuleNotFoundError:
            logging.error(
                'Could not install maya script button. '
                'Make sure to run the setup from Maya.')
            return False

        logging.info('Installation successfull.')
        return True


class Node(manager.Node):
    _file_size = None

    def __init__(self, node):
        self.node = node

        self.locked_attributes.extend([
            'status',
            'file_size',
            'channels'
            ])

    def __repr__(self):
        return 'Node({})'.format(self.name)

    def __str__(self):
        return self.name

    def __getattr__(self, name):
        return self.get_node_attr(name)

    def __setattr__(self, name, value):
        if name not in dir(self):
            self.set_node_attr(name, value)
        else:
            object.__setattr__(self, name, value)

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
            'channels'
        ]

        return attrs

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
        connections = []
        out_connections = cmds.listConnections(
                    self.node, destination=True, source=False, connections=True, plugs=True)

        for i in range(0, len(out_connections), 2):
            source = out_connections[i]
            destination = out_connections[i + 1]

            destination_node = destination.split('.')[0]
            if not cmds.objExists(destination_node):
                continue
            cls = cmds.nodeType(destination_node)
            ignore_classes = [
                'shadingEngine',
                'defaultShaderList',
                'materialInfo',
                'nodeGraphEditorInfo']
            if cls in ignore_classes:
                continue

            valid_attr = source.split('.')[-1] not in ('message', 'partition')
            if valid_attr:
                connections.append(destination.split('.')[-1])

        return ', '.join(set(connections))
