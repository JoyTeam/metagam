from mg import *

class IndexPage(Module):
    def register(self):
        Module.register(self)

class IndexPageAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("ext-admin-indexpage.settings", self.ext_settings)

    def menu_root_index(self, menu):
        menu.append({"id": "indexpage/settings", "text": self._("Index page settings"), "leaf": True})

    def ext_settings(self):
        self.call("admin.response", "Index page settings", {})
