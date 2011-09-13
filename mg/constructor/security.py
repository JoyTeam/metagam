from mg.constructor import *

class SecuritySuspicion(CassandraObject):
    _indexes = {
        "performed": [[], "performed"],
        "app-performed": [["app"], "performed"],
        "app-action-performed": [["app", "action"], "performed"],
        "action-performed": [["action"], "performed"],
        "admin-performed": [["admin"], "performed"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "SecuritySuspicion-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return SecuritySuspicion._indexes

class SecuritySuspicionList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "SecuritySuspicion-"
        kwargs["cls"] = SecuritySuspicion
        CassandraObjectList.__init__(self, *args, **kwargs)

class Security(ConstructorModule):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("security.suspicion", self.suspicion)

    def objclasses_list(self, objclasses):
        objclasses["SecuritySuspicion"] = (SecuritySuspicion, SecuritySuspicionList)

    def suspicion(self, **kwargs):
        ent = self.main_app().obj(SecuritySuspicion)
        ent.set("performed", self.now())
        ent.set("app", self.app().tag)
        for key, value in kwargs.iteritems():
            ent.set(key, value)
        ent.store()
