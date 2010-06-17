import weakref
import re
import sys
import imp
import mg.mod
from operator import itemgetter
from concurrence.extra import Lock

class Hooks(object):
    """
    This class is a hook manager for the application. It keeps list of loaded handlers
    and passes them hook calls.
    """
    def __init__(self, app):
        self.handlers = dict()
        self._loaded_groups = set()
        self.app = weakref.ref(app)

    def load_groups(self, groups):
        """
        Load all modules handling any hooks from the given groups
        groups - list of hook group names
        """
        # TODO: fetch list of modules handling this groups from the database


        # TODO: call self.app().modules.load_groups(groups)
        # TODO: cache group status in self._loaded_groups
        # TODO: don't forget to wrap I/O operations in the application-wide mutex
        pass

    def register(self, name, handler, priority=100):
        """
        Register hook handler
        name - hook name (format: "group.name")
        handler - will be called on hook calls
        priority - order of hooks execution
        """
        list = self.handlers.get(name)
        if list is None:
            list = []
            self.handlers[name] = list
        list.append((handler, priority))
        list.sort(key=itemgetter(1))

    def call(self, name, *args, **kwargs):
        """
        Call hook
        name - hook name (format: "group.name" or "group.name.anything.else")
        *args and **kwargs - arbitrary parameters that will be passed to the handlers
        Hook handler receives all parameters passed to the method
        """
        path = name.split(".")
        # ensure modules are loaded
        if path[0] not in self._loaded_groups:
            self.load_groups([path[0]])
        # call handlers
        handlers = self.handlers.get("%s.%s" % (path[0], path[1]))
        if handlers is not None:
            for handler, priority in handlers:
                handler(*args, **kwargs)

class Config(object):
    """
    This class is a config manager for the application. It keeps list of loaded
    config groups and can perform get operation on the configuration.
    """
    def __init__(self, app):
        self._config = dict()
        self.app = weakref.ref(app)

    def load_groups(self, groups):
        """
        Load requested config groups.
        groups - list of config group names
        """
        # TODO: don't forget to wrap I/O operations in the application-wide mutex
        pass

    def load_all(self):
        """
        Load all config entries related to the application
        """
        pass

    def get(self, group, name, default=None):
        """
        Returns config value
        group and name - key identifier
        default - default value for the key
        """
        # ensure modules are loaded
        if group not in self._config:
            self.load_groups([group])
        # fetch the value
        return self._config[group].get(name, default)

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
        "Syntactic sugar for app.hooks.register(...)"
        self.app().hooks.register(*args, **kwargs)

    def call(self, *args, **kwargs):
        "Syntactic sugar for app.hooks.call(...)"
        self.app().hooks.call(*args, **kwargs)

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
        self._path_re = re.compile(r'^(.+)\.(.+)$')
        self._loaded_modules = dict()

    def load(self, modules):
        """
        Load requested modules.
        modules - list of module names (format: "group.Class" means
        "import Class from mg.mod.group")
        """
        with self.app().inst.modules_lock:
            for mod in modules:
                if not mod in self._loaded_modules:
                    m = self._path_re.match(mod)
                    if not m:
                        raise ModuleError("Invalid module name: %s" % mod)
                    (module_name, class_name) = m.group(1, 2)
                    module = sys.modules.get(module_name)
                    if module is None:
                        (file, pathname, description) = imp.find_module(module_name, mg.mod.__path__)
                        module = imp.load_module(module_name, file, pathname, description)
                    cls = module.__dict__[class_name]
                    obj = cls(self.app(), mod)
                    obj.register()
                    self._loaded_modules[mod] = obj

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

    def http_request(self, request, group, hook, args):
        print "group=%s, hook=%s, args=%s" % (group, hook, args)
        args = cgi.escape(args)
        param = request.param('param')
        param = cgi.escape(param)
        return request.response_unicode('<html><body>Hello, world! args=%s, param=%s</body></html>' % (args, param))

    def db(self):
        return self.dbpool.dbget(self.keyspace)
