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
        self.rhook("menu-admin-root.index", self.menu_root_index)

    def menu_root_index(self, menu):
        menu.append({"id": "peaceful.index", "text": self._("Peaceful activities"), "order": 22})
