from mg import *
from concurrence import Tasklet
import sys
import json

class Worker(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.cass_struct.CommonCassandraStruct", "mg.core.cluster.Cluster", "mg.core.web.Web", "mg.core.queue.Queue", "mg.core.cass_maintenance.CassandraMaintenance"])
        modules = self.app().inst.config.get("modules")
        if modules:
            self.rdep(modules)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("worker.run", self.run)
        self.rhook("core.appfactory", self.appfactory, priority=-10)
        self.rhook("core.webdaemon", self.webdaemon, priority=-10)

    def appfactory(self):
        raise Hooks.Return(ApplicationFactory(self.app().inst))

    def webdaemon(self):
        raise Hooks.Return(WebDaemon(self.app().inst))

    def fastidle(self):
        self.call("core.check_last_ping")

    def run(self, cls, ext_app=None):
        inst = self.app().inst
        int_daemon = WebDaemon(inst, self.app())
        int_port = int_daemon.serve_any_port("0.0.0.0")
        # application factory
        inst.appfactory = self.call("core.appfactory")
        inst.appfactory.add(self.app())
        # external daemon
        ext_daemon = self.call("core.webdaemon")
        ext_port = ext_daemon.serve_any_port("0.0.0.0")
        ext_daemon.app = ext_app
        # registering
        res = self.call("cluster.query_director", "/director/ready", {
            "type": "worker",
            "port": int_port,
            "parent": sys.argv[1],
            "id": sys.argv[2],
            "params": json.dumps({
                "ext_port": ext_port,
                "class": cls,
            }),
        })
        # background tasks
        inst.set_server_id(res["server_id"], re.sub(r'^\d+\.\d+\.\d+\.\d+-server-\d+-', '', res["server_id"]))
        while True:
            try:
                self.call("core.fastidle")
            except (SystemExit, TaskletExit, KeyboardInterrupt):
                raise
            except BaseException as e:
                self.exception(e)
            Tasklet.sleep(1)
