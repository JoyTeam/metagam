from mg.srv.common import WebDaemon, WebApplication
from concurrence import Tasklet
from mg.stor.db import DatabasePool
from mg.stor.mc import MemcachedPool, Memcached
import json

class Server(WebDaemon):
    "A web server starting on every node and handling server requests: 'spawn', 'kill', etc"

    def __init__(self, inst):
        self.cluster_config = self.download_config()
        app = WebApplication(inst, DatabasePool(hosts=self.cluster_config["cassandra"]), "server", Memcached(pool=MemcachedPool(host=self.cluster_config["memcached"][0]), prefix="srv_"), "int")
        app.modules.load(["db.CommonDatabaseStruct", "cluster.Director"])
        app.dbrestruct()
        WebDaemon.__init__(self, inst, app)

    def run(self):
        port = self.serve_any_port("0.0.0.0")
        self.app.hooks.call("director.query", "/director/ready", {
            "type": "server",
            "port": port,
            "params": json.dumps({
               "backend": 1
            })
        })

