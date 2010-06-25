from mg.core import Module

class Server(Module):
    def register(self):
        Module.register(self)
        self.rdep(["db.CommonDatabaseStruct", "cluster.Director", "web.Web"])
