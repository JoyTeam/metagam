from mg import *
from concurrence import Tasklet
from mg.core.common import *
import json
import time

class Worker(Module):
    def register(self):
        self.rdep(["mg.core.cluster.Cluster", "mg.core.web.Web", "mg.core.queue.Queue", "mg.core.dbexport.Export"])
        self.rhook("core.application_reloaded", self.application_reloaded)

    def application_reloaded(self):
        self.app().inst.application_version = self.conf("application.version", 0)
