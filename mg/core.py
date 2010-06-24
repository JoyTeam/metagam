import weakref
import re
import sys
import imp
import mg.mod
from operator import itemgetter
from concurrence.extra import Lock
from cassandra.ttypes import *
import time
import json

class HookFormatException(Exception):
    "Invalid hook format"
    pass

class Hooks(object):
    """
    This class is a hook manager for the application. It keeps list of loaded handlers
    and passes them hook calls.
    """

    class Return(Exception):
        "This exception is raised when a hook handler wants to return the value immediately"
        def __init__(self, value=None):
            self.value = value

    def __init__(self, app):
        self.handlers = dict()
        self._groups = dict()
        self._loaded_hooks = set()
        self.app = weakref.ref(app)
        self._path_re = re.compile(r'^(.+?)\.(.+)$')

    def load_groups(self, groups):
        """
        Load all modules handling any hooks from the given groups
        groups - list of hook group names
        """
        with self.app().hook_lock:
            self._load_groups(groups)

    def _load_groups(self, groups):
        """
        The same as load_groups but without locking
        """
        load_groups = [g for g in groups if g not in self._groups]
        if len(load_groups):
            db = self.app().db()
            data = db.get_slice("Hooks", ColumnParent(column_family="Core"), SlicePredicate(column_names=load_groups), ConsistencyLevel.ONE)
            for col in data:
                self._groups[col.column.name] = json.loads(col.column.value)
            for g in load_groups:
                if g not in self._groups:
                    self._groups[g] = {}

    def load_handlers(self, names):
        """
        Load all modules handling any of listed hooks
        names - list of hook names
        """
        with self.app().hook_lock:
            load_hooks = [n for n in names if n not in self._loaded_hooks]
            if len(load_hooks):
                load_groups = []
                load_hooks_list = []
                for name in load_hooks:
                    m = self._path_re.match(name)
                    if not m:
                        raise HookFormatException("Invalid hook name: %s" % name)
                    (hook_group, hook_name) = m.group(1, 2)
                    if hook_group not in self._groups:
                        load_groups.append(hook_group)
                    load_hooks_list.append((hook_group, hook_name))
                    self._loaded_hooks.add(name)
                self._load_groups(load_groups)
                modules = []
                for hook_group, hook_name in load_hooks_list:
                    modules = self._groups[hook_group].get(hook_name)
                    if modules is not None:
                        self.app().modules.load(modules)

    def register(self, module_name, hook_name, handler, priority=0):
        """
        Register hook handler
        module_name - fully qualified module name
        hook_name - hook name (format: "group.name")
        handler - will be called on hook calls
        priority - order of hooks execution
        """
        list = self.handlers.get(hook_name)
        if list is None:
            list = []
            self.handlers[hook_name] = list
        list.append((handler, priority, module_name))
        list.sort(key=itemgetter(1), reverse=True)

    def unregister_all(self):
        "Unregister all registered hooks"
        self.handlers.clear()

    def call(self, name, *args):
        """
        Call hook
        name - hook name (format: "group.name")
        *args - arbitrary parameters that will be passed to the handlers
        Hook handler receives all parameters passed to the method
        """
        m = self._path_re.match(name)
        if not m:
            raise HookFormatException("Invalid hook name: %s" % name)
        (hook_group, hook_name) = m.group(1, 2)
        # ensure modules are loaded
        if hook_group != "core":
            if name not in self._loaded_hooks:
                self.load_handlers([name])
        # call handlers
        handlers = self.handlers.get(name)
        ret = None
        if handlers is not None:
            for handler, priority, module_name in handlers:
                try:
                    res = handler(*args)
                    if type(res) == tuple:
                        args = res
                    elif res is not None:
                        ret = res
                except Hooks.Return, e:
                    return e.value
        return ret

    def store(self):
        """
        This method iterates over installed handlers and stores group => struct(name => modules_list)
        into the database
        """
        rec = dict()
        for name, handlers in self.handlers.iteritems():
            m = self._path_re.match(name)
            if not m:
                raise HookFormatException("Invalid hook name: %s" % name)
            (hook_group, hook_name) = m.group(1, 2)
            if hook_group != "core":
                grpdict = rec.get(hook_group)
                if grpdict is None:
                    grpdict = rec[hook_group] = dict()
                grpdict[hook_name] = [handler[2] for handler in handlers]
        with self.app().hook_lock:
            db = self.app().db()
            timestamp = time.time() * 1000
            data = [(g, json.dumps(rec[g])) for g in rec]
            mutations = [Mutation(column_or_supercolumn=ColumnOrSuperColumn(column=Column(name=g, value=v, clock=Clock(timestamp=timestamp)))) for (g, v) in data]
            mutations.insert(0, Mutation(deletion=Deletion(clock=Clock(timestamp=timestamp-1))))
            db.batch_mutate({"Hooks": {"Core": mutations}}, ConsistencyLevel.ALL)

class Config(object):
    """
    This class is a config manager for the application. It keeps list of loaded
    config groups and can perform get operation on the configuration.
    """
    def __init__(self, app):
        self._config = dict()
        self._modified = set()
        self.app = weakref.ref(app)
        self._path_re = re.compile(r'^(.+?)\.(.+)$')

    def load_groups(self, groups):
        """
        Load requested config groups.
        groups - list of config group names
        """
        with self.app().config_lock:
            load_groups = [g for g in groups if g not in self._config]
            if len(load_groups):
                db = self.app().db()
                data = db.get_slice("Config", ColumnParent(column_family="Core"), SlicePredicate(column_names=load_groups), ConsistencyLevel.ONE)
                for col in data:
                    self._config[col.column.name] = json.loads(col.column.value)
                for g in load_groups:
                    if not g in self._config:
                        self._config[g] = {}

    def load_all(self):
        """
        Load all config entries related to the application
        """
        pass

    def get(self, name, default=None):
        """
        Returns config value
        name - key identifier (format: "group.name")
        default - default value for the key
        """
        m = self._path_re.match(name)
        if not m:
            raise ModuleException("Invalid config key: %s" % name)
        (group, name) = m.group(1, 2)
        if group not in self._config:
            self.load_groups([group])
        return self._config[group].get(name, default)

    def set(self, name, value):
        """
        Change config value
        name - key identifier (format: "group.name")
        value - value to set
        Note: to store configuration in the database use store() method
        """
        m = self._path_re.match(name)
        if not m:
            raise ModuleException("Invalid config key: %s" % name)
        (group, name) = m.group(1, 2)
        with self.app().config_lock:
            if group not in self._config:
                self.load_groups([group])
            self._config[group][name] = value
            self._modified.add(group)

    def delete(self, name):
        """
        Delete config value
        name - key identifier (format: "group.name")
        Note: to store configuration in the database use store() method
        """
        m = self._path_re.match(name)
        if not m:
            raise ModuleException("Invalid config key: %s" % name)
        (group, name) = m.group(1, 2)
        with self.app().config_lock:
            if group not in self._config:
                self.load_groups([group])
            del self._config[group][name]
            self._modified.add(group)

    def store(self):
        if len(self._modified):
            with self.app().config_lock:
                db = self.app().db()
                timestamp = time.time() * 1000
                data = [(g, json.dumps(self._config[g])) for g in self._modified]
                mutations = [Mutation(column_or_supercolumn=ColumnOrSuperColumn(column=Column(name=g, value=v, clock=Clock(timestamp=timestamp)))) for (g, v) in data]
                db.batch_mutate({"Config": {"Core": mutations}}, ConsistencyLevel.ALL)
                self._modified.clear()

class Module(object):
    """
    Module is a main container for the software payload.
    Module can intercept and handle hooks to provide any reaction
    """
    def __init__(self, app, fqn):
        """
        app - an Application object
        fqn - fully qualified module name (format: "group.Class")
        """
        self.app = weakref.ref(app)
        self.fqn = fqn

    def rhook(self, *args, **kwargs):
        "Registers handler for the current module. Arguments: all for Hooks.register() without module name"
        self.app().hooks.register(self.fqn, *args, **kwargs)

    def rdep(self, modules):
        "Register module dependency. This module will be loaded automatically"
        self.app().modules._load(modules)

    def conf(self, *args):
        "Syntactic sugar for app.config.get(...)"
        return self.app().config.get(*args)

    def call(self, *args, **kwargs):
        "Syntactic sugar for app.hooks.call(...)"
        return self.app().hooks.call(*args, **kwargs)

    def register(self):
        "Register all required event handlers"
        self.rhook("core.loaded_modules", self.loaded_modules)

    def loaded_modules(self, list):
        "Appends name of the current module to the list"
        list.append(self.fqn)

    def db(self):
        return self.app().dbpool.dbget(self.app().keyspace)

class ModuleException(Exception):
    "Error during module loading"
    pass

class Modules(object):
    """
    This class is a modules manager for the application. It keeps list of loaded
    modules and can load modules on demand
    """
    def __init__(self, app):
        self.app = weakref.ref(app)
        self._path_re = re.compile(r'^(.+?)\.(.+)$')
        self._loaded_modules = dict()

    def load(self, modules):
        """
        Load requested modules.
        modules - list of module names (format: "group.Class" means
        "import Class from mg.mod.group")
        """
        with self.app().inst.modules_lock:
            self._load(modules)

    def _load(self, modules):
        "The same as load but without locking"
        for mod in modules:
            if mod not in self._loaded_modules:
                m = self._path_re.match(mod)
                if not m:
                    raise ModuleException("Invalid module name: %s" % mod)
                (module_name, class_name) = m.group(1, 2)
                module = sys.modules.get(module_name)
                if module is None:
                    (file, pathname, description) = imp.find_module(module_name, mg.mod.__path__)
                    module = imp.load_module(module_name, file, pathname, description)
                cls = module.__dict__[class_name]
                obj = cls(self.app(), mod)
                obj.register()
                self._loaded_modules[mod] = obj

    def reload(self):
        "Reload all modules"
        with self.app().inst.modules_lock:
            modules = []
            for name, mod in self._loaded_modules.iteritems():
                modules.append(name)
                m = self._path_re.match(name)
                if not m:
                    raise ModuleException("Invalid module name: %s" % name)
                (module_name, class_name) = m.group(1, 2)
                try:
                    del sys.modules[module_name]
                except KeyError:
                    pass
            self._loaded_modules.clear()
            self.app().hooks.unregister_all()
            self._load(modules)

class Instance(object):
    """
    This is an executable instance. It keeps references to all major objects
    """
    def __init__(self):
        self.modules_lock = Lock()

class Application(object):
    """
    Application is anything that can process unified /group/hook/args
    HTTP requests, call hooks, keep it's own database with configuration,
    data and hooks
    """
    def __init__(self, inst, dbpool, keyspace, mc):
        """
        inst - Instance object
        dbpool - DatabasePool object
        keyspace - database keyspace
        mc - Memcached object
        dbhost, dbname - database host and name
        mcprefix - memcached prefix
        """
        self.inst = inst
        self.dbpool = dbpool
        self.keyspace = keyspace
        self.mc = mc
        self.hooks = Hooks(self)
        self.config = Config(self)
        self.modules = Modules(self)
        self.config_lock = Lock()
        self.hook_lock = Lock()

    def db(self):
        "Get an instance of the Database"
        return self.dbpool.dbget(self.keyspace)

    def dbrestruct(self):
        "Check database structure and update if necessary"
        dbstruct = {}
        self.hooks.call("core.dbstruct", dbstruct)
        self.hooks.call("core.dbapply", dbstruct)

    def reload(self):
        "Reload all loaded modules"
        self.modules.reload()
