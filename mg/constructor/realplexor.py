import mg.core.realplexor
from mg import *

class Realplexor(Module):
    def register(self):
        Module.register(self)
        self.rhook("stream.send", self.send)

    def send(self, ids, data):
        self.debug("Sending to %s%s: %s" % (self.app().tag + "_", ids, data))
        rpl = mg.core.realplexor.Realplexor(self.main_app().config.get("cluster.realplexor", "127.0.0.1"), 10010, self.app().tag + "_")
        rpl.send(ids, data)

class RealplexorAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-constructor.cluster", self.menu_constructor_cluster)
        self.rhook("ext-admin-constructor.realplexor-settings", self.realplexor_settings, priv="realplexor.config")
        self.rhook("headmenu-admin-constructor.realplexor-settings", self.headmenu_realplexor_settings)

    def permissions_list(self, perms):
        perms.append({"id": "realplexor.config", "name": self._("Realplexor configuration")})

    def menu_constructor_cluster(self, menu):
        req = self.req()
        if req.has_access("realplexor.config"):
            menu.append({"id": "constructor/realplexor-settings", "text": self._("Realplexor"), "leaf": True})

    def realplexor_settings(self):
        req = self.req()
        realplexor = req.param("realplexor")
        if req.param("ok"):
            config = self.app().config
            config.set("cluster.realplexor", realplexor)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            realplexor = self.conf("cluster.realplexor", "127.0.0.1")
        fields = [
            {"name": "realplexor", "label": self._("Realplexor host name"), "value": realplexor},
        ]
        self.call("admin.form", fields=fields)

    def headmenu_realplexor_settings(self, args):
        return self._("Realplexor settings")
