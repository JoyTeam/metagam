from mg.core import Module

class Worker(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.cass.CommonDatabaseStruct", "mg.cluster.Cluster", "mg.web.Web"])
