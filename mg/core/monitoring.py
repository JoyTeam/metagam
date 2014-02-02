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

class ClusterMonitor(mg.Module):
    def register(self):
        self.rhook("mon-index.index", self.index, priv="public")

    def index(self):
        req = self.req()
        vars = {
            "title": self._("Cluster monitoring"),
        }
        daemons = self.int_app().call("cluster.daemons")
        servers = []
        databases = []
        procman = {}
        srvhost = {}
        dbhost = {}
        webservices = {}
        intservices = []
        for dmnid, dmninfo in daemons.iteritems():
            if dmninfo.get("cls") != self.inst.cls:
                continue
            hostid = dmninfo.get("hostid")
            for svcid, svcinfo in dmninfo.get("services", {}).iteritems():
                if svcinfo.get("type") == "procman":
                    procman[hostid] = svcinfo
                if svcinfo.get("webbackend"):
                    srvhost[hostid] = True
                if svcinfo.get("type") == "cassandra" or svcinfo.get("type") == "mysql":
                    dbhost[hostid] = True
                # service info
                webbackend = svcinfo.get("webbackend")
                if webbackend:
                    if webbackend in webservices:
                        srv = webservices[webbackend]
                    else:
                        srv = {
                            "name": webbackend
                        }
                        webservices[webbackend] = srv
                    if "svc-rps" in svcinfo:
                        srv["rps"] = srv.get("rps", 0) + svcinfo["svc-rps"]
                else:
                    srv = {
                        "name": svcid,
                    }
                    if "svc-rps" in svcinfo:
                        srv["rps"] = "%.2f" % svcinfo["svc-rps"]
                    intservices.append(srv)
        for hostid, procmaninfo in procman.iteritems():
            hostinfo = {
                "name": hostid,
            }
            if "cpu-load" in procmaninfo:
                hostinfo["cpu_load"] = "%.2f" % procmaninfo["cpu-load"]
            if "cpu-user" in procmaninfo:
                hostinfo["cpu_user"] = "%.2f%%" % (procmaninfo["cpu-user"] * 100)
            if "cpu-system" in procmaninfo:
                hostinfo["cpu_system"] = "%.2f%%" % (procmaninfo["cpu-system"] * 100)
            if "cpu-idle" in procmaninfo:
                hostinfo["cpu_idle"] = "%.2f%%" % (procmaninfo["cpu-idle"] * 100)
            if "cpu-iowait" in procmaninfo:
                hostinfo["cpu_iowait"] = "%.2f%%" % (procmaninfo["cpu-iowait"] * 100)
            if "cpu-stolen" in procmaninfo:
                hostinfo["cpu_stolen"] = "%.2f%%" % (procmaninfo["cpu-stolen"] * 100)
            if hostid in dbhost:
                databases.append(hostinfo)
            else:
                servers.append(hostinfo)
        webservices = webservices.values()
        for srv in webservices:
            if "rps" in srv:
                srv["rps"] = "%.2f" % srv["rps"]
        servers.sort(cmp=lambda x, y: cmp(x["name"], y["name"]))
        databases.sort(cmp=lambda x, y: cmp(x["name"], y["name"]))
        webservices.sort(cmp=lambda x, y: cmp(x["name"], y["name"]))
        intservices.sort(cmp=lambda x, y: cmp(x["name"], y["name"]))
        vars["servers"] = servers
        vars["databases"] = databases
        vars["webservices"] = webservices
        vars["intservices"] = intservices
        self.call("socio.setup-interface", vars)
        vars["content"] = self.call("web.parse_layout", "monitoring/dashboard.html", vars)
        self.call("web.response", self.call("web.parse_layout", "constructor/socio_global.html", vars))
