from mg import *
import re

re_limit_kind = re.compile(r'^(\S+)/(forum-silence|chat-silence)$')

class UserLimit(CassandraObject):
    _indexes = {
        "user": [["user"]],
        "till": [[], "till"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserLimit-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return UserLimit._indexes

class UserLimitList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserLimit-"
        kwargs["cls"] = UserLimit
        CassandraObjectList.__init__(self, *args, **kwargs)

class Limits(Module):
    def register(self):
        Module.register(self)
        self.rhook("limits.check", self.limits_check)
        self.rhook("limits.set", self.limits_set)

    def limits_check(self, user_uuid, limits):
        user_limits = self.objlist(UserLimitList, query_index="user", query_equal=user_uuid)
        user_limits.load(silent=True)
        for ent in user_limits:
            till = ent.get("till")
            if till > self.now():
                kind = ent.get("kind")
                if kind in limits:
                    if till > limits[kind]["till"]:
                        limits[kind]["till"] = till
                else:
                    limits[kind] = {
                        "till": till
                    }

    def limits_set(self, user_uuid, kind, interval, reason, admin=None, prolong=False):
        with self.lock(["UserLimits"]):
            user_limits = self.objlist(UserLimitList, query_index="user", query_equal=user_uuid)
            user_limits.load(silent=True)
            found = False
            for ent in user_limits:
                if ent.get("kind") == kind:
                    if prolong:
                        ent.set("till", from_unixtime(unix_timestamp(ent.get("till")) + interval))
                    else:
                        ent.set("till", self.now(interval))
                    found = True
                    break
            if found:
                user_limits.store()
            else:
                ent = self.obj(UserLimit, data={})
                ent.set("user", user_uuid)
                ent.set("till", self.now(interval))
                ent.set("kind", kind)
                ent.store()
        if kind == "chat-silence":
            content = self._("Chat silence")
        elif kind == "forum-silence":
            content = self._("Forum silence")
        else:
            content = kind
        interval = self.call("l10n.literal_interval", interval)
        if prolong and found:
            interval = '%s %s' % (self._("plus"), interval)
        content = '%s: %s' % (content, interval)
        if reason:
            content = '%s\n%s' % (content, reason)
        self.call("dossier.write", user=user_uuid, admin=admin, content=content)

class LimitsAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("admin-limits.cleanup", self.cleanup)
        self.rhook("permissions.chat", self.permissions_chat)
        self.rhook("permissions.forum", self.permissions_forum)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-limits.add", self.limits_add, priv="logged")
        self.rhook("headmenu-admin-limits.add", self.headmenu_limits_add)
        self.rhook("ext-admin-limits.remove", self.limits_remove, priv="logged")

    def objclasses_list(self, objclasses):
        objclasses["UserLimit"] = (UserLimit, UserLimitList)

    def schedule(self, sched):
        sched.add("admin-limits.cleanup", "10 1 * * *", priority=10)

    def cleanup(self):
        with self.lock(["UserLimits"]):
            self.objlist(UserLimitList, query_index="till", query_finish=self.now()).remove()

    def permissions_chat(self, perms):
        perms.append({"id": "limits.chat-silence", "name": self._("Settings silence limits for users in the chat")})

    def permissions_forum(self, perms):
        perms.append({"id": "limits.forum-silence", "name": self._("Settings silence limits for users on the forum")})

    def user_tables(self, user, tables):
        req = self.req()
        limits = {}
        self.call("limits.check", user.uuid, limits)
        params = []
        kinds = {
            "chat-silence": self._("Chat silence"),
            "forum-silence": self._("Forum silence"),
        }
        for kind in sorted(kinds.keys()):
            if req.has_access("limits.%s" % kind):
                limit = limits.get(kind)
                if limit:
                    status = '<span class="no">%s</span>' % (self._("till %s") % self.call("l10n.timeencode2", limit["till"]))
                    actions = '<hook:admin.link href="limits/remove/%s/%s" title="%s" />, <hook:admin.link href="limits/add/%s/%s" title="%s" />' % (user.uuid, kind, self._("remove"), user.uuid, kind, self._("change"))
                else:
                    status = '<span class="yes">%s</span>' % self._("no")
                    actions = '<hook:admin.link href="limits/add/%s/%s" title="%s" />' % (user.uuid, kind, self._("limit///give"))
                params.append((kinds.get(kind, kind), status, actions))
        if params:
            tables.append({
                "title": self._("User limits"),
                "rows": params,
                "order": -10,
            })

    def limits_add(self):
        req = self.req()
        m = re_limit_kind.match(req.args)
        if not m:
            self.call("web.not_found")
        user_uuid, kind = m.group(1, 2)
        self.call("session.require_permission", "limits.%s" % kind)
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
            self.call("limits.set", user_uuid, kind=kind, prolong=(mode == 1), interval=interval, reason=reason, admin=req.user())
            self.call("admin.redirect", "auth/user-dashboard/%s" % user_uuid)
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
            {"name": "mode", "label": self._("Limit setting mode"), "type": "combo", "value": 1, "values": [(1, self._("Prolong")), (2, self._("Replace"))], "inline": True},
            {"name": "reason", "label": self._("Reason"), "type": "textarea"}
        ]
        self.call("admin.form", fields=fields)

    def headmenu_limits_add(self, args):
        m = re_limit_kind.match(args)
        if m:
            user_uuid, kind = m.group(1, 2)
            if kind == "chat-silence":
                return [self._("Chat silence"), "auth/user-dashboard/%s" % user_uuid]
            elif kind == "forum-silence":
                return [self._("Forum silence"), "auth/user-dashboard/%s" % user_uuid]

    def limits_remove(self):
        req = self.req()
        m = re_limit_kind.match(req.args)
        if not m:
            self.call("web.not_found")
        user_uuid, kind = m.group(1, 2)
        self.call("session.require_permission", "limits.%s" % kind)
        user_limits = self.objlist(UserLimitList, query_index="user", query_equal=user_uuid)
        user_limits.load(silent=True)
        for ent in user_limits:
            if ent.get("kind") == kind:
                ent.remove()
        self.call("admin.redirect", "auth/user-dashboard/%s" % user_uuid)
