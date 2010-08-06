from mg.core import Module
import re
import json
from concurrence import Tasklet, JoinError

class CassandraStruct(Module):
    def register(self):
        self.rdep(["mg.core.cass_struct.CommonCassandraStruct"])

class Director(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.director.CassandraStruct", "mg.core.web.Web", "mg.core.cluster.Cluster"])
        self.rhook("web.global_html", self.web_global_html)
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

    def director_reload(self):
        request = self.req()
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

    def web_global_html(self):
        return "director/global.html"

    def director_index(self):
        vars = {
            "title": self._("Welcome to the Director control center"),
            "setup": self._("Change director settings")
        }
        if len(self.servers_online):
            hosts = self.servers_online.keys()
            hosts.sort()
            vars["servers_online"] = {
                "title": self._("List of servers online"),
                "list": [{"host": host, "type": info["type"], "params": json.dumps(info["params"])} for host, info in [(host, self.servers_online[host]) for host in hosts]]
            }
        return self.call("web.response_template", "director/index.html", vars)

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

    def director_config(self):
        request = self.req()
        return request.jresponse(self.config())

    def split_host_port(self, str, defport):
        ent = re.split(':', str)
        if len(ent) >= 2:
            return (ent[0], int(ent[1]))
        else:
            return (str, defport)
        
    def director_setup(self):
        request = self.req()
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
        return self.call("web.response_template", "director/setup.html", {
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
            try:
                if info["type"] == "server" and info["params"].get("nginx"):
                    nginx.add((info["host"], info["port"]))
                elif info["type"] == "worker":
                    workers.append((info["host"], info["params"].get("ext_port")))
            except KeyError:
                pass
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

    def director_ready(self):
        request = self.req()
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

    def director_offline(self):
        request = self.req()
        server_id = request.param("server_id")
        server = self.servers_online.get(server_id)
        port = server.get("port")
        if server and (port is None or port == int(request.param("port"))):
            del self.servers_online[server_id]
            self.store_servers_online()
            return request.jresponse({ "ok": 1 })
        else:
            return request.jresponse({ "already": 1 })

