from mg import *
from concurrence import Timeout, TimeoutError
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from urllib import urlencode
from uuid import uuid4
import urlparse
import json
import random
import re

alphabet = "abcdefghijklmnopqrstuvwxyz"
re_extract_uuid = re.compile(r'-([a-f0-9]{32})\.[a-z0-9]+$')

class TempFile(CassandraObject):
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

class TempFileList(CassandraObjectList):
    objcls = TempFile

class Cluster(Module):
    def register(self):
        self.rhook("cluster.query_director", self.query_director)
        self.rhook("cluster.query_server", self.query_server)
        self.rhook("cluster.servers_online", self.servers_online)
        self.rhook("cluster.static_upload", self.static_upload)
        self.rhook("cluster.appconfig_changed", self.appconfig_changed)
        self.rhook("cluster.static_upload_temp", self.static_upload_temp)
        self.rhook("cluster.static_preserve", self.static_preserve)
        self.rhook("cluster.static_upload_zip", self.static_upload_zip)
        self.rhook("cluster.static_put", self.static_put)
        self.rhook("cluster.static_delete", self.static_delete)
        self.rhook("objclasses.list", self.objclasses_list)

    def query_director(self, uri, params={}):
        """
        Connect to Director and query given URI
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        return dir_query(uri, params)

    def query_server(self, host, port, uri, params={}, timeout=20):
        """
        Connect to an arbitrary server and query given URI
        host:port - server socket
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        return query(host, port, uri, params, timeout=timeout)

    def servers_online(self):
        """
        Returns list of internal servers currently online
        """
        config = self.app().inst.int_app.config
        config.clear()
        online = config.get("director.servers", {})
        if online is None:
            online = {}
        return online

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
            request.add_header("Content-length", len(request.body))
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
        host = str(random.choice(self.app().inst.config["storage"]))
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
            request.add_header("Content-length", len(request.body))
            request.add_header("Connection", "close")
            response = cnn.perform(request)
            if response.status_code != 201 and response.status_code != 204:
                raise StaticUploadError(self._("Error storing object {0}: {1}").format(uri, response.status))
        finally:
            cnn.close()
        return (uri, url, host, id)

    def static_upload_zip(self, subdir, zip, upload_list):
        host = str(random.choice(self.app().inst.config["storage"]))
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
                request.add_header("Content-length", len(data))
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
        tempfile = self.int_app().obj(TempFile, id, data=data)
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
            def reload_server(info):
                try:
                    self.int_app().hooks.call("cluster.query_server", info["host"], info["port"], "/core/appconfig/%s" % tag, {})
                except HTTPError as e:
                    self.error(e)
                except Exception as e:
                    self.exception(e)
            tasklets = []
            for server, info in self.servers_online().items():
                if info["type"] == "worker":
                    tasklets.append(Tasklet.new(reload_server)(info))
            Tasklet.join_all(tasklets)
    
    def objclasses_list(self, objclasses):
        objclasses["TempFile"] = (TempFile, TempFileList)

    def static_preserve(self, uri):
        m = re_extract_uuid.search(uri)
        if not m:
            return
        uuid = m.groups()[0]
        try:
            tempfile = self.int_app().obj(TempFile, uuid)
        except ObjectNotFoundException:
            pass
        else:
            tempfile.remove()

def dir_query(uri, params):
    return query("director", 3000, uri, params)

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
        raise HTTPError("Error downloading http://%s:%s%s: %s" % (host, port, uri, e))
    except TimeoutError:
        raise HTTPError("Timeout downloading http://%s:%s%s" % (host, port, uri))

class ClusterAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-cluster.monitoring", self.menu_cluster_monitoring)
        self.rhook("ext-admin-workers.monitor", self.workers_monitor, priv="monitoring")
        self.rhook("headmenu-admin-workers.monitor", self.headmenu_workers_monitor)

    def permissions_list(self, perms):
        perms.append({"id": "monitoring", "name": self._("Cluster monitoring")})

    def menu_root_index(self, menu):
        menu.append({"id": "constructor.cluster", "text": self._("Cluster"), "order": 28})
        menu.append({"id": "cluster.monitoring", "text": self._("Monitoring"), "order": 29})

    def menu_cluster_monitoring(self, menu):
        req = self.req()
        if req.has_access("monitoring"):
            menu.append({"id": "workers/monitor", "text": self._("Workers"), "leaf": True})

    def workers_monitor(self):
        rows = []
        vars = {
            "tables": [
                {
                    "header": [self._("ID"), self._("Class"), self._("Interface"), self._("Version"), self._("Status"), self._("Web"), self._("Daemons")],
                    "rows": rows
                }
            ]
        }
        lst = self.int_app().objlist(WorkerStatusList, query_index="all")
        lst.load(silent=True)
        for ent in lst:
            act = ent.get("active_requests", {})
            rows.append([ent.uuid, ent.get("cls"), "%s:%d" % (ent.get("host"), ent.get("port")), ent.get("ver"), self._("Reloading") if ent.get("reloading") else self._("OK"), act.get("web"), act.get("daemons")])
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_workers_monitor(self, args):
        return self._("Workers monitor")
