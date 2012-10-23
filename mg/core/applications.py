from mg.core.cass import CassandraObject, CassandraObjectList
from concurrence import Tasklet, Timeout, TimeoutError
from concurrence.extra import Lock
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from mg.core.tools import *
from mg.core.common import *
from mg.core.memcached import Memcached, MemcachedLock
from mg.core.config import Config
from operator import itemgetter
import weakref
import re
import cStringIO
import urlparse
import datetime
import gettext
import sys
import traceback

re_hook_path = re.compile(r'^(.+?)\.(.+)$')
re_module_path = re.compile(r'^(.+)\.(.+)$')
re_remove_domain = re.compile(r'^.{,20}///')

class DBHookGroupModules(CassandraObject):
    clsname = "HookGroupModules"
    indexes = {
        "all": [[]]
    }

class DBHookGroupModulesList(CassandraObjectList):
    objcls = DBHookGroupModules

class Hooks(object):
    """
    This class is a hook manager for an application. It keeps list of loaded handlers
    and passes them hook calls.
    """

    class Return(Exception):
        "This exception is raised when a hook handler wants to return the value immediately"
        def __init__(self, value=None):
            self.value = value

    def __init__(self, app):
        self.handlers = dict()
        self.loaded_groups = set()
        self.app = weakref.ref(app)
        self.dynamic = False

    def load_groups(self, groups):
        """
        Load all modules handling any hooks in the given groups
        groups - list of hook group names
        """
        t = Tasklet.current()
        if getattr(t, "hooks_locked", False):
            self._load_groups(groups)
        else:
            with self.app().hook_lock:
                t.hooks_locked = True
                self._load_groups(groups)
                t.hooks_locked = False

    def _load_groups(self, groups):
        """
        The same as load_groups but without locking
        """
        load_groups = [g for g in groups if (g != "all") and (g not in self.loaded_groups)]
        if len(load_groups):
            lst = self.app().objlist(DBHookGroupModulesList, load_groups)
            lst.load(silent=True)
            modules = set()
            for obj in lst:
                if obj.get("list"):
                    for mod in obj.get("list"):
                        modules.add(mod)
            modules = list(modules)
            if len(modules):
                self.app().modules.load(modules, silent=True, auto_loaded=True)
            for g in load_groups:
                self.loaded_groups.add(g)

    def register(self, module_name, hook_name, handler, priority=0, priv=None):
        """
        Register hook handler
        module_name - fully qualified module name
        hook_name - hook name (format: "group.name")
        handler - will be called on hook calls
        priority - order of hooks execution
        """
        lst = self.handlers.get(hook_name)
        if lst is None:
            lst = []
            self.handlers[hook_name] = lst
        lst.append((handler, priority, module_name, priv))
        lst.sort(key=itemgetter(1), reverse=True)

    def clear(self):
        "Unregister all registered hooks"
        self.handlers.clear()
        self.loaded_groups.clear()

    def call(self, name, *args, **kwargs):
        """
        Call handlers of the hook
        name - hook name ("group.name")
        *args, **kwargs - arbitrary parameters passed to the handlers
        Some special kwargs (they are not passed to the handlers):
        check_priv - require permission setting for the habdler
        """
        if "check_priv" in kwargs:
            check_priv = kwargs["check_priv"]
            del kwargs["check_priv"]
        else:
            check_priv = None
        m = re_hook_path.match(name)
        if not m:
            raise HookFormatError("Invalid hook name: %s" % name)
        (hook_group, hook_name) = m.group(1, 2)
        # ensure handling modules are loaded. "core" handlers are not loaded automatically
        if self.dynamic and hook_group != "core" and hook_group not in self.loaded_groups and kwargs.get("load_handlers") is not False:
            self.load_groups([hook_group])
        if "load_handlers" in kwargs:
            del kwargs["load_handlers"]
        # call handlers
        handlers = self.handlers.get(name)
        ret = None
        if handlers is not None:
            for handler, priority, module_name, priv in handlers:
                if check_priv:
                    if priv is None:
                        raise HandlerPermissionError("No privilege information in handler %s of module %s" % (name, module_name))
                    if priv == "public":
                        pass
                    elif priv == "logged":
                        self.call("session.require_login")
                    else:
                        self.call("session.require_login")
                        self.call("session.require_permission", priv)
                try:
                    res = handler(*args, **kwargs)
                    if type(res) == tuple:
                        args = res
                    elif res is not None:
                        ret = res
                except Hooks.Return as e:
                    return e.value
        return ret

    def store(self):
        """
        This method iterates over installed handlers and stores group => struct(name => modules_list)
        into the database
        """
        if not self.dynamic:
            return
        rec = dict()
        for name, handlers in self.handlers.items():
            m = re_hook_path.match(name)
            if not m:
                raise HookFormatError("Invalid hook name: %s" % name)
            (hook_group, hook_name) = m.group(1, 2)
            if hook_group != "core":
                grpset = rec.get(hook_group)
                if grpset is None:
                    grpset = rec[hook_group] = set()
                for handler in handlers:
                    grpset.add(handler[2])
        with self.app().hook_lock:
            with self.app().lock(["HOOK-GROUPS"]):
                t = Tasklet.current()
                t.hooks_locked = True
                old_groups = self.app().objlist(DBHookGroupModulesList, query_index="all")
                for obj in old_groups:
                    if not obj.uuid in rec:
                        obj.remove()
                groups = self.app().objlist(DBHookGroupModulesList, [])
                for group, grpset in rec.iteritems():
                    if group != "all":
                        obj = self.app().obj(DBHookGroupModules, group, data={})
                        obj.set("list", list(grpset))
                        groups.append(obj)
                groups.store(dont_load=True)
                t.hooks_locked = False

class Module(Loggable):
    """
    Module is a main container for the software payload.
    Module can intercept and handle hooks to provide any reaction
    """
    def __init__(self, app, fqn):
        """
        app - an Application object
        fqn - fully qualified module name (format: "group.Class")
        """
        Loggable.__init__(self, fqn)
        self.app = weakref.ref(app)

    def db(self):
        return self.app().db

    @property
    def sql_read(self):
        return self.app().sql_read

    @property
    def sql_write(self):
        return self.app().sql_write

    def rhook(self, *args, **kwargs):
        "Registers handler for the current module. Arguments: all for Hooks.register() without module name"
        self.app().hooks.register(self.fqn, *args, **kwargs)

    def rdep(self, modules):
        "Register module dependency. This module will be loaded automatically"
        self.app().modules._load(modules, auto_loaded=True)

    def conf(self, key, default=None, reset_cache=False):
        "Syntactic sugar for app.config.get(key)"
        conf = self.app().config
        if reset_cache:
            conf.clear()
        return conf.get(key, default)

    def call(self, *args, **kwargs):
        "Syntactic sugar for app.hooks.call(...)"
        return self.app().hooks.call(*args, **kwargs)

    def _register(self):
        "Register all required event handlers"
        self.rhook("core.loaded_modules", self.loaded_modules)
        self.register()

    def register(self):
        pass

    def loaded_modules(self, list):
        "Appends name of the current module to the list"
        list.append(self.fqn)

    def ok(self):
        """Returns value of "ok" HTTP parameter"""
        return self.req().param("ok")

    def exception(self, exception, silent=False, *args):
        if not silent:
            self.logger.exception(exception, *args)
        self.call("exception.report", exception)

    def _(self, val):
        try:
            value = self.req().trans.gettext(val)
            if type(value) == str:
                value = unicode(value, "utf-8")
            return re_remove_domain.sub('', value)
        except AttributeError:
            pass
        return re_remove_domain.sub('', self.call("l10n.gettext", val))

    def obj(self, *args, **kwargs):
        return self.app().obj(*args, **kwargs)

    def objlist(self, *args, **kwargs):
        return self.app().objlist(*args, **kwargs)

    def req(self):
        return Tasklet.current().req

    def nowmonth(self):
        return self.app().nowmonth()

    def nowdate(self):
        return self.app().nowdate()

    def now(self, add=0):
        return self.app().now(add)

    def now_local(self, add=0):
        return self.app().now_local(add)

    def yesterday_interval(self):
        return self.app().yesterday_interval()

    def lock(self, *args, **kwargs):
        return self.app().lock(*args, **kwargs)

    def int_app(self):
        "Returns reference to the application 'int'"
        return self.app().inst.int_app

    def main_app(self):
        "Returns reference to the application 'main'"
        try:
            return self._main_app
        except AttributeError:
            pass
        self._main_app = self.app().inst.appfactory.get_by_tag("main")
        return self._main_app

    def child_modules(self):
        return []

    def stemmer(self):
        try:
            return self.req()._stemmer
        except AttributeError:
            pass
        st = self.call("l10n.stemmer")
        try:
            self.req()._stemmer = st
        except AttributeError:
            pass
        return st

    def stem(self, word):
        return self.stemmer().stemWord(word)

    def httpfile(self, url):
        "Downloads given URL and returns it wrapped in StringIO"
        try:
            return cStringIO.StringIO(self.download(url))
        except DownloadError:
            return cStringIO.StringIO("")

    def download(self, url):
        "Downloads given URL and returns it"
        if url is None:
            raise DownloadError()
        if type(url) == unicode:
            url = url.encode("utf-8")
        url_obj = urlparse.urlparse(url, "http", False)
        if url_obj.scheme != "http":
            self.error("Scheme '%s' is not supported", url_obj.scheme)
        elif url_obj.hostname is None:
            self.error("Empty hostname: %s", url)
        else:
            cnn = HTTPConnection()
            try:
                with Timeout.push(50):
                    cnn.set_limit(20000000)
                    port = url_obj.port
                    if port is None:
                        port = 80
                    cnn.connect((url_obj.hostname, port))
                    request = cnn.get(url_obj.path + url_obj.query)
                    request.add_header("Connection", "close")
                    response = cnn.perform(request)
                    if response.status_code != 200:
                        self.error("Error downloading %s: %s %s", url, response.status_code, response.status)
                        return ""
                    return response.body
            except TimeoutError:
                self.error("Timeout downloading %s", url)
            except Exception as e:
                self.error("Error downloading %s: %s", url, str(e))
            finally:
                try:
                    cnn.close()
                except Exception:
                    pass
        raise DownloadError()

    def webdav_delete(self, url):
        "Downloads given URL and returns it"
        if url is None:
            return
        if type(url) == unicode:
            url = url.encode("utf-8")
        url_obj = urlparse.urlparse(url, "http", False)
        if url_obj.scheme != "http":
            self.error("Scheme '%s' is not supported", url_obj.scheme)
        elif url_obj.hostname is None:
            self.error("Empty hostname: %s", url)
        else:
            cnn = HTTPConnection()
            try:
                with Timeout.push(50):
                    port = url_obj.port
                    if port is None:
                        port = 80
                    cnn.connect((url_obj.hostname, port))
                    request = HTTPRequest()
                    request.method = "DELETE"
                    request.path = url_obj.path + url_obj.query
                    request.host = url_obj.hostname
                    request.add_header("Connection", "close")
                    cnn.perform(request)
            except TimeoutError:
                self.error("Timeout deleting %s", url)
            except Exception as e:
                self.error("Error deleting %s: %s", url, str(e))
            finally:
                try:
                    cnn.close()
                except Exception:
                    pass

    def image_format(self, image):
        if image.format == "JPEG":
            return ("jpg", "image/jpeg")
        elif image.format == "PNG":
            return ("png", "image/png")
        elif image.format == "GIF":
            return ("gif", "image/gif")
        else:
            return (None, None)

    def qevent(self, event, **kwargs):
        self.call("quests.event", event, **kwargs)

    def clconf(self, key, default=None):
        return self.app().clconf(key, default)

    @property
    def main_host(self):
        return self.app().main_host

class ModuleError(Exception):
    "Error during module loading"
    pass

class Modules(object):
    """
    This class is a modules manager for the application. It keeps list of loaded
    modules and can load modules on demand
    """
    def __init__(self, app):
        self.app = weakref.ref(app)
        self.modules_lock = Lock()
        self.loaded_modules = dict()
        self.not_auto_loaded = set()
        self.modules_locked_by = None

    def load(self, modules, silent=False, auto_loaded=False):
        """
        Load requested modules.
        modules - list of module names (format: "mg.group.Class" means
        silent - don't fail on ImportError
        auto_loaded - remove this modules on full reload
        "import Class from mg.group")
        """
        t = Tasklet.current()
        if getattr(t, "modules_locked", False):
            return self._load(modules, silent, auto_loaded)
        else:
            wasLocked = False
            if self.modules_lock.is_locked():
                wasLocked = True
                print "wait modules_lock load (app %s, locked by %s)" % (self.app().tag, self.modules_locked_by)
            with self.modules_lock:
                if wasLocked:
                    print "modules_lock load acquired (app %s)" % self.app().tag
                self.modules_locked_by = traceback.format_stack()
                t.modules_locked = True
                res = self._load(modules, silent, auto_loaded)
                t.modules_locked = False
                self.modules_locked_by = None
                return res

    def _load(self, modules, silent=False, auto_loaded=False):
        "The same as load but without locking"
        errors = 0
        app = self.app()
        for mod in modules:
            if not auto_loaded:
                self.not_auto_loaded.add(mod)
            if mod not in self.loaded_modules:
                m = re_module_path.match(mod)
                if not m:
                    raise ModuleError("Invalid module name: %s" % mod)
                (module_name, class_name) = m.group(1, 2)
                module = sys.modules.get(module_name)
                app.inst.modules.add(module_name)
                if not module:
                    try:
                        try:
                            __import__(module_name, globals(), locals(), [], -1)
                        except ImportError as e:
                            if silent:
                                logging.getLogger("%s:mg.core.Modules" % self.app().inst.instid).exception(e)
                            else:
                                raise
                        module = sys.modules.get(module_name)
                    except Exception as e:
                        errors += 1
                        module = sys.modules.get(module_name)
                        if module:
                            logging.getLogger("%s:mg.core.Modules" % self.app().inst.instid).exception(e)
                        else:
                            raise
                if module:
                    cls = module.__dict__[class_name]
                    obj = cls(app, mod)
                    self.loaded_modules[mod] = obj
                    obj._register()
                else:
                    app.inst.modules.remove(module_name)
        return errors

    def clear(self):
        "Remove all modules"
        with self.modules_lock:
            self.loaded_modules.clear()

    def load_all(self):
        "Load all available modules"
        with self.modules_lock:
            self.modules_locked_by = traceback.format_stack()
            t = Tasklet.current()
            t.modules_locked = True
            # removing automatically loaded modules
            modules = []
            complete = set()
            for mod in self.loaded_modules.keys():
                if mod in self.not_auto_loaded:
                    modules.append(mod)
            self.loaded_modules.clear()
            self.app().hooks.clear()
            self._load(modules)
            repeat = True
            while repeat:
                repeat = False
                for name, mod in self.loaded_modules.items():
                    if name not in complete:
                        children = mod.child_modules()
                        self._load(children, auto_loaded=True)
                        complete.add(name)
                        repeat = True
            t.modules_locked = False
            self.modules_locked_by = None

class ApplicationConfigUpdater(object):
    """
    This module holds configuration changes and applies
    it when store() called
    """
    def __init__(self, app):
        self.app = app
        self.params = {}
        self.del_params = {}

    def set(self, param, value):
        self.params[param] = value
        try:
            del self.del_params[param]
        except KeyError:
            pass

    def delete(self, param):
        self.del_params[param] = True
        try:
            del self.params[param]
        except KeyError:
            pass

    def get(self, param, default=None):
        if param in self.del_params:
            return None
        return self.params.get(param, self.app.config.get(param, default))

    def store(self, update_hooks=True, notify=True):
        if self.params or self.del_params:
            config = self.app.config
            for key, value in self.params.iteritems():
                config.set(key, value)
            for key, value in self.del_params.iteritems():
                config.delete(key)
            if update_hooks:
                self.app.store_config_hooks(notify)
            else:
                config.store()
                if notify:
                    self.app.hooks.call("cluster.appconfig_changed")
            self.params = {}
            self.app.hooks.call("config.changed")

class Application(Loggable):
    """
    Application is anything that can process unified /group/hook/args
    HTTP requests, call hooks, keep it's own database with configuration,
    data and hooks
    """
    def __init__(self, inst, tag, storage=None, keyspace=None, fqn="mg.core.applications.Application"):
        """
        inst - Instance object
        tag - Application tag
        """
        Loggable.__init__(self, fqn)
        if storage is None:
            if tag == "int" or tag == "main":
                storage = 1
            else:
                storage = 0
        self.storage = storage
        self.inst = inst
        self.tag = tag
        self.keyspace = keyspace
        self.hooks = Hooks(self)
        self.config = Config(self)
        self.modules = Modules(self)
        self.config_lock = Lock()
        self.hook_lock = Lock()
        self.dynamic = False

    @property
    def db(self):
        try:
            return self._db
        except AttributeError:
            pass
        if self.storage == 2:
            self._db = self.inst.dbpool.dbget(self.keyspace, self.mc, self.storage, self.tag)
        else:
            self._db = self.inst.dbpool.dbget(self.tag, self.mc, self.storage)
        return self._db

    @property
    def mc(self):
        try:
            return self._mc
        except AttributeError:
            pass
        self._mc = Memcached(self.inst.mcpool, prefix="%s-" % self.tag)
        return self._mc

    @property
    def sql_read(self):
        try:
            return self._sql_read
        except AttributeError:
            pass
        self._sql_read = self.inst.sql_read.dbget(self)
        return self._sql_read

    @property
    def sql_write(self):
        try:
            return self._sql_write
        except AttributeError:
            pass
        self._sql_write = self.inst.sql_write.dbget(self)
        return self._sql_write

    def obj(self, cls, uuid=None, data=None, silent=False):
        "Create CassandraObject instance"
        return cls(self.db, uuid=uuid, data=data, silent=silent)

    def objlist(self, cls, uuids=None, **kwargs):
        "Create CassandraObjectList instance"
        return cls(self.db, uuids=uuids, **kwargs)

    def lock(self, keys, patience=20, delay=0.1, ttl=30):
        return MemcachedLock(self.mc, keys, patience, delay, ttl, value_prefix=str(self.inst.instid) + "-")

    def nowmonth(self):
        return datetime.datetime.utcnow().strftime("%Y-%m")

    def nowdate(self):
        return datetime.datetime.utcnow().strftime("%Y-%m-%d")

    def now(self, add=0):
        return (datetime.datetime.utcnow() + datetime.timedelta(seconds=add)).strftime("%Y-%m-%d %H:%M:%S")

    def now_local(self, add=0):
        now = self.hooks.call("l10n.now_local", add)
        if not now:
            return self.now(add)
        return now.strftime("%Y-%m-%d %H:%M:%S")

    def yesterday_interval(self):
        now = datetime.datetime.utcnow()
        yesterday = (now + datetime.timedelta(seconds=-86400)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")
        return '%s 00:00:00' % yesterday, '%s 00:00:00' % today

    def store_config_hooks(self, notify=True):
        self.config.store()
        self.modules.load_all()
        self.hooks.store()
        if notify:
            self.hooks.call("cluster.appconfig_changed")

    def config_updater(self):
        return ApplicationConfigUpdater(self)

    def clconf(self, key, default=None):
        return self.inst.dbconfig.get(key, default)

    @property
    def main_host(self):
        return self.clconf("main_host", "main")

    def load(self, *args, **kwargs):
        "Syntactic sugar for modules.load(...)"
        return self.modules.load(*args, **kwargs)

    def call(self, *args, **kwargs):
        "Syntactic sugar for hooks.call(...)"
        return self.hooks.call(*args, **kwargs)

class TaskletLock(Lock):
    def __init__(self):
        Lock.__init__(self)
        self.locked_by = None
        self.depth = None

    def __enter__(self):
        task = id(Tasklet.current())
        if self.locked_by and self.locked_by == task:
            self.depth += 1
            return self
        Lock.__enter__(self)
        self.locked_by = task
        self.depth = 0
        return self

    def __exit__(self, type, value, traceback):
        self.depth -= 1
        if self.depth <= 0:
            self.locked_by = None
            Lock.__exit__(self, type, value, traceback)

class ApplicationFactory(object):
    """
    ApplicationFactory returns Application object by it's tag
    """
    def __init__(self, inst):
        self.inst = inst
        self.applications = weakref.WeakValueDictionary()
        self.lock = TaskletLock()

    def add(self, app):
        "Add application to the factory"
        self.applications[app.tag] = app
        self.added(app)

    def added(self, app):
        pass

    def remove_by_tag(self, tag):
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

    def get_by_tag(self, tag, load=True):
        "Find application by tag and load it"
        tag = utf2str(tag)
        with self.lock:
            try:
                return self.applications[tag]
            except KeyError:
                pass
            if not load:
                return None
            app = self.load(tag)
            if app is None:
                return None
            self.add(app)
            return app

    def load(self, tag):
        "Load application if not yet"
        return None
