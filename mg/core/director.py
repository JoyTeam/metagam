from mg import *
from concurrence import Tasklet, JoinError, Timeout
from concurrence.http import HTTPConnection
from mg.core.classes import *
import re
import json

class CassandraStruct(Module):
    def register(self):
        self.rdep(["mg.core.cass_struct.CommonCassandraStruct"])

class Director(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.director.CassandraStruct", "mg.core.web.Web", "mg.core.cluster.Cluster", "mg.core.queue.Queue", "mg.core.queue.QueueRunner", "mg.core.projects.Projects",
            "mg.core.daemons.DaemonsManager", "mg.core.realplexor.RealplexorAdmin"])
        self.config()
        self.app().inst.setup_logger()
        self.app().servers_online = self.conf("director.servers", {})
        self.app().servers_online_modified = False
        self.queue_workers = {}
        self.workers_str = None
        self.rhook("web.setup_design", self.web_setup_design)
        self.rhook("int-director.ready", self.director_ready, priv="public")
        self.rhook("int-director.reload", self.int_director_reload, priv="public")
        self.rhook("int-index.index", self.director_index, priv="public")
        self.rhook("int-director.setup", self.director_setup, priv="public")
        self.rhook("int-director.config", self.director_config, priv="public")
        self.rhook("director.reload_servers", self.reload_servers)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("director.queue_workers", self.director_queue_workers)
        self.rhook("cluster.servers_online", self.cluster_servers_online, priority=10)
        self.rhook("director.run", self.run)
        self.rhook("core.appfactory", self.appfactory, priority=-10)
        self.servers_online_updated()

    def run(self):
        # daemon
        daemon = WebDaemon(self.app().inst)
        daemon.app = self.app()
        daemon.serve(("0.0.0.0", 3000))
        # application factory
        inst = self.app().inst
        inst.appfactory = self.call("core.appfactory")
        inst.appfactory.add(self.app())
        inst.reloading_hard = 0
        # background tasks
        Tasklet.new(self.monitor)()
        Tasklet.new(self.call)("queue.process")
        Tasklet.new(self.call)("daemon.monitor")
        while True:
            try:
                self.call("core.fastidle")
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(1)

    def monitor(self):
        while True:
            try:
                # pinging servers
                for server_id, info in self.app().servers_online.items():
                    host = info.get("host")
                    port = info.get("port")
                    success = False
                    try:
                        with Timeout.push(30):
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
                                        if info["type"] == "worker":
                                            try:
                                                st = self.obj(WorkerStatus, server_id)
                                            except ObjectNotFoundException:
                                                success = False
                                                request = cnn.get("/core/abort")
                                                cnn.perform(request)
                                        if success:
                                            self.call("director.ping_results", str(host), int(port), body)
                            finally:
                                cnn.close()
                    except Exception as e:
                        self.info("%s - %s", server_id, e)
                    if not success:
                        fact_server = self.app().servers_online.get(server_id)
                        if fact_server is not None:
                            fact_port = fact_server.get("port")
                            if fact_port is None or fact_port == port:
                                del self.app().servers_online[server_id]
                                self.store_servers_online()
                                self.servers_online_updated()
                                # removing status object
                                st = self.obj(WorkerStatus, server_id, silent=True)
                                st.remove()
                                # additional actions
                                self.call("director.unregistering_server", server_id)
                # examining WorkerStatus records
                lst = self.objlist(WorkerStatusList, query_index="all")
                lst.load(silent=True)
                expire = self.now(-180)
                for st in lst:
                    info = self.app().servers_online.get(st.uuid)
                    abort = False
                    if st.get("updated") < expire:
                        self.warning("WorkerStatus %s expired: %s < %s", st.uuid, st.get("updated"), expire)
                        st.remove()
                        # checking existing servers
                        abort = True
                        for server_id, info in self.app().servers_online.items():
                            host = info.get("host")
                            port = info.get("port")
                            if host == st.get("host") and (port == st.get("port") or info["params"].get("ext_port") == st.get("ext_port")) and server_id != st.uuid:
                                abort = False
                                break
                    else:
                        if not info:
                            self.warning("WorkerStatus %s doesn't match any registered server. Killing %s:%d", st.uuid, st.get("host"), st.get("port"))
                            abort = True
                        elif info["params"]["class"] != st.get("cls"):
                            self.warning("WorkerStatus %s class is %s, although registered one is %s. Killing %s:%d", st.uuid, st.get("cls"), info["params"]["class"], st.get("host"), st.get("port"))
                            abort = True
                    if abort:
                        with Timeout.push(30):
                            cnn = HTTPConnection()
                            cnn.connect((str(st.get("host")), int(st.get("port"))))
                            try:
                                request = cnn.get("/core/abort")
                                cnn.perform(request)
                                # will be reached unless timed out
                                st.remove()
                            finally:
                                cnn.close()
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(10)

    def appfactory(self):
        raise Hooks.Return(ApplicationFactory(self.app().inst))

    def cluster_servers_online(self):
        raise Hooks.Return(self.app().servers_online)

    def director_queue_workers(self):
        return self.queue_workers

    def int_director_reload(self):
        # incrementing application.version
        config = self.int_app().config
        ver = config.get("application.version", 0) + 1
        config.set("application.version", ver)
        config.store(notify=False)
        # reloading ourselves
        result = self.director_reload()
        req = self.req()
        hard = req.param("hard")
        # reloading cluster
        if hard == "1":
            result["enqueued"] = ver
            self.app().inst.reloading_hard = ver
            Tasklet.new(self.hard_reload)(ver)
        else:
            self.reload_servers(result)
        self.call("web.response_json", result)

    def hard_reload(self, ver):
        self.info("Hard reload: %s", ver)
        lst = self.objlist(WorkerStatusList, query_index="all")
        lst.load(silent=True)
        lst.sort(cmp=lambda x, y: cmp(x.get("cls"), y.get("cls")))
        self.debug("Workers: %s", lst)
        i = 0
        while i < len(lst):
            del lst[i:i + 1]
            i += 2
        self.debug("Reloading 2/3 of workers: %s", lst)
        for st in lst:
            self.debug("Reloading worker %s", st.uuid)
            try:
                with Timeout.push(30):
                    cnn = HTTPConnection()
                    cnn.connect((str(st.get("host")), int(st.get("port"))))
                    try:
                        request = cnn.get("/core/reload-hard")
                        cnn.perform(request)
                    finally:
                        cnn.close()
            except Exception as e:
                self.exception(e)
        self.store_servers_online()
        self.servers_online_updated()
        start = time.time()
        while True:
            Tasklet.sleep(1)
            if self.conf("application.version") > ver:
                self.debug("Application version changed during reloading: %s => %s", ver, self.conf("application.version"))
                return
            lst = self.objlist(WorkerStatusList, query_index="all")
            lst.load(silent=True)
            reloaded = 0
            for st in lst:
                if st.get("ver") >= ver:
                    reloaded += 1
            if reloaded >= len(lst) / 3:
                self.debug("1/3 of workers reloaded successfully")
                break
            if time.time() > start + 60:
                self.debug("1/3 of workers hasn't reloaded. Reloading remaining")
                break
        self.debug("reloading all workers not reloaded yet")
        lst = self.objlist(WorkerStatusList, query_index="all")
        lst.load(silent=True)
        for st in lst:
            if st.get("ver") < ver:
                self.debug("reloading worker %s", st.uuid)
                try:
                    with Timeout.push(30):
                        cnn = HTTPConnection()
                        cnn.connect((str(st.get("host")), int(st.get("port"))))
                        try:
                            request = cnn.get("/core/reload-hard")
                            cnn.perform(request)
                        finally:
                            cnn.close()
                except Exception as e:
                    self.exception(e)
        self.store_servers_online()
        self.servers_online_updated()
        self.debug("waiting until all workers reload")
        while True:
            Tasklet.sleep(1)
            if self.conf("application.version") > ver:
                self.debug("Application version changed during reloading: %s => %s", ver, self.conf("application.version"))
                return
            lst = self.objlist(WorkerStatusList, query_index="all")
            lst.load(silent=True)
            reloaded = 0
            for st in lst:
                if st.get("ver") >= ver:
                    reloaded += 1
            if reloaded > len(lst):
                self.info("Hard reload to version %s completed", ver)
                self.app().inst.reloading_hard = 0
                return
            if time.time() > start + 3600:
                self.error("Hard reload timeout. Forcing abort to every not reloaded worker")
                for st in lst:
                    if st.get("ver") < ver:
                        self.debug("aborting worker %s", st.uuid)
                        try:
                            with Timeout.push(30):
                                cnn = HTTPConnection()
                                cnn.connect((str(st.get("host")), int(st.get("port"))))
                                try:
                                    request = cnn.get("/core/abort")
                                    cnn.perform(request)
                                finally:
                                    cnn.close()
                        except Exception as e:
                            self.exception(e)
                break
        self.store_servers_online()
        self.servers_online_updated()
        self.app().inst.reloading_hard = 0

    def director_reload(self):
        result = {}
        errors = self.app().reload()
        if errors:
            result["director"] = "ERRORS: %d" % errors
        else:
            result["director"] = "ok: application.version=%d" % self.conf("application.version")
        return result

    def reload_servers(self, result={}):
        config = json.dumps(self.config())
        for server_id, info in self.app().servers_online.items():
            errors = 1
            try:
                with Timeout.push(20):
                    res = self.call("cluster.query_server", info["host"], info["port"], "/core/reload", {"config": config})
                err = res.get("errors")
                if err is None:
                    errors = 0
                else:
                    errors = err
            except Exception as e:
                self.error("%s:%d - %s", info["host"], info["port"], e)
            tag = "%s (%s:%d)" % (server_id, info["host"], info["port"])
            if errors:
                result[tag] = "ERRORS: %d" % errors
            else:
                result[tag] = "ok"

    def web_setup_design(self, vars):
        vars["global_html"] = "director/global.html"

    def director_index(self):
        vars = {
            "title": self._("Welcome to the cluster control center"),
            "setup": self._("Change cluster settings")
        }
        if len(self.app().servers_online):
            hosts = self.app().servers_online.keys()
            hosts.sort()
            vars["servers_online"] = {
                "title": self._("List of servers online"),
                "list": [{"host": host, "type": info["type"], "params": json.dumps(info["params"])} for host, info in [(host, self.app().servers_online[host]) for host in hosts]]
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
        if conf.get("main_host") is None:
            conf["main_host"] = "main"
        if conf.get("storage") is None:
            conf["storage"] = ["storage"]
        if conf.get("smtp_server") is None:
            conf["smtp_server"] = "localhost"
        if conf.get("locale") is None:
            conf["locale"] = "en"
        self.app().inst.config = conf
        return conf

    def director_config(self):
        self.call("web.response_json", self.config())

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
        main_host = request.param("main_host")
        admin_user = request.param("admin_user")
        smtp_server = request.param("smtp_server")
        locale = request.param("locale")
        config = self.config()
        if self.ok():
            config["memcached"] = [self.split_host_port(srv, 11211) for srv in re.split('\s*,\s*', memcached)]
            config["cassandra"] = [self.split_host_port(srv, 9160) for srv in re.split('\s*,\s*', cassandra)]
            config["storage"] = re.split('\s*,\s*', storage)
            config["main_host"] = main_host
            config["admin_user"] = admin_user
            config["smtp_server"] = smtp_server
            config["locale"] = locale
            self.app().config.set("director.config", config)
            self.app().config.store()
            self.director_reload()
            self.call("web.redirect", "/")
        else:
            memcached = ", ".join("%s:%s" % (port, host) for port, host in config["memcached"])
            cassandra = ", ".join("%s:%s" % (port, host) for port, host in config["cassandra"])
            storage = ", ".join(config["storage"])
            main_host = config["main_host"]
            admin_user = config.get("admin_user")
            smtp_server = config.get("smtp_server")
            locale = config.get("locale")
        return self.call("web.response_template", "director/setup.html", {
            "title": self._("Cluster settings"),
            "form": {
                "memcached_desc": self._("<strong>Memcached servers</strong> (host:port, host:port, ...)"),
                "memcached": memcached,
                "cassandra_desc": self._("<strong>Cassandra servers</strong> (host:port, host:post, ...)"),
                "cassandra": cassandra,
                "storage_desc": self._("<strong>Storage servers</strong> (host, host, ...)"),
                "storage": storage,
                "main_host_desc": self._("<strong>Main application host name</strong> (without www)"),
                "main_host": main_host,
                "admin_user_desc": self._("<strong>Administrator</strong> (uuid)"),
                "admin_user": admin_user,
                "smtp_server_desc": self._("<strong>SMTP server</strong> (host)"),
                "smtp_server": smtp_server,
                "locale_desc": self._("<strong>Global locale</strong> (en, ru)"),
                "locale": locale,
                "submit_desc": self._("Save")
            }
        })

    def store_servers_online(self):
        self.app().servers_online_modified = True

    def servers_online_updated(self):
        self.queue_workers = {}
        for id, srv in self.app().servers_online.items():
            if srv["type"] == "worker" and srv["params"].get("queue"):
                cls = srv["params"].get("class")
                try:
                    self.queue_workers[cls].append(srv)
                except KeyError:
                    self.queue_workers[cls] = [srv]

    def fastidle(self):
        if self.app().servers_online_modified:
            self.app().servers_online_modified = False
            self.app().config.set("director.servers", self.app().servers_online)
            self.app().config.store()
            try:
                if not self.configure_nginx():
                    self.app().servers_online_modified = True
            except JoinError:
                self.app().servers_online_modified = True

    def configure_nginx(self):
        nginx = set()
        workers = {}
        for server_id, info in self.app().servers_online.items():
            if self.app().inst.reloading_hard:
                st = self.obj(WorkerStatus, server_id, silent=True)
                if st.get("reloading"):
                    continue
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
            self.workers_str = workers_str
            tasklets = []
            for host, port in nginx:
                tasklet = Tasklet.new(self.configure_nginx_server)(host, port, workers_str)
                tasklets.append(tasklet)
            for tasklet in tasklets:
                if not Tasklet.join(tasklet):
                    return False
        return True

    def configure_nginx_server(self, host, port, workers):
        try:
            with Timeout.push(20):
                self.call("cluster.query_server", host, port, "/server/nginx", {"workers": workers})
            return True
        except Exception as e:
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
            with Timeout.push(20):
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
        if parent and parent != "":
            server_id = "%s-server-%s" % (server_id, parent)
            params["parent"] = "%s-%s-%s" % (host, "server", parent)
            if request.param("queue") != "":
                params["queue"] = request.param("queue")
            if params.get("queue") is None:
                parent_info = self.app().servers_online.get(params["parent"])
                if parent_info is not None:
                    if parent_info["params"].get("queue"):
                        params["queue"] = True
        server_id = "%s-%s" % (server_id, type)
        id = request.param("id")
        if id and id != "":
            server_id = "%s-%02d" % (server_id, int(id))
            conf["id"] = id
        self.app().servers_online[server_id] = conf
        self.call("director.registering_server", server_id, conf)
        # clearing possibly "reloading" state
        obj = self.obj(WorkerStatus, server_id, {}, silent=True)
        obj.remove()
        # updating nginx
        self.store_servers_online()
        self.servers_online_updated()
        if type == "server" and self.workers_str != None:
            Tasklet.new(self.configure_nginx_server)(host, port, self.workers_str)
        self.call("web.response_json", {"ok": 1, "server_id": server_id, "host": host})
