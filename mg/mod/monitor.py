from mg.core import Module
from concurrence.http import HTTPConnection
import re
import json

class Monitor(Module):
    def register(self):
        Module.register(self)
        self.rdep(["db.CommonDatabaseStruct", "cluster.Director", "web.Web"])
        self.rhook("monitor.check", self.monitor_check)

    def monitor_check(self):
        self.app().config.clear()
        servers_online = self.conf("director.servers", {})
        for host, info in servers_online.iteritems():
            host, port = re.split(':', host)
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
                        if body.get("ok"):
                            success = True
                finally:
                    cnn.close()
            except BaseException as e:
                print "%s:%s - %s" % (host, port, e)
            if not success:
                self.call("director.query", "/director/offline", {
                    "host": "%s:%s" % (host, port)
                })
