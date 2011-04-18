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
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-constructor.settings", self.ext_constructor_settings, priv="constructor.settings")

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("constructor.projects"):
            projects = []
            self.call("projects.owned_by", user.uuid, projects)
            if len(projects):
                tables.append({
                    "header": [self._("Project ID"), self._("Project name"), self._("Project code")],
                    "rows": [('<hook:admin.link href="constructor/project-dashboard/{0}" title="{0}" />'.format(p.get("uuid")), p.get("title_short"), p.get("title_code")) for p in projects]
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
        domain = project.get("domain")
        if domain:
            dom = self.obj(Domain, domain, silent=True)
            dom.remove()
        project.delkey("domain")
        project.delkey("title_full")
        project.delkey("title_short")
        project.delkey("title_code")
        project.delkey("published")
        project.delkey("logo")
        project.store()
        app.hooks.call("wizards.new", "mg.constructor.setup.ProjectSetupWizard")
        app.hooks.call("cluster.appconfig_changed")
        self.call("admin.redirect", "constructor/project-dashboard/%s" % req.args)

    def ext_project_dashboard(self):
        req = self.req()
        try:
            app = self.app().inst.appfactory.get_by_tag(req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        vars = {
            "Id": self._("Id"),
            "TitleFull": self._("Full title"),
            "TitleShort": self._("Short title"),
            "TitleCode": self._("Title code"),
            "Owner": self._("Owner"),
            "Domain": self._("Domain"),
            "Created": self._("Created"),
            "Published": self._("Published"),
            "unpublish": self._("unpublish"),
            "no": self._("no"),
            "ConfirmUnpublish": self._("Are you sure want to unpublish the project?"),
            "Update": self._("Update"),
            "Logo": self._("Logo"),
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
                "created": project.get("created"),
                "unpublish": req.has_access("constructor.projects.unpublish"),
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
        perms.append({"id": "constructor.projects.unpublish", "name": self._("Constructor: unpublishing projects")})

    def ext_constructor_settings(self):
        req = self.req()
        invitations = True if req.param("invitations") else False
        moderator_email = req.param("moderator_email")
        projects_domain = req.param("projects_domain")
        if req.param("ok"):
            changed = False
            config = self.main_app().config_updater()
            if config.get("constructor.invitations") != invitations:
                self.call("admin.update_menu")
            config.set("constructor.invitations", invitations)
            config.set("constructor.moderator-email", moderator_email)
            config.set("constructor.projects-domain", projects_domain)
            config.store()
            self.call("admin.response", self._("Constructor settings stored"), {})
        else:
            config = self.main_app().config
            invitations = config.get("constructor.invitations")
            moderator_email = config.get("constructor.moderator-email")
            projects_domain = config.get("constructor.projects-domain", self.app().inst.config["main_host"])
        fields = [
            {"type": "checkbox", "name": "invitations", "label": self._("Registration on invitations"), "checked": invitations},
            {"name": "moderator_email", "label": self._("Email of projects moderator"), "value": moderator_email},
            {"name": "projects_domain", "label": self._("Projects domain"), "value": projects_domain},
        ]
        self.call("admin.form", fields=fields)

