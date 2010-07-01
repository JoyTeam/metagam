from mg.core import Module
from mg.web import WebDaemon, WebApplication
from mg.memcached import Memcached
import re
import mg.core

class Worker(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.cass.CommonDatabaseStruct", "mg.cluster.Cluster", "mg.web.Web"])

class ApplicationFactory(mg.core.ApplicationFactory):
    """
    ApplicationFactory implementation based on config and database search
    """
    def __init__(self, inst, dbpool, mcpool):
        mg.core.ApplicationFactory.__init__(self, inst)
        self.dbpool = dbpool
        self.mcpool = mcpool

    def get(self, tag):
        if tag == "metagam":
            app = WebApplication(self.inst, self.dbpool, "metagam", Memcached(self.mcpool, prefix="mg_"), "ext")
            app.modules.load(["mg.mainsite.MainSite"])
            return app

class MultiapplicationWebDaemon(WebDaemon):
    "This is a WebDaemon that accesses application depending on HTTP host"
    def __init__(self, inst, dbpool, mcpool):
        """
        inst - Instance reference
        dbpool - DatabasePool reference
        mcpool - MemcachedPool reference
        """
        WebDaemon.__init__(self, inst)
        self.dbpool = dbpool
        self.mcpool = mcpool
        self.metagam_host = self.inst.config["metagam_host"]

    def req_handler(self, request, group, hook, args):
        host = request.environ.get("HTTP_X_REAL_HOST")
        if host is None:
            return request.response("X-Real-Host HTTP header not configured")
        host = host.lower()
        app = None
        if host == self.metagam_host:
            app = self.inst.appfactory.get("metagam")
        if app is None:
            return request.redirect("http://%s" % str(self.metagam_host))
        app.hooks.call("l10n.set_request_lang", request)
        return app.http_request(request, group, hook, args)
