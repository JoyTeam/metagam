from __future__ import print_function
from concurrence import Tasklet
from mg.core.cluster import DBCluster
import subprocess
import mg
import re

re_class = re.compile('^upstream (\S+) {')

class Nginx(mg.Module):
    def register(self):
        self.rhook("nginx.register", self.register_nginx)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("ngx-nginx.reload", self.reload, priv="public")

    def register_nginx(self):
        inst = self.app().inst
        # Load nginx configuration
        self.nginx_config = inst.conf("nginx", "conffile", "/etc/nginx/nginx-metagam.conf")
        self.nginx_upstreams = set()
        self.nginx_backends = None
        self.nginx_nextcheck = ""
        try:
            with open(self.nginx_config, "r") as f:
                for line in f:
                    m = re_class.match(line)
                    if m:
                        cls = m.group(1)
                        self.nginx_upstreams.add(cls)
        except IOError as e:
            pass
        # Register service
        int_app = inst.int_app
        srv = mg.SingleApplicationWebService(self.app(), "%s-nginx" % inst.instid, "nginx", "ngx")
        srv.serve_any_port()
        int_app.call("cluster.register-service", srv)

    def fastidle(self):
        if self.now() < self.nginx_nextcheck:
            return
        self.nginx_nextcheck = self.now(10)
        self.nginx_check()

    def reload(self):
        self.nginx_nextcheck = ""
        self.call("web.response_json", {"retval": 1})

    def nginx_check(self):
        daemons = self.obj(DBCluster, "daemons", silent=True)
        backends = {}
        for cls in self.nginx_upstreams:
            backends[cls] = set()
        for dmnid, dmninfo in daemons.data.iteritems():
            for svcid, svcinfo in dmninfo.get("services", {}).iteritems():
                webbackend = svcinfo.get("webbackend")
                if not webbackend:
                    continue
                port = svcinfo.get("webbackendport")
                if port is None:
                    port = svcinfo.get("port")
                ent = "%s:%d" % (svcinfo.get("addr"), port)
                if webbackend not in backends:
                    backends[webbackend] = set()
                backends[webbackend].add(ent)
        if self.nginx_backends != backends:
            self.debug("Nginx backends: %s", "%s" % backends)
            try:
                with open(self.nginx_config, "w") as f:
                    for cls, lst in backends.iteritems():
                        print("upstream %s {" % cls, file=f)
                        if lst:
                            for srv in lst:
                                print("\tserver %s;" % srv, file=f)
                        else:
                            print("\tserver 127.0.0.1:65534;", file=f)
                        print("}", file=f)
                subprocess.check_call(["/usr/bin/sudo", "/etc/init.d/nginx", "reload"])
                self.nginx_backends = backends
            except IOError as e:
                self.error("Error writing %s: %s", self.nginx_config, e)
            except subprocess.CalledProcessError as e:
                self.error("Error reloading nginx: %s", e)
