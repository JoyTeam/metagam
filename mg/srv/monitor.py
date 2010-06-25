from mg.srv.common import WebDaemon, WebApplication
from concurrence import Tasklet
from mg.stor.db import DatabasePool
from mg.stor.mc import MemcachedPool, Memcached
import json
import traceback

class Monitor(WebDaemon):
    "A web server that checks availability and parameters of every running server"

    def __init__(self, inst):
        self.cluster_config = self.download_config()
        app = WebApplication(inst, DatabasePool(hosts=self.cluster_config["cassandra"]), "director", Memcached(pool=MemcachedPool(host=self.cluster_config["memcached"][0]), prefix="dir_"), "int")
        app.modules.load(["db.CommonDatabaseStruct", "cluster.Director", "monitor.Monitor"])
        app.dbrestruct()
        WebDaemon.__init__(self, inst, app)

    def run(self):
        port = self.serve_any_port("0.0.0.0")
        self.app.hooks.call("director.query", "/director/ready", {
            "type": "monitor",
            "port": port,
            "params": json.dumps({})
        })
        Tasklet.new(self.check)()

    def check(self):
        while True:
            try:
                self.app.hooks.call("monitor.check")
            except:
                traceback.print_exc()
            Tasklet.sleep(10)
