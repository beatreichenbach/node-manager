import importlib
import pkgutil
import logging
import re

try:
    from . import plugins
except ImportError:
    import plugins


def dcc_plugins():
    _plugins = all_plugins()
    dcc_plugins = {key: value for key, value in _plugins.items() if '_' not in key}
    return dcc_plugins


def all_plugins():
    _plugins = {}
    for finder, name, ispkg in iter_namespace(plugins):
        _plugins[name.split('.')[-1]] = name

    return _plugins


def contexts(dcc):
    _plugins = all_plugins()
    pattern = re.compile('{}_([^_]+)_'.format(re.escape(dcc)))
    contexts = []
    for key, value in _plugins.items():
        match = pattern.match(key)
        if match:
            contexts.append(match.group(1))
    return list(set(contexts))


def node_plugins(dcc, context):
    _plugins = all_plugins()
    pattern = re.compile('{}_{}_'.format(re.escape(dcc), re.escape(context)))
    node_plugins = {}
    for key, value in _plugins.items():
        if pattern.match(key):
            name = pattern.sub('', key)
            node_plugins[name] = value
    return node_plugins


def node_plugin(dcc, context, node):
    name = '{}_{}_{}'.format(dcc, context, node)
    return all_plugins().get(name)


def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + '.')


def plugin_class(cls, plugin):
    plugin = '.{}'.format(plugin)
    package = '{}.plugins'.format(__package__ or '')
    try:
        module = importlib.import_module(plugin, package=package)
        cls = getattr(module, cls.__name__)
    except ImportError as e:
        logging.error(e)
        logging.error(
            'Could not find plugin: "{}{}" '
            'Using base class instead.'.format(package, plugin))
    return cls
