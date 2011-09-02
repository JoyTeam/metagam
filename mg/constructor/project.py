from mg import *
import re

re_newline = re.compile(r'\n')
re_remove_www = re.compile(r'^www\.', re.IGNORECASE)

class ConstructorProject(Module):
    "This is the main module of every project. It must load very fast"
    def register(self):
        self.rdep(["mg.core.web.Web"])
        self.rhook("web.setup_design", self.web_setup_design)
        self.rhook("project.title", self.project_title)
        self.rhook("email.sender", self.email_sender)
        self.rhook("modules.list", self.modules_list)

    def child_modules(self):
        lst = [
            "mg.core.auth.Sessions",
            "mg.core.auth.Interface",
            "mg.admin.AdminInterface",
            "mg.core.cluster.Cluster",
            "mg.core.emails.Email",
            "mg.core.queue.Queue",
            "mg.core.cass_maintenance.CassandraMaintenance",
            "mg.admin.wizards.Wizards",
            "mg.constructor.project.ConstructorProjectAdmin",
            "mg.constructor.admin.ConstructorUtils",
            "mg.constructor.domains.Domains",
            "mg.constructor.auth.Auth",
            "mg.constructor.players.CharactersMod",
            "mg.core.daemons.Daemons",
            "mg.constructor.logo.LogoAdmin",
            "mg.core.dbexport.Export",
        ]
        project = self.app().project
        if not project.get("inactive"):
            lst.extend([
                "mg.constructor.game.Game",
                "mg.core.money.Money", "mg.core.money.MoneyAdmin",
                "mg.core.realplexor.Realplexor",
                "mg.constructor.chat.Chat",
                "mg.constructor.interface.Dynamic",
                "mg.constructor.interface.Interface",
                "mg.constructor.design.DesignMod",
                "mg.constructor.design.IndexPage", "mg.constructor.design.IndexPageAdmin",
                "mg.constructor.design.GameInterface", "mg.constructor.design.GameInterfaceAdmin",
                "mg.constructor.script.ScriptEngine",
                "mg.core.auth.Dossiers",
                "mg.core.sites.Counters", "mg.core.sites.CountersAdmin", "mg.core.sites.SiteAdmin",
                "mg.socio.restraints.Restraints", "mg.socio.restraints.RestraintsAdmin",
                "mg.mmo.locations.Locations", "mg.mmo.locations.LocationsAdmin",
                "mg.core.icons.Icons",
                "mg.socio.SocioAdmin",
                "mg.constructor.money.Money",
                "mg.constructor.paidservices.PaidServices",
                "mg.constructor.paidservices.PaidServicesAdmin",
                "mg.core.modifiers.Modifiers",
                "mg.core.icons.IconsAdmin",
            ])
            if project.get("published"):
                lst.extend([
                    "mg.core.money.Xsolla",
                    "mg.constructor.stats.GameReporter",
                ])
            if self.conf("module.socio"):
                lst.extend(["mg.socio.Socio", "mg.constructor.socio.Socio"])
                lst.extend(["mg.constructor.design.SocioInterface", "mg.constructor.design.SocioInterfaceAdmin"])
            if self.conf("module.storage"):
                lst.extend(["mg.constructor.storage.StorageAdmin"])
        return lst

    def modules_list(self, modules):
        modules.append({
            "id": "socio",
            "name": self._("Social modules"),
            "description": self._("Couple of modules related to social interactions among players (smiles, forums, blogs, etc)"),
        })
        modules.append({
            "id": "storage",
            "name": self._("Static storage"),
            "description": self._("Server storage of static objects"),
        })

    def project_title(self):
        return self.app().project.get("title_short", "New Game")

    def web_setup_design(self, vars):
        req = self.req()
        vars["domain"] = req.host()
        vars["base_domain"] = re_remove_www.sub('', req.host())
        if not vars.get("global_html"):
            if req.group == "admin":
                vars["global_html"] = "constructor/admin_global.html"
            else:
                vars["global_html"] = "game/global.html"
        vars["main_host"] = self.app().inst.config.get("main_host")

    def email_sender(self, params):
        project = self.app().project
        params["name"] = project.get("title_short")
        params["prefix"] = u"[%s] " % project.get("title_code").lower()
        params["signature"] = u"%s - http://www.%s" % (project.get("title_full"), project.get("domain"))

class ConstructorProjectAdmin(Module):
    def register(self):
        self.rhook("menu-admin-top.list", self.menu_top_list, priority=10)
        self.rhook("ext-admin-project.destroy", self.project_destroy, priv="project.admin")
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("forum-admin.init-categories", self.forum_init_categories)
        self.rhook("ext-admin-game.dashboard", self.game_dashboard, priv="project.admin")
        self.rhook("ext-admin-game.domain", self.game_domain, priv="project.admin")
        self.rhook("constructor-project.notify-owner", self.notify_owner)
        self.rhook("advice.all", self.advice_all)
        self.rhook("ext-admin-game.moderation", self.game_moderation, priv="project.admin")
        self.rhook("menu-admin-root.index", self.menu_root_index)

    def menu_top_list(self, topmenu):
        req = self.req()
        if self.app().project.get("inactive") and req.has_access("project.admin"):
            topmenu.append({"href": "/admin-project/destroy", "text": self._("Destroy this game"), "tooltip": self._("You can destroy your game while not created")})

    def menu_root_index(self, menu):
        project = self.app().project
        if project.get("inactive"):
            menu[:] = [ent for ent in menu if ent.get("leaf")]
        else:
            req = self.req()
            if req.has_access("project.admin"):
                menu.append({"id": "game/dashboard", "text": self._("Game dashboard"), "leaf": True, "admin_index": True, "order": -20, "icon": "/st-mg/menu/dashboard.png", "even_unpublished": True})

    def project_destroy(self):
        if self.app().project.get("inactive"):
            self.main_app().hooks.call("project.cleanup", self.app().project.uuid)
        redirect = "//www.%s/cabinet" % self.app().inst.config["main_host"]
        req = self.req()
        if req.args == "admin":
            self.call("web.response_json", {"success": True, "redirect_top": redirect})
        else:
            self.call("web.redirect", redirect)

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

    def game_dashboard(self):
        vars = {
            "Tips": self._("Tips"),
            "BeforeLaunch": self._("Prepare to launch"),
        }
        recommended_actions = []
        self.call("admin-game.recommended-actions", recommended_actions)
        recommended_actions.sort(cmp=lambda a, b: cmp(a.get("order", 0), b.get("order", 0)))
        req = self.req()
        project = self.app().project
        before_launch = []
        others = []
        for ent in recommended_actions:
            if ent.get("before_launch"):
                before_launch.append(ent)
            else:
                others.append(ent)
        if not project.get("published") and project.get("moderation"):
            before_launch.append({"icon": "/st/img/help-hint.png", "content": self._("Your game is being checked by the moderators. Moderation results will be sent you via e-mail. Please be patient.")})
            vars["BeforeLaunch"] = self._("Moderation in progress")
        if not project.get("inactive") and not project.get("published") and not project.get("moderation") and req.has_access("project.admin"):
            if before_launch:
                before_launch.append({"icon": "/st/img/application-exit.png", "content": '<strong>%s</strong>' % self._("Before launching your game perform the steps listed above")})
            else:
                before_launch.append({"icon": "/st/img/arrow-right.png", "content": u'<strong>%s</strong> <hook:admin.link href="game/moderation" title="%s" />' % (self._("Congratulations! Your game is ready to be published."), self._("game///Send it to moderation"))})
        if not project.get("published") and not project.get("moderation") and project.get("moderation_reject"):
            before_launch.insert(0, {"icon": "/st/img/application-exit.png", "content": htmlescape(project.get("moderation_reject"))})
        if len(before_launch):
            vars["before_launch"] = before_launch
        if len(others) and (project.get("published") or project.get("moderation")):
            vars["recommended_actions"] = others
        if project.get("published"):
            vars["published"] = True
            self.call("game.dashboard", vars)
        else:
            self.call("admin.advice", {"title": self._("How to launch the game"), "content": self._('Step-by-step tutorial about preparing the game to launch you can read in the <a href="//www.%s/doc/newgame" target="_blank">reference manual</a>.') % self.app().inst.config["main_host"]})
        self.call("admin.response_template", "admin/game/dashboard.html", vars)

    def advice_all(self, group, hook, args, advice):
        req = self.req()
        project = self.app().project
        if not project.get("inactive") and not project.get("published") and not project.get("moderation") and (group != "admin-game" or hook != "dashboard") and req.has_access("project.admin"):
            advice.append({"title": self._("Launching your game"), "content": self._('Your game is not published yet. To publish it perform the steps listed on the <hook:admin.link href="game/dashboard" title="Game dashboard" /> page'), "order": 1000})

    def game_domain(self):
        if self.app().project.get("domain"):
            self.call("admin.redirect", "game/dashboard")
        wizs = self.call("wizards.find", "domain")
        if len(wizs):
            self.call("admin.redirect", "wizard/call/%s" % wizs[0].uuid)
        wiz = self.call("wizards.new", "mg.constructor.domains.DomainWizard", redirect_fail="game/dashboard")
        self.call("admin.redirect", "wizard/call/%s" % wiz.uuid)

    def notify_owner(self, subject, content):
        owner = self.main_app().obj(User, self.app().project.get("owner"))
        name = owner.get("name")
        email = owner.get("email")
        self.main_app().hooks.call("email.send", email, name, subject, content)

    def game_moderation(self):
        project = self.app().project
        recommended_actions = []
        self.call("admin-game.recommended-actions", recommended_actions)
        for ent in recommended_actions:
            if ent.get("before_launch"):
                self.call("admin.redirect", "game/dashboard")
        if project.get("inactive") or project.get("published") or project.get("moderation"):
            self.call("admin.redirect", "game/dashboard")
        req = self.req()
        if req.args == "commit":
            with self.lock(["project.%s" % project.uuid]):
                project.load()
                if not project.get("moderation"):
                    project.set("moderation", 1)
                    # message to the moderator
                    email = self.main_app().config.get("constructor.moderator-email")
                    if email:
                        content = self._("New project has been registered: {0}\nPlease perform required moderation actions: http://www.{1}/admin#constructor/project-dashboard/{2}").format(project.get("title_full"), self.app().inst.config["main_host"], project.uuid)
                        self.main_app().hooks.call("email.send", email, self._("Constructor moderator"), self._("Project moderation: %s") % project.get("title_short"), content)
                    project.store()
                    self.app().store_config_hooks()
            self.call("admin.redirect", "game/dashboard")
        project = self.app().project
        description = re_newline.sub('<br />', htmlescape(self.conf("gameprofile.description")))
        vars = {
            "TitleFull": self._("Full title"),
            "TitleShort": self._("Short title"),
            "TitleEn": self._("Title in English"),
            "TitleCode": self._("Title code"),
            "GameDescription": self._("Game description"),
            "Domain": self._("Game domain"),
            "Logo": self._("Logo"),
            "Recheck": self._("Recheck all settings thoroughly. After sending data to moderation you won't have an ability to change fields with red border and game logo"),
            "Submit": self._("Everything is correct. Send to moderation"),
            "edit": self._("edit"),
            "project": {
                "title_full": htmlescape(project.get("title_full")),
                "title_short": htmlescape(project.get("title_short")),
                "title_en": htmlescape(project.get("title_en")),
                "title_code": htmlescape(project.get("title_code")),
                "description": description,
                "domain": htmlescape(project.get("domain")),
                "logo": htmlescape(project.get("logo")),
            },
        }
        params = []
        self.call("constructor.project-params", params)
        if len(params):
            vars["project"]["params"] = params
        self.call("admin.response_template", "admin/game/moderation.html", vars)
