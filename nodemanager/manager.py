import os
import re
import glob
import logging
import shutil

from PySide2 import QtWidgets, QtCore, QtGui

class NodesModel(QtGui.QStandardItemModel):
    def __init__(self, parent=None):
        super(NodesModel, self).__init__(parent)


    def populate(self):
        self.setHorizontalHeaderLabels(['Name', 'Path', 'Colorspace'])

        foods = [
            'Cookie dough',
            'Hummus',
            'Spaghetti',
            'Dal makhani',
            'Chocolate whipped cream'
        ]

        for food in foods:
            item = QtGui.QStandardItem(food)
            self.appendRow(item)

        logging.debug(self.horizontalHeaderItem(1).text())


class Manager(object):
    display_name = ''
    plugin_name = ''

    settings_group = ''
    settings_defaults = {
        }
    actions = []

    def __init__(self):
        self.settings = utils.Settings()
        self.init_settings()

    def init_settings(self):
        self.settings.beginGroup(self.settings_group)
        for setting, value in self.settings_defaults.items():
            if not self.settings.contains(setting):
                self.settings.setValue(setting, value)
        self.settings.endGroup()

    @classmethod
    def from_plugin(cls, plugin):
        cls = plugin_utils.plugin_class(cls, plugin)
        return cls()

    def load_plugin(self):
        pass

    def addAction(self, group, name, func):
        actions.append([group, name, func])
