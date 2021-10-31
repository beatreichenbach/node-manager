from __future__ import absolute_import
import sys
from PySide2 import QtWidgets
from nodemanager import manager_dialog
from maya import mel, cmds
from .. import manager
from .. import setup
import logging
import os

def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    main_window = next(w for w in app.topLevelWidgets() if w.objectName() == 'MayaWindow')
    dialog = manager_dialog.ManagerDialog(main_window, dcc='maya')
    dialog.show()
    return main_window

class Manager(manager.Manager):
    display_name = ''
    plugin_name = ''
    settings_group = 'maya'
    settings_defaults = {
        }

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
