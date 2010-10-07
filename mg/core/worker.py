from mg import *

class Worker(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.cass_struct.CommonCassandraStruct", "mg.core.cluster.Cluster", "mg.core.web.Web", "mg.core.queue.Queue"])
        self.rhook("core.fastidle", self.fastidle)

    def fastidle(self):
        self.call("core.check_last_ping")
