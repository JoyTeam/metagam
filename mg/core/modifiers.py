from mg import *

class DBAlienModifier(CassandraObject):
    """
    DBAlienModifiers are stored in the main database. Special checker process regularly
    looks for expired modifiers in the single index
    """
    _indexes = {
        "till": [[], "till"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AlienModifier-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBAlienModifier._indexes

class DBAlienModifierList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AlienModifier-"
        kwargs["cls"] = DBAlienModifier
        CassandraObjectList.__init__(self, *args, **kwargs)

class DBModifier(CassandraObject):
    """
    DBModifiers are stored in the project databases
    """
    _indexes = {
        "target": [["target"]],
        "till": [[], "till"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Modifier-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBModifier._indexes

class DBModifierList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Modifier-"
        kwargs["cls"] = DBModifier
        CassandraObjectList.__init__(self, *args, **kwargs)

class ModifiersManager(Module):
    def register(self):
        Module.register(self)
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
    def __init__(self, app, id="modifiers"):
        Daemon.__init__(self, app, "mg.core.modifiers.ModifiersDaemon", id)
        self.persistent = True

    def main(self):
        while not self.terminate:
            try:
                modifiers = self.objlist(DBAlienModifierList, query_index="till", query_finish=self.now())
                modifiers.load(silent=True)
                for mod in modifiers:
                    self.call("queue.add", "modifiers.stop", {"mod": mod.uuid}, retry_on_fail=True, app_tag=mod.get("app"), app_cls=mod.get("cls", "metagam"))
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(3)

class Modifiers(Module):
    def register(self):
        Module.register(self)
        self.rhook("modifiers.kind", self.mod_kind)
        self.rhook("modifiers.add", self.mod_add)
        self.rhook("modifiers.prolong", self.mod_prolong)
        self.rhook("modifiers.list", self.mod_list)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("all.schedule", self.schedule)
        self.rhook("modifiers.cleanup", self.mod_cleanup)
        self.rhook("modifiers.stop", self.mod_stop)

    def schedule(self, sched):
        sched.add("modifiers.cleanup", "20 1 * * *", priority=10)

    def mod_cleanup(self):
        modifiers = self.objlist(SessionList, query_index="till", query_finish=self.now())
        modifiers.load(silent=True)
        modifiers.remove()
        # Invalidating cache
        for mod in modifiers:
            try:
                del self.req()._modifiers_cache[mod.get("target")]
            except AttributeError:
                pass
            except KeyError:
                pass
        # Processing destroyed events
        for mod in modifiers:
            try:
                self.mod_destroyed(mod)
            except Exception as e:
                self.exception(e)

    def mod_stop(self, mod):
        try:
            modifier = self.obj(DBModifier, mod)
        except ObjectNotFoundException:
            pass
        else:
            modifier.remove()
            try:
                self.main_app().obj(DBAlienModifier, mod).remove()
            except ObjectNotFoundException:
                pass
            # Invalidating cache
            try:
                del self.req()._modifiers_cache[modifier.get("target")]
            except AttributeError:
                pass
            except KeyError:
                pass
            # Processing destroyed events
            self.mod_destroyed(modifier)

    def mod_destroyed(self, mod):
        self.debug("Destroyed modifier %s: %s", mod.uuid, mod.data)
        self.call("modifiers.destroyed", mod)

    def objclasses_list(self, objclasses):
        objclasses["Modifier"] = (DBModifier, DBModifierList)

    def mod_prolong(self, target_type, target, kind, value, period, **kwargs):
        with self.lock(["Modifiers.%s" % target]):
            mod = self.mod_kind(target, kind)
            if mod:
                # Prolong
                self.objlist(DBModifierList, query_index="target", query_equal=target).remove()
                self._mod_add(target_type, target, kind, value, from_unixtime(unix_timestamp(mod["maxtill"]) + period), period=period, **kwargs)
            else:
                # Add new
                self._mod_add(target_type, target, kind, value, self.now(period), period=period, **kwargs)
            # Invalidating cache
            try:
                del self.req()._modifiers_cache[target]
            except AttributeError:
                pass
            except KeyError:
                pass

    def mod_add(self, *args, **kwargs):
        with self.lock(["Modifiers.%s" % target]):
            self._mod_add(*args, **kwargs)

    def _mod_add(self, target_type, target, kind, value, till, **kwargs):
        obj = self.obj(DBModifier)
        obj.set("target_type", target_type)
        obj.set("target", target)
        obj.set("kind", kind)
        obj.set("value", value)
        obj.set("till", till)
        for key, val in kwargs.iteritems():
            obj.set(key, val)
        mobj = self.main_app().obj(DBAlienModifier, obj.uuid, data={})
        mobj.set("till", till)
        mobj.set("app", self.app().tag)
        mobj.set("cls", self.app().inst.cls)
        mobj.store()
        obj.store()

    def mod_list(self, target):
        cache = False
        try:
            req = self.req()
        except AttributeError:
            pass
        else:
            try:
                modifiers_cache = req._modifiers_cache
            except AttributeError:
                modifiers_cache = {}
                req._modifiers_cache = modifiers_cache
            try:
                return modifiers_cache[target]
            except KeyError:
                pass
            cache = True
        modifiers = {}
        lst = self.objlist(DBModifierList, query_index="target", query_equal=target)
        lst.load(silent=True)
        for ent in lst:
            kind = ent.get("kind")
            val = ent.get("value")
            till = ent.get("till")
            res = modifiers.get(kind)
            if res:
                if val > res["maxval"]:
                    res["maxval"] = val
                if val < res["minval"]:
                    res["minval"] = val
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
        if cache:
            modifiers_cache[target] = modifiers
        return modifiers

    def mod_kind(self, target, kind):
        return self.mod_list(target).get(kind)
