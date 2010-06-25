from mg.core import Module
from concurrence.http import HTTPConnection, HTTPError
import json
from urllib import urlencode

class Director(Module):
    def register(self):
        Module.register(self)
        self.rhook("director.query", self.director_query)

    def director_query(self, uri, params):
        """
        Connect to Director and query given URI
        uri - URI
        params - HTTP form params
        Return value: received response (application/json will be decoded automatically)
        """
        cnn = HTTPConnection()
        cnn.connect(("director", 3000))
        try:
            request = cnn.post(uri, urlencode(params))
            request.add_header("Content-type", "application/x-www-form-urlencoded")
            response = cnn.perform(request)
            if response.status_code != 200:
                raise HTTPError("Error downloading http://director:3000%s: %s" % (uri, response.status))
            body = response.body
            if response.get_header("Content-type") == "application/json":
                body = json.loads(body)
            return body
        finally:
            cnn.close()
