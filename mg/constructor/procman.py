from mg.constructor import ConstructorModule
from mg.core.cluster import DBCluster, ClusterError
from uuid import uuid4
import json

PERSISTENT_SERVICES = {
    "realplexor": {
        "exec": "daemons/mg_realplexor"
    }
}

class ProcessManager(ConstructorModule):
    def register(self):
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("cluster.run-daemon-loop", self.run, priority=10)

    def run(self):
        inst = self.app().inst
        # Run child processes
        if inst.conf("procman", "runConstructorWorker"):
            self.call("procman.newdaemon", "worker", "mg_worker")

    def fastidle(self):
        with self.lock(["Cluster"]):
            # Check availability of all daemons and services
            hosts = []
            allServices = set()
            expire = self.now(-120)
            daemons = self.obj(DBCluster, "daemons", silent=True)
            for dmnid, dmninfo in daemons.data.items():
                if dmninfo.get("updated") < expire:
                    self.info('Daemon "%s" last time updated at %s. Clearing it from the configuration',
                            dmnid, dmninfo.get("updated"))
                    daemons.delkey(dmnid)
                    daemons.touch()
                    continue
                # Record services
                for svcid, svcinfo in dmninfo.get("services", {}).iteritems():
                    tp = svcinfo.get("type")
                    allServices.add(tp)
                    if tp == "procman":
                        # Record a host
                        hosts.append({
                            "id": dmnid,
                            "addr": svcinfo.get("addr"),
                            "port": svcinfo.get("port"),
                            "load": svcinfo.get("load", 0),
                        })
            # Check whether all required services are running
            hostsSorted = False
            for svctype, svcinfo in PERSISTENT_SERVICES.items():
                if svctype not in allServices:
                    self.info('Service "%s" is not running. Looking where to launch it', svctype)
                    if not hosts:
                        self.error('No available hosts where to run "%s"', svctype)
                        break
                    if not hostsSorted:
                        hosts.sort(lambda x, y: cmp(x["load"], y["load"]))
                        self.debug("Available hosts: %s", hosts)
                    # Rotate hosts list and fetch a node with minimal load
                    host = hosts.pop(0)
                    hosts.append(host)
                    # Query procman to launch a daemon
                    self.debug('Querying %s "%s:%d" to launch daemon %s', host["id"], host["addr"], host["port"], svctype)
                    try:
                        inst = self.app().inst
                        uuid = "%s-%s" % (svctype, uuid4().hex)
                        val = self.call("cluster.query_server", host["addr"], host["port"], "/spawn", timeout=20, params={
                            "procid": uuid,
                            "args": json.dumps([svcinfo["exec"], uuid])
                        })
                        self.debug("Procman query result: %s", val)
                        if val and val.get("ok"):
                            # Create temporary record that will be automatically updated by
                            # newly started daemon
                            daemons.set(uuid, {
                                "registered": self.now(),
                                "updated": self.now(),
                                "addr": host["addr"],
                                "services": {
                                    svctype: {
                                        "type": svctype
                                    }
                                }
                            })
                            daemons.touch()
                    except ClusterError as e:
                        self.error("Error querying procman %s:%d: %s", host["addr"], host["port"], e)
            # Commit changes
            daemons.store()
