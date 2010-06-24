from mg.srv.common import WebDaemon, WebApplication
from concurrence import Tasklet
from mg.stor.db import DatabasePool
from mg.stor.mc import MemcachedPool, Memcached

class Server(WebDaemon):
    "A web server starting on every node and handling server requests: 'spawn', 'kill', etc"

    def __init__(self, inst):
        # TODO: ask director about application configuration (database address, memcached address etc)
        app = WebApplication(inst, DatabasePool(hosts=(("director-db", 9160),)), "director", Memcached(pool=MemcachedPool(host=("director-mc", 11211)), prefix="dir_"), "int")
        app.modules.load(["db.CommonDatabaseStruct", "director.Director"])
        app.dbrestruct()
        WebDaemon.__init__(self, inst, app)

    def run(self):
        self.serve(("0.0.0.0", 3000))
