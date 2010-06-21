from mg.srv.common import WebDaemon, WebApplication
from concurrence import Tasklet
from mg.stor.db import DatabasePool
from mg.stor.mc import MemcachedPool, Memcached

class Director(WebDaemon):
    "Director receives announces from Servers and manages all Servers"
    
    def __init__(self, inst):
        app = WebApplication(inst, DatabasePool(hosts=(("director-db", 9160),)), "director", Memcached(pool=MemcachedPool(host=("director-mc", 11211)), prefix="dir_"))
        app.modules.load(["db.CommonDatabaseStruct", "director.Director"])
        app.dbrestruct()
        WebDaemon.__init__(self, inst, app)

    def run(self):
        self.serve(("0.0.0.0", 3000))

