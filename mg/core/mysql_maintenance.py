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

class MySQLMonitor(mg.Module):
    def register(self):
        self.rhook("mysql.register", self.register_mysql)

    def register_mysql(self):
        inst = self.app().inst
        # Register service
        int_app = inst.int_app
        srv = mg.SingleApplicationWebService(self.app(), "%s-mysql" % inst.instid, "mysql", "mysql")
        srv.serve_any_port()
        int_app.call("cluster.register-service", srv)
