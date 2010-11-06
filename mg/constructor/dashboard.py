from mg import *
from mg.core.auth import User
from mg.constructor import *
import cgi

class ProjectDashboard(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-constructor.index", self.menu_constructor_index)
        self.rhook("ext-admin-constructor.user-find", self.ext_user_find)
        self.rhook("ext-admin-constructor.user-dashboard", self.ext_user_dashboard)
        self.rhook("ext-admin-constructor.project-find", self.ext_project_find)
        self.rhook("ext-admin-constructor.project-dashboard", self.ext_project_dashboard)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-constructor.project-dashboard", self.headmenu_project_dashboard)
        self.rhook("headmenu-admin-constructor.user-dashboard", self.headmenu_user_dashboard)
        self.rhook("ext-admin-constructor.dns", self.ext_dns)

    def menu_root_index(self, menu):
        menu.append({"id": "constructor.index", "text": self._("Constructor")})

    def headmenu_project_dashboard(self, args):
        app = self.app().inst.appfactory.get_by_tag(args)
        if app is None:
            return
        project = getattr(app, "project", None)
        if project:
            project = self.app().inst.int_app.obj(Project, args)
            return [self._("Project %s") % project.get("title_short", project.uuid)]
        else:
            return [self._("Project %s") % app.tag]

    def headmenu_user_dashboard(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("User %s") % cgi.escape(user.get("name"))]

    def menu_constructor_index(self, menu):
        req = self.req()
        if req.has_access("constructor.users"):
            menu.append({"id": "constructor/user-find", "text": self._("Find user"), "leaf": True})
        if req.has_access("constructor.projects"):
            menu.append({"id": "constructor/project-find", "text": self._("Find project"), "leaf": True})
            menu.append({"id": "constructor/project-dashboard/main", "text": self._("Main project"), "leaf": True})
        if req.has_access("constructor.dns"):
            menu.append({"id": "constructor/dns", "text": self._("DNS settings"), "leaf": True})

    def ext_dns(self):
        req = self.req()
        ns1 = req.param("ns1")
        ns2 = req.param("ns2")
        if req.param("ok"):
            config = self.app().config
            config.set("dns.ns1", ns1)
            config.set("dns.ns2", ns2)
            config.store()
            self.call("admin.response", self._("DNS settings stored"), {})
        else:
            ns1 = self.conf("dns.ns1")
            ns2 = self.conf("dns.ns2")
        fields = [
            {"name": "ns1", "label": self._("DNS server 1"), "value": ns1},
            {"name": "ns2", "label": self._("DNS server 2"), "value": ns2},
        ]
        self.call("admin.form", fields=fields)

    def ext_user_find(self):
        self.call("session.require_permission", "constructor.users")
        req = self.req()
        name = req.param("name")
        if req.ok():
            errors = {}
            if not name:
                errors["name"] = self._("Enter user name")
            else:
                user = self.call("session.find_user", name)
                if not user:
                    errors["name"] = self._("User not found")
                else:
                    self.call("admin.redirect", "constructor/user-dashboard/%s" % user.uuid)
            self.call("web.response_json", {"success": False, "errors": errors})
        fields = [
            {"name": "name", "label": self._("User name"), "value": name},
        ]
        buttons = [{"text": self._("Search")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def ext_user_dashboard(self):
        self.call("session.require_permission", "constructor.users")
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        vars = {
            "user": {
                "uuid": user.uuid,
            },
            "User": self._("User"),
            "ProjectId": self._("Project ID"),
            "ProjectName": self._("Project name"),
            "ProjectCode": self._("Project code"),
        }
        if req.has_access("constructor.projects"):
            projects = []
            self.call("projects.owned_by", user.uuid, projects)
            if len(projects):
                vars["projects"] = projects
        options = []
        self.call("constructor.user-options", user, options)
        if len(options):
            vars["options"] = options
        self.call("admin.response_template", "admin/constructor/user-dashboard.html", vars)

    def ext_project_find(self):
        self.call("session.require_permission", "constructor.projects")
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

    def ext_project_dashboard(self):
        self.call("session.require_permission", "constructor.projects")
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
        }
        project = getattr(app, "project", None)
        if project:
            owner = self.obj(User, project.get("owner"))
            vars["project"] = {
                "uuid": project.uuid,
                "title_full": project.get("title_full"),
                "title_short": project.get("title_short"),
                "title_code": project.get("title_code"),
            }
            vars["owner"] = {
                "uuid": owner.uuid,
                "name": cgi.escape(owner.get("name")),
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
        perms.append({"id": "constructor.users", "name": self._("Constructor users")})
        perms.append({"id": "constructor.projects", "name": self._("Constructor projects")})
        perms.append({"id": "constructor.dns", "name": self._("Constructor DNS settings")})

