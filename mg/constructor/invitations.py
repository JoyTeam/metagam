from mg import *
import re
import random

re_valid_code = re.compile(r'^\d\d\d\d-\d\d\d\d-\d\d\d\d$')

class Invitation(CassandraObject):
    _indexes = {
        "created": [[], "created"],
        "user-type": [["user", "type"]],
        "touser": [["touser"]],
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
        self.rhook("headmenu-admin-constructor.invitations", self.headmenu_constructor_invitations)
        self.rhook("ext-admin-constructor.invitations", self.ext_constructor_invitations, priv="constructor.invitations")
        self.rhook("menu-admin-constructor.index", self.menu_constructor_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("invitation.ok", self.invitation_ok)
        self.rhook("invitation.enter", self.invitation_enter)
        self.rhook("objclasses.list", self.objclasses_list)

    def objclasses_list(self, objclasses):
        objclasses["Invitation"] = (Invitation, InvitationList)

    def menu_constructor_index(self, menu):
        req = self.req()
        if req.has_access("constructor.invitations") and self.conf("constructor.invitations"):
            menu.append({"id": "constructor/invitations", "text": self._("Invitations"), "leaf": True, "order": 100})

    def permissions_list(self, perms):
        perms.append({"id": "constructor.invitations", "name": self._("Constructor: giving invitations")})

    def headmenu_constructor_invitations(self, args):
        if args == "add" or args == "add-user":
            return [self._("New invitation"), "constructor/invitations"]
        elif args == "mass" or args == "mass-send":
            return [self._("Massive invitations"), "constructor/invitations"]
        return self._("Invitations for the registration")

    def ext_constructor_invitations(self):
        if not self.conf("constructor.invitations"):
            self.call("web.not_found")
        req = self.req()
        if req.args == "add":
            if req.ok():
                person = req.param("person")
                errors = {}
                if not person or person == "":
                    errors["person"] = self._("Enter recipient name")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                code = "1%03d-%04d-%04d" % (random.randint(0, 1000), random.randint(0, 10000), random.randint(0, 10000))
                inv = self.obj(Invitation, uuid=code, silent=True)
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
        elif req.args == "add-user":
            if req.ok():
                name = req.param("name")
                errors = {}
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    user = self.call("session.find_user", name)
                    if not user:
                        errors["name"] = self._("User not found")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                code = "2%03d-%04d-%04d" % (random.randint(0, 1000), random.randint(0, 10000), random.randint(0, 10000))
                inv = self.obj(Invitation, uuid=code, silent=True)
                inv.set("created", self.now())
                inv.set("person", self._("User %s") % user.get("name"))
                inv.set("type", "newproject")
                inv.set("touser", user.uuid)
                self.call("email.send", user.get("email"), user.get("name"), self._("Invitation for the MMO Constructor"), self._("Hello, {name}.\n\nWe are glad to invite you for the closed alpha-testing of the MMO Constructor project.\nYour invitation code is: {code}\nFeel free to use any features of the MMO Constructor you want.").format(name=user.get("name"), code=code))
                inv.store()
                self.call("web.response_json", {"success": True, "redirect": "constructor/invitations"})
            fields = [
                {"name": "name", "label": self._("User name")},
            ]
            buttons = [
                {"text": self._("Send invitation code")}
            ]
            self.call("admin.form", fields=fields, buttons=buttons)
        elif req.args == "mass-send":
            user_uuids = [uuid for uuid in req.param("users").split(",") if uuid]
            if not user_uuids:
                self.call("admin.redirect", "constructor/invitations/mass")
            lst = self.objlist(UserList, user_uuids)
            lst.load(silent=True)
            if not len(lst):
                self.call("admin.redirect", "constructor/invitations/mass")
            if req.ok():
                for user in lst:
                    if req.param("u_%s" % user.uuid):
                        self.debug("Inviting user %s", user.uuid)
                        code = "3%03d-%04d-%04d" % (random.randint(0, 1000), random.randint(0, 10000), random.randint(0, 10000))
                        inv = self.obj(Invitation, uuid=code, silent=True)
                        inv.set("created", self.now())
                        inv.set("person", self._("Mass user %s") % user.get("name"))
                        inv.set("type", "newproject")
                        inv.set("touser", user.uuid)
                        self.call("email.send", user.get("email"), user.get("name"), self._("Invitation for the MMO Constructor"), self._("Hello, {name}.\n\nWe are glad to invite you for the closed alpha-testing of the MMO Constructor project.\nYour invitation code is: {code}\nFeel free to use any features of the MMO Constructor you want.").format(name=user.get("name"), code=code))
                        inv.store()
                self.call("admin.redirect", "constructor/invitations")
            fields = [
                {"type": "hidden", "name": "users", "value": req.param("users")},
            ]
            for ent in lst:
                fields.append({"type": "checkbox", "name": "u_%s" % ent.uuid, "checked": True, "label": htmlescape(ent.get("name"))})
            buttons = [
                {"text": self._("Send invitations")}
            ]
            self.call("admin.form", fields=fields, buttons=buttons)
        elif req.args == "mass":
            if req.ok():
                cnt = intz(req.param("cnt"))
                errors = {}
                if cnt < 1:
                    errors["cnt"] = self._("Minimal value - 1")
                else:
                    max_users = cnt
                    selected = set()
                    start = ""
                    while len(selected) < max_users:
                        lst = self.objlist(UserList, query_index="created", query_limit=max_users - len(selected), query_start=start)
                        lst.load()
                        self.debug("loaded users: %s", lst.uuids())
                        exists = self.objlist(InvitationList, query_index="touser", query_equal=lst.uuids())
                        exists.load()
                        exists = set([ent.get("touser") for ent in exists])
                        self.debug("exists: %s", exists)
                        next_start = None
                        for user in lst:
                            if user.uuid not in selected and not user.uuid in exists:
                                self.debug("selecting user %s", user.uuid)
                                selected.add(user.uuid)
                                next_start = user.get("created")
                        if next_start is None or next_start <= start:
                            break
                        else:
                            start = next_start
                    if selected:
                        self.call("admin.redirect", "constructor/invitations/mass-send", {"users": ",".join(selected)})
                    errors["cnt"] = self._("No users selected")
                self.call("web.response_json", {"success": False, "errors": errors})
            fields = [
                {"name": "cnt", "label": self._("Invitations count"), "value": 3},
            ]
            buttons = [
                {"text": self._("Select users")}
            ]
            self.call("admin.form", fields=fields, buttons=buttons)
        rows = []
        invs = self.objlist(InvitationList, query_index="created", query_limit=100, query_reversed=True)
        invs.load(silent=True)
        for inv in invs:
            user = inv.get("user")
            if user:
                userobj = self.obj(User, user, silent=True)
                user = '<hook:admin.link href="auth/user-dashboard/%s" title="%s" />' % (user, htmlescape(userobj.get("name")))
            rows.append((inv.uuid, inv.get("type"), htmlescape(inv.get("person")), user))
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "constructor/invitations/add", "text": self._("Give a new invitation")},
                        {"hook": "constructor/invitations/add-user", "text": self._("Invitation for a user")},
                        {"hook": "constructor/invitations/mass", "text": self._("Massive invitations"), "lst": True},
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
