from mg import *
import re

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_aggr = re.compile(r'^(max|min|sum|cnt)_(.+)$')
re_delete_modifier = re.compile(r'^([a-f0-9]+)/(\S+)$')

class DBModifiers(CassandraObject):
    """
    DBModifiers are stored in the project databases
    """
    clsname = "Modifier"

class DBModifiersList(CassandraObjectList):
    objcls = DBModifiers

class MemberModifiers(Module):
    def __init__(self, app, target_type, uuid):
        Module.__init__(self, app, "mg.core.modifiers.MemberModifiers")
        self.target_type = target_type
        self.uuid = uuid

    @property
    def lock_key(self):
        return "Modifiers.%s" % self.uuid

    def load(self):
        try:
            self._mods = self.obj(DBModifiers, self.uuid)
        except ObjectNotFoundException:
            self._mods = self.obj(DBModifiers, self.uuid, data={})
            self._mods.set("mods", [])
            self._mods.set("target_type", self.target_type)
        # mapping uuid => mod
        self.expired = {}
        self.destroyed = {}
        self.prolong = {}
        self.created = {}
        self.mobjs = []
        try:
            del self._lst
        except AttributeError:
            pass

    def store(self, remove_expired=False):
        if remove_expired:
            # removing expired items without auto_prolong flag
            if self.expired:
                new_mods = []
                modified = False
                for mod in self._mods.get("mods"):
                    if mod["uuid"] in self.expired:
                        modified = True
                    else:
                        new_mods.append(mod)
                if modified:
                    self._mods.set("mods", new_mods)
        # storing database object
        if self._mods.dirty:
            self._mods.store()
            try:
                del self._lst
            except AttributeError:
                pass
        # storing mobjs
        if self.mobjs:
            for mobj in self.mobjs:
                self.sql_write.do("insert into modifiers(till, cls, app, target_type, target) values (?, ?, ?, ?, ?)", *mobj)
            self.mobjs = []

    def notify(self):
        expired = self.expired
        self.expired = {}
        destroyed = self.destroyed
        self.destroyed = {}
        created = self.created
        self.created = {}
        prolong = self.prolong
        self.prolong = {}
        # sending events
        for mod in created.values():
            self.call("%s-modifier.created" % self.target_type, self, mod)
            self.call("modifier.created", self, mod)
        for mod in destroyed.values():
            self.call("%s-modifier.destroyed" % self.target_type, self, mod)
            self.call("modifier.destroyed", self, mod)
        kinds = set()
        for mod in expired.values():
            kind = mod["kind"]
            if kind in kinds:
                continue
            kinds.add(kind)
            #self.debug("Expired modifier (target_type=%s, target=%s): %s", self.target_type, self.uuid, mod)
            self.call("%s-modifier.expired" % self.target_type, self, mod)
            self.call("modifier.expired", self, mod)
        for mod in prolong.values():
            self.call("%s-modifier.prolong" % self.target_type, self, mod)
            self.call("modifier.prolong", self, mod)

    def update(self, *args, **kwargs):
        with self.lock([self.lock_key]):
            self.load()
            self.mods()
            self.store(remove_expired=True)
        self.notify()

    def mods(self):
        try:
            return self._lst
        except AttributeError:
            pass
        if not getattr(self, "mod", None):
            self.load()
        modifiers = {}
        self.expired = {}
        self.prolong = {}
        now = None
        # Workaround
        if self._mods.get("mods") is None:
            self._mods.set("mods", [])
        # calculating list of currently alive objects
        # (without respect to their 'till')
        alive = set()
        for ent in self._mods.get("mods"):
            alive.add(ent.get("kind"))
        # checking all modifiers
        for ent in self._mods.get("mods"):
            kind = ent.get("kind")
            val = ent.get("value")
            till = ent.get("till")
            if till:
                if now is None:
                    now = self.now()
                if now >= till:
                    if ent.get("dependent") and ent.get("dependent") in alive:
                        # If the modifier depends on other modifier and parent modifier is still alive
                        # then don't touch expired child
                        # If nobody prolongs this 'child' modifier it will be destroyed
                        # on the next pass
                        pass
                    elif ent.get("auto_prolong"):
                        self.prolong[ent["uuid"]] = ent
                    else:
                        self.expired[ent["uuid"]] = ent
                        #self.debug("Found expired modifier (target_type=%s, target=%s): %s", self.target_type, self.uuid, ent)
                        continue
            res = modifiers.get(kind)
            if res:
                res["sumval"] += val
                if val > res["maxval"]:
                    res["maxval"] = val
                if val < res["minval"]:
                    res["minval"] = val
                if till:
                    if res["maxtill"] and till > res["maxtill"]:
                        res["maxtill"] = till
                    if res["mintill"] and till < res["mintill"]:
                        res["mintill"] = till
                res["mods"].append(ent)
            else:
                res = {
                    "cnt": 1,
                    "minval": val,
                    "maxval": val,
                    "sumval": val,
                    "mintill": till,
                    "maxtill": till,
                    "mods": [ent],
                }
                modifiers[kind] = res
        for mod in modifiers.values():
            mod["mods"].sort(cmp=lambda x, y: cmp(x.get("till", "9999-99-99"), y.get("till", "9999-99-99")))
        self._lst = modifiers
        return modifiers

    def touch(self):
        self._mods.touch()

    def add(self, *args, **kwargs):
        with self.lock([self.lock_key]):
            self.load()
            self._add(*args, **kwargs)
            self.store(remove_expired=True)
        self.notify()

    def _add(self, kind, value, till, **kwargs):
        ent = kwargs
        ent["uuid"] = uuid4().hex
        ent["kind"] = kind
        ent["value"] = value
        ent["till"] = till
        self._mods.get("mods").append(ent)
        self._mods.touch()
        self.created[ent["uuid"]] = ent
        if till:
            mobj = [till, self.app().inst.cls, self.app().tag, self.target_type, self.uuid]
            self.mobjs.append(mobj)
        return ent

    def destroy(self, *args, **kwargs):
        with self.lock([self.lock_key]):
            self.load()
            self._destroy(*args, **kwargs)
            self.store(remove_expired=True)
        self.notify()

    def _destroy(self, kind, expiration=False):
        new_mods = []
        modified = False
        for ent in self._mods.get("mods"):
            if ent["kind"] == kind:
                modified = True
                if expiration:
                    self.expired[ent["uuid"]] = ent
                else:
                    self.destroyed[ent["uuid"]] = ent
            else:
                new_mods.append(ent)
        if modified:
            self._mods.set("mods", new_mods)

    def get(self, kind):
        return self.mods().get(kind)

    def prolong(self, *args, **kwargs):
        with self.lock([self.lock_key]):
            self.load()
            self._prolong(*args, **kwargs)
            self.store(remove_expired=True)
        self.notify()

    def _prolong(self, kind, value, period, **kwargs):
        mod = self.get(kind)
        if mod:
            # Prolong
            self._destroy(kind)
            till = from_unixtime(unix_timestamp(mod["maxtill"]) + period)
            self._add(kind, value, till, period=period, **kwargs)
            # considering this items neither created nor destroyed
            self.created = dict([(uuid, mod) for uuid, mod in self.created.iteritems() if mod["kind"] != kind])
            self.destroyed = dict([(uuid, mod) for uuid, mod in self.destroyed.iteritems() if mod["kind"] != kind])
            self.prolong = dict([(uuid, mod) for uuid, mod in self.prolong.iteritems() if mod["kind"] != kind])
        else:
            # Add new
            till = self.now(period)
            ent = self._add(kind, value, till, period=period, **kwargs)

    def script_attr(self, attr, handle_exceptions=True):
        if self.get(attr):
            return 1
        m = re_aggr.match(attr)
        if m:
            aggr, kind = m.group(1, 2)
            mod = self.get(kind)
            if aggr == "max":
                return mod["maxval"] if mod else 0
            elif aggr == "min":
                return mod["minval"] if mod else 0
            elif aggr == "cnt":
                return mod["cnt"] if mod else 0
            elif aggr == "sum":
                return mod["sumval"] if mod else 0
        return 0

    def __str__(self):
        return "[mod %s.%s]" % (self.target_type, self.uuid)

    __repr__ = __str__

class ModifiersManager(Module):
    "This module is loaded in the 'main' project"
    def register(self):
        self.rhook("daemons.persistent", self.daemons_persistent)
        self.rhook("int-modifiers.daemon", self.daemon, priv="public")

    def daemons_persistent(self, daemons):
        daemons.append({"cls": "metagam", "app": "main", "daemon": "modifiers", "url": "/modifiers/daemon"})

    def daemon(self):
        self.debug("Running modifiers daemon")
        daemon = ModifiersDaemon(self.main_app())
        daemon.run()
        self.call("web.response_json", {"ok": True})

class ModifiersDaemon(Daemon):
    "This daemon constantly monitors expiring modifiers and sends notifications to the corresponding application"
    def __init__(self, app, id="modifiers"):
        Daemon.__init__(self, app, "mg.core.modifiers.ModifiersDaemon", id)
        self.persistent = True

    def main(self):
        while not self.terminate:
            try:
                now = self.now()
                for mod in self.sql_write.selectall_dict("select target_type, target, app, cls from modifiers where ?>=till group by target_type, target, app, cls", now):
                    self.call("queue.add", "modifiers.stop", {"target_type": mod["target_type"], "target": mod["target"]}, retry_on_fail=True, app_tag=mod["app"], app_cls=mod["cls"], unique="mod-%s-%s" % (mod["app"], mod["target"]))
                    self.sql_write.do("delete from modifiers where app=? and target=? and ?>=till", mod["app"], mod["target"], now)
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(3)

class Modifiers(Module):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("modifiers.stop", self.mod_stop)
        self.rhook("modifiers.obj", self.mod_obj)

    def child_modules(self):
        return ["mg.core.modifiers.ModifiersAdmin"]

    def mod_obj(self, target_type, target):
        return MemberModifiers(self.app(), target_type, target)

    def mod_stop(self, target_type, target):
        #self.debug("Called modifiers.stop for app=%s, target_type=%s, target=%s", self.app().tag, target_type, target)
        mods = MemberModifiers(self.app(), target_type, target)
        mods.update()

    def objclasses_list(self, objclasses):
        objclasses["Modifiers"] = (DBModifiers, DBModifiersList)

class ModifiersAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-modifier.delete", self.admin_delete, priv="modifiers.delete")

    def permissions_list(self, perms):
        perms.append({"id": "modifiers.view", "name": self._("Viewing users' modifiers")})
        perms.append({"id": "modifiers.delete", "name": self._("Deleting users' modifiers")})

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("modifiers.view"):
            modifiers = MemberModifiers(self.app(), "user", user.uuid)
            header = [
                self._("Code"),
                self._("Description"),
                self._("Cnt"),
                self._("Min/max/sum"),
                self._("Till"),
            ]
            if req.has_access("modifiers.delete"):
                header.append(self._("Deletion"))
            rows = []
            mods = modifiers.mods()
            self.call("admin-modifiers.descriptions", modifiers, mods)
            mods = mods.items()
            mods.sort(cmp=lambda x, y: cmp(x[0], y[0]))
            for m, mod in mods:
                # till
                mintill = self.call("l10n.time_local", mod.get("mintill"))
                maxtill = self.call("l10n.time_local", mod.get("maxtill"))
                if mintill == maxtill:
                    till = mintill
                else:
                    till = "%s -<br />%s" % (mintill, maxtill)
                # rendering
                rmod = [
                    "char.mod.%s" % m if re_valid_identifier.match(m) else m,
                    mod.get("description"),
                    mod.get("cnt"),
                    "%s/%s/%s" % (htmlescape(mod.get("minval")), htmlescape(mod.get("maxval")), htmlescape(mod.get("sumval"))),
                    till or self._("forever"),
                ]
                if req.has_access("modifiers.delete"):
                    rmod.append(u'<hook:admin.link href="modifier/delete/%s/%s" title="%s" confirm="%s" />' % (user.uuid, m, self._("delete"), self._("Are you sure want to delete this modifier?")))
                rows.append(rmod)
            table = {
                "type": "modifiers",
                "title": self._("Modifiers"),
                "order": 38,
                "header": header,
                "rows": rows,
            }
            tables.append(table)

    def admin_delete(self):
        req = self.req()
        m = re_delete_modifier.match(req.args)
        if not m:
            self.call("web.not_found")
        user_uuid, kind = m.group(1, 2)
        modifiers = MemberModifiers(self.app(), "user", user_uuid)
        modifiers.destroy(kind)
        self.call("admin.redirect", "auth/user-dashboard/%s?active_tab=modifiers" % user_uuid)
