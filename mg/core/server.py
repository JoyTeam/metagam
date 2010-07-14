from __future__ import print_function
from mg.core import Module
import subprocess
import sys
import re
import json

class Server(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.cass.CommonCassandraStruct", "mg.core.cluster.Cluster", "mg.core.web.Web"])
        self.rhook("int-server.spawn", self.spawn)
        self.rhook("int-server.nginx", self.nginx)
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

    def spawn(self):
        request = self.req()
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
                try:
                    workers[i] = subprocess.Popen([self.executable, "%s-%d" % (server_id, i)])
                except OSError, e:
                    raise RuntimeError("Running %s: %s" % (self.executable, e))
            workers["count"] = new_count
        return request.jresponse({"ok": 1})

    def fastidle(self):
        workers = self.running_workers()
        server_id = self.app().server_id
        for i in range(0, workers["count"]):
            workers[i].poll()
            if workers[i].returncode is not None:
                self.debug("respawning child %d (process %s)", i, self.executable)
                workers[i] = subprocess.Popen([self.executable, "%s-%d" % (server_id, i)])

    def nginx(self):
        request = self.req()
        workers = json.loads(request.param("workers"))
        filename = "/etc/nginx/nginx-metagam.conf"
        try:
            with open(filename, "w") as f:
                print("upstream metagam {", file=f)
                for srv in workers:
                    print("\tserver %s:%d;" % (srv[0], srv[1]), file=f)
                print("}", file=f)
            subprocess.check_call(["/usr/bin/sudo", "/etc/init.d/nginx", "reload"])
        except IOError as e:
            self.error("Error writing %s: %s", filename, e)
            return request.internal_server_error()
        except subprocess.CalledProcessError as e:
            self.error("Error reloading nginx: %s", e)
            return request.internal_server_error()
        return request.jresponse({"ok": 1})
