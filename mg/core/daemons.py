from mg import *
from concurrence import Timeout, TimeoutError
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from mg.core.classes import WorkerStatus, WorkerStatusList
from urllib import urlencode
import re
import time
import random
import json

re_daemon_call = re.compile(r'^([a-z0-9]+)/([a-z0-9]+)/([a-zA-Z][a-zA-Z0-9_]*)$')
check_daemons_interval = 30
check_daemons_interval_fast = 3

class DaemonError(Exception):
    pass

class DaemonStatus(CassandraObject):
    _indexes = {
        "updated": [[], "updated"],
        "server_id": [["server_id"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "DaemonStatus-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DaemonStatus._indexes

class DaemonStatusList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "DaemonStatus-"
        kwargs["cls"] = DaemonStatus
        CassandraObjectList.__init__(self, *args, **kwargs)

class Daemons(Module):
    def register(self):
        self.rhook("daemon.query", self.query)

    def query(self, daemon_id, method_name, timeout=30, *args, **kwargs):
        try:
            st = self.int_app().obj(DaemonStatus, "%s.%s" % (self.app().tag, daemon_id))
        except ObjectNotFoundException:
            raise DaemonError("Missing DaemonStatus record")
        try:
            with Timeout.push(timeout):
                cnn = HTTPConnection()
                try:
                    cnn.connect((st.get("host").encode("utf-8"), st.get("port")))
                except IOError as e:
                    raise DaemonError("Error connecting to the %s:%s: %s" % (st.get("host"), st.get("port"), e))
                params = {
                    "args": json.dumps(args),
                    "kwargs": json.dumps(kwargs)
                }
                try:
                    uri = "/daemon/call/%s/%s/%s" % (self.app().tag, daemon_id, method_name)
                    if type(uri) == unicode:
                        uri = uri.encode("utf-8")
                    request = cnn.post(uri, urlencode(params))
                    request.add_header("Content-type", "application/x-www-form-urlencoded")
                    response = cnn.perform(request)
                    if response.status_code != 200:
                        raise DaemonError("Daemon returned status %d" % response.status_code)
                    res = json.loads(response.body)
                    if res.get("error"):
                        raise DaemonError(u"Daemon returned error: %s" % res["error"])
                    return res["retval"]
                finally:
                    cnn.close()
        except TimeoutError:
            raise DaemonError("Timeout querying daemon %s/%s/%s" % (self.app().tag, daemon_id, method_name))

class Daemon(Module):
    def __init__(self, app, fqn, id):
        """
        app - application name
        fqn - fully qualified daemon classname
        id - ID of the daemon
        """
        Module.__init__(self, app, fqn)
        self.id = id
        self.tasklets = {}
        self._no = 0
        # main cycle should be aborted if this field is set
        self.terminate = False
        # persistent means autorespawning daemon
        self.persistent = False

    def run(self):
        """
        Run function 'func' in the context of tasklet 'main'
        """
        self.tasklet(self.main, "main")

    def main(self):
        pass

    def tasklet(self, func, name=None):
        """
        Create new tasklet with given name and run function 'func' in its context
        """
        if name is None:
            self._no += 1
            name = "auto-%d" % self._no
        if name in self.tasklets:
            raise RuntimeError("Tasklet %s is running already" % name)
        tasklet = Tasklet.new(self._tasklet_run)
        tasklet.name = name
        tasklet(func)

    def _tasklet_run(self, func):
        tasklet = Tasklet.current()
        self.tasklets[tasklet.name] = tasklet
        if tasklet.name == "main":
            self.int_app().hooks.call("daemon.start", self)
        forced_abort = False
        try:
            func()
        except TaskletExit:
            self.info("Forced abort of tasklet %s", tasklet.name)
            forced_abort = True
        finally:
            if tasklet.name == "main" and not forced_abort:
                for n, t in self.tasklets.items():
                    if n != "main":
                        t.kill()
                self.int_app().hooks.call("daemon.stop", self)
            del self.tasklets[tasklet.name]

    def fastidle(self):
        "Called regularly in the main cycle"
        pass

    def term(self):
        self.terminate = True

class DaemonsManager(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.next_status_update = 0

    def register(self):
        self.rhook("daemon.start", self.daemon_start)
        self.rhook("daemon.stop", self.daemon_stop)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("int-daemon.call", self.daemon_call, priv="public")
        self.rhook("daemon.monitor", self.monitor)
        self.rhook("web.ping_response", self.ping_response)
        self.rhook("director.registering_server", self.registering_server)
        self.rhook("director.unregistering_server", self.unregistering_server)
        self.rhook("int-daemon.stopped", self.daemon_stopped, priv="public")
        self.rhook("web.active_requests", self.active_requests)
        self.rhook("core.reloading_hard", self.reloading_hard)

    def running(self, app_tag=None, create=True):
        inst = self.app().inst
        try:
            running = inst.running_daemons
        except AttributeError:
            if not create:
                return None
            running = {}
            inst.running_daemons = running
        if app_tag is None:
            return running
        try:
            running_app = running[app_tag]
        except KeyError:
            if not create:
                return None
            running_app = {}
            running[app_tag] = running_app
        return running_app

    def daemon_start(self, daemon):
        running = self.running(daemon.app().tag)
        running[daemon.id] = daemon
        inst = self.app().inst
        st = self.status(daemon)
        st.set("cls", daemon.app().inst.cls)
        st.set("app", daemon.app().tag)
        st.set("daemon", daemon.id)
        st.set("host", inst.int_host)
        st.set("port", inst.int_port)
        st.set("server_id", inst.server_id)
        st.store()

    def daemon_stop(self, daemon):
        running = self.running(daemon.app().tag)
        del running[daemon.id]
        self.status_remove(daemon)
        if daemon.persistent:
            self.call("cluster.query_director", "/daemon/stopped/%s" % daemon.id)

    def fastidle(self):
        now = time.time()
        if now > self.next_status_update:
            self.next_status_update = now + random.randrange(40, 60)
            update = True
        else:
            update = False
        running = self.running()
        for cls, daemons in running.items():
            for daemon in daemons.values():
                # running may change during traversal
                if daemon.id in daemons:
                    daemon.fastidle()
                    if update:
                        st = self.status(daemon)
                        inst = self.app().inst
                        if st.get("host") != inst.int_host or st.get("port") != inst.int_port:
                            self.error("Daemon %s.%s running at the unexpected node %s:%s (my socket it %s:%s). Aborting our instance", cls, daemon.id, st.get("host"), st.get("port"), inst.int_host, inst.int_port)
                            try:
                                del running[daemon.id]
                            except KeyError:
                                pass
                            for t in daemon.tasklets.values():
                                t.kill()
                            try:
                                del daemons[daemon.id]
                            except KeyError:
                                pass
                        else:
                            st.store()

    def reloading_hard(self):
        for cls, daemons in self.running().items():
            for daemon in daemons.values():
                if daemon.persistent:
                    daemon.terminate = True

    def status(self, daemon):
        st = self.obj(DaemonStatus, "%s.%s" % (daemon.app().tag, daemon.id), silent=True)
        st.set("updated", self.now())
        return st

    def status_remove(self, daemon):
        try:
            st = self.obj(DaemonStatus, "%s.%s" % (daemon.app().tag, daemon.id))
        except ObjectNotFoundException:
            pass
        else:
            st.remove()

    def daemon_call(self):
        req = self.req()
        m = re_daemon_call.match(req.args)
        if not m:
            self.error("Invalid daemon call: %s", req.args)
            self.call("web.not_found")
        app_tag, daemon_id, method_name = m.group(1, 2, 3)
        running = self.running(app_tag, False)
        if not running:
            self.warning("Application %s has no daemons running at this host", app_tag)
            self.call("web.not_found")
        if not daemon_id in running:
            self.warning("Daemon %s/%s is not running on this host", app_tag, daemon_id)
            self.call("web.not_found")
        daemon = running[daemon_id]
        method_name = str(method_name)
        method = getattr(daemon, method_name, None)
        if not method or not callable(method):
            self.error("Daemon %s/%s has no method %s", app_tag, daemon_id, method_name)
            self.call("web.not_found")
        try:
            args = req.param("args")
            if args != "":
                args = json.loads(args)
            else:
                args = []
            kwargs = req.param("kwargs")
            if kwargs != "":
                kwargs = json.loads(kwargs)
            else:
                kwargs = {}
            res = method(*args, **kwargs)
            self.call("web.response_json", {"ok": True, "retval": res})
        except WebResponse:
            raise
        except Exception as e:
            self.exception(e)
            self.call("web.response_json", {"ok": False, "error": str(e)})

    def monitor(self):
        inst = self.app().inst
        inst.check_daemons = True
        timer = check_daemons_interval
        while True:
            try:
                if inst.check_daemons:
                    inst.check_daemons = False
                    # list of running daemons
                    running = set()
                    # worker processes
                    workers = {}
                    priority = {}
                    # loading status info of the running workers
                    lst = self.objlist(WorkerStatusList, query_index="all")
                    lst.load(silent=True)
                    for worker in lst:
                        if worker.get("reloading") or not worker.get("accept_daemons"):
                            continue
                        try:
                            priority[worker.get("cls")][worker.uuid] = 0
                        except KeyError:
                            priority[worker.get("cls")] = {worker.uuid: 0}
                        workers[worker.uuid] = worker
                    # loading status info of the running daemons
                    lst = self.objlist(DaemonStatusList, query_index="updated")
                    lst.load(silent=True)
                    for st in lst:
                        try:
                            running.add("%s-%s-%s" % (st.get("cls"), st.get("app"), st.get("daemon")))
                            # setting priority may fail if this server_id is not loaded (or reloading)
                            priority[st.get("cls")][st.get("server_id")] -= 1
                        except KeyError:
                            pass
#                    self.debug("Workers: %s", workers)
#                    self.debug("Priority: %s", priority)
#                    self.debug("Daemons: %s", running)
                    # persistent daemons
                    daemons = []
                    self.call("daemons.persistent", daemons)
                    for daemon in daemons:
                        if not ("%s-%s-%s" % (daemon["cls"], daemon["app"], daemon["daemon"])) in running:
                            timer = check_daemons_interval_fast
                            try:
                                worker_candidates = priority[daemon["cls"]].items()
                            except KeyError:
                                self.warning("No workers of the class %s", daemon["cls"])
                            else:
                                if len(worker_candidates):
                                    worker_candidates.sort(cmp=lambda x, y: cmp(y[1], x[1]))
#                                    self.debug("Sorted workers of the class %s: %s", daemon["cls"], worker_candidates)
                                    worker = workers[worker_candidates[0][0]]
#                                    self.debug("Selected worker %s (%s:%s)", worker.uuid, worker.get("host"), worker.get("port"))
                                    try:
                                        self.call("cluster.query_server", worker.get("host"), worker.get("port"), daemon["url"])
                                    except Exception as e:
                                        self.error("Error during spawning daemon: %s", e)
                                else:
                                    self.warning("No workers of the class %s where to run daemons", daemon["cls"])
                timer -= 1
                if timer <= 0:
                    lst = self.objlist(DaemonStatusList, query_index="updated", query_finish=self.now(-120))
                    if len(lst):
                        self.info("Removing stale daemon statuses: %s" % lst.uuids())
                        lst.remove()
                    inst.check_daemons = True
                    timer = check_daemons_interval
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(1)

    def ping_response(self, response):
        res = []
        running = self.running()
        for cls, daemons in running.items():
            for daemon in daemons.values():
                res.append((cls, daemon.app().tag, daemon.id))
        response["daemons"] = res

    def registering_server(self, server_id, conf):
#        self.debug("Registering server %s", server_id)
        lst = self.objlist(DaemonStatusList, query_index="server_id", query_equal=server_id)
        if len(lst):
#            self.debug("Removing daemon statuses due to %s restart: %s", server_id, lst.uuids())
            lst.remove()
        self.app().inst.check_daemons = True

    def unregistering_server(self, server_id):
#        self.debug("Unregistering server %s", server_id)
        lst = self.objlist(DaemonStatusList, query_index="server_id", query_equal=server_id)
        if len(lst):
#            self.debug("Removing daemon statuses due to %s restart: %s", server_id, lst.uuids())
            lst.remove()
        self.app().inst.check_daemons = True

    def daemon_stopped(self):
        self.app().inst.check_daemons = True
        self.call("web.response_json", {"ok": True})

    def active_requests(self, active_requests):
        cnt = 0
        running = self.running()
        for cls, daemons in running.items():
            for daemon in daemons.values():
                cnt += 1
        active_requests["daemons"] = cnt

class DaemonsAdmin(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.rhook("menu-admin-cluster.monitoring", self.menu_cluster_monitoring)
        self.rhook("ext-admin-daemons.monitor", self.daemons_monitor, priv="monitoring")
        self.rhook("headmenu-admin-daemons.monitor", self.headmenu_daemons_monitor)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-daemons.control", self.daemons_control, priv="daemons.control")
        self.rhook("headmenu-admin-daemons.control", self.headmenu_daemons_control)

    def menu_cluster_monitoring(self, menu):
        req = self.req()
        if req.has_access("monitoring"):
            menu.append({"id": "daemons/monitor", "text": self._("Daemons"), "leaf": True})

    def daemons_monitor(self):
        rows = []
        vars = {
            "tables": [
                {
                    "header": [self._("Class"), self._("App"), self._("ID"), self._("Interface"), self._("Updated")],
                    "rows": rows
                }
            ]
        }
        lst = self.int_app().objlist(DaemonStatusList, query_index="updated")
        lst.load(silent=True)
        for ent in lst:
            rows.append([ent.get("cls"), ent.get("app"), '<hook:admin.link href="daemons/control/%s" title="%s" />' % (ent.uuid, ent.get("daemon")), "%s:%d" % (ent.get("host"), ent.get("port")), ent.get("updated")])
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_daemons_monitor(self, args):
        return self._("Daemons monitor")

    def permissions_list(self, perms):
        perms.append({"id": "daemons.control", "name": self._("Daemons control")})

    def daemons_control(self):
        req = self.req()
        try:
            st = self.int_app().obj(DaemonStatus, req.args)
        except ObjectNotFoundException:
            self.call("admin.response", self._("Daemon doesn't exist"), {})
        app = self.app().inst.appfactory.get_by_tag(st.get("app"))
        if not app:
            self.call("admin.response", self._("Application %s is not accessible") % st.get("app"), {})
        if req.ok():
            method = req.param("method")
            errors = {}
            if not method:
                errors["method"] = self._("Specify method name")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            try:
                res = app.hooks.call("daemon.query", st.get("daemon"), method)
                self.call("admin.response", self._("Query successful. Server response: %s") % res, {})
            except DaemonError as e:
                errors["method"] = self._(u"Error during query: %s") % e
            self.call("web.response_json", {"success": False, "errors": errors})
        fields = [
            {"name": "method", "label": self._("Method name")},
        ]
        buttons = [{"text": self._("Call daemon method")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def headmenu_daemons_control(self, args):
        return [htmlescape(args), "daemons/monitor"]

