from mg.constructor import *

class SecuritySuspicion(CassandraObject):
    clsname = "SecuritySuspicion"
    indexes = {
        "performed": [[], "performed"],
        "app_performed": [["app"], "performed"],
        "app_action_performed": [["app", "action"], "performed"],
        "action_performed": [["action"], "performed"],
        "admin_performed": [["admin"], "performed"],
    }

class SecuritySuspicionList(CassandraObjectList):
    objcls = SecuritySuspicion

class Security(ConstructorModule):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("security.suspicion", self.suspicion)
        self.rhook("security.icon", self.icon)

    def objclasses_list(self, objclasses):
        objclasses["SecuritySuspicion"] = (SecuritySuspicion, SecuritySuspicionList)

    def suspicion(self, **kwargs):
        ent = self.main_app().obj(SecuritySuspicion)
        ent.set("performed", self.now())
        ent.set("app", self.app().tag)
        for key, value in kwargs.iteritems():
            ent.set(key, value)
        ent.store()

    def icon(self):
        return ' <a href="//www.%s/doc/security" target="_blank"><img class="inline-icon" src="/st-mg/icons/security-check.png" alt="[sec]" title="%s" /></a>' % (self.main_host, self._("Read security note"))
