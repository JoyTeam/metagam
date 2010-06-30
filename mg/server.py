from mg.core import Module
import subprocess
import sys
import re

class Server(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.cass.CommonDatabaseStruct", "mg.cluster.Cluster", "mg.web.Web"])
        self.rhook("int-server.spawn", self.spawn)

    def spawn(self, args, request):
        executable = re.sub(r'[^\/]+$', 'mg_worker', sys.argv[0])
        print "running %s" % executable
        for i in range(0, int(request.param("workers"))):
            subprocess.Popen(executable)
        return request.jresponse({ "ok": 1 })
