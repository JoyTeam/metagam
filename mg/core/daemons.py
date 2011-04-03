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
        Module.register(self)
        self.rhook("daemon.query", self.query)

    def query(self, daemon_id, method_name, timeout=30, *args, **kwargs):
        try:
            st = self.int_app().obj(DaemonStatus, "%s-%s" % (self.app().tag, daemon_id))
        except CassandraObjectNotFound:
            raise DaemonError("Missing DaemonStatus record")
        try:
            with Timeout(timeout):
                cnn = HTTPConnection()
                try:
                    cnn.connect((st.get("host"), st.get("post")))
                except IOError as e:
                    raise DaemonError("Error connecting to the %s:%s: %s" % (st.get("host"), st.get("post"), e))
                params = {
                    "args": args,
                    "kwargs": kwargs
                }
                try:
                    request = cnn.post("/daemon/call/%s/%s/%s" % (self.app().tag, daemon_id, method_name), urlencode(params))
                    request.add_header("Content-type", "application/x-www-form-urlencoded")
                    response = cnn.perform(request)
                    if response.status_code != 200:
                        raise DaemonError("Daemon returned status %d" % response.status_code)
                    res = json.loads(response.body)
                    if res.get("error"):
                        raise DaemonError(u"Daemon returned error: %s" % res["error"])
                    return res["result"]
                finally:
                    cnn.close()
        except TimeoutError:
            raise DaemonError("Timeout querying daemon %s/%s/%s" % (self.app().tag, daemon_id, method_name))

class DaemonsManager(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.next_status_update = 0

    def register(self):
        Module.register(self)
        self.rhook("daemon.start", self.daemon_start)
        self.rhook("daemon.stop", self.daemon_stop)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("int-daemon.call", self.daemon_call, priv="public")
        self.rhook("daemon.monitor", self.monitor)
        self.rhook("web.ping_response", self.ping_response)
        self.rhook("director.ping_results", self.ping_results)
        self.rhook("director.registering_server", self.registering_server)

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
                            self.error("Daemon %s.%s running at the unexpected node %s:%s. Aborting our instance", cls, daemon.id, st.get("host"), st.get("port"))
                            try:
                                del running[daemon.id]
                            except KeyError:
                                pass
                            for t in daemon.tasklets.values():
                                t.kill()
                        st.store()

    def status(self, daemon):
        st = self.obj(DaemonStatus, "%s.%s" % (daemon.app().tag, daemon.id), silent=True)
        st.set("updated", self.now())
        return st

    def status_remove(self, daemon):
        try:
            st = self.obj(DaemonStatus, "%s.%s" % (daemon.app().tag, daemon.id))
        except CassandraObjectNotFound:
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
            self.debug("Application %s has no daemons running at this host", app_tag)
            self.call("web.not_found")
        if not daemon_id in running:
            self.debug("Daemon %s/%s is not running on this host", app_tag, daemon_id)
            self.call("web.not_found")
        daemon = running[daemon_id]
        method = getattr(daemon, method_name, None)
        self.debug("daemon: %s, method_name: %s, method: %s", daemon, method_name, method)
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
            self.call("web.response_json", {"ok": True, "response": res})
        except WebResponse:
            raise
        except Exception as e:
            self.exception(e)
            self.call("web.response_json", {"ok": False, "error": str(e)})

    def monitor(self):
        self.check_daemons = True
        timer = 0
        while True:
            try:
                if self.check_daemons:
                    self.debug("Checking daemons status")
                    self.check_daemons = False
                    # list of running daemons
                    running = set()
                    # worker processes
                    workers = {}
                    priority = {}
                    # loading status info of the running workers
                    lst = self.objlist(WorkerStatusList, query_index="all")
                    lst.load(silent=True)
                    for worker in lst:
                        if worker.get("reloading"):
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
                            priority[st.get("server_id")] -= 1
                            running.add("%s-%s-%s" % (st.get("cls"), st.get("app"), st.get("daemon")))
                        except KeyError:
                            pass
                    self.debug("Workers: %s", workers)
                    self.debug("Priority: %s", priority)
                    self.debug("Daemons: %s", running)
                    if not "metagam-main-realplexor" in running:
                        try:
                            worker_candidates = priority["metagam"].items()
                        except KeyError:
                            self.debug("No workers of the class %s", "metagam")
                        else:
                            if len(worker_candidates):
                                worker_candidates.sort(cmp=lambda x, y: cmp(y[1], x[1]))
                                self.debug("Sorted workers of the class %s: %s", "metagam", worker_candidates)
                                worker = workers[worker_candidates[0][0]]
                                self.debug("Selected worker %s (%s:%s)", worker.uuid, worker.get("host"), worker.get("port"))
                                try:
                                    self.call("cluster.query_server", worker.get("host"), worker.get("port"), "/realplexor/daemon")
                                except Exception as e:
                                    self.error("Error during spawning daemon: %s", e)
                            else:
                                self.debug("No workers of the class %s where to run daemons", "metagam")
                timer += 1
                if timer > 30:
                    lst = self.objlist(DaemonStatusList, query_index="updated", query_finish=self.now(-120))
                    if len(lst):
                        self.debug("Removing stale daemon statuses: %s" % lst.uuids())
                        lst.remove()
                        self.check_daemons = True
                    timer = 0
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

    def ping_results(self, host, port, res):
        self.debug("ping results: %s, %s, %s" % (host, port, res))

    def registering_server(self, server_id, conf):
        self.debug("Registering server %s", server_id)
        lst = self.objlist(DaemonStatusList, query_index="server_id", query_equal=server_id)
        if len(lst):
            self.debug("Removing daemon statuses due to %s restart: %s", server_id, lst.uuids())
            lst.remove()
        self.check_daemons = True

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
        try:
            func()
        finally:
            if tasklet.name == "main":
                self.int_app().hooks.call("daemon.stop", self)
                for n, t in self.tasklets.items():
                    if n != "main":
                        t.kill()
            del self.tasklets[tasklet.name]

    def fastidle(self):
        "Called regularly in the main cycle"
        pass
