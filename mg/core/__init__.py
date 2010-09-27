from concurrence.extra import Lock
from concurrence import Tasklet, http
from concurrence.http import HTTPError
from cassandra.ttypes import *
from operator import itemgetter
from mg.core.memcached import MemcachedLock, Memcached
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from uuid import uuid4
import weakref
import re
import sys
import mg
import time
import json
import gettext
import logging
import logging.handlers
import datetime

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
            db = self.app().db
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

    def call(self, name, *args, **kwargs):
        """
        Call hook
        name - hook name (format: "group.name")
        *args, **kwargs - arbitrary parameters that will be passed to the handlers
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
                    res = handler(*args, **kwargs)
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
            db = self.app().db
            timestamp = time.time() * 1000
            data = [(g, json.dumps(rec[g])) for g in rec]
            mutations = [Mutation(column_or_supercolumn=ColumnOrSuperColumn(column=Column(name=g, value=v, clock=Clock(timestamp=timestamp)))) for (g, v) in data]
            mutations.insert(0, Mutation(deletion=Deletion(clock=Clock(timestamp=timestamp-1))))
            db.batch_mutate({"Hooks": {"Core": mutations}}, ConsistencyLevel.ALL)

class ConfigGroup(CassandraObject):
    _indexes = {
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ConfigGroup-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return ConfigGroup._indexes

class ConfigGroupList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ConfigGroup-"
        kwargs["cls"] = ConfigGroup
        CassandraObjectList.__init__(self, *args, **kwargs)

class Config(object):
    """
    This class is a config manager for the application. It keeps list of loaded
    config groups and can perform get operation on the configuration.
    """
    def __init__(self, app):
        self.clear()
        self.app = weakref.ref(app)
        self._path_re = re.compile(r'^(.+?)\.(.+)$')

    def clear(self):
        self._config = {}
        self._modified = set()

    def _load_groups(self, groups):
        """
        Load requested config groups without lock
        groups - list of config group names
        """
        load_groups = [g for g in groups if g not in self._config]
        if len(load_groups):
            list = self.app().objlist(ConfigGroupList, load_groups)
            list.load(silent=True)
            for g in list:
                self._config[g.uuid] = g.data
            for g in load_groups:
                if not g in self._config:
                    self._config[g] = {}

    def load_groups(self, groups):
        """
        Load requested config groups with lock
        groups - list of config group names
        """
        with self.app().config_lock:
            self._load_groups(groups)

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
        if type(value) == str:
            value = unicode(value, "utf-8")
        m = self._path_re.match(name)
        if not m:
            raise ModuleException("Invalid config key: %s" % name)
        (group, name) = m.group(1, 2)
        with self.app().config_lock:
            if group not in self._config:
                self._load_groups([group])
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
                self._load_groups([group])
            del self._config[group][name]
            self._modified.add(group)

    def store(self):
        if len(self._modified):
            with self.app().config_lock:
                list = self.app().objlist(ConfigGroupList, [])
                list.load()
                for g in self._modified:
                    obj = self.app().obj(ConfigGroup, g, data=self._config[g])
                    obj.dirty = True
                    list.append(obj)
                list.store()
                self._modified.clear()
            tag = None
            try:
                tag = self.app().tag
            except AttributeError:
                pass
            if tag is not None:
                try:
                    int_app = self.app().inst.int_app
                except AttributeError:
                    int_app = None
                if int_app is not None:
                    servers_online = int_app.hooks.call("cluster.servers_online")
                    if servers_online is not None:
                        for server, info in servers_online.items():
                            if info["type"] == "worker":
                                try:
                                    int_app.hooks.call("cluster.query_server", info["host"], info["port"], "/core/appconfig/%s" % tag, {})
                                except HTTPError as e:
                                    logging.getLogger("mg.core.Config").error(e)
                                except BaseException as e:
                                    logging.getLogger("mg.core.Config").exception(e)

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

    def db(self):
        return self.app().db

    def rhook(self, *args, **kwargs):
        "Registers handler for the current module. Arguments: all for Hooks.register() without module name"
        self.app().hooks.register(self.fqn, *args, **kwargs)

    def rdep(self, modules):
        "Register module dependency. This module will be loaded automatically"
        self.app().modules._load(modules)

    def conf(self, key, reset_cache=False, default=None):
        "Syntactic sugar for app.config.get(key)"
        conf = self.app().config
        if reset_cache:
            conf.clear()
        val = conf.get(key)
        if val is None:
            val = default
        return val

    def call(self, *args, **kwargs):
        "Syntactic sugar for app.hooks.call(...)"
        return self.app().hooks.call(*args, **kwargs)

    def register(self):
        "Register all required event handlers"
        self.rhook("core.loaded_modules", self.loaded_modules)

    def loaded_modules(self, list):
        "Appends name of the current module to the list"
        list.append(self.fqn)

    def ok(self):
        """Returns value of "ok" HTTP parameter"""
        return self.req().param("ok")

    def logger(self):
        return logging.getLogger(self.fqn)

    def log(self, level, msg, *args):
        logger = self.logger()
        if logger.isEnabledFor(level):
            logger.log(level, msg, *args)

    def debug(self, msg, *args):
        self.logger().debug(msg, *args)

    def info(self, msg, *args):
        self.logger().info(msg, *args)

    def warning(self, msg, *args):
        self.logger().warning(msg, *args)

    def error(self, msg, *args):
        self.logger().error(msg, *args)

    def critical(self, msg, *args):
        self.logger().critical(msg, *args)

    def exception(self, msg, *args):
        self.logger().exception(msg, *args)

    def _(self, val):
        try:
            value = self.req().trans.gettext(val)
            if type(value) == str:
                value = unicode(value, "utf-8")
            return value
        except:
            pass
        return self.call("l10n.gettext", val)

    def obj(self, *args, **kwargs):
        return self.app().obj(*args, **kwargs)

    def objlist(self, *args, **kwargs):
        return self.app().objlist(*args, **kwargs)

    def req(self):
        try:
            return Tasklet.current().req
        except AttributeError:
            raise RuntimeError("Module.req() called outside of a web handler")

    def nowdate(self):
        return datetime.datetime.utcnow().strftime("%Y-%m-%d")

    def now(self, add=0):
        return (datetime.datetime.utcnow() + datetime.timedelta(seconds=add)).strftime("%Y-%m-%d %H:%M:%S")

    def lock(self, *args, **kwargs):
        return self.app().lock(*args, **kwargs)

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
        modules - list of module names (format: "mg.group.Class" means
        "import Class from mg.group")
        """
        with self.app().inst.modules_lock:
            return self._load(modules)

    def _load(self, modules):
        "The same as load but without locking"
        errors = 0
        app = self.app()
        for mod in modules:
            if mod not in self._loaded_modules:
                m = self._path_re.match(mod)
                if not m:
                    raise ModuleException("Invalid module name: %s" % mod)
                (module_name, class_name) = m.group(1, 2)
                module = sys.modules.get(module_name)
                app.inst.modules.add(module_name)
                if not module:
                    try:
                        __import__(module_name, globals(), locals(), [], -1)
                        module = sys.modules.get(module_name)
                    except BaseException as e:
                        errors += 1
                        module = sys.modules.get(module_name)
                        if module:
                            logging.getLogger("%s:mg.core.Modules" % self.app().inst.server_id).exception(e)
                        else:
                            raise
                cls = module.__dict__[class_name]
                obj = cls(app, mod)
                self._loaded_modules[mod] = obj
                obj.register()
        return errors

    def reload(self):
        "Reload all modules"
        with self.app().inst.modules_lock:
            modules = self._loaded_modules.keys()
            self._loaded_modules.clear()
            self.app().hooks.unregister_all()
            return self._load(modules)

class Formatter(logging.Formatter):
    def format(self, record):
        if record.__dict__.get("user"):
            record.msg = "user:%s %s" % (record.user, record.msg)
        if record.__dict__.get("ip"):
            record.msg = "ip:%s %s" % (record.ip, record.msg)
        if record.__dict__.get("app"):
            record.msg = "app:%s %s" % (record.app, record.msg)
        if record.__dict__.get("host"):
            record.msg = "host:%s %s" % (record.host, record.msg)
        str = logging.Formatter.format(self, record)
        if type(str) == unicode:
            str = str.encode("utf-8")
        return str

class Filter(logging.Filter):
    def filter(self, record):
        try:
            req = Tasklet.current().req
            record.host = req.environ.get("HTTP_X_REAL_HOST")
            record.ip = req.environ.get("HTTP_X_REAL_IP")
            app = req.app
            record.app = app.tag
            if req.__dict__.has_key("_session"):
                record.user = req.user()
        except AttributeError:
            pass
        return 1

class Instance(object):
    """
    This is an executable instance. It keeps references to all major objects
    """
    def __init__(self):
        self.modules_lock = Lock()
        self.config = {}
        self.appfactory = None
        self.modules = set()
        self.server_id = uuid4().hex
        self.logger_id = self.server_id
        self.log_channel = None
        self.setup_logger()

    def setup_logger(self):
        modlogger = logging.getLogger("")
        modlogger.setLevel(logging.DEBUG)
        # log channel
        if self.log_channel:
            modlogger.removeHandler(self.log_channel)
        self.log_channel = logging.handlers.SysLogHandler(address="/dev/log")
        self.log_channel.setLevel(logging.DEBUG)
        formatter = Formatter(self.logger_id + " cls:%(name)s %(message)s")
        self.log_channel.setFormatter(formatter)
        filter = Filter()
        self.log_channel.addFilter(filter)
        modlogger.addHandler(self.log_channel)

    def set_server_id(self, id, logger_id=None):
        self.server_id = id
        if logger_id is None:
            self.logger_id = id
        else:
            self.logger_id = id
        self.setup_logger()

    def reload(self):
        "Reloads instance. Return value: number of errors"
        self.setup_logger()
        if self.appfactory is None:
            return 0
        return self.appfactory.reload()

    def download_config(self):
        """
        Connect to Director and ask for the claster configuration: http://director:3000/director/config
        Return value: config dict
        Side effect: stores downloaded dict in the inst.config
        """
        cnn = http.HTTPConnection()
        try:
            cnn.connect(("director", 3000))
        except BaseException as e:
            raise RuntimeError("Couldn't connect to director:3000: %s" % e)
        try:
            request = cnn.get("/director/config")
            response = cnn.perform(request)
            config = json.loads(response.body)
            for key in ("memcached", "cassandra"):
                config[key] = [tuple(ent) for ent in config[key]]
            self.config = config
            self.setup_logger()
            return config
        finally:
            cnn.close()

class Application(object):
    """
    Application is anything that can process unified /group/hook/args
    HTTP requests, call hooks, keep it's own database with configuration,
    data and hooks
    """
    def __init__(self, inst, dbpool, mcpool, tag):
        """
        inst - Instance object
        dbpool - CassandraPool object
        mcpool - MemcachedPool object
        tag - Application tag
        """
        self.inst = inst
        self.mc = Memcached(mcpool, prefix="%s-" % tag)
        self.db = dbpool.dbget("metagam", self.mc)
        self.keyprefix = "%s-" % tag
        self.tag = tag
        self.hooks = Hooks(self)
        self.config = Config(self)
        self.modules = Modules(self)
        self.config_lock = Lock()
        self.hook_lock = Lock()

    def dbrestruct(self):
        "Check database structure and update if necessary"
        dbstruct = {}
        self.hooks.call("core.dbstruct", dbstruct)
        self.hooks.call("core.dbapply", dbstruct)

    def reload(self):
        "Reload all loaded modules"
        errors = 0
        errors += self.modules.reload()
        return errors

    def obj(self, cls, uuid=None, data=None, silent=False):
        "Access CassandraObject constructor"
        return cls(self.db, uuid, data, dbprefix=self.keyprefix, silent=silent)

    def objlist(self, cls, uuids=None, **kwargs):
        return cls(self.db, uuids, dbprefix=self.keyprefix, **kwargs)

    def lock(self, keys, patience=20, delay=0.1, ttl=30):
        return MemcachedLock(self.mc, keys, patience, delay, ttl, value_prefix=str(self.inst.server_id) + "-")

    def log_params(self, req):
        d = {}
        val = req.environ.get("HTTP_X_REAL_IP")
        if val:
            d["ip"] = val
        val = req.environ.get("HTTP_X_REAL_HOST")
        if val:
            d["host"] = val
        try:
            d["app"] = self.app().tag
        except AttributeError:
            pass
        print "log_params=%s" % d
        return d

class ApplicationFactory(object):
    """
    ApplicationFactory returns Application object by it's tag
    """
    def __init__(self, inst):
        self.inst = inst
        self.applications = {}

    def add(self, app):
        "Add application to the factory"
        self.applications[app.tag] = app

    def remove_tag(self, tag):
        "Remove application from the factory by its tag"
        try:
            app = self.applications[tag]
        except KeyError:
            return
        self.remove(app)

    def remove(self, app):
        "Remove application from the factory"
        try:
            del self.applications[app.tag]
        except KeyError:
            pass

    def get_by_tag(self, tag):
        "Find application by tag and load it"
        try:
            return self.applications[tag]
        except KeyError:
            pass
        app = self.load(tag)
        if app is None:
            return None
        self.add(app)
        return app

    def load(self, tag):
        "Load application if not yet"
        return None

    def reload(self):
        "Reload all modules and applications"
        errors = 0
        for module_name in self.inst.modules:
            module = sys.modules.get(module_name)
            if module:
                try:
                    reload(module)
                except BaseException as e:
                    errors += 1
                    module = sys.modules.get(module_name)
                    if module:
                        logging.getLogger("mg.core.Modules").exception(e)
                    else:
                        raise
        errors = errors + self.reload_applications()
        return errors

    def reload_applications(self):
        "Reload all applications"
        # NOTE: if this will be very slow, it can be replaced with unloading unloadable modules
        # and reloading not unloadable ones
        errors = 0
        for app in self.applications.values():
            errors = errors + app.reload()
        return errors
