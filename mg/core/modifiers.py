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

    def objclasses_list(self, objclasses):
        objclasses["AlienModifier"] = (DBAlienModifier, DBAlienModifierList)

class Modifiers(Module):
    def register(self):
        Module.register(self)
        self.rhook("modifiers.kind", self.mod_kind)
        self.rhook("modifiers.add", self.mod_add)
        self.rhook("modifiers.prolong", self.mod_prolong)
        self.rhook("modifiers.list", self.mod_list)
        self.rhook("objclasses.list", self.objclasses_list)

    def objclasses_list(self, objclasses):
        objclasses["Modifier"] = (DBModifier, DBModifierList)

    def mod_prolong(self, target_type, target, kind, value, period):
        with self.lock(["Modifiers.%s" % target]):
            mod = self.mod_kind(target, kind)
            if mod:
                # Prolong
                self.objlist(DBModifierList, query_index="target", query_equal=target).remove()
                self._mod_add(target_type, target, kind, value, from_unixtime(unix_timestamp(mod["maxtill"]) + period))
            else:
                # Add new
                self._mod_add(target_type, target, kind, value, self.now(period))
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

    def _mod_add(self, target_type, target, kind, value, till):
        obj = self.obj(DBModifier)
        obj.set("target_type", target_type)
        obj.set("target", target)
        obj.set("kind", kind)
        obj.set("value", value)
        obj.set("till", till)
        mobj = self.main_app().obj(DBAlienModifier, obj.uuid, data={})
        mobj.set("till", till)
        mobj.set("app", self.app().tag)
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
            else:
                res = {
                    "cnt": 1,
                    "minval": val,
                    "maxval": val,
                    "mintill": till,
                    "maxtill": till,
                }
                modifiers[kind] = res
        if cache:
            modifiers_cache[target] = modifiers
        return modifiers

    def mod_kind(self, target, kind):
        return self.mod_list(target).get(kind)
