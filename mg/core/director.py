from mg.core import Module
from concurrence import Tasklet, JoinError
from concurrence.http import HTTPConnection
import re
import json
import logging

class CassandraStruct(Module):
    def register(self):
        self.rdep(["mg.core.cass_struct.CommonCassandraStruct"])

class Director(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.director.CassandraStruct", "mg.core.web.Web", "mg.core.cluster.Cluster",
            "mg.core.queue.Queue"])
        self.rhook("web.global_html", self.web_global_html)
        self.rhook("int-director.ready", self.director_ready)
        self.rhook("int-director.reload", self.int_director_reload)
        self.rhook("int-index.index", self.director_index)
        self.rhook("int-director.setup", self.director_setup)
        self.rhook("int-director.config", self.director_config)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("monitor.check", self.monitor_check)
        self.servers_online = self.conf("director.servers", default={})
        self.servers_online_modified = True
        self.workers_str = None

    def int_director_reload(self):
        request = self.req()
        result = self.director_reload()
        return request.jresponse(result)

    def director_reload(self):
        result = {}
        errors = self.app().reload()
        if errors:
            result["director"] = "ERRORS: %d" % errors
        else:
            result["director"] = "ok"
        config = json.dumps(self.config())
        for server_id, info in self.servers_online.iteritems():
            errors = 1
            try:
                res = self.call("cluster.query_server", info["host"], info["port"], "/core/reload", {"config": config})
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
        return result

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
        if conf.get("storage") is None:
            conf["storage"] = ["storage"]
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
        storage = request.param("storage")
        metagam_host = request.param("metagam_host")
        admin_user = request.param("admin_user")
        config = self.config()
        if self.ok():
            config["memcached"] = [self.split_host_port(srv, 11211) for srv in re.split('\s*,\s*', memcached)]
            config["cassandra"] = [self.split_host_port(srv, 9160) for srv in re.split('\s*,\s*', cassandra)]
            config["storage"] = re.split('\s*,\s*', storage)
            config["metagam_host"] = metagam_host
            config["admin_user"] = admin_user
            self.app().config.set("director.config", config)
            self.app().config.store()
            self.director_reload()
            self.call("web.redirect", "/")
        else:
            memcached = ", ".join("%s:%s" % (port, host) for port, host in config["memcached"])
            cassandra = ", ".join("%s:%s" % (port, host) for port, host in config["cassandra"])
            storage = ", ".join(config["storage"])
            metagam_host = config["metagam_host"]
            admin_user = config.get("admin_user")
        return self.call("web.response_template", "director/setup.html", {
            "title": self._("Director settings"),
            "form": {
                "memcached_desc": self._("<strong>Memcached servers</strong> (host:port, host:port, ...)"),
                "memcached": memcached,
                "cassandra_desc": self._("<strong>Cassandra servers</strong> (host:port, host:post, ...)"),
                "cassandra": cassandra,
                "storage_desc": self._("<strong>Storage servers</strong> (host, host, ...)"),
                "storage": storage,
                "metagam_host_desc": self._("<strong>Main application host name</strong> (without www)"),
                "metagam_host": metagam_host,
                "admin_user_desc": self._("<strong>Admin user uuid</strong>"),
                "admin_user": admin_user,
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
        workers = {}
        for server_id, info in self.servers_online.iteritems():
            try:
                if info["type"] == "server" and info["params"].get("nginx"):
                    nginx.add((info["host"], info["port"]))
                elif info["type"] == "worker":
                    cls = info["params"].get("class")
                    if workers.get(cls) is None:
                        workers[cls] = []
                    workers[cls].append((info["host"], info["params"].get("ext_port")))
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
        if params.get("backends"):
            self.call("cluster.query_server", host, port, "/server/spawn", {
                "workers": params.get("backends"),
            })

        # storing online list
        server_id = str(host)
        conf = {
            "host": host,
            "port": port,
            "type": type,
            "params": params
        }
        parent = request.param("parent")
        if parent:
            server_id = "%s-server-%s" % (server_id, parent)
            params["parent"] = "%s-%s-%s" % (host, "server", parent)
        server_id = "%s-%s" % (server_id, type)
        id = request.param("id")
        if id:
            server_id = "%s-%s" % (server_id, id)
            conf["id"] = id
        self.servers_online[server_id] = conf
        self.store_servers_online()
        return request.jresponse({ "ok": 1, "server_id": server_id })

    def monitor_check(self):
        for server_id, info in self.servers_online.items():
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
                logging.getLogger("mg.core.director.Director").info("%s - %s", server_id, e)
            if not success:
                # at the moment failing server could be removed from the configuration already
                fact_server = self.servers_online.get(server_id)
                if fact_server is not None:
                    fact_port = fact_server.get("port")
                    if fact_port is None or fact_port == port:
                        del self.servers_online[server_id]
                        self.store_servers_online()
