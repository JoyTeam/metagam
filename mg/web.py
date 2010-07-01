from concurrence import quit, Tasklet, http
from concurrence.http import server
from mg.cass import Database
from mg.memcached import Memcached
from mg.core import Application, Instance, Module, ApplicationFactory
from template import Template
from template.provider import Provider
import urlparse
import cgi
import re
import mg.tools
import json
import socket
import mg
import logging

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
        # WORKAROUND: concurrence bug. It wsgi.input remains untouched the connection will hang infinitely
        if self._params_loaded is None:
            self.load_params()
        if self.headers_sent:
            raise DoubleResponseException()
        self.headers_sent = True
        self._start_response(*args)

    def load_params(self):
        self._params_loaded = True
        if self.environ.get("CONTENT_TYPE") is None:
            self.environ["CONTENT_TYPE"] = "application/octet-stream"
        self._params = cgi.parse(fp = self.environ["wsgi.input"], environ = self.environ, keep_blank_values = 1)

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

    def redirect(self, uri):
        "Return 302 Found. uri - redirect URI"
        self.headers.append(('Location', uri))
        return self.send_response("302 Found", self.headers, "")

class HTTPHandler(server.HTTPHandler):
    def handle(self, socket, application):
        self._remote_addr, self._remote_port = socket.socket.getpeername()
        server.HTTPHandler.handle(self, socket, application)

    def handle_request(self, control, request, application):
        request.environ["REMOTE_ADDR"] = self._remote_addr
        request.environ["REMOTE_PORT"] = self._remote_port
        response = self._server.handle_request(request, application)
        self.MSG_REQUEST_HANDLED.send(control)(request, response)

class WSGIServer(http.WSGIServer):
    def handle_connection(self, socket):
        HTTPHandler(self).handle(socket, self._application)

class WebDaemon(object):
    "Abstract web application serving HTTP requests"

    def __init__(self, inst, app=None):
        object.__init__(self)
        self.server = WSGIServer(self.req)
        self.inst = inst
        self.app = app
        self.logger = logging.getLogger("mg.web.WebDaemon")

    def serve(self, addr):
        "Runs a WebDaemon instance listening given port"
        try:
            self.server.serve(addr)
            self.logger.info("serving %s:%d", addr[0], addr[1])
        except Exception as err:
            self.logger.error("Listen %s:%d: %s", addr[0], addr[1], err)
            quit(1)

    def serve_any_port(self, hostaddr):
        "Runs a WebDaemon instance listening arbitrarily selected port"
        for port in range(3000, 65536):
            try:
                try:
                    self.server.serve((hostaddr, port))
                    self.logger.info("serving %s:%d", hostaddr, port)
                    return port
                except socket.error as err:
                    if err.errno == 98:
                        pass
                    else:
                        raise
            except Exception as err:
                self.logger.error("Listen %s:%d: %s (%s)", hostaddr, port, err, type(err))
                quit(1)
        self.logger.error("Couldn't find any unused port")
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
        except BaseException as e:
            self.logger.exception(e)
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
        self.app.hooks.call("l10n.set_request_lang", request)
        return self.app.http_request(request, group, hook, args)

    def download_config(self):
        """
        Connect to Director and ask for the claster configuration: http://director:3000/director/config
        Return value: config dict
        Side effect: stores downloaded dict in the inst.config
        """
        cnn = http.HTTPConnection()
        try:
            cnn.connect(("director", 3000))
        except BaseException as e:
            raise RuntimeError("Couldn't connect to director:3000: %s" % e)
        try:
            request = cnn.get("/director/config")
            response = cnn.perform(request)
            config = json.loads(response.body)
            for key in ("memcached", "cassandra"):
                config[key] = [tuple(ent) for ent in config[key]]
            self.inst.config = config
            return config
        finally:
            cnn.close()

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

class Web(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.tpl = None

    def register(self):
        Module.register(self)
        self.rdep(["mg.l10n.L10n"])
        self.rhook("web.template", self.web_template)
        self.rhook("web.response", self.web_response)
        self.rhook("web.parse_template", self.parse_template)
        self.rhook("web.set_global_html", self.set_global_html)
        self.rhook("int-core.ping", self.core_ping)

    def parse_template(self, filename, struct):
        if self.tpl is None:
            conf = {
                "INCLUDE_PATH": [ mg.__path__[0] + "/templates" ],
                "ANYCASE": True,
            }
            try:
                conf["LOAD_TEMPLATES"] = self.app().inst.tpl_provider
            except AttributeError, e:
                provider = Provider(conf)
                self.app().inst.tpl_provider = provider
                conf["LOAD_TEMPLATES"] = provider
            self.tpl = Template(conf)
        return self.tpl.process(filename, struct)

    def set_global_html(self, global_html):
        Tasklet.current().req.global_html = global_html

    def web_template(self, filename, struct):
        struct["content"] = self.call("web.parse_template", filename, struct)
        self.call("web.response", self.call("web.parse_template", Tasklet.current().req.global_html, struct))

    def web_response(self, content):
        return Tasklet.current().req.response(content)

    def core_ping(self, args, request):
        response = {"ok": 1}
        try:
            response["server_id"] = self.app().inst.server_id
        except:
            pass
        return request.jresponse(response)

