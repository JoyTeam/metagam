from mg import *
import mg.core
import re

class Project(CassandraObject):
    _indexes = {
        "created": [[], "created"],
        "inactive": [["inactive"], "created"],
        "owner": [["owner"], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Project-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Project._indexes

class ProjectList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Project-"
        kwargs["cls"] = Project
        CassandraObjectList.__init__(self, *args, **kwargs)

    def tag_by_domain(self, domain):
        tag = super(ApplicationFactory, self).tag_by_domain(domain)
        if tag is not None:
            return tag
        m = re.match("^([0-9a-f]{32})\.%s" % self.inst.config["main_host"], domain)
        if m:
            return m.groups(1)[0]
        return None

class ApplicationFactory(mg.core.ApplicationFactory):
    """
    ApplicationFactory implementation based on config and database search
    """
    def __init__(self, inst):
        super(ApplicationFactory, self).__init__(inst)
        self.apps_by_domain = {}

    def tag_by_domain(self, domain):
        if domain is None:
            return None
        main_host = self.inst.config["main_host"]
        if domain == "www.%s" % main_host:
            return "main"
        elif domain == main_host:
            return "main"
        m = re.match("^([0-9a-f]{32})\.%s" % main_host, domain)
        if m:
            return m.groups(1)[0]
        return None

    def get_by_domain(self, domain):
        tag = self.tag_by_domain(domain)
        if tag is None:
            return None
        return self.get_by_tag(tag)

    def load(self, tag):
        if tag == "main":
            app = WebApplication(self.inst, tag, "ext")
            app.domain = self.inst.config["main_host"]
            app.modules.load(["mg.constructor.mod.Constructor"])
            return app
        try:
            project = self.inst.int_app.obj(Project, tag)
        except ObjectNotFoundException:
            project = None
        if project:
            domain = project.get("domain")
            if domain is None:
                domain = "%s.%s" % (tag, self.inst.config["main_host"])
            app = WebApplication(self.inst, tag, "ext")
            app.domain = domain
            app.project = project
            app.modules.load(["mg.constructor.mod.ConstructorProject"])
            return app
        return None

    def add(self, app):
        super(ApplicationFactory, self).add(app)
        try:
            self.apps_by_domain[app.domain] = app
        except AttributeError:
            pass

    def remove(self, app):
        super(ApplicationFactory, self).remove(app)
        try:
            del self.apps_by_domain[app.domain]
        except KeyError:
            pass
        except AttributeError:
            pass

class MultiapplicationWebDaemon(WebDaemon):
    "This is a WebDaemon that accesses application depending on HTTP host"
    def req_handler(self, request, group, hook, args):
        host = request.host()
        app = self.inst.appfactory.get_by_domain(host)
        if app is None:
            return request.redirect("http://www.%s" % str(self.inst.config["main_host"]))
        #app.hooks.call("l10n.set_request_lang")
        return app.http_request(request, group, hook, args)
