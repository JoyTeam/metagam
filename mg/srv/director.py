from mg.srv.common import WebDaemon, Application
from concurrence import Tasklet
from mg.stor.db import DatabasePool
from mg.stor.mc import MemcachedPool

class Director(WebDaemon):
    "Director receives announces from Servers and manages all Servers"
    
    def __init__(self, inst):
        WebDaemon.__init__(self, inst)
        self.app = DirectorApplication()

    def run(self):
        self.serve(("0.0.0.0", 3000))

    def req_handler(self, request, group, hook, args):
        return self.app.http_request(request, group, hook, args)

class DirectorApplication(Application):
    def __init__(self):
        Application.__init__(self,
            dbpool=DatabasePool(),
            dbhost="director-db",
            dbname="director",
            mcpool=MemcachedPool(host="director-mc"),
            mcprefix="dir_"
        )
