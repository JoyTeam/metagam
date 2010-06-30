from mg.core import Module

class Server(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.cass.CommonDatabaseStruct", "mg.cluster.Director", "mg.web.Web"])
