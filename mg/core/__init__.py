from concurrence.extra import Lock
from concurrence import Tasklet, http, Timeout, TimeoutError
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from cassandra.ttypes import *
from operator import itemgetter
from mg.core.memcached import MemcachedLock, Memcached, MemcachedPool
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException, CassandraPool
from mg.core.mysql import MySQLPool
from mg.core.classes import *
from mg.core.tools import *
from uuid import uuid4
from weakref import WeakValueDictionary
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
import urlparse
import cStringIO

re_hook_path = re.compile(r'^(.+?)\.(.+)$')
re_config_path = re.compile(r'^(.+?)\.(.+)$')
re_module_path = re.compile(r'^(.+)\.(.+)$')
re_remove_domain = re.compile(r'^.{,20}///')

class HookFormatException(Exception):
    "Invalid hook format"
    pass

class HookGroupModules(CassandraObject):
    clsname = "HookGroupModules"
    indexes = {
        "all": [[]]
    }

class HookGroupModulesList(CassandraObjectList):
    objcls = HookGroupModules

class DownloadError(Exception):
    "Failed Module().download()"
    pass

class HandlerPermissionError(Exception):
    "Permission checks on the hook handler failed"
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
            lst = self.app().objlist(HookGroupModulesList, load_groups)
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

    def unregister_all(self):
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
            raise HookFormatException("Invalid hook name: %s" % name)
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
                raise HookFormatException("Invalid hook name: %s" % name)
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
                old_groups = self.app().objlist(HookGroupModulesList, query_index="all")
                for obj in old_groups:
                    if not obj.uuid in rec:
                        obj.remove()
                groups = self.app().objlist(HookGroupModulesList, [])
                for group, grpset in rec.iteritems():
                    if group != "all":
                        obj = self.app().obj(HookGroupModules, group, data={})
                        obj.set("list", list(grpset))
                        groups.append(obj)
                groups.store(dont_load=True)
                t.hooks_locked = False

class ConfigGroup(CassandraObject):
    clsname = "ConfigGroup"
    indexes = {
        "all": [[]],
    }

class ConfigGroupList(CassandraObjectList):
    objcls = ConfigGroup

class Config(object):
    """
    This class is a config manager for the application. It keeps list of loaded
    config groups and can perform get operation on the configuration.
    """
    def __init__(self, app):
        self.app = weakref.ref(app)
        self.clear()

    def clear(self):
        self._config = {}
        self._modified = set()
        self._deleted = set()
        #logging.getLogger("mg.core.Modules").debug("CLEARING CONFIG FOR APP %s", self.app().tag)

    def _load_groups(self, groups):
        """
        Load requested config groups without lock
        groups - list of config group names
        """
        load_groups = [g for g in groups if g not in self._config]
        if load_groups:
            list = self.app().objlist(ConfigGroupList, load_groups)
            list.load(silent=True)
            for g in list:
                self._config[g.uuid] = g.data
                #logging.getLogger("mg.core.Modules").debug("  - loaded config for app %s: %s => %s", self.app().tag, g.uuid, g.data)
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
        m = re_config_path.match(name)
        if not m:
            raise ModuleException("Invalid config key: %s" % name)
        (group, name) = m.group(1, 2)
        if group not in self._config:
            self.load_groups([group])
        return self._config[group].get(name, default)

    def get_group(self, group):
        """
        Returns config group as a dict
        group - group name
        """
        if not group in self._config:
            self.load_groups([group])
        return self._config[group]

    def set(self, name, value):
        """
        Change config value
        name - key identifier (format: "group.name")
        value - value to set
        Note: to store configuration in the database use store() method
        """
        if type(value) == str:
            value = unicode(value, "utf-8")
        m = re_config_path.match(name)
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
        m = re_config_path.match(name)
        if not m:
            raise ModuleException("Invalid config key: %s" % name)
        (group, name) = m.group(1, 2)
        with self.app().config_lock:
            if group not in self._config:
                self._load_groups([group])
            try:
                del self._config[group][name]
                self._modified.add(group)
            except KeyError:
                pass

    def delete_group(self, group):
        """
        Delete config group completely
        group - group identifier
        """
        with self.app().config_lock:
            self._deleted.add(group)
            if group in self._modified:
                del self._modified[group]
            if group in self._config:
                del self._config[group]
            self._config[group] = {}

    def store(self):
        if len(self._modified):
            with self.app().config_lock:
                for g in self._deleted:
                    try:
                        obj = self.app().obj(ConfigGroup, g)
                    except ObjectNotFoundException:
                        pass
                    else:
                        obj.remove()
                lst = self.app().objlist(ConfigGroupList, [])
                lst.load()
                for g in self._modified:
                    obj = self.app().obj(ConfigGroup, g, data=self._config[g])
                    obj.dirty = True
                    lst.append(obj)
                lst.store()
                self._modified.clear()
                self._deleted.clear()

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

    def exception(self, exception, silent=False, *args):
        if not silent:
            self.logger().exception(exception, *args)
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
        try:
            return self._int_app
        except AttributeError:
            pass
        self._int_app = self.app().inst.appfactory.get_by_tag("int")
        return self._int_app

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
        self.loaded_modules = dict()
        self.not_auto_loaded = set()

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
            with self.app().inst.modules_lock:
                t.modules_locked = True
                res = self._load(modules, silent, auto_loaded)
                t.modules_locked = False
                return res

    def _load(self, modules, silent=False, auto_loaded=False):
        "The same as load but without locking"
        errors = 0
        app = self.app()
        for mod in modules:
            if not auto_loaded:
                self.not_auto_loaded.add(mod)
            if mod not in self.loaded_modules:
                #logging.getLogger("mg.core.Modules").debug("LOAD MODULE %s", mod)
                m = re_module_path.match(mod)
                if not m:
                    raise ModuleException("Invalid module name: %s" % mod)
                (module_name, class_name) = m.group(1, 2)
                module = sys.modules.get(module_name)
                app.inst.modules.add(module_name)
                if not module:
                    try:
                        try:
                            __import__(module_name, globals(), locals(), [], -1)
                        except ImportError as e:
                            if silent:
                                logging.getLogger("%s:mg.core.Modules" % self.app().inst.server_id).exception(e)
                            else:
                                raise
                        module = sys.modules.get(module_name)
                    except Exception as e:
                        errors += 1
                        module = sys.modules.get(module_name)
                        if module:
                            logging.getLogger("%s:mg.core.Modules" % self.app().inst.server_id).exception(e)
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

    def reload(self):
        "Reload all modules"
        with self.app().inst.modules_lock:
            t = Tasklet.current()
            t.modules_locked = True
            modules = self.loaded_modules.keys()
            self.loaded_modules.clear()
            self.app().hooks.unregister_all()
            res = self._load(modules, auto_loaded=True)
            t.modules_locked = False
            return res

    def load_all(self):
        "Load all available modules"
        with self.app().inst.modules_lock:
            t = Tasklet.current()
            t.modules_locked = True
            # removing automatically loaded modules
            modules = []
            complete = set()
            for mod in self.loaded_modules.keys():
                if mod in self.not_auto_loaded:
                    modules.append(mod)
            self.loaded_modules.clear()
            self.app().hooks.unregister_all()
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

class Formatter(logging.Formatter):
    def format(self, record):
        self._fmt = utf2str(self._fmt)
        record.msg = utf2str(record.msg)
        for key, value in record.__dict__.items():
            if type(value) == unicode:
                record.__dict__[key] = value.encode("utf-8")
        record.args = tuple([utf2str(arg) for arg in record.args])
        if not record.__dict__.get("mg_formatted"):
            if record.__dict__.get("user"):
                record.msg = "user=%s %s" % (record.user, record.msg)
            if record.__dict__.get("ip"):
                record.msg = "ip=%s %s" % (record.ip, record.msg)
            if record.__dict__.get("app"):
                record.msg = "app=%s %s" % (record.app, record.msg)
            if record.__dict__.get("host"):
                record.msg = "host=%s %s" % (record.host, record.msg)
            record.mg_formatted = True
        s = logging.Formatter.format(self, record)
        if type(s) == unicode:
            s = s.encode("utf-8")
        return s

class Filter(logging.Filter):
    def filter(self, record):
        try:
            try:
                if record.args[0] == "200 OK" and record.args[1] == "/core/ping":
                    return 0
            except KeyError:
                pass
            except IndexError:
                pass
            except AttributeError:
                pass
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

class StderrFilter(Filter):
    def filter(self, record):
        try:
            if record.name == "WSGIServer":
                return 0
            if record.name == "mg.core.cass.CassandraObject" and record.levelname == "DEBUG":
                return 0
        except Exception:
            pass
        try:
            if record.args[0] == "200 OK" and record.args[1] == "/core/ping":
                return 0
        except Exception:
            pass
        return 1

class Instance(object):
    """
    This is an executable instance. It keeps references to all major objects
    """
    def __init__(self, server_id=None):
        self.modules_lock = Lock()
        self.config = {}
        self.appfactory = None
        self.modules = set()
        self.syslog_channel = None
        self.stderr_channel = None
        self.set_server_id(server_id if server_id else uuid4().hex)

    def setup_logger(self):
        modlogger = logging.getLogger("")
        modlogger.setLevel(logging.DEBUG)

        # syslog
        if self.syslog_channel:
            modlogger.removeHandler(self.syslog_channel)
        self.syslog_channel = logging.handlers.SysLogHandler(address="/dev/log")
        self.syslog_channel.setLevel(logging.DEBUG)
        formatter = Formatter(unicode(self.logger_id + " cls=%(name)s %(message)s"))
        self.syslog_channel.setFormatter(formatter)
        filter = Filter()
        self.syslog_channel.addFilter(filter)
        modlogger.addHandler(self.syslog_channel)

        # stderr
        if self.stderr_channel:
            modlogger.removeHandler(self.stderr_channel)
        self.stderr_channel = logging.StreamHandler()
        self.stderr_channel.setLevel(logging.DEBUG)
        filter = StderrFilter()
        self.stderr_channel.addFilter(filter)
        formatter = Formatter(unicode("%(asctime)s " + self.logger_id + " cls=%(name)s %(message)s"))
        self.stderr_channel.setFormatter(formatter)
        modlogger.addHandler(self.stderr_channel)

    def set_server_id(self, id, logger_id=None):
        self.server_id = id
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
        except Exception as e:
            raise RuntimeError("Couldn't connect to director:3000: %s" % e)
        try:
            request = cnn.get("/director/config")
            request.add_header("Connection", "close")
            response = cnn.perform(request)
            config = json.loads(response.body)
            for key in ("memcached", "cassandra"):
                config[key] = [tuple(ent) for ent in config[key]]
            self.config = config
            self.setup_logger()
            self.dbpool = CassandraPool(config["cassandra"], primary_host_id=0)
            self.mcpool = MemcachedPool(config["memcached"][0])
            self.sql_read = MySQLPool(((config["mysql_server"], 3306),), config["mysql_user"], config["mysql_password"], config["mysql_database"], primary_host_id=0)
            self.sql_write = MySQLPool(((config["mysql_server"], 3306),), config["mysql_user"], config["mysql_password"], config["mysql_database"], primary_host_id=0)
            return config
        finally:
            cnn.close()

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

class Application(object):
    """
    Application is anything that can process unified /group/hook/args
    HTTP requests, call hooks, keep it's own database with configuration,
    data and hooks
    """
    def __init__(self, inst, tag, storage=None, keyspace=None):
        """
        inst - Instance object
        tag - Application tag
        """
        if storage is None:
            if tag == "int" or tag == "main":
                storage = 1
            else:
                storage = 0
        self.inst = inst
        self.mc = Memcached(inst.mcpool, prefix="%s-" % tag)
        if storage == 2:
            self.db = inst.dbpool.dbget(keyspace, self.mc, storage, tag)
        else:
            self.db = inst.dbpool.dbget(tag, self.mc, storage)
        self.keyspace = tag
        self.tag = tag
        self.hooks = Hooks(self)
        self.config = Config(self)
        self.modules = Modules(self)
        self.config_lock = Lock()
        self.hook_lock = Lock()
        self.dynamic = False
        try:
            sql_read_pool = inst.sql_read
        except AttributeError:
            pass
        else:
            self.sql_read = sql_read_pool.dbget(self)
        try:
            sql_write_pool = inst.sql_write
        except AttributeError:
            pass
        else:
            self.sql_write = sql_write_pool.dbget(self)

    def reload(self):
        "Reload all loaded modules"
        self.config.clear()
        errors = 0
        errors += self.modules.reload()
        return errors

    def obj(self, cls, uuid=None, data=None, silent=False):
        "Create CassandraObject instance"
        return cls(self.db, uuid=uuid, data=data, silent=silent)

    def objlist(self, cls, uuids=None, **kwargs):
        "Create CassandraObjectList instance"
        return cls(self.db, uuids=uuids, **kwargs)

    def lock(self, keys, patience=20, delay=0.1, ttl=30):
        return MemcachedLock(self.mc, keys, patience, delay, ttl, value_prefix=str(self.inst.server_id) + "-")

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
        self.applications = WeakValueDictionary()
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

    def _reload(self):
        errors = 0
        for i in range(0, 2):
            for module_name in self.inst.modules:
                module = sys.modules.get(module_name)
                if module:
                    try:
                        reload(module)
                    except Exception as e:
                        errors += 1
                        module = sys.modules.get(module_name)
                        if module:
                            logging.getLogger("mg.core.Modules").exception(e)
                        else:
                            raise
        errors = errors + self._reload_applications()
        return errors

    def reload(self):
        "Reload all modules and applications"
        with self.lock:
            return self._reload()

    def _reload_applications(self):
        errors = 0
        for app in self.applications.values():
            if app.dynamic:
                self.remove(app)
            else:
                errors = errors + app.reload()
        return errors

    def reload_applications(self):
        "Reload all applications"
        with self.lock:
            return self._reload_applications()
