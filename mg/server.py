from mg.core import Module
import subprocess
import sys
import re

class Server(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.cass.CommonDatabaseStruct", "mg.cluster.Cluster", "mg.web.Web"])
        self.rhook("int-server.spawn", self.spawn)
        self.rhook("core.fastidle", self.fastidle)
        self.executable = re.sub(r'[^\/]+$', 'mg_worker', sys.argv[0])

    def running_workers(self):
        """
        returns map of currently running worker processes (worker_id => process)
        """
        app = self.app()
        try:
            return app.running_workers
        except:
            app.running_workers = {"count": 0}
            return app.running_workers

    def spawn(self, args, request):
        workers = self.running_workers()
        new_count = int(request.param("workers"))
        old_count = workers["count"]
        server_id = self.app().server_id
        if new_count < old_count: 
            # Killing
            workers["count"] = new_count
            for i in range(new_count, old_count):
                process = workers[i]
                self.debug("terminating child %d (pid %d)", i, process.pid)
                process.terminate()
                del workers[i]
        elif new_count > old_count:
            # Spawning
            for i in range(old_count, new_count):
                self.debug("running child %d (process %s)", i, self.executable)
                workers[i] = subprocess.Popen([self.executable, "%s-%d" % (server_id, i)])
            workers["count"] = new_count
        return request.jresponse({ "ok": 1 })

    def fastidle(self):
        workers = self.running_workers()
        server_id = self.app().server_id
        for i in range(0, workers["count"]):
            workers[i].poll()
            if workers[i].returncode is not None:
                self.debug("respawning child %d (process %s)", i, self.executable)
                workers[i] = subprocess.Popen([self.executable, "%s-%d" % (server_id, i)])
