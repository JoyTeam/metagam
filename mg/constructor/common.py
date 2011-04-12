from mg import *
import mg.core
import re

re_remove_www = re.compile(r'^www.', re.IGNORECASE)

class Domain(CassandraObject):
    _indexes = {
        "all": [[], "created"],
        "user": [["user"], "created"],
        "registered": [["registered"], "created"],
        "project": [["project"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Domain-"
        CassandraObject.__init__(self, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Domain-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Domain._indexes

class DomainList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Domain-"
        kwargs["cls"] = Domain
        CassandraObjectList.__init__(self, *args, **kwargs)

class ApplicationFactory(mg.core.ApplicationFactory):
    """
    ApplicationFactory implementation based on config and database search
    """
    def __init__(self, inst):
        super(ApplicationFactory, self).__init__(inst)
        self.apps_by_domain = WeakValueDictionary()
        # to avoid garbage collection
        self.main_app = self.get_by_tag("main")

    def tag_by_domain(self, domain):
        if domain is None:
            return None
        domain = re_remove_www.sub('', domain)
        main_host = self.inst.config["main_host"]
        if domain == main_host:
            return "main"
        m = re.match("^([0-9a-f]{32})\.%s" % main_host, domain)
        if m:
            return m.groups(1)[0]
        try:
            domain = self.get_by_tag("main").obj(Domain, domain)
        except ObjectNotFoundException:
            pass
        else:
            tag = domain.get("project")
            if tag is not None:
                return tag
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
            app.modules.load(["mg.constructor.admin.Constructor"])
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
            app.hooks.dynamic = True
            app.domain = domain
            app.project = project
            app.modules.load(["mg.constructor.project.ConstructorProject"])
            return app
        return None

    def added(self, app):
        project = getattr(app, "project", None)
        if project:
            ver = self.get_by_tag("int").config.get("application.version", 0)
            if project.get("app_version") != ver:
                with app.lock(["ReconfigureHooks"]):
                    project.load()
                    if project.get("app_version") != ver:
                        app.store_config_hooks(notify=False)
                        project.set("app_version", ver)
                        project.store()
                        app.hooks.call("cluster.appconfig_changed")

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
        try:
            return app.http_request(request, group, hook, args)
        except Exception as e:
            app.hooks.call("exception.report", e)
            raise
