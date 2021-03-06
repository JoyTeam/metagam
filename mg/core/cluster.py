#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

import mg
from mg.core.tools import utf2str
from mg.core.cass import CassandraObject, CassandraObjectList
from mg.core.common import StaticUploadError
from concurrence import Timeout, TimeoutError, Tasklet
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from urllib import urlencode
from uuid import uuid4
import urlparse
import json
import random
import re
import os
import sys

alphabet = "abcdefghijklmnopqrstuvwxyz"
re_extract_uuid = re.compile(r'-([a-f0-9]{32})\.[a-z0-9]+$')

class ClusterError(Exception):
    pass

class HTTPConnectionRefused(HTTPError):
    pass

class DBCluster(CassandraObject):
    clsname = "Cluster"
    indexes = {
    }

class DBTempFile(CassandraObject):
    clsname = "TempFile"
    indexes = {
        "till": [[], "till"],
        "wizard": [["wizard"]],
        "app": [["app"]],
    }

    def delete(self):
        host = str(self.get("host"))
        url = str(self.get("url"))
        uri = str(self.get("uri"))
        cnn = HTTPConnection()
        cnn.connect((str(host), 80))
        try:
            request = HTTPRequest()
            request.method = "DELETE"
            request.path = url
            request.host = host
            request.add_header("Connection", "close")
            cnn.perform(request)
        except Exception:
            pass
        finally:
            cnn.close()

class DBTempFileList(CassandraObjectList):
    objcls = DBTempFile

class ClusterDaemon(mg.Module):
    def register(self):
        inst = self.app().inst
        if not hasattr(inst, "services"):
            inst.services = {}
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("cluster.daemons", self.daemons)
        self.rhook("cluster.register-daemon", self.register_daemon)
        self.rhook("cluster.run-daemon-loop", self.run_daemon_loop)
        self.rhook("cluster.run-int-service", self.run_int_service)
        self.rhook("cluster.register-service", self.register_service)
        self.rhook("cluster.unregister-service", self.unregister_service)
        self.rhook("cluster.cleanup-host", self.cleanup_host)
        self.rhook("cluster.terminate-daemon", self.terminate_daemon)

    def terminate_daemon(self):
        inst = self.app().inst
        for svcid, svcinfo in inst.services.items():
            self.debug("Stopping service %s", svcid)
            service = svcinfo["service"]
            service.stop()

    def objclasses_list(self, objclasses):
        objclasses["Cluster"] = (DBCluster,)

    @property
    def cluster_lock(self):
        return self.lock(["Cluster"])

    def run_daemon_loop(self):
        inst = self.app().inst
        next_update = self.now()
        while True:
            try:
                if self.now() >= next_update:
                    next_update = self.now(10)
                    with self.cluster_lock:
                        self.store_daemon()
                self.call("core.fastidle")
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(1)

    def daemons(self):
        return self.obj(DBCluster, "daemons", silent=True).data

    def register_daemon(self, must_exist=False):
        "Register daemon in the DB"
        inst = self.app().inst
        inst.uuid = uuid4().hex
        with self.cluster_lock:
            self.debug("Registered daemon %s", inst.instid)
            now = self.now()
            obj = self.obj(DBCluster, "daemons", silent=True)
            daemon = obj.get(inst.instid)
            if must_exist and not daemon:
                logger.error("Daemon %s started but not found daemon record. Exiting", inst.instid)
                sys.exit(0)
            if daemon is None:
                daemon = {}
                obj.set(inst.instid, daemon)
            daemon["registered"] = now
            daemon["type"] = inst.insttype
            daemon["updated"] = now
            daemon["addr"] = inst.instaddr
            daemon["hostid"] = inst.conf("global", "id")
            daemon["uuid"] = inst.uuid
            daemon["cls"] = inst.cls
            obj.touch()
            obj.store()

    def store_daemon(self):
        inst = self.app().inst
        obj = self.obj(DBCluster, "daemons", silent=True)
        info = obj.get(inst.instid)
        if not info:
            self.error('Daemon record "%s" lost. Terminating' % inst.instid)
            self.call("cluster.terminate-daemon")
            raise SystemExit()
        if info.get("uuid") != inst.uuid:
            self.error('Daemon record "%s" changed UUID from "%s" to "%s". Terminating' % (inst.instid, inst.uuid, info.get("uuid")))
            self.call("cluster.terminate-daemon")
            raise SystemExit()
        info["updated"] = self.now()
        if inst.services:
            services = {}
            now = self.now()
            for svcid, svcinfo in inst.services.items():
                service = svcinfo["service"]
                svcinfo = {
                    "registered": svcinfo["registered"],
                    "updated": now,
                    "type": service.type,
                    "addr": service.addr[0],
                    "port": service.addr[1]
                }
                for key, val in service.svcinfo.iteritems():
                    svcinfo[key] = val
                service.publish(svcinfo)
                services[svcid] = svcinfo
            info["services"] = services
        obj.touch()
        obj.store()

    def register_service(self, service):
        inst = self.app().inst
        service_id = service.id
        service_type = service.type
        if service_id in inst.services:
            self.call("unregister-service", service_id)
        with self.cluster_lock:
            inst.services[service_id] = {
                "registered": self.now(),
                "service": service,
            }
            self.store_daemon()
        # Reload nginx servers if web backend is registered
        if service.svcinfo.get("webbackend"):
            self.call("cluster.query-services", "nginx", "/nginx/reload")

    def unregister_service(self, service_id):
        inst = self.app().inst
        now = self.now()
        with self.cluster_lock:
            ent = inst.services.get(service_id)
            if ent:
                ent["service"].stop()
                del inst.services[service_id]
                obj = self.obj(DBCluster, "services", silent=True)
                obj.delkey(service_id)
                obj.store()

    def run_int_service(self):
        inst = self.app().inst
        service_id = "%s-int" % inst.instid
        srv = mg.SingleApplicationWebService(self.app(), service_id, "int", "int")
        srv.serve_any_port()
        self.call("cluster.register-service", srv)

    def cleanup_host(self):
        inst = self.app().inst
        addr = inst.instaddr
        self.debug("Dropping all daemons from host %s", addr)
        with self.cluster_lock:
            obj = self.obj(DBCluster, "daemons", silent=True)
            for dmnid, dmninfo in obj.data.items():
                if dmninfo.get("cls") != inst.cls:
                    continue
                if dmninfo.get("addr") == addr:
                    self.debug("Dropped daemon %s", dmnid)
                    obj.delkey(dmnid)
            obj.store()

class Cluster(mg.Module):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("cluster.query_server", self.query_server)
        self.rhook("cluster.static_upload", self.static_upload)
        self.rhook("cluster.appconfig_changed", self.appconfig_changed)
        self.rhook("cluster.static_upload_temp", self.static_upload_temp)
        self.rhook("cluster.static_preserve", self.static_preserve)
        self.rhook("cluster.static_upload_zip", self.static_upload_zip)
        self.rhook("cluster.static_put", self.static_put)
        self.rhook("cluster.static_delete", self.static_delete)
        self.rhook("cluster.query-service", self.query_service)
        self.rhook("cluster.services", self.services)
        self.rhook("cluster.query-services", self.query_services)

    def query_server(self, host, port, uri, params={}, timeout=20):
        """
        Connect to an arbitrary server and query given URI
        host:port - server socket
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        return query(host, port, uri, params, timeout=timeout)

    def static_put(self, uri, content_type, data):
        if uri is None:
            raise StaticUploadError(self._("Invalid store URI"))
        if type(uri) == unicode:
            uri = uri.encode("utf-8")
        uri_obj = urlparse.urlparse(uri, "http", False)
        if uri_obj.hostname is None:
            raise StaticUploadError(self._("Empty hostname"))
        cnn = HTTPConnection()
        cnn.connect((uri_obj.hostname, 80))
        try:
            request = HTTPRequest()
            request.method = "PUT"
            request.path = uri_obj.path
            request.host = uri_obj.hostname
            request.body = data
            request.add_header("Content-type", content_type)
            request.add_header("Connection", "close")
            response = cnn.perform(request)
            if response.status_code != 201 and response.status_code != 204:
                raise StaticUploadError(self._("Error storing object {0}: {1}").format(uri, response.status))
        finally:
            cnn.close()

    def static_delete(self, uri):
        if uri is None:
            raise StaticUploadError(self._("Invalid delete URI"))
        if type(uri) == unicode:
            uri = uri.encode("utf-8")
        uri_obj = urlparse.urlparse(uri, "http", False)
        if uri_obj.hostname is None:
            raise StaticUploadError(self._("Empty hostname"))
        cnn = HTTPConnection()
        cnn.connect((uri_obj.hostname, 80))
        try:
            request = HTTPRequest()
            request.method = "DELETE"
            request.path = uri_obj.path
            request.host = uri_obj.hostname
            request.add_header("Connection", "close")
            cnn.perform(request)
        finally:
            cnn.close()

    def upload(self, subdir, ext, content_type, data, filename=None):
        host = str(random.choice(self.clconf("storage", ["storage"])))
        tag = self.app().tag
        id = uuid4().hex
        if filename is None:
            url = str("/%s/%s/%s%s/%s/%s.%s" % (subdir, tag[0], tag[0], tag[1], tag, id, ext))
        else:
            url = str("/%s/%s/%s%s/%s/%s-%s" % (subdir, tag[0], tag[0], tag[1], tag, id, filename))
        uri = str("//" + host + url)
        cnn = HTTPConnection()
        cnn.connect((str(host), 80))
        try:
            request = HTTPRequest()
            request.method = "PUT"
            request.path = url
            request.host = host
            request.body = data
            request.add_header("Content-type", content_type)
            request.add_header("Connection", "close")
            response = cnn.perform(request)
            if response.status_code != 201 and response.status_code != 204:
                raise StaticUploadError(self._("Error storing object {0}: {1}").format(uri, response.status))
        finally:
            cnn.close()
        return (uri, url, host, id)

    def static_upload_zip(self, subdir, zip, upload_list):
        host = str(random.choice(self.clconf("storage", ["storage"])))
        id = uuid4().hex
        tag = self.app().tag
        url = str("/%s/%s/%s%s/%s/%s" % (subdir, tag[0], tag[0], tag[1], tag, id))
        uri = str("//" + host + url)
        for ent in upload_list:
            cnn = HTTPConnection()
            cnn.connect((str(host), 80))
            try:
                request = HTTPRequest()
                request.method = "PUT"
                request.path = str("%s/%s" % (url, ent["filename"]))
                request.host = host
                data = ent.get("data")
                if data is None and zip:
                    data = zip.read(ent["zipname"])
                if data is None and ent.get("path"):
                    with open(ent.get("path")) as f:
                        data = f.read()
                request.body = data
                request.add_header("Content-type", str(ent["content-type"]))
                request.add_header("Connection", "close")
                response = cnn.perform(request)
                if response.status_code != 201 and response.status_code != 204:
                    raise StaticUploadError(self._("Error storing object {name}: {err}").format(name=ent["filename"], err=response.status))
            finally:
                cnn.close()
        return uri

    def static_upload(self, subdir, ext, content_type, data, filename=None):
        uri, url, host, id = self.upload(subdir, ext, content_type, data, filename=filename)
        return uri

    def static_upload_temp(self, subdir, ext, content_type, data, wizard=None):
        uri, url, host, id = self.upload(subdir, ext, content_type, data)
        data = {
            "uri": uri,
            "url": url,
            "host": host,
            "app": self.app().tag
        }
        tempfile = self.int_app().obj(DBTempFile, id, data=data)
        if wizard is None:
            tempfile.set("till", self.now(86400))
        else:
            tempfile.set("wizard", wizard)
        tempfile.store()
        return uri

    def appconfig_changed(self):
        tag = None
        try:
            tag = self.app().tag
        except AttributeError:
            pass
        if tag is not None:
            try:
                with Timeout.push(3):
                    self.call("cluster.query-services", "int", "/core/appconfig/%s" % tag)
            except TimeoutError:
                pass
    
    def objclasses_list(self, objclasses):
        objclasses["TempFile"] = (DBTempFile, DBTempFileList)

    def static_preserve(self, uri):
        m = re_extract_uuid.search(uri)
        if not m:
            return
        uuid = m.groups()[0]
        try:
            tempfile = self.int_app().obj(DBTempFile, uuid)
        except ObjectNotFoundException:
            pass
        else:
            tempfile.remove()

    def query_services(self, service_type, url, timeout=10, call_int=False, delay=0, *args, **kwargs):
        inst = self.app().inst
        daemons = inst.int_app.obj(DBCluster, "daemons", silent=True)
        tasklets = []
        for dmnid, dmninfo in daemons.data.items():
            services = dmninfo.get("services", {})
            for svcid, svcinfo in services.items():
                if svcinfo.get("type") != service_type:
                    continue
                if call_int:
                    found = False
                    for sid, sinfo in services.items():
                        if sinfo.get("type") != "int":
                            continue
                        found = True
                        svcid = sid
                        svcinfo = sinfo
                        break
                    if not found:
                        continue
                if "addr" not in svcinfo:
                    continue
                if "port" not in svcinfo:
                    continue
                task = Tasklet.new(self.do_query_service_exc)
                tasklets.append(task)
                task(svcid, svcinfo, url, timeout, *args, **kwargs)
                if delay > 0:
                    Tasklet.sleep(delay)
        Tasklet.join_all(tasklets)

    def query_service(self, service_id, url, timeout=30, *args, **kwargs):
        inst = self.app().inst
        daemons = inst.int_app.obj(DBCluster, "daemons", silent=True)
        svc = None
        for dmnid, dmninfo in daemons.data.items():
            svcinfo = dmninfo.get("services", {}).get(service_id)
            if svcinfo:
                if ("addr" in svcinfo) and ("port" in svcinfo):
                    svc = svcinfo
                break
        if svc is None:
            raise ClusterError("Service %s not running" % service_id)
        return self.do_query_service(service_id, svc, url, timeout, *args, **kwargs)

    def do_query_service_exc(self, service_id, *args, **kwargs):
        try:
            self.do_query_service(service_id, *args, **kwargs)
        except Exception as e:
            self.error("Error calling service %s: %s" % (service_id, e))

    def do_query_service(self, service_id, svc, url, timeout, verbose=False, *args, **kwargs):
        try:
            with Timeout.push(timeout):
                cnn = HTTPConnection()
                addr = (svc.get("addr").encode("utf-8"), svc.get("port"))
                try:
                    cnn.connect(addr)
                except IOError as e:
                    raise ClusterError("Error connecting to service %s(%s:%s): %s" % (service_id, addr[0], addr[1], e))
                params = {
                    "args": json.dumps(args),
                    "kwargs": json.dumps(kwargs)
                }
                try:
                    uri = utf2str("/service/call/%s%s" % (service_id, url))
                    request = cnn.post(uri, urlencode(params))
                    request.add_header("Content-type", "application/x-www-form-urlencoded")
                    request.add_header("Connection", "close")
                    if verbose:
                        self.debug("Query http://%s:%s%s", addr[0], addr[1], uri)
                    response = cnn.perform(request)
                    if response.status_code != 200:
                        raise ClusterError("Service %s (%s:%d) returned status %d for URL %s" % (service_id, addr[0], addr[1], response.status_code, uri))
                    res = json.loads(response.body)
                    if res.get("error"):
                        raise ClusterError(u"Service %s returned error: %s" % (service_id, res["error"]))
                    return res.get("retval")
                finally:
                    cnn.close()
        except TimeoutError:
            raise ClusterError("Timeout querying %s of service %s" % (url, service_id))

    def services(self):
        """
        Returns map of services:
        {
        type => [{}, {}, {}, ...],
        type => [{}, {}, {}, ...]
        }
        Every service record contains id, addr and port fields.
        """
        services = {}
        daemons = self.app().inst.int_app.obj(DBCluster, "daemons", silent=True)
        for dmnid, dmninfo in daemons.data.items():
            for svcid, svcinfo in dmninfo.get("services", {}).iteritems():
                tp = svcinfo.get("type")
                svc = {
                    "id": svcid,
                    "addr": svcinfo.get("addr"),
                    "port": svcinfo.get("port"),
                }
                if tp in services:
                    services[tp].append(svc)
                else:
                    services[tp] = [svc]
        return services

def query(host, port, uri, params, timeout=20):
    try:
        with Timeout.push(timeout):
            cnn = HTTPConnection()
            cnn.connect((str(host), int(port)))
            try:
                request = cnn.post(str(uri), urlencode(params))
                request.add_header("Content-type", "application/x-www-form-urlencoded")
                request.add_header("Connection", "close")
                response = cnn.perform(request)
                if response.status_code != 200:
                    raise HTTPError("Error downloading http://%s:%s%s: %s" % (host, port, uri, response.status))
                body = response.body
                if response.get_header("Content-type") == "application/json":
                    body = json.loads(body)
                return body
            finally:
                cnn.close()
    except IOError as e:
        if e.errno == 111:
            raise HTTPConnectionRefused("Connection refused during downloading http://%s:%s%s" % (host, port, uri))
        else:
            raise HTTPError("Error downloading http://%s:%s%s: %s" % (host, port, uri, e))
    except TimeoutError:
        raise HTTPError("Timeout downloading http://%s:%s%s" % (host, port, uri))

class ClusterAdmin(mg.Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-metagam.cluster", self.menu_metagam_cluster)
        self.rhook("ext-admin-cluster.monitor", self.cluster_monitor, priv="monitoring")
        self.rhook("headmenu-admin-cluster.monitor", self.headmenu_cluster_monitor)
        self.rhook("ext-admin-cluster.config", self.cluster_config, priv="clusterconfig")

    def permissions_list(self, perms):
        perms.append({"id": "clusterconfig", "name": self._("Cluster configuration")})
        perms.append({"id": "monitoring", "name": self._("Cluster monitoring")})

    def menu_root_index(self, menu):
        menu.append({"id": "metagam.cluster", "text": self._("Cluster"), "order": 28})

    def menu_metagam_cluster(self, menu):
        req = self.req()
        if req.has_access("clusterconfig"):
            menu.append({"id": "cluster/config", "text": self._("Cluster configuration"), "leaf": True})
        if req.has_access("monitoring"):
            menu.append({"id": "cluster/monitor", "text": self._("Cluster monitor"), "leaf": True})

    def cluster_config(self):
        req = self.req()
        inst = self.app().inst
        dbconfig = inst.dbconfig
        params = ["memcached", "storage", "admin_user", "smtp_server", "mysql_write_server",
            "mysql_database", "mysql_user", "mysql_password", "wm_w3s_gate", "wm_login_gate",
            "wm_passport_gate", "xsolla_gate", "xsolla_api_gate", "locale", "mysql_read_server"]
        if req.ok():
            errors = {}
            values = {}
            listParams = set(["memcached", "storage", "mysql_read_server", "mysql_write_server"])
            for param in params:
                val = req.param(param).strip()
                values[param] = val
                if val == "":
                    dbconfig.delkey(param)
                else:
                    if param in listParams:
                        val = re.split(r'\s*,\s*', val)
                    dbconfig.set(param, val)
            dbconfig.store()
            self.call("cluster.query-services", "int", "/core/dbconfig")
            self.call("admin.response", self._("Configuration stored"), {})
        fields = []
        fields.append({"name": "admin_user", "label": self._("Administrator UUID"), "value": dbconfig.get("admin_user")})
        fields.append({"name": "memcached", "label": self._("Memcached servers (comma separated list)"), "value": ", ".join(dbconfig.get("memcached", ["127.0.0.1"]))})
        fields.append({"name": "storage", "label": self._("Storage servers (comma separated list)"), "value": ", ".join(dbconfig.get("storage", ["storage"]))})
        fields.append({"name": "smtp_server", "label": self._("SMTP server"), "value": dbconfig.get("smtp_server", "127.0.0.1")})
        fields.append({"name": "mysql_write_server", "label": self._("MySQL write server (master)"), "value": ", ".join(dbconfig.get("mysql_write_server", ["127.0.0.1"]))})
        fields.append({"name": "mysql_read_server", "label": self._("MySQL read servers (master + slaves; comma separated list)"), "value": ", ".join(dbconfig.get("mysql_read_server", ["127.0.0.1"]))})
        fields.append({"name": "mysql_database", "label": self._("MySQL database name"), "value": dbconfig.get("mysql_database", "metagam")})
        fields.append({"name": "mysql_user", "label": self._("MySQL user name"), "value": dbconfig.get("mysql_user", "metagam")})
        fields.append({"name": "mysql_password", "label": self._("MySQL user password"), "value": dbconfig.get("mysql_password")})
        fields.append({"name": "wm_w3s_gate", "label": self._("Gate to WebMoney w3s API"), "value": dbconfig.get("wm_w3s_gate", "localhost:85")})
        fields.append({"name": "wm_login_gate", "label": self._("Gate to WebMoney login API"), "value": dbconfig.get("wm_login_gate", "localhost:86")})
        fields.append({"name": "wm_passport_gate", "label": self._("Gate to WebMoney passport API"), "value": dbconfig.get("wm_passport_gate", "localhost:87")})
        fields.append({"name": "xsolla_gate", "label": self._("Gate to secure.xsolla.com"), "value": dbconfig.get("xsolla_gate", "localhost:88")})
        fields.append({"name": "xsolla_api_gate", "label": self._("Gate to api.xsolla.com"), "value": dbconfig.get("xsolla_api_gate", "localhost:89")})
        fields.append({"name": "locale", "label": self._("Server locale"), "value": dbconfig.get("locale", "en")})
        self.call("admin.form", fields=fields)

    def cluster_monitor(self):
        daemons = self.app().inst.int_app.call("cluster.daemons")
        vars = {
            "state": json.dumps(daemons, indent=4)
        }
        self.call("admin.response_template", "admin/cluster/monitor.html", vars)

    def headmenu_cluster_monitor(self, args):
        return self._("Cluster monitor")
