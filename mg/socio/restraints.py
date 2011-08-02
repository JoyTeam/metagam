from mg import *
import re

re_restraint_kind = re.compile(r'^(\S+)/(forum-silence|chat-silence|ban|hide-info)$')

class UserRestraint(CassandraObject):
    _indexes = {
        "user": [["user"]],
        "till": [[], "till"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserRestraint-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return UserRestraint._indexes

class UserRestraintList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserRestraint-"
        kwargs["cls"] = UserRestraint
        CassandraObjectList.__init__(self, *args, **kwargs)

class Restraints(Module):
    def register(self):
        Module.register(self)
        self.rhook("restraints.check", self.restraints_check)
        self.rhook("restraints.set", self.restraints_set)

    def restraints_check(self, user_uuid, restraints):
        user_restraints = self.objlist(UserRestraintList, query_index="user", query_equal=user_uuid)
        user_restraints.load(silent=True)
        for ent in user_restraints:
            till = ent.get("till")
            if till > self.now():
                kind = ent.get("kind")
                if kind in restraints:
                    if till > restraints[kind]["till"]:
                        restraints[kind]["till"] = till
                else:
                    restraints[kind] = {
                        "till": till
                    }

    def restraints_set(self, user_uuid, kind, interval, reason, admin=None, prolong=False):
        with self.lock(["UserRestraints"]):
            user_restraints = self.objlist(UserRestraintList, query_index="user", query_equal=user_uuid)
            user_restraints.load(silent=True)
            found = False
            for ent in user_restraints:
                if ent.get("kind") == kind:
                    if prolong:
                        ent.set("till", from_unixtime(unix_timestamp(ent.get("till")) + interval))
                    else:
                        ent.set("till", self.now(interval))
                    found = True
                    break
            if found:
                user_restraints.store()
            else:
                ent = self.obj(UserRestraint, data={})
                ent.set("user", user_uuid)
                ent.set("till", self.now(interval))
                ent.set("kind", kind)
                ent.store()
        if kind == "chat-silence":
            content = self._("Chat silence")
        if kind == "hide-info":
            content = self._("Hide info")
        elif kind == "forum-silence":
            content = self._("Forum silence")
        elif kind == "ban":
            content = self._("Ban")
        else:
            content = kind
        interval = self.call("l10n.literal_interval", interval)
        if prolong and found:
            interval = '%s %s' % (self._("plus"), interval)
        content = '%s: %s' % (content, interval)
        if reason:
            content = '%s\n%s' % (content, reason)
        self.call("dossier.write", user=user_uuid, admin=admin, content=content)

class RestraintsAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("admin-restraints.cleanup", self.cleanup)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("permissions.chat", self.permissions_chat)
        self.rhook("permissions.forum", self.permissions_forum)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-restraints.add", self.restraints_add, priv="logged")
        self.rhook("headmenu-admin-restraints.add", self.headmenu_restraints_add)
        self.rhook("ext-admin-restraints.remove", self.restraints_remove, priv="logged")

    def objclasses_list(self, objclasses):
        objclasses["UserRestraint"] = (UserRestraint, UserRestraintList)

    def schedule(self, sched):
        sched.add("admin-restraints.cleanup", "10 1 * * *", priority=10)

    def cleanup(self):
        with self.lock(["UserRestraints"]):
            self.objlist(UserRestraintList, query_index="till", query_finish=self.now()).remove()

    def permissions_list(self, perms):
        perms.append({"id": "restraints.ban", "name": self._("Banning users")})
        perms.append({"id": "restraints.hide-info", "name": self._("Hiding user's info")})

    def permissions_chat(self, perms):
        perms.append({"id": "restraints.chat-silence", "name": self._("Settings silence restraints for users in the chat")})

    def permissions_forum(self, perms):
        perms.append({"id": "restraints.forum-silence", "name": self._("Settings silence restraints for users on the forum")})

    def user_tables(self, user, tables):
        req = self.req()
        restraints = {}
        self.call("restraints.check", user.uuid, restraints)
        params = []
        kinds = {
            "chat-silence": self._("Chat silence"),
            "hide-info": self._("Hide info"),
            "forum-silence": self._("Forum silence"),
            "ban": self._("Ban"),
        }
        for kind in sorted(kinds.keys()):
            if req.has_access("restraints.%s" % kind):
                restraint = restraints.get(kind)
                if restraint:
                    status = '<span class="no">%s</span>' % (self._("till %s") % self.call("l10n.time_local", restraint["till"]))
                    actions = '<hook:admin.link href="restraints/remove/%s/%s" title="%s" />, <hook:admin.link href="restraints/add/%s/%s" title="%s" />' % (user.uuid, kind, self._("remove"), user.uuid, kind, self._("change"))
                else:
                    status = '<span class="yes">%s</span>' % self._("no")
                    actions = '<hook:admin.link href="restraints/add/%s/%s" title="%s" />' % (user.uuid, kind, self._("restraint///give"))
                params.append((kinds.get(kind, kind), status, actions))
        if params:
            tables.append({
                "type": "restraints",
                "title": self._("Restraints"),
                "rows": params,
                "order": 15,
            })

    def restraints_add(self):
        req = self.req()
        m = re_restraint_kind.match(req.args)
        if not m:
            self.call("web.not_found")
        user_uuid, kind = m.group(1, 2)
        self.call("session.require_permission", "restraints.%s" % kind)
        if req.ok():
            errors = {}
            interval = intz(req.param("v_interval"))
            if interval < 60 or interval > 86400 * 365:
                errors["v_interval"] = self._("Select silence interval")
            reason = req.param("reason").strip()
            if not reason:
                errors["reason"] = self._("Reason is mandatory")
            mode = intz(req.param("v_mode"))
            if mode < 1 or mode > 2:
                errors["v_mode"] = self._("Select correct mode")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            self.call("restraints.set", user_uuid, kind=kind, prolong=(mode == 1), interval=interval, reason=reason, admin=req.user())
            self.call("admin.redirect", "auth/user-dashboard/%s" % user_uuid, {"active_tab": "restraints"})
        intervals = [
            (60, self._("1 minute")),
            (300, self._("5 minutes")),
            (600, self._("10 minutes")),
            (1800, self._("30 minutes")),
            (3600, self._("1 hour")),
            (3600 * 2, self._("2 hours")),
            (3600 * 3, self._("3 hours")),
            (3600 * 6, self._("6 hours")),
            (3600 * 12, self._("12 hours")),
            (86400, self._("1 day")),
            (86400 * 2, self._("2 days")),
            (86400 * 4, self._("4 days")),
            (86400 * 7, self._("1 week")),
            (86400 * 14, self._("2 weeks")),
            (86400 * 21, self._("3 weeks")),
            (86400 * 30, self._("30 days")),
            (86400 * 60, self._("60 days")),
            (86400 * 90, self._("90 days")),
            (86400 * 365, self._("1 year")),
        ]
        fields = [
            {"name": "interval", "value": 3600, "values": intervals, "type": "combo", "label": self._("Silence time")},
            {"name": "mode", "label": self._("Restraint setting mode"), "type": "combo", "value": 1, "values": [(1, self._("Prolong")), (2, self._("Replace"))], "inline": True},
            {"name": "reason", "label": self._("Reason"), "type": "textarea"}
        ]
        self.call("admin.form", fields=fields)

    def headmenu_restraints_add(self, args):
        m = re_restraint_kind.match(args)
        if m:
            user_uuid, kind = m.group(1, 2)
            if kind == "chat-silence":
                return [self._("Chat silence"), "auth/user-dashboard/%s?active_tab=restraints" % user_uuid]
            elif kind == "hide-info":
                return [self._("Hide info"), "auth/user-dashboard/%s?active_tab=restraints" % user_uuid]
            elif kind == "forum-silence":
                return [self._("Forum silence"), "auth/user-dashboard/%s?active_tab=restraints" % user_uuid]
            elif kind == "ban":
                return [self._("Ban"), "auth/user-dashboard/%s?active_tab=restraints" % user_uuid]

    def restraints_remove(self):
        req = self.req()
        m = re_restraint_kind.match(req.args)
        if not m:
            self.call("web.not_found")
        user_uuid, kind = m.group(1, 2)
        self.call("session.require_permission", "restraints.%s" % kind)
        user_restraints = self.objlist(UserRestraintList, query_index="user", query_equal=user_uuid)
        user_restraints.load(silent=True)
        for ent in user_restraints:
            if ent.get("kind") == kind:
                ent.remove()
        self.call("admin.redirect", "auth/user-dashboard/%s" % user_uuid, {"active_tab": "restraints"})
