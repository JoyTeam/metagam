from mg.core import Module
import re
import json
from concurrence import Tasklet, JoinError

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
        self.rhook("core.fastidle", self.fastidle)
        self.servers_online = self.conf("director.servers", {})
        self.servers_online_modified = True
        self.workers_str = None

    def director_reload(self, args, request):
        result = {
        }
        errors = self.app().reload()
        if errors:
            result["director"] = "ERRORS: %d" % errors
        else:
            result["director"] = "ok"

        for server_id, info in self.servers_online.iteritems():
            errors = 1
            try:
                res = self.call("cluster.query_server", info["host"], info["port"], "/core/reload", {})
                err = res.get("errors")
                if err is None:
                    errors = 0
                else:
                    errors = err
            except BaseException as e:
                self.error("%s:%d - %s", info["host"], info["port"], e)
            tag = "%s (%s:%d)" % (server_id, info["host"], info["port"])
            if errors:
                result[tag] = "ERRORS: %d" % errors
            else:
                result[tag] = "ok"
        return request.jresponse(result)

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
        self.servers_online_modified = True

    def fastidle(self):
        if self.servers_online_modified:
            self.app().config.set("director.servers", self.servers_online)
            self.app().config.store()
            try:
                if self.configure_nginx():
                    self.servers_online_modified = False
            except JoinError:
                pass

    def configure_nginx(self):
        nginx = set()
        workers = []
        for server_id, info in self.servers_online.iteritems():
            if info["type"] == "server" and info["params"].get("nginx"):
                nginx.add((info["host"], info["port"]))
            elif info["type"] == "worker":
                workers.append((info["host"], info["params"].get("ext_port")))
        workers_str = json.dumps(workers, sort_keys=True)
        if workers_str != self.workers_str:
            tasklets = []
            for host, port in nginx:
                tasklet = Tasklet.new(self.configure_nginx_server)(host, port, workers_str)
                tasklets.append(tasklet)
            for tasklet in tasklets:
                if not Tasklet.join(tasklet):
                    return False
            self.workers_str = workers_str
        return True

    def configure_nginx_server(self, host, port, workers):
        try:
            self.call("cluster.query_server", host, port, "/server/nginx", {"workers": workers})
            return True
        except BaseException as e:
            self.error("%s:%d - %s", host, port, e)
            return False

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

