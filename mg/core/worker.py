from mg import *
from concurrence import Tasklet
from mg.core.classes import *
import json
import time

class Worker(Module):
    def register(self):
        self.rdep(["mg.core.cluster.Cluster", "mg.core.web.Web", "mg.core.queue.Queue", "mg.core.daemons.DaemonsManager", "mg.core.dbexport.Export"])
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("worker.run", self.run)
        self.rhook("core.appfactory", self.appfactory, priority=-10)
        self.rhook("core.webdaemon", self.webdaemon, priority=-10)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("core.application_reloaded", self.application_reloaded)
        self.rhook("core.reloading_hard", self.reloading_hard)
        self.rhook("web.active_requests", self.active_requests)
        self.last_status = None

    def objclasses_list(self, objclasses):
        objclasses["WorkerStatus"] = (WorkerStatus, WorkerStatusList)

    def appfactory(self):
        raise Hooks.Return(ApplicationFactory(self.app().inst))

    def webdaemon(self):
        raise Hooks.Return(WebDaemon(self.app().inst))

    def application_reloaded(self):
        self.app().inst.application_version = self.conf("application.version", 0)
        self.store_status()

    def fastidle(self):
        self.call("core.check_last_ping")
        now = time.time()
        if self.last_status is None or now > self.last_status + 120:
            self.last_status = now
            self.store_status()

    def active_requests(self, active_requests):
        inst = self.app().inst
        active_requests["web"] = inst.int_daemon.active_requests + inst.ext_daemon.active_requests

    def store_status(self):
        inst = self.app().inst
        obj = self.obj(WorkerStatus, inst.server_id, {}, silent=True)
        obj.set("accept_daemons", inst.accept_daemons)
        obj.set("updated", self.now())
        obj.set("performance", 0)
        obj.set("host", inst.int_host)
        obj.set("port", inst.int_port)
        obj.set("cls", inst.cls)
        obj.set("ver", self.app().inst.application_version)
        active_requests = {}
        self.call("web.active_requests", active_requests)
        obj.set("active_requests", active_requests)
        try:
            if self.app().inst.reloading_hard:
                obj.set("reloading", True)
        except AttributeError:
            pass
        obj.store()

    def reloading_hard(self):
        self.app().inst.reloading_hard = True
        self.store_status()

    def run(self, cls, parent="", id="", ext_app=None):
        inst = self.app().inst
        inst.cls = cls
        inst.accept_daemons = True
        inst.active_web_requests = 0
        inst.int_daemon = WebDaemon(inst, self.app())
        inst.int_port = inst.int_daemon.serve_any_port("0.0.0.0")
        # application factory
        inst.appfactory = self.call("core.appfactory")
        inst.appfactory.add(self.app())
        # external daemon
        inst.ext_daemon = self.call("core.webdaemon")
        inst.ext_port = inst.ext_daemon.serve_any_port("0.0.0.0")
        inst.ext_daemon.app = ext_app
        if ext_app:
            inst.appfactory.add(ext_app)
        inst.application_version = self.conf("application.version", 0)
        # registering
        params = {
            "type": "worker",
            "port": inst.int_port,
            "parent": parent,
            "id": id,
            "params": {
                "ext_port": inst.ext_port,
                "class": cls,
            },
        }
        self.call("core.worker_params", params)
        params["params"] = json.dumps(params["params"])
        res = self.call("cluster.query_director", "/director/ready", params)
        # background tasks
        inst.set_server_id(res["server_id"], re.sub(r'^\d+\.\d+\.\d+\.\d+-server-\d+-', '', res["server_id"]))
        inst.int_host = res["host"]
        while True:
            try:
                self.call("core.fastidle")
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(1)
