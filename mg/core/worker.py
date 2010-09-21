from mg.core import Module
from mg.core.web import WebDaemon, WebApplication
from mg.core.memcached import Memcached
import re
import mg.core

class Worker(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.cass_struct.CommonCassandraStruct", "mg.core.cluster.Cluster", "mg.core.web.Web", "mg.core.queue.Queue"])
        self.rhook("core.fastidle", self.fastidle)

    def fastidle(self):
        self.call("core.check_last_ping")

class ApplicationFactory(mg.core.ApplicationFactory):
    """
    ApplicationFactory implementation based on config and database search
    """
    def __init__(self, inst, dbpool, mcpool):
        mg.core.ApplicationFactory.__init__(self, inst)
        self.dbpool = dbpool
        self.mcpool = mcpool
        self.apps_by_domain = {}

    def tag_by_domain(self, domain):
        metagam_host = self.inst.config["metagam_host"]
        if domain == "www.%s" % metagam_host:
            return "metagam"
        elif domain == metagam_host:
            return "metagam"
        return None

    def get_by_domain(self, domain):
        tag = self.tag_by_domain(domain)
        if tag is None:
            return None
        return self.get_by_tag(tag)

    def load(self, tag):
        if tag == "metagam":
            app = WebApplication(self.inst, self.dbpool, self.mcpool, tag, "ext")
            app.domain = self.inst.config["metagam_host"]
            app.modules.load(["mg.constructor.Constructor"])
            return app
        return None

    def add(self, app):
        mg.core.ApplicationFactory.add(self, app)
        try:
            self.apps_by_domain[app.domain] = app
        except AttributeError:
            pass

    def remove(self, app):
        ApplicationFactory.remove(self, app)
        try:
            del self.apps_by_domain[app.domain]
        except KeyError:
            pass
        except AttributeError:
            pass

class MultiapplicationWebDaemon(WebDaemon):
    "This is a WebDaemon that accesses application depending on HTTP host"
    def __init__(self, inst, dbpool, mcpool):
        """
        inst - Instance reference
        dbpool - CassandraPool reference
        mcpool - MemcachedPool reference
        """
        WebDaemon.__init__(self, inst)
        self.dbpool = dbpool
        self.mcpool = mcpool

    def req_handler(self, request, group, hook, args):
        host = request.host()
        app = self.inst.appfactory.get_by_domain(host)
        if app is None:
            return request.redirect("http://www.%s" % str(self.inst.config["metagam_host"]))
        #app.hooks.call("l10n.set_request_lang")
        return app.http_request(request, group, hook, args)
