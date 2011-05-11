from mg import *
from mg.constructor.common import *
import cgi

class ProjectDashboard(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.constructor.invitations.Invitations"])
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-constructor.index", self.menu_constructor_index)
        self.rhook("ext-admin-constructor.project-find", self.ext_project_find, priv="constructor.projects")
        self.rhook("ext-admin-constructor.project-dashboard", self.ext_project_dashboard, priv="constructor.projects")
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-constructor.project-dashboard", self.headmenu_project_dashboard)
        self.rhook("ext-admin-constructor.project-unpublish", self.ext_project_unpublish, priv="constructor.projects.unpublish")
        self.rhook("ext-admin-constructor.project-publish", self.ext_project_publish, priv="constructor.projects.publish")
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-constructor.settings", self.ext_constructor_settings, priv="constructor.settings")

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
                    rows.append(('<hook:admin.link href="constructor/project-dashboard/{0}" title="{1}" />'.format(p.get("uuid"), htmlescape(p.get("title_short"))), p.get("title_code"), status))
                tables.append({
                    "header": [self._("Project name"), self._("Project code"), self._("Status")],
                    "rows": rows
                })

    def menu_root_index(self, menu):
        menu.append({"id": "constructor.index", "text": self._("Constructor"), "order": -100})

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
            menu.append({"id": "constructor/settings", "text": self._("Global settings"), "leaf": True})
        if req.has_access("constructor.projects"):
            menu.append({"id": "constructor/project-find", "text": self._("Find project"), "leaf": True})
            menu.append({"id": "constructor/project-dashboard/main", "text": self._("Main project"), "leaf": True})

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
        with self.lock(["project.%s" % project.uuid]):
            if project.get("published"):
                project.delkey("published")
                project.set("moderation", 1)
#               app.hooks.call("wizards.new", "mg.constructor.setup.ProjectSetupWizard")
                app.hooks.call("constructor-project.notify-owner", self._("Game unpublished: %s") % project.get("title_short"), self._("We are sorry. Your game '{0}' was unpublished.").format(project.get("title_short")))
#               domain = project.get("domain")
#               if domain:
#                   dom = self.obj(Domain, domain, silent=True)
#                   dom.remove()
                project.store()
                app.store_config_hooks()
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
            "Owner": self._("Game owner"),
            "Domain": self._("Game domain"),
            "Created": self._("game///Created"),
            "Moderation": self._("Moderation required"),
            "Published": self._("game///Published"),
            "unpublish": self._("unpublish"),
            "no": self._("no"),
            "yes": self._("yes"),
            "ConfirmUnpublish": self._("Are you sure want to unpublish the project?"),
            "Update": self._("Update"),
            "Logo": self._("Logo"),
            "permit": self._("moderation///permit"),
        }
        project = getattr(app, "project", None)
        if project:
            owner = self.obj(User, project.get("owner"))
            vars["project"] = {
                "uuid": project.uuid,
                "title_full": htmlescape(project.get("title_full")),
                "title_short": htmlescape(project.get("title_short")),
                "title_code": htmlescape(project.get("title_code")),
                "logo": htmlescape(project.get("logo")),
                "domain": htmlescape(project.get("domain")),
                "published": project.get("published"),
                "moderation": project.get("moderation"),
                "created": project.get("created"),
                "unpublish": req.has_access("constructor.projects.unpublish") and project.get("published"),
                "publish": req.has_access("constructor.projects.publish") and project.get("moderation"),
            }
            vars["owner"] = {
                "uuid": owner.uuid,
                "name": htmlescape(owner.get("name")),
            }
        else:
            vars["project"] = {
                "uuid": app.tag,
            }
        options = []
        app.hooks.call("constructor.project-options",options)
        if len(options):
            vars["options"] = options
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
        with self.lock(["project.%s" % project.uuid]):
            if not project.get("published"):
                project.delkey("moderation")
                project.set("published", self.now())
                app.modules.load(["mg.game.money.TwoPay"])
                app.hooks.call("2pay.register")
                app.hooks.call("constructor-project.notify-owner", self._("Moderation passed: %s") % project.get("title_short"), self._("Congratulations! Your game '{0}' has passed moderation successfully.".format(project.get("title_short"))))
                project.store()
                app.store_config_hooks()
        self.call("admin.redirect", "constructor/project-dashboard/%s" % req.args)

