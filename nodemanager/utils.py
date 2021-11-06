import os
import logging
import json
from PySide2 import QtWidgets, QtCore, QtGui
import sys
import re


def join_url(url, *urls):
    urls = list(urls)
    urls.insert(0, url)
    return '/'.join([s.strip('/') for s in urls])


def sorted_dict(dict):
    return sorted(dict, key=lambda i: i[0].replace(' ', '').lower())


def to_dict(obj):
    return json.loads(
        json.dumps(obj, default=lambda o: getattr(o, '__dict__', str(o)))
    )


def unload_modules():
    for module in list(sys.modules.values()):
        if module and module.__name__.startswith(__package__):
            logging.debug('Unloading module: {}'.format(module.__name__))
            try:
                del sys.modules[module.__name__]
            except KeyError:
                pass


class Settings(QtCore.QSettings):
    def __init__(self):
        self.settings_path = os.path.dirname(__file__)

        if not os.access(self.settings_path, os.W_OK):
            home_path = os.path.join(os.path.expanduser("~"), '.{}'.format(__package__))
            self.settings_path = home_path

        settings_file_path = os.path.join(self.settings_path, 'settings.ini')
        super(Settings, self).__init__(settings_file_path, QtCore.QSettings.IniFormat)

        self.init_defaults()

    def init_defaults(self):
        default_values = {
        }
        for key, value in default_values.items():
            if key not in self.childKeys():
                self.setValue(key, value)

    def bool(self, key):
        value = self.value(key, False)
        if isinstance(value, bool):
            return value
        else:
            if isinstance(value, str):
                return value.lower() == 'true'
            else:
                return bool(value)

    def list(self, key):
        value = self.value(key, [])
        # py2.7
        try:
            if isinstance(value, basestring):
                value = [value, ]
            value = [int(i) if isinstance(i, basestring) and i.isdigit() else i for i in value]
        except NameError:
            if isinstance(value, str):
                value = [value, ]
            value = [int(i) if isinstance(i, str) and i.isdigit() else i for i in value]

        return value

    def clear(self):
        super(Settings, self).clear()
        self.init_defaults()


class NoSelectionException(Exception):
    message = 'Nothing selected.'


class NotFoundException(Exception):
    message = 'Not found.'


class Enum(object):
    def __init__(self, enums=[], current=None):
        self._enums = {}
        self._current = None
        self.enums = enums
        self.current = current

    def __repr__(self):
        return 'Enum({})'.format(repr({'current': self.current, 'enums': self._enums}))

    def __str__(self):
        return self.enums[self.current]

    def __int__(self):
        return int(self.current)

    def __lt__(self, other):
        return self.current < other.current

    def __le__(self, other):
        return self.current <= other.current

    def __gt__(self, other):
        return self.current > other.current

    def __ge__(self, other):
        return self.current >= other.current

    def __eq__(self, other):
        return self._enums == other._enums and self.current == other.current

    def __ne__(self, other):
        return self._enums != other._enums or self.current != other.current

    @property
    def enums(self):
        return self._enums

    @enums.setter
    def enums(self, value):
        if isinstance(value, list):
            self._enums = {i: enum for i, enum in enumerate(value)}
        elif isinstance(value, dict):
            self._enums = value
        else:
            raise TypeError('Expected list or dict, got {} instead.'.format(type(value)))

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, value):
        if value is None:
            return
        if isinstance(value, int):
            self._current = value
        elif value in self._enums.values():
            self._current = list(self._enums.values()).index(value)


class FileSize(int):
    factors = {
        'KB': 1<<10,
        'MB': 1<<20,
        'GB': 1<<30,
        'TB': 1<<40
        }

    unit = 'KB'

    def __init__(self, bytes=0):
        self.size = bytes

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        text = '{:,.0f} {}'.format(self.size / (self.factors[self.unit]), self.unit)
        return text

    def __int__(self):
        return int(self.size)

    def __lt__(self, other):
        return self.size < other.size

    def __le__(self, other):
        return self.size <= other.size

    def __gt__(self, other):
        return self.size > other.size

    def __ge__(self, other):
        return self.size >= other.size

    def __eq__(self, other):
        return self.size == other.size

    def __ne__(self, other):
        return self.size != other.size

    @classmethod
    def from_file(cls, filepath):
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
        else:
            size = 0
        return cls(size)

if __name__ == '__main__':
    print(FileSize())


def title(text):
    text = re.sub(r'(\w)([A-Z])', r'\1 \2', text).replace('_', ' ').title()
    return text
