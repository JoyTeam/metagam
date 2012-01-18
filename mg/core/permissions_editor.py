from mg import *

re_valid_identifier = re.compile(r'^u_[a-z0-9_]+$', re.IGNORECASE)
re_del = re.compile(r'^del\/(.+)$')

class Permissions(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list, priority=10)

    def permissions_list(self, perms):
        perms.extend(self.conf("auth.permissions", []))

    def child_modules(self):
        return ["mg.core.permissions_editor.PermissionsAdmin"]

class PermissionsAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-auth.index", self.menu_auth_index)
        self.rhook("ext-admin-auth.permissions-editor", self.admin_permissions_editor, priv="permissions.editor")
        self.rhook("headmenu-admin-auth.permissions-editor", self.headmenu_permissions_editor)

    def permissions_list(self, perms):
        perms.append({"id": "permissions.editor", "name": self._("Editor of user defined permissions")})

    def menu_auth_index(self, menu):
        req = self.req()
        if req.has_access("permissions.editor"):
            menu.append({"id": "auth/permissions-editor", "text": self._("User defined permissions"), "leaf": True, "order": 20})

    def headmenu_permissions_editor(self, args):
        if args == "new":
            return [self._("New permission"), "auth/permissions-editor"]
        else:
            for p in self.conf("auth.permissions", []):
                if p["id"] == args:
                    return [htmlescape(p["name"]), "auth/permissions-editor"]
            return self._("User defined permissions")

    def admin_permissions_editor(self):
        req = self.req()
        perms = self.conf("auth.permissions", [])
        if req.args:
            m = re_del.match(req.args)
            if m:
                ident = m.group(1)
                perms = [p for p in perms if p["id"] != ident]
                config = self.app().config_updater()
                config.set("auth.permissions", perms)
                config.store()
                self.call("admin.redirect", "auth/permissions-editor")
            if req.args == "new":
                perm = {}
            else:
                perm = None
                for p in perms:
                    if p["id"] == req.args:
                        perm = p
                        break
                if not perm:
                    self.call("admin.redirect", "auth/permissions-editor")
            if req.ok():
                new_perm = {}
                errors = {}
                # id
                ident = req.param("id").strip()
                print "ident=%s" % ident
                if not ident:
                    errors["id"] = self._("This field is mandatory")
                elif not re_valid_identifier.match(ident):
                    errors["id"] = self._("Permission identifier must start with 'u_' prefix. Other symbols may be latin letters, digits or '_'")
                else:
                    success = True
                    if perm.get("id") != ident:
                        for p in perms:
                            if p["id"] == ident:
                                errors["id"] = self._("Permission with the same identifier already exists")
                                success = False
                                break
                    if success:
                        new_perm["id"] = ident
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    new_perm["name"] = name
                # errors handling
                if errors:
                    print errors
                    self.call("web.response_json", {"success": False, "errors": errors})
                # storing
                perms = [p for p in perms if p["id"] != perm.get("id")]
                perms.append(new_perm)
                perms.sort(cmp=lambda x, y: cmp(x["id"], y["id"]))
                config = self.app().config_updater()
                config.set("auth.permissions", perms)
                config.store()
                self.call("admin.redirect", "auth/permissions-editor")
            fields = [
                {"name": "id", "label": self._("Permission identifier (u_...)"), "value": perm.get("id")},
                {"name": "name", "label": self._("Permission name"), "value": perm.get("name")},
            ]
            self.call("admin.form", fields=fields)
        rows = []
        for ent in perms:
            rows.append([
                ent["id"],
                htmlescape(ent["name"]),
                u'<hook:admin.link href="auth/permissions-editor/%s" title="%s" />' % (ent["id"], self._("edit")),
                u'<hook:admin.link href="auth/permissions-editor/del/%s" title="%s" confirm="%s" />' % (ent["id"], self._("delete"), self._("Are you sure want to delete this permission?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "auth/permissions-editor/new", "text": self._("New permission"), "lst": True},
                    ],
                    "header": [
                        self._("Identifier"),
                        self._("permission///Name"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
