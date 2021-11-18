from __future__ import absolute_import
import sys
import logging
import os
from enum import Enum

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

    def load_plugin(self):
        if not self.plugin_name:
            raise RuntimeError
        if not (cmds.pluginInfo(self.plugin_name, query=True, loaded=True)):
            cmds.loadPlugin(self.plugin_name)


class Node(manager.Node):
    def __getattr__(self, name):
        return self.get_node_attr(name)

    def __setattr__(self, name, value):
        if name not in dir(self):
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
        except ValueError:
            raise AttributeError('No attribute matches name: {}'.format(attr))

        if attr_type == 'float3':
            value = QtGui.QColor.fromRgbF(*value[0])
        elif attr_type == 'double3':
            value = list(*value[0])
        elif attr_type == 'enum':
            enum_strings = cmds.attributeQuery(name, node=self.node, listEnum=True)
            names = enum_strings[0].split(':')
            class_ = Enum(name.title(), names, start=0)
            value = class_(value)
        return value

    def set_node_attr(self, name, value):
        attr = self.attr(name)
        try:
            if isinstance(value, str):
                value = value.replace('\\', '/')
                cmds.setAttr(attr, value, type='string')
            elif isinstance(value, Enum):
                cmds.setAttr(attr, value.value)
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
    def exists(self):
        return cmds.objExists(self.node)


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
