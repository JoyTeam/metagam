from mg.constructor import *

class Peaceful(ConstructorModule):
    def register(self):
        self.rhook("modules.list", self.modules_list)

    def child_modules(self):
        modules = ["mg.mmorpg.peaceful.PeacefulAdmin"]
        if self.conf("module.crafting"):
            modules.append("mg.mmorpg.crafting.Crafting")
        return modules

    def modules_list(self, modules):
        modules.extend([
            {
                "id": "crafting",
                "name": self._("Crafting"),
                "description": self._("Crafting"),
                "parent": "peaceful",
            }
        ])

class PeacefulAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-peaceful.index", self.menu_peaceful_index)

    def permissions_list(self, perms):
        perms.append({"id": "peaceful.config", "name": self._("Peaceful activities: configuration")})

    def menu_root_index(self, menu):
        menu.append({"id": "peaceful.index", "text": self._("Peaceful activities"), "order": 22})

    def menu_peaceful_index(self, menu):
        req = self.req()
        if req.has_access("peaceful.config"):
            menu.append({"id": "peaceful/config", "text": self._("Peaceful activities configuration"), "order": 0, "leaf": True})
