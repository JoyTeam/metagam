from mg import *
from mg.constructor.common import *
import cgi
import re

re_newline = re.compile(r'\n')

class ProjectDashboard(Module):
    def register(self):
        self.rdep(["mg.constructor.invitations.Invitations"])
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-constructor.index", self.menu_constructor_index)
        self.rhook("ext-admin-constructor.project-find", self.ext_project_find, priv="constructor.projects")
        self.rhook("ext-admin-constructor.project-dashboard", self.ext_project_dashboard, priv="constructor.projects")
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-constructor.project-dashboard", self.headmenu_project_dashboard)
        self.rhook("ext-admin-constructor.project-unpublish", self.ext_project_unpublish, priv="constructor.projects.unpublish")
        self.rhook("ext-admin-constructor.project-publish", self.ext_project_publish, priv="constructor.projects.publish")
        self.rhook("headmenu-admin-constructor.project-reject", self.headmenu_project_reject)
        self.rhook("ext-admin-constructor.project-reject", self.ext_project_reject, priv="constructor.projects.publish")
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-constructor.settings", self.ext_constructor_settings, priv="constructor.settings")
        self.rhook("ext-admin-constructor.register-xsolla", self.ext_project_register_xsolla, priv="constructor.projects.publish")
        self.rhook("headmenu-admin-constructor.waiting-moderation", self.headmenu_waiting_moderation)
        self.rhook("ext-admin-constructor.waiting-moderation", self.waiting_moderation, priv="constructor.projects.publish")

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("constructor.projects"):
            projects = []
            self.call("projects.owned_by", user.uuid, projects)
            if len(projects):
                rows = []
                for p in projects:
                    if p.get("inactive"):
                        status = self._("projstatus///inactive")
                    elif p.get("moderation"):
                        status = self._("projstatus///moderation")
                    elif p.get("published"):
                        status = self._("projstatus///published")
                    else:
                        status = self._("projstatus///not published")
                    rows.append((u'<hook:admin.link href="constructor/project-dashboard/{0}" title="{1}" />'.format(p.get("uuid"), htmlescape(p.get("title_short"))), p.get("title_code"), status))
                tables.append({
                    "type": "games",
                    "title": self._("Games"),
                    "order": 50,
                    "header": [self._("Project name"), self._("Project code"), self._("Status")],
                    "rows": rows
                })

    def menu_root_index(self, menu):
        menu.append({"id": "constructor.index", "text": self._("Constructor"), "order": 10})

    def headmenu_project_dashboard(self, args):
        app = self.app().inst.appfactory.get_by_tag(args)
        if app is None:
            return
        project = getattr(app, "project", None)
        if project:
            project = self.int_app().obj(Project, args)
            return [self._("Project %s") % project.get("title_short", project.uuid), "auth/user-dashboard/%s" % project.get("owner")]
        else:
            return [self._("Project %s") % app.tag]

    def menu_constructor_index(self, menu):
        req = self.req()
        if req.has_access("constructor.settings"):
            menu.append({"id": "constructor/settings", "text": self._("Global settings"), "leaf": True, "order": 10})
        if req.has_access("constructor.projects"):
            menu.append({"id": "constructor/project-find", "text": self._("Find project"), "leaf": True, "order": 20})
            menu.append({"id": "constructor/project-dashboard/main", "text": self._("Main project"), "leaf": True, "order": 30})
        if req.has_access("constructor.projects.publish"):
            menu.append({"id": "constructor/waiting-moderation", "text": self._("Waiting for moderation"), "leaf": True, "order": 40})

    def headmenu_waiting_moderation(self, args):
        return self._("Projects waiting for moderation")

    def waiting_moderation(self):
        lst = self.int_app().objlist(ProjectList, query_index="moderation", query_equal="1")
        lst.load()
        rows = []
        for ent in lst:
            user = self.obj(User, ent.get("owner"))
            rows.append([
                self.call("l10n.time_local", ent.get("created")),
                '<hook:admin.link href="constructor/project-dashboard/%s" title="%s" />' % (ent.uuid, htmlescape(ent.get("title_short"))),
                '<hook:admin.link href="auth/user-dashboard/%s?active_tab=games" title="%s" />' % (user.uuid, htmlescape(user.get("name"))),
            ])
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Created"),
                        self._("Project"),
                        self._("Administrator"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def ext_project_find(self):
        req = self.req()
        uuid = req.param("uuid")
        if req.ok():
            errors = {}
            if not uuid:
                errors["uuid"] = self._("Enter project uuid")
            else:
                app = self.app().inst.appfactory.get_by_tag(uuid)
                if app is None:
                    errors["uuid"] = self._("Project not found")
                else:
                    self.call("admin.redirect", "constructor/project-dashboard/%s" % uuid)
            self.call("web.response_json", {"success": False, "errors": errors})
        fields = [
            {"name": "uuid", "label": self._("Project uuid"), "value": uuid},
        ]
        buttons = [{"text": self._("Search")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def ext_project_unpublish(self):
        req = self.req()
        try:
            app = self.app().inst.appfactory.get_by_tag(req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        for wiz in app.hooks.call("wizards.list"):
            wiz.abort()
        project = app.project
        with self.lock(["project.%s" % project.uuid], patience=120):
            project.load()
            if project.get("published"):
                project.delkey("published")
                project.delkey("moderation")
                project.set("moderation_reject", self._("Game was unpublished by a moderator"))
#               app.hooks.call("wizards.new", "mg.constructor.setup.ProjectSetupWizard")
                app.hooks.call("constructor-project.notify-owner", self._("Game unpublished: %s") % project.get("title_short"), self._("We are sorry. Your game '{0}' was unpublished.").format(project.get("title_short")))
#               domain = project.get("domain")
#               if domain:
#                   dom = self.obj(Domain, domain, silent=True)
#                   dom.remove()
                project.store()
                app.store_config_hooks()
                app.hooks.call("project.unpublished")
        self.call("admin.redirect", "constructor/project-dashboard/%s" % req.args)

    def ext_project_dashboard(self):
        req = self.req()
        try:
            app = self.app().inst.appfactory.get_by_tag(req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        vars = {
            "Id": self._("Game id"),
            "TitleFull": self._("Full title"),
            "TitleShort": self._("Short title"),
            "TitleCode": self._("Title code"),
            "TitleEn": self._("Title in English"),
            "GameDescription": self._("Game description"),
            "Owner": self._("Game owner"),
            "Domain": self._("Game domain"),
            "Created": self._("game///Created"),
            "Moderation": self._("Moderation required"),
            "Published": self._("game///Published"),
            "unpublish": self._("Unpublish"),
            "no": self._("no"),
            "yes": self._("yes"),
            "ConfirmUnpublish": self._("Are you sure want to unpublish the project?"),
            "Update": self._("Update"),
            "Logo": self._("Logo"),
            "permit": self._("moderation///permit"),
            "reject": self._("moderation///reject"),
            "by": self._("created///by"),
            "WaitingModeration": self._("This game is waiting for moderation"),
            "PublishedAt": self._("This game is published at"),
            "GameInactive": self._("This game is inactive yet"),
            "GameSetup": self._("This game is being set up by its administrator"),
        }
        project = getattr(app, "project", None)
        if project:
            owner = self.obj(User, project.get("owner"))
            description = re_newline.sub('<br />', htmlescape(app.config.get("gameprofile.description")))
            vars["project"] = {
                "uuid": project.uuid,
                "title_full": htmlescape(project.get("title_full")),
                "title_short": htmlescape(project.get("title_short")),
                "title_code": htmlescape(project.get("title_code")),
                "title_en": htmlescape(project.get("title_en")),
                "logo": htmlescape(project.get("logo")),
                "domain": htmlescape(project.get("domain")),
                "moderation_reject": htmlescape(project.get("moderation_reject")),
                "published": project.get("published"),
                "moderation": project.get("moderation"),
                "created": project.get("created"),
                "unpublish": req.has_access("constructor.projects.unpublish") and project.get("published"),
                "publish": req.has_access("constructor.projects.publish") and project.get("moderation"),
                "description": description,
            }
            vars["owner"] = {
                "uuid": owner.uuid,
                "name": htmlescape(owner.get("name")),
            }
        else:
            vars["project"] = {
                "uuid": app.tag,
                "main": True,
            }
        options = []
        app.hooks.call("constructor.project-options", options)
        if len(options):
            vars["options"] = options
        params = []
        app.hooks.call("constructor.project-params", params)
        if len(params):
            vars["project"]["params"] = params
        notifications = []
        if project and not app.config.get("xsolla.project-id") and req.has_access("constructor.projects.publish") and project.get("published"):
            notifications.append({"icon": "/st/img/coins.png", "content": u'%s <hook:admin.link href="constructor/register-xsolla/%s" title="%s" />' % (self._("This game is not registered in the Xsolla system."), project.uuid, self._("Register"))})
        app.hooks.call("constructor.project-notifications", notifications)
        if len(notifications):
            vars["project"]["notifications"] = notifications
        self.call("admin.response_template", "admin/constructor/project-dashboard.html", vars)

    def permissions_list(self, perms):
        perms.append({"id": "constructor.settings", "name": self._("Constructor: global settings")})
        perms.append({"id": "constructor.projects", "name": self._("Constructor: projects")})
        perms.append({"id": "constructor.projects.publish", "name": self._("Constructor: publishing projects (moderation)")})
        perms.append({"id": "constructor.projects.unpublish", "name": self._("Constructor: unpublishing projects")})

    def ext_constructor_settings(self):
        req = self.req()
        invitations = intz(req.param("v_invitations"))
        moderator_email = req.param("moderator_email")
        projects_domain = req.param("projects_domain")
        invitations_text = req.param("invitations_text")
        if req.param("ok"):
            changed = False
            config = self.main_app().config_updater()
            if config.get("constructor.invitations") != invitations:
                self.call("admin.update_menu")
            config.set("constructor.invitations", invitations)
            config.set("constructor.invitations-text", invitations_text)
            config.set("constructor.moderator-email", moderator_email)
            config.set("constructor.projects-domain", projects_domain)
            config.store()
            self.call("admin.response", self._("Constructor settings stored"), {})
        else:
            config = self.main_app().config
            invitations = config.get("constructor.invitations")
            moderator_email = config.get("constructor.moderator-email")
            projects_domain = config.get("constructor.projects-domain", self.app().inst.config["main_host"])
            invitations_text = config.get("constructor.invitations-text", self._("Open registration of new games is unavailable at the moment"))
        fields = [
            {"type": "combo", "name": "invitations", "label": self._("Registration on invitations"), "value": invitations, "values": [(0, self._("Open registration")), (1, self._("Registration on invitations")), (2, self._("Registration closed"))]},
            {"name": "invitations_text", "label": self._("HTML message about registration on invitations"), "value": invitations_text},
            {"name": "moderator_email", "label": self._("Email of projects moderator"), "value": moderator_email},
            {"name": "projects_domain", "label": self._("Projects domain"), "value": projects_domain},
        ]
        self.call("admin.form", fields=fields)

    def ext_project_publish(self):
        req = self.req()
        try:
            app = self.app().inst.appfactory.get_by_tag(req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        project = app.project
        with self.lock(["project.%s" % project.uuid], patience=120):
            project.load()
            if project.get("moderation"):
                project.delkey("moderation")
                project.delkey("moderation_reject")
                project.set("published", self.now())
                app.modules.load(["mg.core.money.Xsolla"])
                if not app.config.get("xsolla.project-id"):
                    app.hooks.call("xsolla.register")
                app.hooks.call("constructor-project.notify-owner", self._("Moderation passed: %s") % project.get("title_short"), self._("Congratulations! Your game '{0}' has passed moderation successfully.").format(project.get("title_short")))
                project.store()
                app.store_config_hooks()
                app.hooks.call("project.published")
        self.call("admin.redirect", "constructor/waiting-moderation")

    def ext_project_reject(self):
        req = self.req()
        try:
            app = self.app().inst.appfactory.get_by_tag(req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        project = app.project
        with self.lock(["project.%s" % project.uuid], patience=120):
            project.load()
            if project.get("moderation"):
                if req.ok():
                    reason = req.param("reason")
                    errors = {}
                    if not reason:
                        errors["reason"] = self._("Reason is mandatory")
                    if len(errors):
                        self.call("web.response_json", {"success": False, "errors": errors})
                    project.delkey("moderation")
                    project.set("moderation_reject", self._("Moderation reject reason: %s") % reason)
                    project.delkey("published")
                    app.hooks.call("constructor-project.notify-owner", self._("Moderation reject: %s") % project.get("title_short"), self._("Your game '{0}' hasn't passed moderation.\nReason: {1}").format(project.get("title_short"), reason))
                    project.store()
                    app.store_config_hooks()
                    self.call("admin.redirect", "constructor/waiting-moderation")
                fields = []
                fields.append({"name": "reason", "label": self._("Reject reason")})
                buttons = [{"text": self._("moderation///Reject")}]
                self.call("admin.form", fields=fields, buttons=buttons)
        self.call("admin.redirect", "constructor/waiting-moderation")

    def headmenu_project_reject(self, args):
        return [self._("Moderation reject"), "constructor/project-dashboard/%s" % args]

    def ext_project_register_xsolla(self):
        req = self.req()
        try:
            app = self.app().inst.appfactory.get_by_tag(req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        project = app.project
        with self.lock(["project.%s.xsolla" % project.uuid], patience=120):
            if not app.config.get("xsolla.project-id"):
                app.hooks.call("xsolla.register")
                if not app.config.get("xsolla.project-id"):
                    self.call("admin.response", u'%s. <hook:admin.link href="constructor/project-dashboard/%s" title="%s" />' % (self._("Registration failed"), project.uuid, self._("Return")), {})
        self.call("admin.redirect", "constructor/project-dashboard/%s" % req.args)

