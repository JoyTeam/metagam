from mg import *

class SiteAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)

    def menu_root_index(self, menu):
        menu.append({"id": "site.index", "text": self._("Site")})

class Counters(Module):
    def register(self):
        Module.register(self)
        self.rhook("web.setup_design", self.web_setup_design)

    def web_setup_design(self, vars):
        vars["counters"] = self.conf("counters.html")

class CountersAdmin(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.sites.SiteAdmin"])
        self.rhook("menu-admin-site.index", self.menu_site)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-site.counters", self.counters, priv="site.counters")

    def permissions_list(self, perms):
        perms.append({"id": "site.counters", "name": self._("Counters administration")})

    def menu_site(self, menu):
        req = self.req()
        if req.has_access("site.counters"):
            menu.append({"id": "site/counters", "text": self._("Counters"), "leaf": True})

    def counters(self):
        req = self.req()
        html = req.param("html")
        if req.param("ok"):
            config = self.app().config
            config.set("counters.html", html)
            config.store()
            self.call("admin.response", self._("Counters stored"), {})
        else:
            html = self.conf("counters.html")
        fields = [
            {"name": "html", "type": "textarea", "label": self._("Counters HTML code"), "value": html},
        ]
        self.call("admin.form", fields=fields)
