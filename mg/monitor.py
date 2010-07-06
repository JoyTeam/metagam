from mg.core import Module
from concurrence.http import HTTPConnection
import re
import json
import logging

class Monitor(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.cass.CommonCassandraStruct", "mg.cluster.Cluster", "mg.web.Web"])
        self.rhook("monitor.check", self.monitor_check)

    def monitor_check(self):
        self.app().config.clear()
        servers_online = self.conf("director.servers", {})
        for server_id, info in servers_online.iteritems():
            host = info.get("host")
            port = info.get("port")
            success = False
            try:
                cnn = HTTPConnection()
                cnn.connect((str(host), int(port)))
                try:
                    request = cnn.get("/core/ping")
                    request.add_header("Content-type", "application/x-www-form-urlencoded")
                    response = cnn.perform(request)
                    if response.status_code == 200 and response.get_header("Content-type") == "application/json":
                        body = json.loads(response.body)
                        if body.get("ok") and body.get("server_id") == server_id:
                            success = True
                finally:
                    cnn.close()
            except BaseException as e:
                logging.getLogger("mg.monitor.Monitor").info("%s - %s", server_id, e)
            if not success:
                self.call("cluster.query_director", "/director/offline", {
                    "server_id": server_id,
                    "port": port
                })
