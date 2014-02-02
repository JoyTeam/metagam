#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

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
