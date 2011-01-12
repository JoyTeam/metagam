from mg import *
from mg.core.auth import User, UserPermissions, Session, UserList, SessionList, UserPermissionsList
from mg.core.queue import QueueTask, QueueTaskList, Schedule
from mg.core.cluster import TempFileList
import mg.constructor.common
from mg.constructor.common import Project, ProjectList
from uuid import uuid4
import time
import datetime

class ConstructorUtils(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-top.list", self.menu_admin_top_list, priority=-500)

    def menu_admin_top_list(self, topmenu):
        topmenu.append({"href": "http://www.%s/forum" % self.app().inst.config["main_host"], "text": self._("Forum"), "tooltip": self._("Go to the Constructor forum")})
        topmenu.append({"href": "http://www.%s/cabinet" % self.app().inst.config["main_host"], "text": self._("Cabinet"), "tooltip": self._("Return to the Cabinet")})

class Constructor(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.web.Web"])
        self.rdep(["mg.socio.Socio", "mg.socio.Forum", "mg.admin.AdminInterface", "mg.socio.ForumAdmin",
            "mg.core.auth.Sessions", "mg.core.auth.Interface", "mg.core.cluster.Cluster",
            "mg.core.emails.Email", "mg.core.queue.Queue", "mg.core.cass_maintenance.CassandraMaintenance", "mg.admin.wizards.Wizards",
            "mg.constructor.ConstructorUtils", "mg.game.money.Money", "mg.constructor.dashboard.ProjectDashboard",
            "mg.constructor.domains.Domains", "mg.game.money.TwoPay", "mg.constructor.design.SocioInterface"])
        self.rhook("web.setup_design", self.web_setup_design)
        self.rhook("ext-index.index", self.index)
        self.rhook("ext-cabinet.index", self.cabinet_index)
        self.rhook("auth.redirects", self.redirects)
        self.rhook("ext-cabinet.settings", self.cabinet_settings)
        self.rhook("ext-documentation.index", self.documentation_index)
        self.rhook("ext-debug.validate", self.debug_validate)
        self.rhook("ext-constructor.newgame", self.constructor_newgame)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("applications.list", self.applications_list)
        self.rhook("all.schedule", self.schedule)
        self.rhook("projects.cleanup_inactive", self.cleanup_inactive)
        self.rhook("core.appfactory", self.appfactory)
        self.rhook("core.webdaemon", self.webdaemon)
        self.rhook("project.title", self.project_title)
        self.rhook("forum-admin.init-categories", self.forum_init_categories)
        self.rhook("projects.list", self.projects_list)
        self.rhook("projects.owned_by", self.projects_owned_by)
        self.rhook("project.cleanup", self.cleanup)
        self.rhook("project.missing", self.missing)
        self.rhook("web.universal_variables", self.universal_variables)

    def missing(self, tag):
        app = self.app().inst.appfactory.get_by_tag(tag)
        return app is None

    def forum_init_categories(self, cats):
        cats.append({"id": uuid4().hex, "topcat": self._("Constructor"), "title": self._("News"), "description": self._("News related to the Constructor"), "order": 10.0, "default_subscribe": True})
        cats.append({"id": uuid4().hex, "topcat": self._("Constructor"), "title": self._("Support"), "description": self._("Constructor technical support"), "order": 20.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Game Development"), "title": self._("Developers club"), "description": self._("Any talks related to the game development"), "order": 30.0})

    def project_title(self):
        return "MMO Constructor"

    def appfactory(self):
        raise Hooks.Return(mg.constructor.common.ApplicationFactory(self.app().inst))

    def webdaemon(self):
        raise Hooks.Return(mg.constructor.common.MultiapplicationWebDaemon(self.app().inst))

    def objclasses_list(self, objclasses):
        objclasses["Project"] = (Project, ProjectList)

    def applications_list(self, apps):
        apps.append("main")
        projects = self.app().inst.int_app.objlist(ProjectList, query_index="created")
        apps.extend(projects.uuids())

    def projects_list(self, projects):
        projects.append({"uuid": "main"})
        list = self.app().inst.int_app.objlist(ProjectList, query_index="created")
        list.load(silent=True)
        projects.extend(list.data())

    def projects_owned_by(self, owner, projects):
        list = self.app().inst.int_app.objlist(ProjectList, query_index="owner", query_equal=owner)
        list.load(silent=True)
        projects.extend(list.data())

    def schedule(self, sched):
        sched.add("projects.cleanup_inactive", "10 1 * * *", priority=10)

    def cleanup_inactive(self):
        inst = self.app().inst
        projects = inst.int_app.objlist(ProjectList, query_index="inactive", query_equal="1", query_finish=self.now(-30 * 86400))
        for project in projects:
            self.info("Removing inactive project %s", project.uuid)
            self.call("project.cleanup", project.uuid)

    def web_setup_design(self, vars):
        req = self.req()
        topmenu = []
        cabmenu = []
        if vars.get("global_html"):
            return
        if req.group == "index" and req.hook == "index":
            vars["global_html"] = "constructor/index_global.html"
        elif req.group == "auth":
            if req.hook == "change" or req.hook == "email":
                vars["global_html"] = "constructor/cabinet_global.html"
                vars["ToTheMainPage"] = self._("To the main page")
                if req.hook == "change":
                    cabmenu.append({"title": self._("Password changing"), "left": True})
                elif req.hook == "email":
                    cabmenu.append({"title": self._("E-mail changing"), "left": True})
                cabmenu.append({"image": "/st/constructor/cabinet/settings.gif", "title": self._("Return to the Settings"), "href": "/cabinet/settings"})
            else:
                vars["global_html"] = "constructor/index_global.html"
        elif req.group == "cabinet":
            vars["global_html"] = "constructor/cabinet_global.html"
            vars["ToTheMainPage"] = self._("To the main page")
            if req.hook == "settings":
                cabmenu.append({"title": self._("Settings"), "left": True})
                cabmenu.append({"title": self._("Return to the Cabinet"), "href": "/cabinet", "image": "/st/constructor/cabinet/constructor.gif"})
            elif req.hook == "index":
                cabmenu.append({"image": "/st/constructor/cabinet/doc.gif", "title": self._("Documentation"), "href": "/documentation", "left": True})
                cabmenu.append({"image": "/st/constructor/cabinet/settings.gif", "title": self._("Settings"), "href": "/cabinet/settings", "left": True})
                cabmenu.append({"image": "/st/constructor/cabinet/forum.gif", "title": self._("Forum"), "href": "/forum", "left": True})
                cabmenu.append({"image": "/st/constructor/cabinet/logout.gif", "title": self._("Logout"), "href": "/auth/logout"})
        elif req.group == "forum":
            vars["global_html"] = "constructor/socio_global.html"
            redirect = req.param("redirect")
            redirect_param = True
            if redirect is None or redirect == "":
                redirect = req.uri()
                redirect_param = False
            redirect = urlencode(redirect)
            if req.hook == "settings":
                pass
            else:
                topmenu.append({"search": True, "button": self._("socio-top///Search")})
                if req.user():
                    topmenu.append({"href": "/forum/settings?redirect=%s" % redirect, "image": "/st/constructor/cabinet/settings.gif", "html": self._("Forum settings")})
                    topmenu.append({"href": "/cabinet", "image": "/st/constructor/cabinet/constructor.gif", "html": self._("Return to the Cabinet")})
                else:
                    topmenu.append({"href": "/auth/login?redirect=%s" % redirect, "html": self._("Log in")})
                    topmenu.append({"href": "/auth/register?redirect=%s" % redirect, "html": self._("Register")})
            if redirect_param:
                topmenu.append({"href": htmlescape(req.parama("redirect")), "html": self._("Cancel")})
        elif req.group == "documentation":
            vars["global_html"] = "constructor/socio_global.html"
            topmenu.append({"href": "/cabinet", "image": "/st/constructor/cabinet/constructor.gif", "html": self._("Return to the Cabinet")})
            topmenu.append({"html": self._("MMO Constructor Documentation"), "header": True, "left": True})
        elif req.group == "admin":
            vars["global_html"] = "constructor/admin_global.html"
        # Topmenu
        if len(topmenu):
            topmenu_left = []
            topmenu_right = []
            first_left = True
            first_right = True
            for ent in topmenu:
                if ent.get("left"):
                    if first_left:
                        first_left = False
                    else:
                        topmenu_left.append({"delim": True})
                    topmenu_left.append(ent)
                else:
                    if first_right:
                        first_right = False
                    else:
                        topmenu_right.append({"delim": True})
                    topmenu_right.append(ent)
            if len(topmenu_left):
                vars["topmenu_left"] = topmenu_left
            if len(topmenu_right):
                vars["topmenu_right"] = topmenu_right
        # Cabmenu
        if len(cabmenu):
            cabmenu_left = []
            cabmenu_right = []
            first_left = True
            first_right = True
            for ent in cabmenu:
                ent["delim"] = True
                if ent.get("left"):
                    cabmenu_left.append(ent)
                else:
                    cabmenu_right.append(ent)
            if len(cabmenu_left):
                vars["cabmenu_left"] = cabmenu_left
                cabmenu_left[-1]["delim"] = False
            if len(cabmenu_right):
                vars["cabmenu_right"] = cabmenu_right
                cabmenu_right[-1]["delim"] = False

    def universal_variables(self, vars):
        vars["ConstructorTitle"] = self._("Browser-based Games Constructor")
        vars["ConstructorCopyright"] = self._("Copyright &copy; Joy Team, 2009-%s") % datetime.datetime.utcnow().strftime("%Y")

    def redirects(self, tbl):
        tbl["login"] = "/cabinet"
        tbl["register"] = "/cabinet"
        tbl["change"] = "/cabinet/settings"

    def index(self):
        req = self.req()
        vars = {
            "title": self._("Constructor of browser-based online games"),
            "login": self._("log in"),
            "register": self._("register"),
            "forum": self._("forum"),
            "cabinet": self._("cabinet"),
            "logout": self._("log out"),
        }
        if req.user():
            vars["logged"] = True
        self.call("web.response_template", "constructor/index.html", vars)

    def cabinet_index(self):
        req = self.req()
        session = self.call("session.require_login")
        menu = []
        menu_projects = []
        # constructor admin
        perms = req.permissions()
        if len(perms):
            menu_projects.append({"href": "/admin", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Constructor administration")})
        # list of games
        projects = self.app().inst.int_app.objlist(ProjectList, query_index="owner", query_equal=req.user())
        projects.load(silent=True)
        if len(projects):
            for project in projects:
                title = project.get("title_short")
                if title is None:
                    title = self._("Untitled game")
                domain = project.get("domain")
                if domain is None:
                    domain = "%s.%s" % (project.uuid, self.app().inst.config["main_host"])
                else:
                    domain = "www.%s" % domain
                logo = project.get("logo")
                if logo is None:
                    logo = "/st/constructor/cabinet/untitled.gif"
                menu_projects.append({"href": "http://%s/admin" % domain, "image": logo, "text": title})
                if len(menu_projects) >= 4:
                    menu.append(menu_projects)
                    menu_projects = []
        if len(menu_projects):
            menu.append(menu_projects)
        vars = {
            "title": self._("Cabinet"),
            "cabinet_menu": menu if len(menu) else None,
            "cabinet_leftbtn": {
                "href": "/constructor/newgame",
                "title": self._("Create a new game")
            },
        }
        self.call("web.response_global", None, vars)

    def cabinet_settings(self):
        session = self.call("session.require_login")
        vars = {
            "title": self._("MMO Constructor Settings"),
            "cabinet_menu": [
                [
                    { "href": "/auth/change", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Change password") },
                    { "href": "/auth/email", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Change e-mail") },
                    { "href": "/forum/settings?redirect=/cabinet/settings", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Forum settings") },
                    { "href": "/constructor/certificate", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("WebMoney Certification") },
                ],
            ],
        }
        self.call("web.response_global", None, vars)

    def documentation_index(self):
        session = self.call("session.require_login")
        vars = {
            "title": self._("MMO Constructor Documentation"),
        }
        self.call("web.response_template", "constructor/documentation.html", vars)

    def debug_validate(self):
        slices_list = self.call("cassmaint.load_database")
#        for slice in slices_list:
#            self.debug("KEY: %s", slice.key)
        inst = self.app().inst
        valid_keys = inst.int_app.hooks.call("cassmaint.validate", slices_list)
        slices_list = [row for row in slices_list if row.key not in valid_keys]
        apps = []
        self.call("applications.list", apps)
        for tag in apps:
            self.debug("validating application %s", tag)
            app = inst.appfactory.get_by_tag(tag)
            if app is not None:
                valid_keys = app.hooks.call("cassmaint.validate", slices_list)
                slices_list = [row for row in slices_list if row.key not in valid_keys]
        clock = Clock(time.time() * 1000)
        mutations = {}
        for row in slices_list:
            if len(row.columns):
                self.warning("Unknown database key %s", row.key)
                mutations[row.key] = {"Objects": [Mutation(deletion=Deletion(clock=clock))]}
#        if len(mutations):
#            self.db().batch_mutate(mutations, ConsistencyLevel.QUORUM)
        self.call("web.response_json", {"ok": 1})

    def constructor_newgame(self):
        self.call("session.require_login")
        req = self.req()
        inst = self.app().inst
        # creating new project and application
        int_app = inst.int_app
        project = int_app.obj(Project)
        project.set("created", self.now())
        project.set("owner", req.user())
        project.set("inactive", 1)
        project.store()
        # accessing new application
        app = inst.appfactory.get_by_tag(project.uuid)
        # setting up everything
        app.hooks.call("all.check")
        # creating admin user
        old_user = self.obj(User, req.user())
        new_user = app.obj(User)
        new_user.set("created", "%020d" % time.time())
        for field in ["name", "name_lower", "sex", "email", "salt", "pass_reminder", "pass_hash"]:
            new_user.set(field, old_user.get(field))
        new_user.set("inactive", 1)
        activation_code = uuid4().hex
        new_user.set("activation_code", activation_code)
        new_user.set("activation_redirect", "/admin")
        new_user.store()
        # giving permissions
        perms = app.obj(UserPermissions, new_user.uuid, {"perms": {"project.admin": True}})
        perms.sync()
        perms.store()
        # creating setup wizard
        app.hooks.call("wizards.new", "mg.constructor.setup.ProjectSetupWizard")
        self.call("web.redirect", "http://%s/auth/activate/%s?ok=1&code=%s" % (app.domain, new_user.uuid, activation_code))

    def cleanup(self, tag):
        inst = self.app().inst
        int_app = inst.int_app
        app = inst.appfactory.get_by_tag(tag)
        tasks = int_app.objlist(QueueTaskList, query_index="app-at", query_equal=tag)
        tasks.remove()
        sched = int_app.obj(Schedule, tag, silent=True)
        sched.remove()
        project = int_app.obj(Project, tag, silent=True)
        project.remove()
        if app is not None:
            sessions = app.objlist(SessionList, query_index="valid_till")
            sessions.remove()
            users = app.objlist(UserList, query_index="created")
            users.remove()
            perms = app.objlist(UserPermissionsList, users.uuids())
            perms.remove()
            config = app.objlist(ConfigGroupList, query_index="all")
            config.remove()
            hook_modules = app.objlist(HookGroupModulesList, query_index="all")
            hook_modules.remove()
            wizards = app.objlist(WizardConfigList, query_index="all")
            wizards.remove()
        temp_files = int_app.objlist(TempFileList, query_index="app", query_equal=tag)
        temp_files.load(silent=True)
        for file in temp_files:
            file.delete()
        temp_files.remove()

