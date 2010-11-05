from mg import *
from mg.core.auth import User, UserPermissions, Session, UserList, SessionList, UserPermissionsList
from mg.core.queue import QueueTask, QueueTaskList, Schedule
from mg.core.cluster import TempFileList
import mg.constructor
from mg.constructor import Project, ProjectList
from uuid import uuid4
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
import re
import time
import cgi
import cStringIO

re_bad_symbols = re.compile(r'.*[\'"<>&\\]')

class ConstructorUtils(Module):
    def register(self):
        Module.register(self)
        self.rhook("project.cleanup", self.cleanup)
        self.rhook("project.missing", self.missing)
        self.rhook("menu-admin-top.list", self.menu_admin_top_list, priority=-500)

    def menu_admin_top_list(self, topmenu):
        topmenu.append({"href": "http://www.%s/forum" % self.app().inst.config["main_host"], "text": self._("Forum"), "tooltip": self._("Go to the Constructor forum")})
        topmenu.append({"href": "http://www.%s/cabinet" % self.app().inst.config["main_host"], "text": self._("Cabinet"), "tooltip": self._("Return to the Cabinet")})

    def missing(self, tag):
        app = self.app().inst.appfactory.get_by_tag(tag)
        return app is None

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
            wizards = app.objlist(WizardConfigList, query_index="all")
            wizards.remove()
        temp_files = int_app.objlist(TempFileList, query_index="app", query_equal=tag)
        temp_files.load(silent=True)
        for file in temp_files:
            file.delete()
        temp_files.remove()

class ConstructorProject(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.web.Web", "mg.admin.AdminInterface", "mg.core.auth.PasswordAuthentication", "mg.core.auth.CookieSession",
            "mg.core.cluster.Cluster", "mg.core.auth.Authorization", "mg.core.emails.Email", "mg.core.queue.Queue",
            "mg.core.cass_maintenance.CassandraMaintenance", "mg.core.wizards.Wizards", "mg.constructor.mod.ConstructorProjectAdmin",
            "mg.constructor.mod.ConstructorUtils"])
        self.rhook("web.global_html", self.web_global_html)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("project.title", self.project_title)
        self.rhook("forum-admin.init-categories", self.forum_init_categories)

    def project_title(self):
        return "New Game"

    def web_global_html(self):
        return "constructor/global.html"

    def permissions_list(self, perms):
        perms.append({"id": "project.admin", "name": self._("Project main administrator")})

    def forum_init_categories(self, cats):
        cats.append({"id": uuid4().hex, "topcat": self._("Game"), "title": self._("News"), "description": self._("Game news published by the administrators"), "order": 10.0, "default_subscribe": True})
        cats.append({"id": uuid4().hex, "topcat": self._("Game"), "title": self._("Game"), "description": self._("Talks about game activities: gameplay, news, wars, politics etc."), "order": 20.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Game"), "title": self._("Newbies"), "description": self._("Dear newbies, if you have any questions about the game, feel free to ask"), "order": 30.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Game"), "title": self._("Diplomacy"), "description": self._("Authorized guild members can talk to each other about diplomacy and politics issues here"), "order": 40.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Admin"), "title": self._("Admin talks"), "description": self._("Discussions with the game administrators. Here you can discuss any issues related to the game itself."), "order": 50.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Admin"), "title": self._("Reference manuals"), "description": self._("Actual reference documents about the game are placed here."), "order": 60.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Admin"), "title": self._("Bug reports"), "description": self._("Report any problems in the game here"), "order": 70.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Reallife"), "title": self._("Smoking room"), "description": self._("Everything not related to the game: humor, forum games, hobbies, sport etc."), "order": 80.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Reallife"), "title": self._("Art"), "description": self._("Poems, prose, pictures, photos, music about the game"), "order": 90.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Trading"), "title": self._("Services"), "description": self._("Any game services: mercenaries, guardians, builders etc."), "order": 100.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Trading"), "title": self._("Market"), "description": self._("Market place to sell and by any item"), "order": 110.0})

class ConstructorProjectAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-top.list", self.menu_top_list, priority=10)
        self.rhook("ext-admin-project.destroy", self.project_destroy)

    def menu_top_list(self, topmenu):
        req = self.req()
        if self.app().project.get("inactive") and req.has_access("project.admin"):
            topmenu.append({"id": "project/destroy", "text": self._("Destroy this game"), "tooltip": self._("You can destroy your game while not created")})

    def project_destroy(self):
        self.call("session.require_permission", "project.admin")
        if self.app().project.get("inactive"):
            self.call("project.cleanup", self.app().project.uuid)
        self.call("admin.redirect_top", "http://www.%s/cabinet" % self.app().inst.config["main_host"])

class Constructor(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.web.Web", "mg.socio.Socio", "mg.socio.Forum", "mg.admin.AdminInterface", "mg.socio.ForumAdmin",
            "mg.core.auth.PasswordAuthentication", "mg.core.auth.CookieSession", "mg.core.cluster.Cluster", "mg.core.auth.Authorization",
            "mg.core.emails.Email", "mg.core.queue.Queue", "mg.core.cass_maintenance.CassandraMaintenance", "mg.core.wizards.Wizards",
            "mg.constructor.mod.ConstructorUtils", "mg.game.money.Money", "mg.constructor.dashboard.ProjectDashboard"])
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
        self.rhook("project.title", self.project_title)
        self.rhook("forum-admin.init-categories", self.forum_init_categories)
        self.rhook("projects.list", self.projects_list)
        self.rhook("projects.owned_by", self.projects_owned_by)

    def forum_init_categories(self, cats):
        cats.append({"id": uuid4().hex, "topcat": self._("Constructor"), "title": self._("News"), "description": self._("News related to the Constructor"), "order": 10.0, "default_subscribe": True})
        cats.append({"id": uuid4().hex, "topcat": self._("Constructor"), "title": self._("Support"), "description": self._("Constructor technical support"), "order": 20.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Game Development"), "title": self._("Developers club"), "description": self._("Any talks related to the game development"), "order": 30.0})

    def project_title(self):
        return "MMO Constructor"

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
                    title = self._("Untitled game")
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
        for slice in slices_list:
            self.debug("KEY: %s", slice.key)
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
    def new(self, **kwargs):
        super(ProjectSetupWizard, self).new(**kwargs)
        self.config.set("state", "intro")
        
    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Setup wizard"), "leaf": True, "admin_index": True, "ord": 10})

    def request(self, cmd):
        req = self.req()
        state = self.config.get("state")
        project = self.app().project
        if state == "intro":
            if cmd == "next":
                self.config.set("state", "offer")
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            vars = {
                "wizard": self.uuid,
                "next_text": jsencode(self._("Next")),
            }
            self.call("admin.advice", {"title": self._("Demo advice"), "content": self._("Look to the right to read some recommendations")})
            self.call("admin.response_template", "constructor/intro-%s.html" % self.call("l10n.lang"), vars)
        elif state == "offer":
            if cmd == "agree":
                self.config.set("state", "name")
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            author = self.app().inst.appfactory.get_by_tag("main").obj(User, project.get("owner"))
            vars = {
                "author": cgi.escape(author.get("name")),
                "wizard": self.uuid,
            }
            self.call("admin.advice", {"title": self._("Law importance"), "content": self._("There are some very important points in the contract. At least read information in the red panel.")})
            self.call("admin.response_template", "constructor/offer-%s.html" % self.call("l10n.lang"), vars)
        elif state == "name":
            if cmd == "name-submit":
                errors = {}
                title_full = req.param("title_full")
                title_short = req.param("title_short")
                title_code = req.param("title_code")

                if not title_full or title_full == "":
                    errors["title_full"] = self._("Enter full title")
                elif len(title_full) > 50:
                    errors["title_full"] = self._("Maximal length - 50 characters")
                elif re_bad_symbols.match(title_full):
                    errors["title_full"] = self._("Bad symbols in the title")

                if not title_short or title_short == "":
                    errors["title_short"] = self._("Enter short title")
                elif len(title_short) > 17:
                    errors["title_short"] = self._("Maximal length - 17 characters")
                elif re_bad_symbols.match(title_short):
                    errors["title_short"] = self._("Bad symbols in the title")

                if not title_code or title_code == "":
                    errors["title_code"] = self._("Enter code")
                elif len(title_code) > 5:
                    errors["title_code"] = self._("Maximal length - 5 characters")
                elif re.match(r'[^a-z0-9A-Z]', title_code):
                    errors["title_code"] = self._("You can use digits and latin letters only")

                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                self.config.set("title_full", title_full)
                self.config.set("title_short", title_short)
                self.config.set("title_code", title_code)
                self.config.set("state", "logo")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            fields = [
                {
                    "name": "title_full",
                    "label": self._("Full title of your game (ex: Eternal Forces: call of daemons)"),
                    "value": self.config.get("title_full"),
                },
                {
                    "name": "title_short",
                    "label": self._("Short title of your game (ex: Eternal Forces)"),
                    "value": self.config.get("title_short"),
                },
                {
                    "name": "title_code",
                    "label": self._("Short abbreviated code of the game (ex: EF)"),
                    "value": self.config.get("title_code"),
                    "inline": True,
                },
            ]
            buttons = [
                {"text": self._("Next"), "url": "admin-wizard/call/%s/name-submit" % self.uuid}
            ]
            self.call("admin.advice", {"title": self._("Choosing titles"), "content": self._("Titles should be short and descriptive. Try to avoid long words, especially in short title. Otherwize you can introduce lines wrapping problems")})
            self.call("admin.form", fields=fields, buttons=buttons)
        elif state == "logo":
            wizs = self.call("wizards.find", "logo")
            if cmd == "upload":
                image = req.param_raw("image")
                if image is None or not len(image):
                    self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Upload logo image")}})
                try:
                    image_obj = Image.open(cStringIO.StringIO(image))
                    if image_obj.load() is None:
                        raise IOError;
                except IOError:
                    self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Image format not recognized")}})
                try:
                    image_obj.seek(1)
                    self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Animated logos are not supported")}})
                except EOFError:
                    pass
                image_obj = image_obj.convert("RGBA")
                width, height = image_obj.size
                if width == 100 and height == 100:
                    image_obj = image_obj.crop((0, 0, 100, 75))
                elif width * 75 >= height * 100:
                    width = width * 75 / height
                    height = 75
                    image_obj = image_obj.resize((width, height), Image.ANTIALIAS)
                    if width != 100:
                        image_obj = image_obj.crop(((width - 100) / 2, 0, (width - 100) / 2 + 100, 75))
                else:
                    height = height * 100 / width
                    width = 100
                    image_obj = image_obj.resize((width, height), Image.ANTIALIAS)
                    if height != 75:
                        image_obj = image_obj.crop((0, (height - 75) / 2, 100, (height - 75) / 2 + 75))
                self.store_logo(image_obj)
                self.call("web.response_json_html", {"success": True, "logo_preview": uri})
            elif cmd == "prev":
                self.config.set("state", "name")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            elif cmd == "constructor":
                if len(wizs):
                    self.call("admin.redirect", "wizard/call/%s" % wizs[0].uuid)
                wiz = self.call("wizards.new", "mg.constructor.logo.LogoWizard", target=["wizard", self.uuid, "constructed", ""], redirect_fail="wizard/call/%s" % self.uuid, title_code=self.config.get("title_code"))
                self.call("admin.redirect", "wizard/call/%s" % wiz.uuid)
            elif cmd == "next":
                if self.config.get("logo"):
                    if len(wizs):
                        for wiz in wizs:
                            wiz.abort()
                self.config.set("state", "domain")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            vars = {
                "GameLogo": self._("Game logo"),
                "HereYouCan": self._("Here you have to create unique logo for your project. You can either upload logo from your computer or create it using Constructor."),
                "FromFile": self._("Alternative 1. Upload logo file"),
                "FromConstructor": self._("Alternative 2. Launch logo constructor"),
                "wizard": self.uuid,
                "logo": self.config.get("logo"),
                "ImageFormat": self._("Upload image: 100x100, without animation"),
                "UploadNote": self._("Note your image will be postprocessed - corners will be rounded, 1px border added, black padding added, title written on the black padding."),
                "LaunchConstructor": self._("Launch constructor"),
            }
            self.call("admin.response_template", "constructor/logo.html", vars)
        elif state == "domain":
            if cmd == "prev":
                self.config.set("state", "logo")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            fields = [
                {
                    "type": "header",
                    "html": self._("Domain for your game"),
                },
                {
                    "type": "html",
                    "html": self._("<p>Now you have to assign a domain name to your game. Domain name is a very important part of your game marketing. Eye-candy names are more attractive. We don't offer free domain names &mdash; you have to register it manually.</p><p><strong>Register a domain name in any zone (ex: YOURDOMAIN.COM), set domain servers ns1.mmoconstructor.com, ns2.mmoconstructor.com and type your domain name without www here (ex: YOURDOMAIN.COM)</strong></p>"),
                },
                {
                    "name": "domain",
                    "label": self._("Domain name for your game (without www)"),
                    "value": self.config.get("domain"),
                },
            ]
            buttons = [
                {"text": self._("Previous"), "url": "admin-wizard/call/%s/prev" % self.uuid},
                {"text": self._("Next"), "url": "admin-wizard/call/%s/domain-submit" % self.uuid}
            ]
            self.call("admin.form", fields=fields, buttons=buttons)
        else:
            raise RuntimeError("Invalid ProjectSetupWizard state: %s" % state)

    def constructed(self, logo, arg):
        self.config.set("state", "logo")
        self.store_logo(logo)

    def store_logo(self, image_obj):
        background = Image.new("RGBA", (100, 100), (255, 255, 255))
        background.paste(image_obj, (0, 0, 100, 75), image_obj)
        # drawing image border
        bord = Image.open(mg.__path__[0] + "/data/logo/logo-pad.png")
        background.paste(bord, None, bord)
        # rounding corners
        mask = Image.open(mg.__path__[0] + "/data/logo/logo-mask.png")
        mask = mask.convert("RGBA")
        mask.paste(background, None, mask)
        # writing text
        textpad = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
        title = self.config.get("title_short")
        font_size = 20
        watchdog = 0
        while font_size > 5:
            font = ImageFont.truetype(mg.__path__[0] + "/data/fonts/arialn.ttf", font_size, encoding="unic")
            w, h = font.getsize(title)
            if w <= 92 and h <= 20:
                break
            font_size -= 1
        draw = ImageDraw.Draw(textpad)
        draw.text((50 - w / 2, 88 - h / 2), title, font=font)
        enhancer = ImageEnhance.Sharpness(textpad)
        textpad_blur = enhancer.enhance(0.5)
        mask.paste(textpad_blur, None, textpad_blur)
        mask.paste(textpad, None, textpad)
        # generating png
        png = cStringIO.StringIO()
        mask.save(png, "PNG")
        png = png.getvalue()
        uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
        self.config.set("logo", uri)
        self.config.store()
