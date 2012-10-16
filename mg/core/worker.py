from mg import *
from concurrence import Tasklet
from mg.core.common import *
import json
import time

class Worker(Module):
    def register(self):
        self.rdep(["mg.core.cluster.Cluster", "mg.core.web.Web", "mg.core.queue.Queue", "mg.core.dbexport.Export"])
        self.rhook("core.appfactory", self.appfactory, priority=-10)
        self.rhook("core.webservice", self.webservice, priority=-10)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("core.application_reloaded", self.application_reloaded)

    def objclasses_list(self, objclasses):
        objclasses["WorkerStatus"] = (WorkerStatus, WorkerStatusList)

    def appfactory(self):
        raise Hooks.Return(ApplicationFactory(self.app().inst))

    def webservice(self):
        raise Hooks.Return(WebService(self.app().inst))

    def application_reloaded(self):
        self.app().inst.application_version = self.conf("application.version", 0)
