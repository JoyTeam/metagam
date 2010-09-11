from mg.core import Module
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
import json
from urllib import urlencode

class StaticUploadError(Exception):
    "Error uploading object to the static server"
    pass

class Cluster(Module):
    def register(self):
        Module.register(self)
        self.rhook("cluster.query_director", self.query_director)
        self.rhook("cluster.query_server", self.query_server)
        self.rhook("cluster.servers_online", self.servers_online)
        self.rhook("cluster.static_upload", self.static_upload)
        self.rhook("cluster.storage_server", self.storage_server)

    def query_director(self, uri, params):
        """
        Connect to Director and query given URI
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        return dir_query(uri, params)

    def query_server(self, host, port, uri, params):
        """
        Connect to an arbitrary server and query given URI
        host:port - server socket
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        return query(host, port, uri, params)

    def servers_online(self):
        """
        Returns list of internal servers currently online
        """
        online = self.conf("director.servers", reset_cache=True)
        if online is None:
            online = []
        return online

    def static_upload(self, image_url, im_data, content_type):
        storage_server = self.call("cluster.storage_server")
        cnn = HTTPConnection()
        cnn.connect((str(storage_server), 80))
        try:
            request = HTTPRequest()
            request.method = "PUT"
            request.path = image_url
            request.host = storage_server
            request.body = im_data
            request.add_header("Content-type", content_type)
            request.add_header("Content-length", len(request.body))
            response = cnn.perform(request)
            if response.status_code != 201:
                raise StaticUploadError(self._("Error storing image: %s") % response.status)
        finally:
            cnn.close()

    def storage_server(self):
        return "storage"

def dir_query(uri, params):
    return query("director", 3000, uri, params)

def query(host, port, uri, params):
    cnn = HTTPConnection()
    cnn.connect((str(host), int(port)))
    try:
        request = cnn.post(uri, urlencode(params))
        request.add_header("Content-type", "application/x-www-form-urlencoded")
        response = cnn.perform(request)
        if response.status_code != 200:
            raise HTTPError("Error downloading http://%s:%s%s: %s" % (host, port, uri, response.status))
        body = response.body
        if response.get_header("Content-type") == "application/json":
            body = json.loads(body)
        return body
    finally:
        cnn.close()
