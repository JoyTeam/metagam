from mg.core import Module
import re
import json

class DatabaseStruct(Module):
    def register(self):
        self.rdep(["mg.cass.CommonDatabaseStruct"])

class Director(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.director.DatabaseStruct", "mg.web.Web", "mg.cluster.Cluster"])
        self.rhook("web.template", self.web_template, 5)
        self.rhook("int-director.ready", self.director_ready)
        self.rhook("int-director.reload", self.director_reload)
        self.rhook("int-index.index", self.director_index)
        self.rhook("int-director.setup", self.director_setup)
        self.rhook("int-director.config", self.director_config)
        self.rhook("int-director.offline", self.director_offline)
        self.servers_online = self.conf("director.servers", {})

    def director_reload(self, args, request):
        errors = self.app().reload()
        if errors:
            return request.jresponse({ "errors": errors })
        else:
            return request.jresponse({ "ok": 1 })

    def web_template(self, filename, struct):
        self.call("web.set_global_html", "director/global.html")

    def director_index(self, args, request):
        params = {
            "title": self._("Welcome to the Director control center"),
            "setup": self._("Change director settings")
        }
        if len(self.servers_online):
            hosts = self.servers_online.keys()
            hosts.sort()
            params["servers_online"] = {
                "title": self._("List of servers online"),
                "list": [{"host": host, "type": info["type"], "params": json.dumps(info["params"])} for host, info in [(host, self.servers_online[host]) for host in hosts]]
            }
        return self.call("web.template", "director/index.html", params)

    def config(self):
        conf = self.conf("director.config")
        if conf is None:
            conf = {}
        if conf.get("cassandra") is None:
            conf["cassandra"] = [("director-db", 9160)]
        if conf.get("memcached") is None:
            conf["memcached"] = [("director-mc", 11211)]
        if conf.get("metagam_host") is None:
            conf["metagam_host"] = "metagam"
        return conf

    def director_config(self, args, request):
        return request.jresponse(self.config())

    def split_host_port(self, str, defport):
        ent = re.split(':', str)
        if len(ent) >= 2:
            return (ent[0], int(ent[1]))
        else:
            return (str, defport)
        
    def director_setup(self, args, request):
        memcached = request.param("memcached")
        cassandra = request.param("cassandra")
        metagam_host = request.param("metagam_host")
        config = self.config()
        if self.ok():
            config["memcached"] = [self.split_host_port(srv, 11211) for srv in re.split('\s*,\s*', memcached)]
            config["cassandra"] = [self.split_host_port(srv, 9160) for srv in re.split('\s*,\s*', cassandra)]
            config["metagam_host"] = metagam_host
            self.app().config.set("director.config", config)
            self.app().config.store()
            return request.redirect('/')
        else:
            memcached = ", ".join("%s:%s" % (port, host) for port, host in config["memcached"])
            cassandra = ", ".join("%s:%s" % (port, host) for port, host in config["cassandra"])
            metagam_host = config["metagam_host"]
        return self.call("web.template", "director/setup.html", {
            "title": self._("Director settings"),
            "form": {
                "memcached_desc": self._("<strong>Memcached servers</strong> (host:port, host:port, ...)"),
                "memcached": memcached,
                "cassandra_desc": self._("<strong>Cassandra servers</strong> (host:port, host:post, ...)"),
                "cassandra": cassandra,
                "metagam_host_desc": self._("<strong>Main application host name</strong> (without www)"),
                "metagam_host": metagam_host,
                "submit_desc": self._("Save")
            }
        })

    def store_servers_online(self):
        self.app().config.set("director.servers", self.servers_online)
        self.app().config.store()

    def director_ready(self, args, request):
        host = request.environ["REMOTE_ADDR"]
        type = request.param("type")
        params = json.loads(request.param("params"))
        port = int(request.param("port"))

        # sending configuration
        if params.get("backend"):
            self.call("cluster.query_server", host, port, "/server/spawn", {
                "workers": 3,
            })

        # storing online list
        server_id = "%s-%s" % (host, type)
        conf = {
            "host": host,
            "port": port,
            "type": type,
            "params": params
        }
        id = request.param("id")
        if id:
            server_id = "%s-%s" % (server_id, id)
            conf["id"] = id
        self.servers_online[server_id] = conf
        self.store_servers_online()
        return request.jresponse({ "ok": 1, "server_id": server_id })

    def director_offline(self, args, request):
        server_id = request.param("server_id")
        server = self.servers_online.get(server_id)
        if server and server["port"] == int(request.param("port")):
            del self.servers_online[server_id]
            self.store_servers_online()
            return request.jresponse({ "ok": 1 })
        else:
            return request.jresponse({ "already": 1 })

