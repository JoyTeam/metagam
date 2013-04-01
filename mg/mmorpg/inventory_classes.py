from mg import *
import re
import hashlib

re_param_attr = re.compile(r'^p_(.+)')
re_dna_parse = re.compile(r'^([a-f0-9]+)(?:|_([0-9a-f]+))$')

class DBItemType(CassandraObject):
    clsname = "ItemType"
    indexes = {
        "all": [[], "name_lower"],
        "name": [["name_lower"]],
    }

class DBItemTypeList(CassandraObjectList):
    objcls = DBItemType

class DBMemberInventory(CassandraObject):
    clsname = "MemberInventory"
    indexes = {
        "all": [[]],
    }

class DBMemberInventoryList(CassandraObjectList):
    objcls = DBMemberInventory

class DBItemTypeParams(CassandraObject):
    clsname = "ItemTypeParams"

class DBItemTypeParamsList(CassandraObjectList):
    objcls = DBItemTypeParams

class DBItemTransfer(CassandraObject):
    clsname = "ItemTransfer"
    indexes = {
        "performed": [[], "performed"],
        "type": [["type"], "performed"],
        "owner_type": [["owner", "type"], "performed"],
        "owner": [["owner"], "performed"],
        "description": [["description"], "performed"],
        "admin": [["admin"], "performed"],
    }

class DBItemTransferList(CassandraObjectList):
    objcls = DBItemTransfer

def dna_join(item_type, dna_suffix):
    res = item_type or ""
    if dna_suffix:
        res = "%s_%s" % (res, dna_suffix)
    return res

def dna_make(mods):
    if not mods:
        return None
    tokens = mods.items()
    tokens.sort(cmp=lambda x, y: cmp(x[0], y[0]))
    new_tokens = []
    for k, v in tokens:
        if type(v) == int or type(v) == float or type(v) == long:
            new_tokens.append((k, str(v)))
        elif type(v) == str or type(v) == unicode:
            new_tokens.append((k, urlencode(v)))
        else:
            raise RuntimeError("Unknown DNA value type: %s" % type(v))
    tokens = "&".join('%s=%s' % (k, v) for k, v in new_tokens)
    dna = hashlib.md5(tokens).hexdigest().lower()
    return dna

def dna_parse(dna):
    if type(dna) != str and type(dna) != unicode:
        return None, None
    m = re_dna_parse.match(dna)
    if not m:
        return None, None
    else:
        return m.group(1, 2)

class ItemType(Module):
    def __init__(self, app, uuid, dna_suffix=None, mods=None, db_item_type=None, db_params=None, fqn="mg.mmorpg.inventory.ItemType"):
        Module.__init__(self, app, fqn)
        self.uuid = uuid
        self._dna_suffix = dna_suffix
        self.mods = mods
        if db_item_type:
            self._db_item_type = db_item_type
        if db_params:
            self._db_params = db_params

    @property
    def dna_suffix(self):
        return self._dna_suffix

    @property
    def dna(self):
        try:
            return self._dna
        except AttributeError:
            self._dna = dna_join(self.uuid, self._dna_suffix)
            return self._dna

    def update_dna(self):
        try:
            delattr(self, "_dna")
        except AttributeError:
            pass
        self._dna_suffix = dna_make(self.mods)

    @property
    def db_item_type(self):
        try:
            return self._db_item_type
        except AttributeError:
            pass
        try:
            req = self.req()
        except AttributeError:
            try:
                self._db_item_type = self.obj(DBItemType, self.uuid)
            except ObjectNotFoundException:
                self._db_item_type = self.obj(DBItemType, self.uuid, data={})
            return self._db_item_type
        try:
            cache = req._db_item_type_cache
        except AttributeError:
            cache = {}
            req._db_item_type_cache = cache
        try:
            self._db_item_type = cache[self.uuid] 
            return self._db_item_type
        except KeyError:
            pass
        try:
            obj = self.obj(DBItemType, self.uuid)
        except ObjectNotFoundException:
            obj = self.obj(DBItemType, self.uuid, data={})
        cache[self.uuid] = obj
        self._db_item_type = obj
        return obj

    def get(self, key, default=None):
        if self.mods:
            try:
                return self.mods[key]
            except KeyError:
                pass
        return self.db_item_type.get(key, default)

    @property
    def name(self):
        try:
            return self._name
        except AttributeError:
            self._name = self.get("name")
            return self._name

    @property
    def name_g(self):
        try:
            return self._name_g
        except AttributeError:
            self._name_g = self.get("name_g") or self.get("name")
            return self._name_g

    @property
    def name_gp(self):
        try:
            return self._name_gp
        except AttributeError:
            self._name_gp = self.get("name_gp") or self.get("name")
            return self._name_gp

    @property
    def name_a(self):
        try:
            return self._name_a
        except AttributeError:
            self._name_a = self.get("name_a") or self.get("name")
            return self._name_a

    def valid(self):
        try:
            db = self.db_item_type
        except ObjectNotFoundException:
            return False
        else:
            return True

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "id":
            return self.uuid
        elif attr == "type":
            return self.uuid
        elif attr == "dna":
            return self.dna
        elif attr == "name":
            return self.name
        elif attr == "name_gp":
            return self.name_gp
        elif attr == "name_a":
            return self.name_a
        elif attr == "equip":
            return 1 if self.get("equip") else 0
        elif attr == "fractions":
            return self.get("fractions", 0)
        elif attr == "used":
            return self.mods.get(":used", 0) if self.mods else 0
        elif attr == "frac_ratio":
            fractions = self.get("fractions")
            if fractions:
                used = self.mods.get(":used", 0) if self.mods else 0
                return (fractions - used) * 1.0 / fractions
            else:
                return 1.0
        else:
            m = re_param_attr.match(attr)
            if m:
                param = m.group(1)
                return self.param(param, handle_exceptions)
            else:
                raise AttributeError(attr)

    def __str__(self):
        return "[item %s]" % utf2str(self.name)
    
    def __unicode__(self):
        return u"[item %s]" % self.name
    
    __repr__ = __str__

    @property
    def db_params(self):
        try:
            return self._db_params
        except AttributeError:
            pass
        try:
            req = self.req()
        except AttributeError:
            self._db_params = self.obj(DBItemTypeParams, self.uuid, silent=True)
            return self._db_params
        try:
            cache = req._db_item_params_cache
        except AttributeError:
            cache = {}
            req._db_item_params_cache = cache
        try:
            self._db_params = cache[self.uuid]
            return self._db_params
        except KeyError:
            pass
        obj = self.obj(DBItemTypeParams, self.uuid, silent=True)
        cache[self.uuid] = obj
        self._db_params = obj
        return obj

    def param(self, key, handle_exceptions=True):
        try:
            cache = self._param_cache
        except AttributeError:
            cache = {}
            self._param_cache = cache
        try:
            return cache[key]
        except KeyError:
            # 'param-value' handles cache storing automatically
            return self.call("item-types.param-value", self, key, handle_exceptions)

    def script_params(self):
        return {"item": self}

    def image(self, kind):
        try:
            cache = self._image_cache
        except AttributeError:
            cache = {}
            self._image_cache = cache
        try:
            return cache[kind]
        except KeyError:
            # 'image' handles cache storing automatically
            return self.call("item-type.image", self, kind)

    @property
    def discardable(self):
        try:
            return self._discardable
        except AttributeError:
            self._discardable = self.get("discardable", 1)
            return self._discardable

    def cat(self, catgroup_id):
        return self.call("item-type.cat", self, catgroup_id)

    @property
    def expiration(self):
        try:
            return self._expiration
        except AttributeError:
            self._expiration = self.get("exp-till")
            return self._expiration

    def copy(self):
        new_item_type = ItemType(self.app(), self.uuid, db_item_type=self.db_item_type, db_params=self.db_params, dna_suffix=self._dna_suffix)
        if self.mods:
            new_item_type.mods = self.mods.copy()
        else:
            new_item_type.mods = None
        return new_item_type
