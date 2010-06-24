from concurrence import quit
from concurrence.http import WSGIServer
from concurrence import Tasklet
from mg.stor.db import Database
from mg.stor.mc import Memcached
from mg.core import Application, Instance
import logging
import urlparse
import cgi
import re
import mg.tools
import json
import traceback

class DoubleResponseException(Exception):
    "start_response called twice on the same request"
    pass

class Request(object):
    "HTTP request"

    def __init__(self, environ, start_response):
        self.environ = environ
        self._start_response = start_response
        self._params_loaded = None
        self.headers = []
        self.content_type = 'text/html; charset=utf-8';
        self.config_stat = {}
        self.hook_stat = {}
        self.headers_sent = False
        self.global_html = "global.html"
        # Storing reference request to the current tasklet. It will be used in different modules to access currenct request implicitly
        Tasklet.current().req = self

    def start_response(self, *args):
        if self.headers_sent:
            raise DoubleResponseException()
        self.headers_sent = True
        self._start_response(*args)

    def is_post_request(self):
        if self.environ['REQUEST_METHOD'].upper() != 'POST':
            return False
        content_type = environ.get('CONTENT_TYPE', 'application/x-www-form-urlencoded')
        return content_type.startswith('application/x-www-form-urlencoded') or content_type.startswith('multipart/form-data')

    def load_params(self):
        self._params_loaded = True
        self._params = cgi.parse(fp = input, environ = self.environ, keep_blank_values = 1)

    def param_dict(self):
        "Get directory of all parameters (both GET and POST)"
        if self._params_loaded is None:
            self.load_params()
        return self._params

    def params(self, key):
        "Get a list of parameters with given name (both GET and POST)"
        if self._params_loaded is None:
            self.load_params()
        return map(lambda val: encode(val, "utf-8"), self._params.get(key, []))

    def param(self, key):
        "Get specific parameter (both GET and POST)"
        if self._params_loaded is None:
            self.load_params()
        val = self._params.get(key)
        if val is None:
            return u''
        else:
            return unicode(val[0], "utf-8")

    def uri(self):
        "Get the URI requested"
        return self.environ['PATH_INFO']

    def send_response(self, status, headers, content):
        self.content = content
        self.start_response(status, headers)
        return [content];

    def not_found(self):
        "Return 404 Not Found"
        return self.send_response("404 Not Found", self.headers, "<html><body><h1>404 Not Found</h1></body></html>")

    def forbidden(self):
        "Return 403 Forbidden"
        return self.send_response("403 Forbidden", self.headers, "<html><body><h1>403 Forbidden</h1></body></html>")

    def internal_server_error(self):
        "Return 500 Internal Server Error"
        return self.send_response("500 Internal Server Error", self.headers, "<html><body><h1>500 Internal Server Error</h1></body></html>")

    def response(self, content):
        "Return HTTP response. content will be returned to the client"
        self.headers.append(('Content-type', self.content_type))
        self.headers.append(('Content-length', len(content)))
        return self.send_response("200 OK", self.headers, content)

    def uresponse(self, content):
        "Return HTTP response. content must be unicode - it will be converted to utf-8"
        return self.response(content.encode("utf-8"))

    def jresponse(self, obj):
        "Return HTTP response. obj will be encoded into JSON"
        self.content_type = "application/json"
        return self.uresponse(json.dumps(obj))

class WebDaemon(object):
    "Abstract web application serving HTTP requests"

    def __init__(self, inst, app=None):
        object.__init__(self)
        self.server = WSGIServer(self.req)
        self.inst = inst
        self.app = app

    def serve(self, addr):
        "Runs a WebDaemon instance listening given port"
        logging.basicConfig(level=logging.DEBUG)
        try:
            self.server.serve(addr)
            print "serving %s:%d" % (addr[0], addr[1])
        except Exception as err:
            print "Listen %s:%d: %s" % (addr[0], addr[1], err)
            quit(1)

    def req(self, environ, start_response):
        "Process single HTTP request"
        request = Request(environ, start_response)
        try:
            # remove doubling, leading and trailing slashes, unquote and convert to utf-8
          uri = re.sub(r'^/*(.*?)/*$', r'\1', re.sub(r'/{2+}', '/', mg.tools.urldecode(request.uri())))
          return self.req_uri(request, uri)
        except SystemExit:
            raise
        except BaseException, e:
            traceback.print_exc()
            return request.internal_server_error()

    def req_uri(self, request, uri):
        "Process HTTP request after URI was extracted, normalized and converted to utf-8"
        if uri == "":
            return self.req_handler(request, "index", "index", "")
        m = re.match(r'^([a-z0-9\-]+)/([a-z0-9\-]+)(?:/(.*)|)', uri)
        if not m:
            return request.not_found()
        (group, hook, args) = m.group(1, 2, 3)
        if args is None:
            args = ""
        return self.req_handler(request, group, hook, args)

    def req_handler(self, request, group, hook, args):
        "Process HTTP request with parsed URI: /<group>/<hook>/<args>"
        return self.app.http_request(request, group, hook, args)

class WebApplication(Application):
    """
    WebApplication is an Application that can handle http requests
    """
    def __init__(self, inst, dbpool, keyspace, mc, hook_prefix):
        """
        inst - Instance object
        dbpool - DatabasePool object
        keyspace - database keyspace
        mc - Memcached object
        dbhost, dbname - database host and name
        mcprefix - memcached prefix
        hook_prefix - prefix for hook names, i.e. prefix "web" means that
           URL /group/hook will be mapped to hook name web-group.hook
        """
        Application.__init__(self, inst, dbpool, keyspace, mc)
        self.hook_prefix = hook_prefix

    def http_request(self, request, group, hook, args):
        "Process HTTP request with parsed URI: /<group>/<hook>/<args>"
        self.hooks.call("%s-%s.%s" % (self.hook_prefix, group, hook), args, request)
        if request.headers_sent:
            return [request.content]
        else:
            return request.not_found()
