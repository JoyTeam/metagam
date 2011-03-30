from __future__ import print_function
from mg import *
from concurrence import Tasklet
import subprocess
import sys
import re
import json
import optparse

re_class = re.compile('^upstream (\S+) {')

class Server(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.cluster.Cluster", "mg.core.web.Web"])
        self.rhook("int-server.spawn", self.spawn)
        self.rhook("int-server.nginx", self.nginx)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("server.run", self.run)
        self.executable = re.sub(r'[^\/]+$', 'mg_worker', sys.argv[0])

    def run(self):
        inst = self.app().inst
        # configuration
        parser = optparse.OptionParser()
        parser.add_option("-n", "--nginx", action="store_true", help="Manage nginx configuration")
        parser.add_option("-q", "--queue", action="store_true", help="Take part in the global queue processing")
        parser.add_option("-b", "--backends", type="int", help="Run the give quantity of backends")
        (options, args) = parser.parse_args()
        # daemon
        daemon = WebDaemon(inst)
        daemon.app = self.app()
        port = daemon.serve_any_port("0.0.0.0")
        self.app().server_id = port
        # application_factory
        inst.appfactory = ApplicationFactory(inst)
        inst.appfactory.add(self.app())
        # default option set
        if not options.backends and not options.nginx and not options.queue:
            options.backends = 4
            options.nginx = True
            options.queue = True
        # registering
        res = self.call("cluster.query_director", "/director/ready", {
            "type": "server",
            "port": port,
            "id": self.app().server_id,
            "params": json.dumps({
                "backends": options.backends,
                "nginx": options.nginx,
                "queue": options.queue,
            })
        })
        # run
        inst.set_server_id(res["server_id"], "server")
        while True:
            try:
                self.call("core.fastidle")
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(1)

    def running_workers(self):
        """
        returns map of currently running worker processes (worker_id => process)
        """
        app = self.app()
        try:
            return app.running_workers
        except AttributeError:
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
                    workers[i] = subprocess.Popen([self.executable, str(server_id), str(i)])
                except OSError, e:
                    raise RuntimeError("Running %s: %s" % (self.executable, e))
            workers["count"] = new_count
        self.call("web.response_json", {"ok": 1})

    def fastidle(self):
        workers = self.running_workers()
        server_id = self.app().server_id
        for i in range(0, workers["count"]):
            workers[i].poll()
            if workers[i].returncode is not None:
                self.debug("respawning child %d (process %s)", i, self.executable)
                workers[i] = subprocess.Popen([self.executable, str(server_id), str(i)])
        self.call("core.check_last_ping")

    def nginx(self):
        req = self.req()
        workers = json.loads(req.param("workers"))
        filename = "/etc/nginx/nginx-metagam.conf"
        classes = set()
        try:
            with open(filename, "r") as f:
                for line in f:
                    m = re_class.match(line)
                    if m:
                        cls = m.group(1)
                        classes.add(cls)
        except IOError as e:
            pass
        try:
            with open(filename, "w") as f:
                for cls, list in workers.iteritems():
                    try:
                        classes.remove(cls)
                    except KeyError:
                        pass
                    print("upstream %s {" % cls, file=f)
                    for srv in list:
                        print("\tserver %s:%d;" % (srv[0], srv[1]), file=f)
                    print("}", file=f)
                for cls in classes:
                    print("upstream %s {" % cls, file=f)
                    print("\tserver 127.0.0.1:65534;", file=f)
                    print("}", file=f)
            subprocess.check_call(["/usr/bin/sudo", "/etc/init.d/nginx", "reload"])
        except IOError as e:
            self.error("Error writing %s: %s", filename, e)
            self.call("web.internal_server_error")
        except subprocess.CalledProcessError as e:
            self.error("Error reloading nginx: %s", e)
            self.call("web.internal_server_error")
        self.call("web.response_json", {"ok": 1})
