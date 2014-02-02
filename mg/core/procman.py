#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

import mg
import os.path
from subprocess import Popen
import json
import re
import time

re_spaces = re.compile(r'\s+')
USER_HZ = 100.0

class ProcmanService(mg.SingleApplicationWebService):
    def __init__(self, *args, **kwargs):
        mg.SingleApplicationWebService.__init__(self, *args, **kwargs)
        self.cpustat = self.get_cpustat()

    def get_cpustat(self):
        started = time.time()
        with open("/proc/stat") as f:
            line = re_spaces.split(f.readline())
            user = int(line[1]) + int(line[2])
            system = int(line[3]) + int(line[6]) + int(line[7])
            idle = int(line[4])
            iowait = int(line[5])
            stolen = int(line[8])
            cpus = 0
            for line in f:
                if line.startswith("cpu"):
                    cpus += 1
            return (started, user, system, idle, iowait, stolen, cpus)

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
                params = ["cpu-user", "cpu-system", "cpu-idle", "cpu-iowait", "cpu-stolen"]
                total = 0
                for i in xrange(0, len(params)):
                    val = (new_cpustat[i + 1] - old_cpustat[i + 1]) / USER_HZ / elapsed / cpus
                    svcinfo[params[i]] = val
                    total += val
                # Normalization
                if total > 0:
                    for p in params:
                        svcinfo[p] /= total
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
        self.rhook("procman-newproc.index", self.newproc_index, priv="public")

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

    def newdaemon(self, procid, executable, respawn=True):
        inst = self.app().inst
        self.newproc(procid, ["%s/%s" % (inst.daemons_dir, executable), '-c', inst.config_filename], respawn=True)

    def spawn_index(self):
        req = self.req()
        procid = req.param("procid")
        executable = req.param("executable")
        respawn = True if req.param("respawn") else False
        self.newdaemon(procid, executable, respawn=respawn)
        self.call("web.response_json", {"ok": 1})

    def newproc_index(self):
        req = self.req()
        procid = req.param("procid")
        args = json.loads(req.param("args"))
        env = json.loads(req.param("env")) if req.param("env") else None
        respawn = True if req.param("respawn") else False
        self.newproc(procid, args, env, respawn)
        self.call("web.response_json", {"ok": 1})

    def newproc(self, procid, args, env=None, respawn=True):
        self.app().inst.child_processes.append({
            "id": procid,
            "args": args,
            "env": env,
            "process": self.spawn(args, env),
            "respawn": respawn
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
