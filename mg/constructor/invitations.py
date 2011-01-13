from mg import *
from mg.core.auth import User
import re
import random

re_valid_code = re.compile(r'^\d\d\d\d-\d\d\d\d-\d\d\d\d$')

class Invitation(CassandraObject):
    _indexes = {
        "created": [[], "created"],
        "user-type": [["user", "type"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Invitation-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Invitation._indexes

class InvitationList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Invitation-"
        kwargs["cls"] = Invitation
        CassandraObjectList.__init__(self, *args, **kwargs)

class Invitations(Module):
    def register(self):
        Module.register(self)
        self.rhook("headmenu-admin-constructor.invitations", self.headmenu_constructor_invitations)
        self.rhook("ext-admin-constructor.invitations", self.ext_constructor_invitations)
        self.rhook("menu-admin-constructor.index", self.menu_constructor_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("invitation.ok", self.invitation_ok)
        self.rhook("invitation.enter", self.invitation_enter)

    def menu_constructor_index(self, menu):
        req = self.req()
        if req.has_access("constructor.invitations") and self.conf("constructor.invitations"):
            menu.append({"id": "constructor/invitations", "text": self._("Invitations"), "leaf": True, "order": 100})

    def permissions_list(self, perms):
        perms.append({"id": "constructor.invitations", "name": self._("Constructor: giving invitations")})

    def headmenu_constructor_invitations(self, args):
        if args == "add":
            return [self._("New invitation"), "constructor/invitations"]
        return self._("Invitations for the registration")

    def ext_constructor_invitations(self):
        self.call("session.require_permission", "constructor.invitations")
        if not self.conf("constructor.invitations"):
            self.call("web.not_found")
        req = self.req()
        if req.args == "add":
            if req.param("ok"):
                person = req.param("person")
                errors = {}
                if not person or person == "":
                    errors["person"] = self._("Enter recipient name")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                code = "%04d-%04d-%04d" % (random.randint(0, 10000), random.randint(0, 10000), random.randint(0, 10000))
                inv = self.obj(Invitation, uuid=code, data={})
                inv.set("created", self.now())
                inv.set("person", person)
                inv.set("type", "newproject")
                inv.store()
                self.call("web.response_json", {"success": True, "redirect": "constructor/invitations"})
            fields = [
                {"name": "person", "label": self._("Person name")},
            ]
            buttons = [
                {"text": self._("Generate invitation code")}
            ]
            self.call("admin.form", fields=fields, buttons=buttons)
        rows = []
        invs = self.objlist(InvitationList, query_index="created", query_limit=100, query_reversed=True)
        invs.load(silent=True)
        for inv in invs:
            user = inv.get("user")
            if user:
                userobj = self.obj(User, user, silent=True)
                user = '<hook:admin.link href="auth/user-dashboard/%s" title="%s" />' % (user, htmlescape(user.get("name")))
            rows.append((inv.uuid, inv.get("type"), htmlescape(inv.get("person")), user))
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "constructor/invitations/add", "text": self._("Give a new invitation"), "lst": True}
                    ],
                    "header": [self._("Invitation code"), self._("Type"), self._("Person"), self._("User")],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def invitation_ok(self, user, type):
        invs = self.objlist(InvitationList, query_index="user-type", query_equal="%s-%s" % (user, type))
        invs.load(silent=True)
        if len(invs):
            return True
        return False

    def invitation_enter(self, user, type, code):
        if not re_valid_code.match(code):
            return self._("Invalid invitation code")
        with self.lock(["Invitation-%s" % code]):
            try:
                obj = self.obj(Invitation, code)
            except ObjectNotFoundException:
                return self._("Invalid invitation code")
            if obj.get("user"):
                return self._("This code is redeemed already")
            if obj.get("type") != type:
                return self._("This code in inappropriate for this action")
            obj.set("user", user)
            obj.store()
            return None
