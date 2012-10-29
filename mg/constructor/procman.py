from mg.constructor import ConstructorModule
from mg.core.cluster import DBCluster, ClusterError
from uuid import uuid4
import json

class ProcessManager(ConstructorModule):
    def register(self):
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("procman.run", self.run)

    def run(self):
        inst = self.app().inst
        # Run child processes
        if inst.conf("procman", "runConstructorWorker"):
            self.call("procman.newdaemon", "worker", "mg_worker")
        if inst.conf("procman", "runNginxManager"):
            self.call("procman.newdaemon", "worker", "mg_nginx")
        if inst.conf("procman", "runCassandraManager"):
            self.call("procman.newdaemon", "worker", "mg_cassandra")
        if inst.conf("procman", "runMySQLManager"):
            self.call("procman.newdaemon", "worker", "mg_mysql")
        if inst.conf("procman", "runQueue"):
            self.call("procman.newdaemon", "queue", "mg_queue")

    def fastidle(self):
        inst = self.app().inst
        cls = inst.cls
        lock = self.lock(["Cluster"])
        if not lock.trylock():
            return
        try:
            # Check availability of all daemons and services
            hosts = []
            allServices = set()
            expire = self.now(-120)
            daemons = self.obj(DBCluster, "daemons", silent=True)
            metagam_running = set()
            for dmnid, dmninfo in daemons.data.items():
                if dmninfo.get("updated") < expire:
                    self.info('Daemon "%s" last time updated at %s. Clearing it from the configuration',
                            dmnid, dmninfo.get("updated"))
                    daemons.delkey(dmnid)
                    daemons.touch()
                    continue
                if dmninfo.get("cls") != cls:
                    continue
                # Record services
                for svcid, svcinfo in dmninfo.get("services", {}).iteritems():
                    tp = svcinfo.get("type")
                    allServices.add(tp)
                    if tp == "procman":
                        # Record a host
                        hosts.append({
                            "id": dmnid,
                            "hostid": dmninfo.get("hostid"),
                            "svcid": svcid,
                            "addr": svcinfo.get("addr"),
                            "port": svcinfo.get("port"),
                            "load": svcinfo.get("load", 0),
                        })
                    elif tp == "metagam":
                        # Host is a valid metagam instance
                        metagam_running.add(dmninfo.get("hostid"))
            # Filter hosts
            hosts = [host for host in hosts if host["hostid"] in metagam_running]
            # Check whether all required services are running
            hostsSorted = False
            services = {}
            self.call("services.list", services)
            for svctype, svcinfo in services.iteritems():
                if svctype not in allServices:
                    self.info('Service "%s" is not running. Looking where to launch it', svctype)
                    if not hosts:
                        self.error('No available hosts where to run "%s"', svctype)
                        break
                    if not hostsSorted:
                        hosts.sort(lambda x, y: cmp(x["load"], y["load"]))
                        self.debug("Available hosts: %s", hosts)
                    # Fetch a node with minimal load and put it to the end
                    host = hosts.pop(0)
                    hosts.append(host)
                    # Query procman to launch a daemon
                    self.debug('Querying %s "%s:%d" to launch daemon %s', host["id"], host["addr"], host["port"], svctype)
                    try:
                        inst = self.app().inst
                        uuid = "%s-%s" % (svctype, inst.conf("global", "id", inst.instaddr))
                        val = self.call("cluster.query_server", host["addr"], host["port"], "/service/call/%s/spawn" % host["svcid"], timeout=20, params={
                            "procid": uuid,
                            "executable": svcinfo["executable"]
                        })
                        self.debug("Procman query result: %s", val)
                        if val and val.get("ok"):
                            # Create temporary record that will be automatically updated by
                            # newly started daemon
                            daemons.set(uuid, {
                                "registered": self.now(),
                                "updated": self.now(),
                                "addr": host["addr"],
                                "cls": cls,
                                "services": {
                                    "%s-%s" % (uuid, svctype): {
                                        "type": svctype
                                    }
                                }
                            })
                            daemons.touch()
                    except ClusterError as e:
                        self.error("Error querying procman %s:%d: %s", host["addr"], host["port"], e)
            # Commit changes
            daemons.store()
        finally:
            lock.unlock()
