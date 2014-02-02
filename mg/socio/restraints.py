#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

from mg import *
from mg.core.auth import AuthLogList, DBBanIP, DBBanIPList
import re

re_restraint_kind = re.compile(r'^(\S+)/(forum-silence|chat-silence|ban|hide-info|ban-ip)$')
re_restraint_remove_ban_ip = re.compile(r'^(\S+)/([0-9\.\*]+)$')

class UserRestraint(CassandraObject):
    clsname = "UserRestraint"
    indexes = {
        "user": [["user"]],
        "till": [[], "till"],
    }

class UserRestraintList(CassandraObjectList):
    objcls = UserRestraint

class Restraints(Module):
    def register(self):
        self.rhook("restraints.check", self.restraints_check)
        self.rhook("restraints.set", self.restraints_set)
        self.rhook("restraints.ip-banned", self.ip_banned)

    def ip_banned(self, ip):
        tokens = ip.split(".")
        lst = self.objlist(DBBanIPList, [
            ip, 
            "%s.%s.%s.*" % (tokens[0], tokens[1], tokens[2]),
            "%s.%s.*.*" % (tokens[0], tokens[1])
        ])
        now = self.now()
        lst.load(silent=True)
        ban = None
        for obj in lst:
            if (ban is None or obj.get("till") > ban["till"]) and now < obj.get("till"):
                ban = {
                    "till": obj.get("till"),
                    "reason_user": obj.get("reason_user"),
                }
        return ban

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
                if ent.get("reason_user"):
                    if restraints[kind].get("reason_user"):
                        restraints[kind]["reason_user"] += u'\n%s' % ent.get("reason_user")
                    else:
                        restraints[kind]["reason_user"] = ent.get("reason_user")

    def restraints_set(self, user_uuid, kind, interval, reason, admin=None, prolong=False, reason_user=None):
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
                if reason_user:
                    ent.set("reason_user", reason_user)
                ent.store()
        if kind == "chat-silence":
            content = self._("Chat silence")
        if kind == "hide-info":
            content = self._("Hide info")
        elif kind == "forum-silence":
            content = self._("Forum silence")
        elif kind == "ban":
            content = self._("Ban")
        elif kind == "ban-ip":
            content = self._("Ban IP for registration")
        else:
            content = kind
        interval = self.call("l10n.literal_interval", interval)
        if prolong and found:
            interval = '%s %s' % (self._("plus"), interval)
        content = '%s: %s' % (content, interval)
        if reason:
            content = self._('{content}\nReason: {reason}').format(content=content, reason=reason)
        if reason_user:
            content = self._('{content}\nReason for the user: {reason}').format(content=content, reason=reason_user)
        self.call("dossier.write", user=user_uuid, admin=admin, content=content)

class RestraintsAdmin(Module):
    def register(self):
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
        self.rhook("ext-admin-restraints.remove-ban-ip", self.restraints_remove_ban_ip, priv="restraints.ban-ip")

    def objclasses_list(self, objclasses):
        objclasses["UserRestraint"] = (UserRestraint, UserRestraintList)

    def schedule(self, sched):
        sched.add("admin-restraints.cleanup", "10 1 * * *", priority=10)

    def cleanup(self):
        with self.lock(["UserRestraints"]):
            self.objlist(UserRestraintList, query_index="till", query_finish=self.now()).remove()

    def permissions_list(self, perms):
        perms.append({"id": "restraints.ban", "name": self._("Banning users")})
        perms.append({"id": "restraints.ban-ip", "name": self._("Banning IP-addresses")})
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
            "ban-ip": self._("Ban IP for registration"),
        }
        for kind in sorted(kinds.keys()):
            if req.has_access("restraints.%s" % kind):
                status = None
                header = kinds.get(kind, kind)
                if kind == "ban-ip":
                    lst = self.objlist(DBBanIPList, query_index="user", query_equal=user.uuid)
                    lst.load(silent=True)
                    now = self.now()
                    bans = []
                    for ent in lst:
                        if now < ent.get("till"):
                            params.append((
                                header,
                                '<span class="no">%s</span>' % (self._("{ip} till {till}").format(ip=ent.uuid, till=self.call("l10n.time_local", ent.get("till")))),
                                '<hook:admin.link href="restraints/remove-ban-ip/%s/%s" title="%s" />' % (user.uuid, ent.uuid, self._("remove"))
                            ))
                            header = None
                else:
                    restraint = restraints.get(kind)
                    if restraint:
                        status = '<span class="no">%s</span>' % (self._("till %s") % self.call("l10n.time_local", restraint["till"]))
                        actions = '<hook:admin.link href="restraints/remove/%s/%s" title="%s" />, <hook:admin.link href="restraints/add/%s/%s" title="%s" />' % (user.uuid, kind, self._("remove"), user.uuid, kind, self._("change"))
                if not status:
                    status = None
                    actions = '<hook:admin.link href="restraints/add/%s/%s" title="%s" />' % (user.uuid, kind, self._("restraint///give"))
                params.append((header, status, actions))
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
        default_interval = 3600
        default_mode = 1
        # loading IP addresses
        if kind == "ban-ip":
            ip_addresses_ok = {}
            ip_addresses_sel = {}
            lst = self.objlist(AuthLogList, query_index="user_performed", query_equal=user_uuid, query_reversed=True, query_limit=100)
            lst.load(silent=True)
            for ent in lst:
                ip = ent.get("ip")
                if ip:
                    ip_addresses_ok[ip] = 1
                    ip_addresses_sel[ip] = True
                    tokens = ip.split(".")
                    ip_addresses_ok["%s.%s.%s.*" % (tokens[0], tokens[1], tokens[2])] = 2
                    ip_addresses_ok["%s.%s.*.*" % (tokens[0], tokens[1])] = 3
            if not ip_addresses_ok:
                self.call("admin.response", self._("No IP addresses in the access log"), {})
            ip_addresses = ip_addresses_ok.items()
            ip_addresses.sort(cmp=lambda x, y: cmp(x[1], y[1]) or cmp(x[0], y[0]))
            ip_addresses = [(mask, mask) for mask, order in ip_addresses]
            default_interval = 86400 * 7
        # processing request
        if req.ok():
            errors = {}
            error = None
            interval = intz(req.param("v_interval"))
            if interval < 60 or interval > 86400 * 365:
                errors["v_interval"] = self._("Select silence interval")
            reason = req.param("reason").strip()
            if not reason:
                errors["reason"] = self._("Reason is mandatory")
            reason_user = req.param("reason_user").strip()
            if kind == "ban-ip":
                ips = set()
                for mask, label in ip_addresses:
                    if req.param("ip-%s" % mask):
                        ips.add(mask)
                if not ips:
                    error = self._("No IP addresses selected")
            else:
                mode = intz(req.param("v_mode"))
                if mode < 1 or mode > 2:
                    errors["v_mode"] = self._("Select correct mode")
            if len(errors) or error:
                self.call("web.response_json", {"success": False, "errors": errors, "error": error})
            if kind == "ban-ip":
                till = self.now(interval)
                for ip in ips:
                    try:
                        obj = self.obj(DBBanIP, ip)
                    except ObjectNotFoundException:
                        obj = self.obj(DBBanIP, ip, data={})
                    obj.set("ip", ip)
                    obj.set("till", till)
                    obj.set("user", user_uuid)
                    if reason_user:
                        obj.set("reason_user", reason_user)
                    obj.store()
                # writing to dossier
                interval = self.call("l10n.literal_interval", interval)
                content = u'%s: %s' % (self._("Ban {ip_addresses}").format(ip_addresses=", ".join(ips)), interval)
                if reason:
                    content = self._('{content}\nReason: {reason}').format(content=content, reason=reason)
                if reason_user:
                    content = self._('{content}\nReason for the user: {reason}').format(content=content, reason=reason_user)
                self.call("dossier.write", user=user_uuid, admin=req.user(), content=content)
            else:
                self.call("restraints.set", user_uuid, kind=kind, prolong=(mode == 1), interval=interval, reason=reason, admin=req.user(), reason_user=reason_user)
            self.call("admin.redirect", "auth/user-dashboard/%s" % user_uuid, {"active_tab": "restraints"})
        # rendering form
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
            {"name": "interval", "value": default_interval, "values": intervals, "type": "combo", "label": self._("Restraint time")}
        ]
        if kind == "ban-ip":
            for mask, label in ip_addresses:
                fields.append({"name": "ip-%s" % mask, "type": "checkbox", "label": label, "checked": ip_addresses_sel.get(mask)})
        else:
            fields.append({"name": "mode", "label": self._("Restraint setting mode"), "type": "combo", "value": default_mode, "values": [(1, self._("Prolong")), (2, self._("Replace"))], "inline": True})
        fields.append({"name": "reason", "label": self._("Reason"), "type": "textarea"})
        fields.append({"name": "reason_user", "label": self._("Reason visible to the violator"), "type": "textarea"})
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
            elif kind == "ban-ip":
                return [self._("Ban IP for registration"), "auth/user-dashboard/%s?active_tab=restraints" % user_uuid]

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

    def restraints_remove_ban_ip(self):
        req = self.req()
        m = re_restraint_remove_ban_ip.match(req.args)
        if not m:
            self.call("web.not_found")
        user_uuid, ip = m.group(1, 2)
        try:
            obj = self.obj(DBBanIP, ip)
            obj.remove()
            # writing to dossier
            content = self._("Removed ban {ip_address}").format(ip_address=ip)
            self.call("dossier.write", user=user_uuid, admin=req.user(), content=content)
        except ObjectNotFoundException:
            pass
        self.call("admin.redirect", "auth/user-dashboard/%s" % user_uuid, {"active_tab": "restraints"})
