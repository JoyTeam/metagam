from mg.core import Module
from concurrence.http import HTTPConnection, HTTPError
import json
from urllib import urlencode

class Cluster(Module):
    def register(self):
        Module.register(self)
        self.rhook("cluster.query_director", self.director_query)
        self.rhook("cluster.query_server", self.server_query)

    def director_query(self, uri, params):
        """
        Connect to Director and query given URI
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        return dir_query(uri, params)

    def server_query(self, host, port, uri, params):
        """
        Connect to an arbitrary server and query given URI
        host:port - server socket
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        return query(host, port, uri, params)

def dir_query(uri, params):
    return query("director", 3000, uri, params)

def query(host, port, uri, params):
    cnn = HTTPConnection()
    cnn.connect((host, port))
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
