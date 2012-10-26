import mg
import os.path
from subprocess import Popen
import json
import re
import time

mgDir = os.path.abspath(mg.__path__[0])
daemonsDir = "%s/bin" % os.path.dirname(mgDir)
re_spaces = re.compile(r'\s+')
USER_HZ = 100.0

class ProcmanService(mg.SingleApplicationWebService):
    def __init__(self, *args, **kwargs):
        mg.SingleApplicationWebService.__init__(self, *args, **kwargs)
        self.cpustat = self.get_cpustat()

    def get_cpustat(self):
        with open("/proc/stat") as f:
            line = re_spaces.split(f.readline())
            user = int(line[1]) + int(line[2])
            system = int(line[3]) + int(line[6]) + int(line[7])
            idle = int(line[4])
            iowait = int(line[5])
            stolen = int(line[8])
            now = time.time()
            cpus = 0
            for line in f:
                if line.startswith("cpu"):
                    cpus += 1
            return (now, user, system, idle, iowait, stolen, cpus)

    def publish(self, svcinfo):
        mg.SingleApplicationWebService.publish(self, svcinfo)
        inst = self.inst
        with open("/proc/loadavg") as f:
            line = f.readline().split(" ")
            svcinfo["cpu-load"] = float(line[0])
            old_cpustat = self.cpustat
            new_cpustat = self.get_cpustat()
            elapsed = new_cpustat[0] - old_cpustat[0]
            cpus = new_cpustat[6]
            if elapsed > 5:
                svcinfo["cpu-user"] = (new_cpustat[1] - old_cpustat[1]) / USER_HZ / elapsed / cpus
                svcinfo["cpu-system"] = (new_cpustat[2] - old_cpustat[2]) / USER_HZ / elapsed / cpus
                svcinfo["cpu-idle"] = (new_cpustat[3] - old_cpustat[3]) / USER_HZ / elapsed / cpus
                svcinfo["cpu-iowait"] = (new_cpustat[4] - old_cpustat[4]) / USER_HZ / elapsed / cpus
                svcinfo["cpu-stolen"] = (new_cpustat[5] - old_cpustat[5]) / USER_HZ / elapsed / cpus
                self.cpustat = new_cpustat

class ProcessManager(mg.Module):
    def register(self):
        inst = self.app().inst
        if not hasattr(inst, "child_processes"):
            inst.child_processes = []
        self.rhook("procman.run", self.run)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("cluster.terminate-daemon", self.terminate_daemon)
        self.rhook("procman.spawn", self.spawn)
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
                    proc["process"] = self.spawn(proc["args"], proc["env"])
                else:
                    # Cleanup
                    del inst.child_processes[i:i+1]
                    continue
            i += 1
