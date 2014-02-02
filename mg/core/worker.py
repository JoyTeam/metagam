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
from concurrence import Tasklet
from mg.core.common import *
import json
import time

class Worker(Module):
    def register(self):
        self.rdep([
            "mg.core.cluster.Cluster",
            "mg.core.l10n.L10n",
            "mg.core.web.Web",
            "mg.core.queue.Queue",
            "mg.core.dbexport.Export",
            "mg.core.cluster.ClusterDaemon",
            "mg.core.tasks.Tasks",
        ])
