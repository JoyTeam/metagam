from mg import *

class DBAlienModifier(CassandraObject):
    """
    DBAlienModifiers are stored in the main database. Special checker process regularly
    looks for expired modifiers in the single index
    """
    clsname = "AlienModifier"
    indexes = {
        "till": [[], "till"],
    }

class DBAlienModifierList(CassandraObjectList):
    objcls = DBAlienModifier

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
                mobj.store()
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
                        continue
            res = modifiers.get(kind)
            if res:
                if val > res["maxval"]:
                    res["maxval"] = val
                if val < res["minval"]:
                    res["minval"] = val
                if till:
                    if till > res["maxtill"]:
                        res["maxtill"] = till
                    if till < res["mintill"]:
                        res["mintill"] = till
                res["mods"].append(ent)
            else:
                res = {
                    "cnt": 1,
                    "minval": val,
                    "maxval": val,
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
            mobj = self.main_app().obj(DBAlienModifier, ent["uuid"], data={})
            mobj.set("target_type", self.target_type)
            mobj.set("target", self.uuid)
            mobj.set("till", till)
            mobj.set("app", self.app().tag)
            mobj.set("cls", self.app().inst.cls)
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
        return 1 if self.get(attr) else 0

    def __str__(self):
        return "[mod %s.%s]" % (self.target_type, self.uuid)

    __repr__ = __str__

class ModifiersManager(Module):
    "This module is loaded in the 'main' project"
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("daemons.persistent", self.daemons_persistent)
        self.rhook("int-modifiers.daemon", self.daemon, priv="public")

    def objclasses_list(self, objclasses):
        objclasses["AlienModifier"] = (DBAlienModifier, DBAlienModifierList)

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
                modifiers = self.objlist(DBAlienModifierList, query_index="till", query_finish=self.now())
                modifiers.load(silent=True)
                for mod in modifiers:
                    target_type = mod.get("target_type")
                    target = mod.get("target")
                    if target and target_type:
                        self.call("queue.add", "modifiers.stop", {"target_type": target_type, "target": target}, retry_on_fail=True, app_tag=mod.get("app"), app_cls=mod.get("cls", "metagam"), unique="mod-%s" % target)
                modifiers.remove()
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
        mods = MemberModifiers(self.app(), target_type, target)
        mods.update()

    def objclasses_list(self, objclasses):
        objclasses["Modifiers"] = (DBModifiers, DBModifiersList)

class ModifiersAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("auth.user-tables", self.user_tables)

    def permissions_list(self, perms):
        perms.append({"id": "modifiers.view", "name": self._("Viewing users' modifiers")})

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("modifiers.view"):
            modifiers = MemberModifiers(self.app(), "user", user.uuid)
            header = [
                self._("Code"),
                self._("Description"),
                self._("Cnt"),
                self._("Min"),
                self._("Max"),
                self._("Till"),
            ]
            rows = []
            mods = modifiers.mods()
            self.call("admin-modifiers.descriptions", mods)
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
                    htmlescape(m),
                    htmlescape(mod.get("description")),
                    mod.get("cnt"),
                    htmlescape(mod.get("minval")),
                    htmlescape(mod.get("maxval")),
                    till,
                ]
                rows.append(rmod)
            table = {
                "type": "modifiers",
                "title": self._("Modifiers"),
                "order": 38,
                "header": header,
                "rows": rows,
            }
            tables.append(table)
