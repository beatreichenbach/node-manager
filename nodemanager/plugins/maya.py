from __future__ import absolute_import
import sys
import logging
import os
import collections
from PySide2 import QtWidgets, QtGui
from maya import mel, cmds, utils as maya_utils

try:
    from enum import Enum
except ImportError:
    # py 2.7
    from ..enum import Enum

from nodemanager import manager_dialog
from .. import manager
from .. import setup
from .. import processing
from .. import util_dialog

# py 2.7
if sys.version_info[0] >= 3:
    unicode = str


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    main_window = next(w for w in app.topLevelWidgets() if w.objectName() == 'MayaWindow')
    dialog = manager_dialog.ManagerDialog(main_window, dcc='maya')
    dialog.show()
    return main_window


UPDATE_MODEL = manager.Action.UPDATE_MODEL
IGNORE_UPDATE = manager.Action.IGNORE_UPDATE
RELOAD_MODEL = manager.Action.RELOAD_MODEL


class Node(manager.Node):
    def __getattr__(self, name):
        return self._get_node_attr(name)

    def __setattr__(self, name, value):
        if name not in dir(self):
            self._set_node_attr(name, value)
        else:
            object.__setattr__(self, name, value)

    def _attr(self, name):
        return '{}.{}'.format(self.node, name)

    def _has_node_attr(self, name):
        return cmds.attributeQuery(name, node=self.node, exists=True)

    def _get_node_attr(self, name):
        attr = self._attr(name)
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

    def _set_node_attr(self, name, value):
        attr = self._attr(name)
        try:
            # py 2.7
            if isinstance(value, str) or isinstance(value, unicode):
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


class Manager(manager.Manager):
    plugin_name = 'mtoa.mll'

    def __init__(self, *args):
        super(Manager, self).__init__(*args)

        self.addAction('Node', 'Select', select, IGNORE_UPDATE)
        self.addAction('Node', 'Remove', remove, RELOAD_MODEL)
        self.addAction('Node', 'Graph Nodes', graph_nodes, IGNORE_UPDATE)

    def load_plugin(self):
        if not self.plugin_name:
            raise RuntimeError
        if not cmds.pluginInfo(self.plugin_name, query=True, loaded=True):
            cmds.loadPlugin(self.plugin_name)

    def nodes(self, options={}, node_cls=Node, node_type=''):
        self.load_plugin()

        if options.get('selection'):
            maya_nodes = cmds.ls(selection=True, type=node_type)

            try:
                shapes = cmds.ls(shapes=True, selection=True, dagObjects=True)
                shading_engines = cmds.listConnections(shapes, type='shadingEngine')
                history = cmds.listHistory(shading_engines)
                relative_nodes = cmds.ls(history, type=node_type)
                maya_nodes.extend([node for node in relative_nodes if node not in maya_nodes])
            except RuntimeError:
                pass

        else:
            maya_nodes = cmds.ls(type=node_type)

        nodes = [node_cls(maya_node) for maya_node in maya_nodes]

        return nodes


class Installer(setup.Installer):
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


class LocateRunnable(manager.LocateRunnable):
    def __init__(self, item):
        super(LocateRunnable, self).__init__(item)

        self.node = ProcessingNode(self.node)


class RelocateRunnable(manager.RelocateRunnable):
    def __init__(self, item):
        super(RelocateRunnable, self).__init__(item)

        self.node = ProcessingNode(self.node)


class TiledRunnable(manager.TiledRunnable):
    def __init__(self, item):
        super(TiledRunnable, self).__init__(item)

        self.node = ProcessingNode(self.node)


class ProcessingNode(object):
    def __init__(self, node):
        self._node = node

        # freeze attributes to be used in thread
        for attr in dir(self._node):
            if not attr.startswith('_'):
                value = getattr(self._node, attr)
                if isinstance(value, collections.Iterator):
                    value = list(value)
                object.__setattr__(self, attr, value)

    def __setattr__(self, name, value):
        if name == '_node':
            object.__setattr__(self, name, value)
        else:
            maya_utils.executeDeferred(lambda: setattr(self._node, name, value))


def graph_nodes(nodes):
    editor = mel.eval('getHypershadeNodeEditor()')
    if editor:
        for node in nodes:
            cmds.nodeEditor(editor, edit=True, frameAll=True, addNode=node.node)


def remove(nodes):
    # todo: keep connections?
    for node in nodes:
        cmds.delete(node.node)


def select(nodes):
    maya_nodes = [node.node for node in nodes]
    cmds.select(maya_nodes, replace=True)


def generate_tiled(nodes):
    runnable_cls = TiledRunnable
    processing.ProcessingDialog.process(nodes, runnable_cls)


def relocate(nodes):
    path = nodes[0].directory
    values = util_dialog.RelocateDialog.get_values(path)

    if not values:
        return

    runnable = RelocateRunnable
    runnable.kwargs = values

    # limit threads to preserve file io
    processing.ProcessingDialog.process(nodes, runnable, threads=2)


def locate(nodes):
    path = nodes[0].directory
    values = util_dialog.FindFilesDialog.get_values(path)

    if not values or not os.path.isdir(values['path']):
        return

    runnable = LocateRunnable
    runnable.kwargs = values

    # limit threads to preserve file io
    processing.ProcessingDialog.process(nodes, runnable, threads=2)
