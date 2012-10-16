from mg import *
from concurrence import Tasklet, JoinError, Timeout
from concurrence.http import HTTPConnection
from mg.core.common import *
import re
import json

class Director(Module):
    def register(self):
        self.rdep(["mg.core.web.Web", "mg.core.cluster.Cluster", "mg.core.queue.Queue", "mg.core.queue.QueueRunner", "mg.core.projects.Projects",
            "mg.core.realplexor.RealplexorAdmin", "mg.core.modifiers.ModifiersManager"])
        #self.app().servers_online = self.conf("director.servers", {})
        #self.app().servers_online_modified = False
        #self.queue_workers = {}
        #self.workers_str = None
        self.rhook("web.setup_design", self.web_setup_design)
        self.rhook("int-director.ready", self.director_ready, priv="public")
        self.rhook("int-director.reload", self.int_director_reload, priv="public")
        self.rhook("int-index.index", self.director_index, priv="public")
        self.rhook("int-director.setup", self.director_setup, priv="public")
        self.rhook("int-director.config", self.director_config, priv="public")
        self.rhook("int-director.servers", self.director_servers, priv="public")
        self.rhook("director.reload_servers", self.reload_servers)
        self.rhook("core.fastidle", self.fastidle)
        self.rhook("director.queue_workers", self.director_queue_workers)
        self.rhook("cluster.servers_online", self.cluster_servers_online, priority=10)
        self.rhook("core.appfactory", self.appfactory, priority=-10)
        self.rhook("director.monitor", self.monitor)
        #self.servers_online_updated()

    def monitor(self):
        while True:
            try:
                # pinging servers
                for instid, info in self.app().servers_online.items():
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
                                request.add_header("Connection", "close")
                                response = cnn.perform(request)
                                if response.status_code == 200 and response.get_header("Content-type") == "application/json":
                                    body = json.loads(response.body)
                                    if body.get("ok") and body.get("instid") == instid:
                                        success = True
                                        if info["type"] == "worker":
                                            try:
                                                st = self.obj(WorkerStatus, instid)
                                            except ObjectNotFoundException:
                                                success = False
                                                request = cnn.get("/core/abort")
                                                cnn.perform(request)
                                        if success:
                                            self.call("director.ping_results", str(host), int(port), body)
                            finally:
                                cnn.close()
                    except Exception as e:
                        self.info("%s - %s", instid, e)
                    if not success:
                        fact_server = self.app().servers_online.get(instid)
                        if fact_server is not None:
                            fact_port = fact_server.get("port")
                            if fact_port is None or fact_port == port:
                                self.server_offline(instid)
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
                        for instid, info in self.app().servers_online.items():
                            host = info.get("host")
                            port = info.get("port")
                            if host == st.get("host") and (port == st.get("port") or info["params"].get("ext_port") == st.get("ext_port")) and instid != st.uuid:
                                abort = False
                                break
                    else:
                        if not info:
                            self.warning("WorkerStatus %s doesn't match any registered server. Killing %s:%s", st.uuid, st.get("host"), st.get("port"))
                            abort = True
                        elif info["params"]["class"] != st.get("cls"):
                            self.warning("WorkerStatus %s class is %s, although registered one is %s. Killing %s:%s", st.uuid, st.get("cls"), info["params"]["class"], st.get("host"), st.get("port"))
                            abort = True
                    if abort:
                        with Timeout.push(30):
                            try:
                                cnn = HTTPConnection()
                                cnn.connect((str(st.get("host")), int(st.get("port"))))
                                try:
                                    request = cnn.get("/core/abort")
                                    request.add_header("Connection", "close")
                                    cnn.perform(request)
                                    # will be reached unless timed out
                                    st.remove()
                                finally:
                                    cnn.close()
                            except Exception as e:
                                self.error("Couldn't abort %s:%s - %s", st.get("host"), st.get("port"), e)
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(10)

    def server_offline(self, instid):
        del self.app().servers_online[instid]
        self.store_servers_online()
        self.servers_online_updated()
        # removing status object
        st = self.obj(WorkerStatus, instid, silent=True)
        st.remove()
        # additional actions
        self.call("director.unregistering_server", instid)

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
        config.store()
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
                        request.add_header("Connection", "close")
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
                            request.add_header("Connection", "close")
                            cnn.perform(request)
                        finally:
                            cnn.close()
                except Exception as e:
                    self.error("Error reloading %s (%s:%s): %s", st.uuid, st.get("host"), st.get("port"), e)
                    self.server_offline(st.uuid)
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
            if reloaded >= len(lst):
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
                                    request.add_header("Connection", "close")
                                    cnn.perform(request)
                                finally:
                                    cnn.close()
                        except Exception as e:
                            self.exception(e)
                break
        self.store_servers_online()
        self.servers_online_updated()
        #self.app().inst.reloading_hard = 0

    def director_reload(self):
        result = {}
        errors = self.app().inst.reload()
        if errors:
            result["director"] = "ERRORS: %s" % errors
        else:
            result["director"] = "ok: application.version=%s" % self.conf("application.version", 0)
        return result

    def reload_servers(self, result={}):
        return
        config = json.dumps(self.config())
        for instid, info in self.app().servers_online.items():
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
                self.error("%s:%s - %s", info["host"], info["port"], e)
            tag = "%s (%s:%s)" % (instid, info["host"], info["port"])
            if errors:
                result[tag] = "ERRORS: %s" % errors
            else:
                result[tag] = "ok"

    def web_setup_design(self, vars):
        vars["global_html"] = "director/global.html"

    def director_index(self):
        vars = {
            "title": self._("Welcome to the cluster control center"),
            "setup": self._("Change cluster settings")
        }
        #if len(self.app().servers_online):
        #    hosts = self.app().servers_online.keys()
        #    hosts.sort()
        #    vars["servers_online"] = {
        #        "title": self._("List of servers online"),
        #        "list": [{
        #            "id": host_id,
        #            "type": info["type"],
        #            "host": info["host"],
        #            "port": info["port"],
        #            "params": json.dumps(info["params"]),
        #        } for host_id, info in [(host, self.app().servers_online[host]) for host in hosts]]
        #    }
        return self.call("web.response_template", "director/index.html", vars)

    def config(self):
        return
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
        if conf.get("mysql_server") is None:
            conf["mysql_server"] = "localhost"
        if conf.get("mysql_database") is None:
            conf["mysql_database"] = "metagam"
        if conf.get("mysql_user") is None:
            conf["mysql_user"] = "metagam"
        if conf.get("mysql_password") is None:
            conf["mysql_password"] = ""
        if conf.get("wm_w3s_gate") is None:
            conf["wm_w3s_gate"] = "localhost:85"
        if conf.get("wm_passport_gate") is None:
            conf["wm_passport_gate"] = "localhost:87"
        if conf.get("wm_login_gate") is None:
            conf["wm_login_gate"] = "localhost:86"
        if conf.get("locale") is None:
            conf["locale"] = "en"
        self.app().inst.config = conf
        return conf

    def apply_config(self):
        inst = self.app().inst
        inst.init_cassandra()
        inst.init_memcached()
        inst.init_mysql()

    def director_config(self):
        self.call("web.response_json", self.config())

    def director_servers(self):
        self.call("web.response_json", self.app().servers_online)

    def director_setup(self):
        req = self.req()
        params = ["memcached", "storage", "main_host", "admin_user", "smtp_server",
                "mysql_read_server", "mysql_write_server", "mysql_database", "mysql_user",
                "mysql_password", "wm_w3s_gate", "wm_passport_gate", "wm_login_gate",
                "locale"]
        listParams = set(["memcached", "storage", "mysql_read_server", "mysql_write_server"])
        defaultValues = {
            "memcached": ["127.0.0.1"],
            "storage": ["storage"],
            "main_host": "main",
            "smtp_server": "127.0.0.1",
            "mysql_read_server": ["127.0.0.1"],
            "mysql_write_server": ["127.0.0.1"],
            "mysql_database": "metagam",
            "mysql_user": "metagam",
            "wm_w3s_gate": "localhost:85",
            "wm_login_gate": "localhost:86",
            "wm_passport_gate": "localhost:87",
            "locale": "en"
        }
        values = {}
        config = self.app().inst.dbconfig
        if self.ok():
            for param in params:
                val = req.param(param).strip()
                values[param] = val
                if val == "":
                    config.delkey(param)
                else:
                    if param in listParams:
                        val = re.split('\s*,\s*', val)
                    config.set(param, val)
            config.store()
            self.apply_config()
            self.director_reload()
            self.reload_servers()
            self.call("web.redirect", "/")
        else:
            for param in params:
                val = config.get(param, defaultValues.get(param))
                if param in listParams:
                    if val:
                        val = ", ".join(val)
                    else:
                        val = ""
                values[param] = val
        return self.call("web.response_template", "director/setup.html", {
            "title": self._("Cluster settings"),
            "form": {
                "memcached_desc": self._("<strong>Memcached servers</strong> (host:port, host:port, ...)"),
                "memcached": values["memcached"],
                "storage_desc": self._("<strong>Storage servers</strong> (host, host, ...)"),
                "storage": values["storage"],
                "main_host_desc": self._("<strong>Main application host name</strong> (without www)"),
                "main_host": values["main_host"],
                "admin_user_desc": self._("<strong>Administrator</strong> (uuid)"),
                "admin_user": values["admin_user"],
                "smtp_server_desc": self._("<strong>SMTP server</strong>"),
                "smtp_server": values["smtp_server"],
                "mysql_write_server_desc": self._("<strong>MySQL write server</strong>"),
                "mysql_write_server": values["mysql_write_server"],
                "mysql_read_server_desc": self._("<strong>MySQL read server</strong>"),
                "mysql_read_server": values["mysql_read_server"],
                "mysql_database_desc": self._("<strong>MySQL database</strong>"),
                "mysql_database": values["mysql_database"],
                "mysql_user_desc": self._("<strong>MySQL user</strong>"),
                "mysql_user": values["mysql_user"],
                "mysql_password_desc": self._("<strong>MySQL password</strong>"),
                "mysql_password": values["mysql_password"],
                "wm_w3s_gate_desc": self._("<strong>HTTP proxy to w3s.wmtransfer.com</strong> (host:port)"),
                "wm_w3s_gate": values["wm_w3s_gate"],
                "wm_login_gate_desc": self._("<strong>HTTP proxy to login.wmtransfer.com</strong> (host:port)"),
                "wm_login_gate": values["wm_login_gate"],
                "wm_passport_gate_desc": self._("<strong>HTTP proxy to passport.webmoney.ru</strong> (host:port)"),
                "wm_passport_gate": values["wm_passport_gate"],
                "locale_desc": self._("<strong>Global locale</strong> (en, ru)"),
                "locale": values["locale"],
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
        return
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
        for instid, info in self.app().servers_online.items():
            if self.app().inst.reloading_hard:
                st = self.obj(WorkerStatus, instid, silent=True)
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
            self.error("%s:%s - %s", host, port, e)
            return False

    def director_ready(self):
        request = self.req()
        host = request.environ["REMOTE_ADDR"]
        type = request.param("type")
        params = json.loads(request.param("params"))
        port = int(request.param("port"))
        # sending configuration
        if params.get("backends"):
            try:
                with Timeout.push(20):
                    self.call("cluster.query_server", host, port, "/server/spawn", {
                        "workers": params.get("backends"),
                    })
            except Exception as e:
                self.exception(e)
        # storing online list
        instid = str(host)
        conf = {
            "host": host,
            "port": port,
            "type": type,
            "params": params
        }
        parent = request.param("parent")
        if parent and parent != "":
            instid = "%s-server-%s" % (instid, parent)
            params["parent"] = "%s-%s-%s" % (host, "server", parent)
            if request.param("queue") != "":
                params["queue"] = request.param("queue")
            if params.get("queue") is None:
                parent_info = self.app().servers_online.get(params["parent"])
                if parent_info is not None:
                    if parent_info["params"].get("queue"):
                        params["queue"] = True
        instid = "%s-%s" % (instid, type)
        id = request.param("id")
        if id and id != "":
            instid = "%s-%02d" % (instid, int(id))
            conf["id"] = id
        self.app().servers_online[instid] = conf
        self.call("director.registering_server", instid, conf)
        # clearing possibly "reloading" state
        obj = self.obj(WorkerStatus, instid, {}, silent=True)
        obj.remove()
        # updating nginx
        self.store_servers_online()
        self.servers_online_updated()
        if type == "server" and self.workers_str != None:
            Tasklet.new(self.configure_nginx_server)(host, port, self.workers_str)
        self.call("web.response_json", {"ok": 1, "instid": instid, "host": host})
