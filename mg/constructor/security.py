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
