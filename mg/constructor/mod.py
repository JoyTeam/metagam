from mg import *
from mg.core.auth import User, UserPermissions, Session, UserList, SessionList, UserPermissionsList
from mg.core.queue import QueueTask, QueueTaskList, Schedule
import mg.constructor
from mg.constructor import Project, ProjectList
from uuid import uuid4
import re
import time

class ConstructorUtils(Module):
    def register(self):
        Module.register(self)
        self.rhook("project.cleanup", self.cleanup)
        self.rhook("project.missing", self.missing)
        self.rhook("menu-admin-root.index", self.menu_root_index, priority=500)
        self.rhook("ext-admin-cabinet.index", self.admin_cabinet)

    def menu_root_index(self, menu):
        menu.append({"id": "cabinet/index", "text": self._("Return to the cabinet"), "leaf": True})

    def admin_cabinet(self):
        self.call("web.response_json", {"redirect_top": "http://www.%s/cabinet" % self.app().inst.config["main_host"]})

    def missing(self, tag):
        app = self.app().inst.appfactory.get_by_tag(tag)
        return app is None

    def cleanup(self, tag):
        inst = self.app().inst
        app = inst.appfactory.get_by_tag(tag)
        if app is not None:
            sessions = app.objlist(SessionList, query_index="valid_till")
            self.debug("Removing sessions: %s", sessions)
            sessions.remove()
            users = app.objlist(UserList, query_index="created")
            self.debug("Removing users: %s", users)
            users.remove()
            perms = app.objlist(UserPermissionsList, users.uuids())
            perms.remove()
            wizards = app.objlist(WizardConfigList, query_index="all")
            self.debug("Removing wizards: %s", wizards)
            wizards.remove()
            config = app.objlist(ConfigGroupList, query_index="all")
            self.debug("Removing config groups: %s", config)
            config.remove()
        int_app = inst.int_app
        tasks = int_app.objlist(QueueTaskList, query_index="app-at", query_equal=tag)
        self.debug("Removing tasks: %s", tasks)
        tasks.remove()
        sched = int_app.obj(Schedule, tag, silent=True)
        sched.remove()
        project = int_app.obj(Project, tag, silent=True)
        project.remove()

class ConstructorProject(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.web.Web", "mg.admin.AdminInterface", "mg.core.auth.PasswordAuthentication", "mg.core.auth.CookieSession",
            "mg.core.cluster.Cluster", "mg.core.auth.Authorization", "mg.core.emails.Email", "mg.core.queue.Queue",
            "mg.core.cass_maintenance.CassandraMaintenance", "mg.core.wizards.Wizards", "mg.constructor.mod.ConstructorProjectAdmin",
            "mg.constructor.mod.ConstructorUtils"])
        self.rhook("web.global_html", self.web_global_html)
        self.rhook("permissions.list", self.permissions_list)

    def web_global_html(self):
        return "constructor/global.html"

    def permissions_list(self, perms):
        perms.append({"id": "project.admin", "name": self._("Project main administrator")})

class ConstructorProjectAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index, priority=-500)
        self.rhook("ext-admin-project.destroy", self.project_destroy)

    def menu_root_index(self, menu):
        req = self.req()
        if self.app().project.get("inactive") and req.has_access("project.admin"):
            menu.append({"id": "project/destroy", "text": self._("Destroy this project"), "leaf": True})

    def project_destroy(self):
        self.call("session.require_permission", "project.admin")
        if self.app().project.get("inactive"):
            self.call("project.cleanup", self.app().project.uuid)
        self.call("web.response_json", {"redirect_top": "http://www.%s/cabinet" % self.app().inst.config["main_host"]})

class Constructor(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.web.Web", "mg.socio.Socio", "mg.socio.Forum", "mg.admin.AdminInterface", "mg.socio.ForumAdmin",
            "mg.core.auth.PasswordAuthentication", "mg.core.auth.CookieSession", "mg.core.cluster.Cluster", "mg.core.auth.Authorization",
            "mg.core.emails.Email", "mg.core.queue.Queue", "mg.core.cass_maintenance.CassandraMaintenance", "mg.core.wizards.Wizards",
            "mg.constructor.mod.ConstructorUtils"])
        self.rhook("web.global_html", self.web_global_html)
        self.rhook("ext-index.index", self.index)
        self.rhook("ext-cabinet.index", self.cabinet_index)
        self.rhook("auth.redirects", self.redirects)
        self.rhook("forum.topmenu", self.forum_topmenu)
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

    def appfactory(self):
        raise Hooks.Return(mg.constructor.ApplicationFactory(self.app().inst))

    def webdaemon(self):
        raise Hooks.Return(mg.constructor.MultiapplicationWebDaemon(self.app().inst))

    def objclasses_list(self, objclasses):
        objclasses["Project"] = (Project, ProjectList)

    def applications_list(self, apps):
        apps.append("main")
        projects = self.app().inst.int_app.objlist(ProjectList, query_index="created")
        apps.extend(projects.uuids())

    def schedule(self, sched):
        sched.add("projects.cleanup_inactive", "10 1 * * *", priority=10)

    def cleanup_inactive(self):
        inst = self.app().inst
        projects = inst.int_app.objlist(ProjectList, query_index="inactive", query_equal="1", query_finish=self.now(-3 * 86400))
        for project in projects:
            self.info("Removing inactive project %s", project.uuid)
            self.call("project.cleanup", project.uuid)

    def web_global_html(self):
        return "constructor/global.html"

    def redirects(self, tbl):
        tbl["login"] = "/cabinet"
        tbl["register"] = "/cabinet"
        tbl["change"] = "/cabinet/settings"

    def forum_topmenu(self, topmenu):
        req = self.req()
        redirect = req.param("redirect")
        redirect_param = True
        if redirect is None or redirect == "":
            redirect = req.uri()
            redirect_param = False
        redirect = urlencode(redirect)
        if req.user():
            topmenu.append({"href": "/auth/logout?redirect=%s" % redirect, "html": self._("Log out")})
            topmenu.append({"href": "/forum/settings?redirect=%s" % redirect, "html": self._("Settings")})
            topmenu.append({"href": "/cabinet", "html": self._("Cabinet"), "left": True})
            topmenu.append({"href": "/documentation", "html": self._("Documentation"), "left": True})
        else:
            topmenu.append({"href": "/auth/login?redirect=%s" % redirect, "html": self._("Log in")})
            topmenu.append({"href": "/auth/register?redirect=%s" % redirect, "html": self._("Register")})
        if redirect_param:
            topmenu.append({"href": redirect, "html": self._("Cancel")})

    def index(self):
        req = self.req()
        vars = {
            "title": self._("Constructor of browser-based online games"),
            "online_games_constructor": self._("Constructor of browser-based online games"),
            "games_constructor": self._("Games constructor"),
            "slogan": self._("Create the world of your dreams"),
            "login": self._("log in"),
            "register": self._("register"),
            "forum": self._("forum"),
            "cabinet": self._("cabinet"),
            "logout": self._("log out"),
        }
        if req.user():
            vars["logged"] = True
        return self.call("web.response_template", "constructor/index.html", vars)

    def cabinet_index(self):
        req = self.req()
        session = self.call("session.require_login")
        perms = req.permissions()
        menu = []
        menu1 = []
        menu1.append({"href": "/documentation", "image": "constructor/cab_documentation.jpg", "text": self._("Documentation")})
        if len(perms):
            menu1.append({"href": "/admin", "image": "constructor/cab_admin.jpg", "text": self._("Administration")})
        menu1.append({"href": "/forum", "image": "constructor/cab_forum.jpg", "text": self._("Forum")})
        menu1.append({"href": "/cabinet/settings", "image": "constructor/cab_settings.jpg", "text": self._("Settings")})
        menu1.append({"href": "/auth/logout", "image": "constructor/cab_logout.jpg", "text": self._("Log out")})
        menu.append(menu1)
        menu2 = []
        menu2.append({"href": "/constructor/newgame", "image": "constructor/cab_newgame.jpg", "text": self._("New game")})
        menu.append(menu2)
        # list of games
        projects = self.app().inst.int_app.objlist(ProjectList, query_index="owner", query_equal=req.user())
        projects.load(silent=True)
        if len(projects):
            menu_projects = []
            for project in projects:
                title = project.get("title")
                if title is None:
                    title = self._("Untitled game %s") % project.uuid
                domain = project.get("domain")
                if domain is None:
                    domain = "%s.%s" % (project.uuid, self.app().inst.config["main_host"])
                    menu_projects.append({"href": "http://%s/admin" % domain, "image": "constructor/cab_game.jpg", "text": title})
                else:
                    menu_projects.append({"href": "http://%s/" % domain, "image": "constructor/cab_game.jpg", "text": title})
                if len(menu_projects) >= 4:
                    menu.append(menu_projects)
                    menu_projects = []
            if len(menu_projects):
                menu.append(menu_projects)
        vars = {
            "title": self._("Cabinet"),
            "menu": menu,
        }
        self.call("web.response_template", "constructor/cabinet.html", vars)

    def cabinet_settings(self):
        session = self.call("session.require_login")
        vars = {
            "title": self._("Settings"),
            "menu": [
                [
                    { "href": "/cabinet", "image": "constructor/cab_return.jpg", "text": self._("Return to the Cabinet") },
                ],
                [
                    { "href": "/auth/change", "image": "constructor/cab_changepass.jpg", "text": self._("Change password") },
                    { "href": "/auth/email", "image": "constructor/cab_changeemail.jpg", "text": self._("Change e-mail") },
                    { "href": "/forum/settings", "image": "constructor/cab_forumsettings.jpg", "text": self._("Forum settings") },
                    { "href": "/constructor/certificate", "image": "constructor/cab_certificate.jpg", "text": self._("WebMoney Certification") },
                ],
            ],
        }
        self.call("web.response_template", "constructor/cabinet.html", vars)

    def documentation_index(self):
        session = self.call("session.require_login")
        vars = {
            "title": self._("Documentation"),
            "menu": [
                [
                    { "href": "/cabinet", "image": "constructor/cab_return.jpg", "text": self._("Return to the Cabinet") },
                ],
            ],
        }
        self.call("web.response_template", "constructor/documentation.html", vars)

    def debug_validate(self):
        slices_list = self.call("cassmaint.load_database")
        inst = self.app().inst
        valid_keys = inst.int_app.hooks.call("cassmaint.validate", slices_list)
        slices_list = [row for row in slices_list if row.key not in valid_keys]
        apps = []
        self.call("applications.list", apps)
        for tag in apps:
            app = inst.appfactory.get_by_tag(tag)
            if app is not None:
                valid_keys = app.hooks.call("cassmaint.validate", slices_list)
                slices_list = [row for row in slices_list if row.key not in valid_keys]
        clock = Clock(time.time() * 1000)
        mutations = {}
        for row in slices_list:
            if len(row.columns):
                self.warning("Unknown database key %s", row.key)
                #mutations[row.key] = {"Objects": [Mutation(deletion=Deletion(predicate=SlicePredicate(slice_range=SliceRange(start="", finish="")), clock=clock))]}
                mutations[row.key] = {"Objects": [Mutation(deletion=Deletion(clock=clock))]}
#       if len(mutations):
#           self.db().batch_mutate(mutations, ConsistencyLevel.QUORUM)
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
        # creating admin user
        old_user = self.obj(User, req.user())
        new_user = app.obj(User)
        new_user.set("created", "%020d" % time.time())
        new_user.set("name", "admin")
        new_user.set("name_lower", "admin")
        for field in ["sex", "email", "salt", "pass_reminder", "pass_hash"]:
            new_user.set(field, old_user.get(field))
        new_user.store()
        # giving permissions
        perms = app.obj(UserPermissions, new_user.uuid, {"perms": {"project.admin": True}})
        perms.sync()
        perms.store()
        # creating new session
        new_session = app.hooks.call("session.get", create=True, cache=False)
        new_session.set("user", new_user.uuid)
        new_session.store()
        # setting up everything
        app.hooks.call("all.check")
        # creating setup wizard
        app.hooks.call("wizards.new", "mg.constructor.mod.ProjectSetupWizard")
        self.call("web.redirect", "http://%s/admin" % app.domain)

class ProjectSetupWizard(Wizard):
    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Setup wizard"), "leaf": True, "admin_index": True})

    def request(self, cmd):
        self.call("admin.update_menu")
        self.call("admin.response", "ProjectSetupWizard contents<br />wizard=%s<br />app=%s<br />session=%s<br />user=%s" % (self.uuid, self.app().tag, self.req().session().uuid, self.req().user()), {})
