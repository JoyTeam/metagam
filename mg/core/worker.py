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
