from mg import *

class SiteAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-site.robots", self.robots, priv="site.robots")
        self.rhook("menu-admin-site.index", self.menu_site)

    def menu_root_index(self, menu):
        menu.append({"id": "site.index", "text": self._("Site"), "order": 30})

    def permissions_list(self, perms):
        perms.append({"id": "site.robots", "name": self._("Robots.txt administration")})

    def menu_site(self, menu):
        req = self.req()
        if req.has_access("site.robots"):
            menu.append({"id": "site/robots", "text": "robots.txt", "leaf": True})

    def robots(self):
        req = self.req()
        indexing = True if req.param("indexing") else False
        if req.param("ok"):
            config = self.app().config_updater()
            config.set("indexing.enabled", indexing)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            indexing = self.conf("indexing.enabled", True)
        fields = [
            {"name": "indexing", "type": "checkbox", "label": self._("Site indexing enabled"), "checked": indexing},
        ]
        self.call("admin.form", fields=fields)

class Counters(Module):
    def register(self):
        Module.register(self)
        self.rhook("web.setup_design", self.web_setup_design)

    def web_setup_design(self, vars):
        vars["counters"] = self.conf("counters.html")
        vars["head"] = vars.get("head", "") + self.conf("counters.head", "")

class CountersAdmin(Module):
    def register(self):
        Module.register(self)
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
        head = req.param("head")
        if req.param("ok"):
            config = self.app().config_updater()
            config.set("counters.html", html)
            config.set("counters.head", head)
            config.store()
            self.call("admin.response", self._("Counters stored"), {})
        else:
            html = self.conf("counters.html")
            head = self.conf("counters.head")
        fields = [
            {"name": "html", "type": "textarea", "label": self._("Counters HTML code"), "value": html},
            {"name": "head", "type": "textarea", "label": self._("Tracking code (before the end of 'head')"), "value": head},
        ]
        self.call("admin.form", fields=fields)
