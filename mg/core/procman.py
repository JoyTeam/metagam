import mg
import os.path
from subprocess import Popen
import json

mgDir = os.path.abspath(mg.__path__[0])
daemonsDir = "%s/bin" % os.path.dirname(mgDir)

class ProcmanService(mg.SingleApplicationWebService):
    def publish(self, svcinfo):
        with open("/proc/loadavg") as f:
            line = f.readline().split(" ")
            svcinfo["load"] = float(line[0])

class ProcessManager(mg.Module):
    def register(self):
        inst = self.app().inst
        if not hasattr(inst, "child_processes"):
            inst.child_processes = []
        self.rhook("procman.run", self.run)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("cluster.terminate-daemon", self.terminate_daemon)
        self.rhook("procman.newproc", self.newproc)
        self.rhook("procman.newdaemon", self.newdaemon)
        self.rhook("procman-spawn.index", self.spawn_index, priv="public")

    def terminate_daemon(self):
        inst = self.app().inst
        for proc in inst.child_processes:
            proc["process"].kill()

    def run(self):
        inst = self.app().inst
        # Register service
        service_id = "%s-procman" % inst.instid
        srv = ProcmanService(self.app(), service_id, "procman", "procman")
        srv.serve_any_port()
        self.call("cluster.register-service", srv)

    def spawn(self, args, env=None):
        self.debug("Spawning process %s" % args)
        return Popen(args, close_fds=True, env=env)

    def newdaemon(self, procid, executable):
        inst = self.app().inst
        self.newproc(procid, ["%s/%s" % (daemonsDir, executable), '-c', inst.config_filename])

    def spawn_index(self):
        req = self.req()
        procid = req.param("procid")
        executable = req.param("executable")
        self.newdaemon(procid, executable)
        self.call("web.response_json", {"ok": 1})

    def newproc(self, procid, args, env=None):
        self.app().inst.child_processes.append({
            "id": procid,
            "args": args,
            "env": env,
            "process": self.spawn(args, env),
            "respawn": True
        })

    def fastidle(self):
        inst = self.app().inst
        # Monitor child processes
        i = 0
        while i < len(inst.child_processes):
            proc = inst.child_processes[i]
            retval = proc["process"].poll()
            if retval != None:
                self.debug("Process %s finished with code %s" % (proc["args"][0], retval))
                if proc.get("respawn"):
                    # Respawn
                    proc["process"] = self.spawn(proc["args"])
                else:
                    # Cleanup
                    del inst.child_processes[i:i+1]
                    continue
            i += 1
