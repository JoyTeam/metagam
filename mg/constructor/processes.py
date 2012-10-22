import mg
from mg.core.web import Request, ApplicationWebService
from weakref import WeakValueDictionary
import re
from mg.core.cass import ObjectNotFoundException
from mg.core.processes import ApplicationFactory
from mg.core.projects import Project
from mg.core.tools import utf2str
from mg.constructor.common import Domain

re_remove_www = re.compile(r'^www.', re.IGNORECASE)

class ConstructorApplicationFactory(ApplicationFactory):
    """
    ApplicationFactory implementation based on config and database search
    """
    def __init__(self, inst):
        ApplicationFactory.__init__(self, inst)
        self.apps_by_domain = WeakValueDictionary()
        # to avoid garbage collection
        self.main_app = self.get_by_tag("main")
        self.main_host = self.main_app.main_host

    def tag_by_domain(self, domain):
        if domain is None:
            return None
        domain = re_remove_www.sub('', domain)
        # main constructor domain
        main_host = self.main_host
        main_app = self.get_by_tag("main")
        if domain == main_host:
            return "main"
        # temporary game domains
        projects_domain = main_app.config.get("constructor.projects-domain", main_host)
        m = re.match("^([0-9a-f]{32})\.%s" % projects_domain, domain)
        if m:
            return str(m.groups(1)[0])
        # permanent game domains
        try:
            domain = main_app.obj(Domain, domain)
        except ObjectNotFoundException:
            pass
        else:
            tag = domain.get("project")
            if tag is not None:
                return str(tag)
        return None

    def get_by_domain(self, domain):
        tag = self.tag_by_domain(domain)
        if tag is None:
            return None
        return self.get_by_tag(tag)

    def load(self, tag):
        if tag == "main":
            app = mg.Application(self.inst, tag)
            app.domain = app.main_host
            app.canonical_domain = "www.%s" % app.domain
            app.modules.load(["mg.constructor.admin.Constructor"])
            return app
        try:
            project = self.inst.int_app.obj(Project, tag)
        except ObjectNotFoundException:
            app = None
        else:
            domain = project.get("domain")
            if domain:
                canonical_domain = "www.%s" % domain
            else:
                main_app = self.get_by_tag("main")
                main_host = self.main_host
                projects_domain = main_app.config.get("constructor.projects-domain", main_host)
                domain = "%s.%s" % (tag, projects_domain)
                canonical_domain = domain
            storage = project.get("storage", 0)
            if storage == 2:
                app = mg.Application(self.inst, tag, storage, utf2str(project.get("keyspace")))
            else:
                app = mg.Application(self.inst, tag, storage)
            app.hooks.dynamic = True
            app.domain = domain
            app.canonical_domain = canonical_domain
            app.project = project
            app.modules.load(["mg.constructor.project.ConstructorProject"])
        return app

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
        ApplicationFactory.add(self, app)
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

class ConstructorWebService(ApplicationWebService):
    "This is a WebService that accesses application depending on HTTP host"
    def req_handler(self, request, group, hook, args):
        host = request.host()
        app = self.inst.appfactory.get_by_domain(host)
        if app is None:
            return request.redirect("//www.%s" % str(self.inst.appfactory.main_host))
        if host != app.canonical_domain:
            if group == "index":
                url = "/"
            else:
                url = "/%s" % group
                if hook != "index":
                    url = "%s/%s" % (url, hook)
                    if args != "":
                        url = "%s/%s" % (url, args)
            return request.redirect("//%s%s" % (app.canonical_domain, url))
        return self.deliver_request(app, request, group, hook, args)

class ConstructorInstance(mg.Instance):
    def init_appfactory(self):
        self._appfactory = ConstructorApplicationFactory(self)

