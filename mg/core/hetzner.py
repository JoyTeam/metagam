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

import mg
import re

class HetznerAdmin(mg.Module):
    def register(self):
        self.rhook("menu-admin-metagam.cluster", self.menu_metagam_cluster)
        self.rhook("ext-admin-hetzner.config", self.cluster_config, priv="clusterconfig")

    def menu_metagam_cluster(self, menu):
        req = self.req()
        if req.has_access("clusterconfig"):
            menu.append({"id": "hetzner/config", "text": self._("Hetzner configuration"), "leaf": True, "order": -5})

    def cluster_config(self):
        req = self.req()
        inst = self.app().inst
        dbconfig = inst.dbconfig
        params = ["hetzner_user", "hetzner_pass", "hetzner_ips"]
        if req.ok():
            errors = {}
            values = {}
            listParams = set(["hetzner_ips"])
            for param in params:
                val = req.param(param).strip()
                values[param] = val
                if val == "":
                    dbconfig.delkey(param)
                else:
                    if param in listParams:
                        val = re.split(r'\s*,\s*', val)
                    dbconfig.set(param, val)
            dbconfig.store()
            self.call("cluster.query-services", "int", "/core/dbconfig")
            self.call("admin.response", self._("Configuration stored"), {})
        fields = []
        fields.append({"name": "hetzner_user", "label": self._("Hetzner username"), "value": dbconfig.get("hetzner_user")})
        fields.append({"name": "hetzner_pass", "label": self._("Hetzner password"), "value": dbconfig.get("hetzner_pass")})
        fields.append({"name": "hetzner_ips", "label": self._("Hetzner failover ip addresses (comma separated list)"), "value": ", ".join(dbconfig.get("hetzner_ips", []))})
        self.call("admin.form", fields=fields)

