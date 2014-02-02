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

from mg import *

class DBExport(CassandraObject):
    clsname = "Export"
    indexes = {
        "all": [[], "stored"],
    }

class DBExportList(CassandraObjectList):
    objcls = DBExport

class Export(Module):
    def register(self):
        self.rhook("dbexport.add", self.add)
        self.rhook("int-dbexport.get", self.get, priv="public")
        self.rhook("int-dbexport.delete", self.delete, priv="public")

    def add(self, tp, **data):
        obj = self.int_app().obj(DBExport)
        for key, val in data.iteritems():
            obj.set(key, val)
        obj.set("app", self.app().tag)
        obj.set("type", tp)
        obj.set("stored", self.now())
        obj.store()

    def get(self):
        with self.lock(["DBExport"]):
            lst = self.objlist(DBExportList, query_index="all", query_limit=1000)
            lst.load(silent=True)
            self.call("web.response_json", lst.data())

    def delete(self):
        req = self.req()
        with self.lock(["DBExport"]):
            self.objlist(DBExportList, uuids=req.param("uuids").split(",")).remove()
            self.call("web.response_json", {"ok": True})
