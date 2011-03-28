from mg import *

class Admin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)

    def menu_root_index(self, menu):
        req = self.req()
        menu.append({"id": "constructor.cluster", "text": self._("Cluster"), "order": -50})
