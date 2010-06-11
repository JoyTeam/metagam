from concurrence import quit
from concurrence.http import WSGIServer
from concurrence import Tasklet
from mg.stor.db import Database
from mg.stor.mc import Memcached
import logging
import urlparse
import cgi
import re
import mg.tools

class Request(object):
    "HTTP request"

    def __init__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response
        self._params_loaded = None
        self.headers = []
        self.content_type = 'text/html; charset=utf-8';
        self.config_stat = {}
        self.hook_stat = {}
        # Storing reference request to the current tasklet. It will be used in different modules to access currenct request implicitly
        Tasklet.current().req = self

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

    def not_found(self):
        "Return 404 Not Found page"
        self.start_response("404 Not Found", self.headers)
        return ["<html><body><h1>404 Not Found</h1></body></html>"]

    def forbidden(self):
        "Return 403 Forbidden page"
        self.start_response("403 Forbidden", self.headers)
        return ["<html><body><h1>403 Forbidden</h1></body></html>"]

    def response(self, content):
        "Return HTTP response. content will be returned to the client"
        self.headers.append(('Content-type', self.content_type))
        self.headers.append(('Content-length', len(content)))
        self.start_response("200 OK", self.headers)
        return [content]

    def response_unicode(self, content):
        "Return HTTP response. content must be unicode - it will be converted to utf-8"
        return self.response(content.encode("utf-8"))

class WebDaemon(object):
    "Abstract web application serving HTTP requests"

    def __init__(self, inst):
        object.__init__(self)
        self.server = WSGIServer(self.req)
        self.inst = inst

    def serve(self, addr):
        "Runs a WebDaemon instance listening given port"
        logging.basicConfig(level=logging.DEBUG)
        try:
            self.server.serve(addr)
        except Exception as err:
            print "Listen %s:%d: %s" % (addr[0], addr[1], err)
            quit()

    def req(self, environ, start_response):
        "Process single HTTP request"
        request = Request(environ, start_response)
        # remove doubling, leading and trailing slashes, unquote and convert to utf-8
        uri = re.sub(r'^/*(.*?)/*$', r'\1', re.sub(r'/{2+}', '/', mg.tools.urldecode(request.uri())))
        return self.req_uri(request, uri)

    def req_uri(self, request, uri):
        "Process HTTP request after URI was extracted, normalized and converted to utf-8"
        m = re.match(r'^([a-z0-9\-]+)/([a-z0-9\-]+)(?:/(.*)|)', uri)
        if not m:
            return request.not_found()
        (group, hook, args) = m.group(1, 2, 3)
        if args is None:
            args = ''
        return self.req_handler(request, group, hook, args)

    def req_handler(self, request, group, hook, args):
        "Process HTTP request with parsed URI: /<group>/<hook>/<args>"
        return request.not_found()

class Instance:
    "Daemon instance. It contains references to all singleton objects"
    def __init__(self):
        pass

class Application:
    """
    Application is anything that can process unified /group/hook/args
    HTTP requests, call hooks, keep it's own database with configuration,
    data and hooks
    """
    def __init__(self, dbpool=None, dbhost=None, dbname=None, mcpool=None, mcprefix=None):
        """
        dbpool - DatabasePool object. If None a new one will be created automatically (size=10)
        mcpool - MemcachedPool object. If None a new one will be created automatically (host=localhost, size=10)
        dbhost, dbname - database host and name
        mcprefix - memcached prefix
        """
        self.db = Database(dbpool, dbhost, dbname)
        self.mc = Memcached(mcpool, mcprefix)
        pass

    def http_request(self, request, group, hook, args):
        print "group=%s, hook=%s, args=%s" % (group, hook, args)
        args = cgi.escape(args)
        param = request.param('param')
        param = cgi.escape(param)
        return request.response_unicode('<html><body>Hello, world! args=%s, param=%s</body></html>' % (args, param))
