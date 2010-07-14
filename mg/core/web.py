from concurrence import quit, Tasklet, http
from concurrence.http import server
from mg.core.cass import Cassandra
from mg.core.memcached import Memcached
from mg.core import Application, Instance, Module
from template import Template
from template.provider import Provider
import urlparse
import cgi
import re
import mg.core.tools
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
        self.templates_parsed = 0
        self.templates_len = 0

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
        self.server = WSGIServer(self.request)
        self.inst = inst
        self.app = app
        self.logger = logging.getLogger("mg.core.web.WebDaemon")

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

    def req(self):
        try:
            return Tasklet.current().req
        except AttributeError:
            raise RuntimeError("Module.req() called outside of a web handler")

    def request(self, environ, start_response):
        "Process single HTTP request"
        request = Request(environ, start_response)
        Tasklet.current().req = request
        try:
            # remove doubling, leading and trailing slashes, unquote and convert to utf-8
            uri = re.sub(r'^/*(.*?)/*$', r'\1', re.sub(r'/{2+}', '/', mg.core.tools.urldecode(request.uri())))
            return self.request_uri(request, uri)
        except SystemExit:
            raise
        except BaseException as e:
            self.logger.exception(e)
            return request.internal_server_error()

    def request_uri(self, request, uri):
        "Process HTTP request after URI was extracted, normalized and converted to utf-8"
        # /
        if uri == "":
            return self.req_handler(request, "index", "index", "")
        # /group/hook[/args]
        m = re.match(r'^([a-z0-9\-]+)/([a-z0-9\-]+)(?:/(.*)|)', uri)
        if m:
            (group, hook, args) = m.group(1, 2, 3)
            if args is None:
                args = ""
            return self.req_handler(request, group, hook, args)
        # /group
        m = re.match(r'^[a-z0-9\-]+', uri)
        if m:
            return self.req_handler(request, uri, "index", "")
        return request.not_found()

    def req_handler(self, request, group, hook, args):
        "Process HTTP request with parsed URI"
        self.app.hooks.call("l10n.set_request_lang")
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
    def __init__(self, inst, dbpool, keyspace, mc, hook_prefix, keyprefix):
        """
        inst - Instance object
        dbpool - CassandraPool object
        keyspace - database keyspace
        mc - Memcached object
        dbhost, dbname - database host and name
        mcprefix - memcached prefix
        hook_prefix - prefix for hook names, i.e. prefix "web" means that
           URL /group/hook will be mapped to hook name web-group.hook
        keyprefix - prefix for CassandraObject keys
        """
        Application.__init__(self, inst, dbpool, keyspace, mc, keyprefix)
        self.hook_prefix = hook_prefix

    def http_request(self, request, group, hook, args):
        "Process HTTP request with parsed URI: /<group>/<hook>/<args>"
        request.group = group
        request.hook = hook
        request.args = args
        self.hooks.call("%s-%s.%s" % (self.hook_prefix, group, hook))
        if request.headers_sent:
            return [request.content]
        else:
            return request.not_found()

class Web(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.tpl = None
        self.re_content = re.compile(r'^(.*)===HEAD===(.*)$', re.DOTALL)
        self.re_hooks_split = re.compile(r'(<hook:[a-z0-9_-]+\.[a-z0-9_\.-]+(?:\s+[a-z0-9_-]+="[^"]*")*\s*/>)')
        self.re_hook_parse = re.compile(r'^<hook:([a-z0-9_-]+\.[a-z0-9_\.-]+)((?:\s+[a-z0-9_-]+="[^"]*")*)\s*/>$')
        self.re_hook_args = re.compile(r'\s+([a-z0-9_-]+)="([^"]*)"')

    def register(self):
        Module.register(self)
        self.rdep(["mg.core.l10n.L10n"])
        self.rhook("int-core.ping", self.core_ping)
        self.rhook("int-core.reload", self.core_reload)
        self.rhook("web.parse_template", self.web_parse_template)
        self.rhook("web.response", self.web_response)
        self.rhook("web.response_global", self.web_response_global)
        self.rhook("web.response_template", self.web_response_template)
        self.rhook("web.parse_layout", self.web_parse_layout)
        self.rhook("web.parse_hook_layout", self.web_parse_hook_layout)
        self.rhook("web.response_layout", self.web_response_layout)
        self.rhook("web.response_hook_layout", self.web_response_hook_layout)

    def core_reload(self):
        request = self.req()
        errors = self.app().inst.reload()
        if errors:
            return request.jresponse({ "errors": errors })
        else:
            return request.jresponse({ "ok": 1 })

    def core_ping(self):
        request = self.req()
        response = {"ok": 1}
        try:
            response["server_id"] = self.app().inst.server_id
        except:
            pass
        return request.jresponse(response)

    def web_parse_template(self, filename, vars):
        req = self.req()
        if req.templates_parsed >= 100:
            return "<too-much-templates />"
        if req.templates_len >= 10000000:
            return "<too-long-templates />"
        req.templates_parsed = req.templates_parsed + 1
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
        self.call("web.universal_variables", vars)
        content = self.tpl.process(filename, vars)
        req.templates_len = req.templates_len + len(content)
        m = self.re_content.match(content)
        if m:
            # everything before ===HEAD=== delimiter will pass to the header
            (head, content) = m.group(1, 2)
            if vars.get("head") is None:
                vars["head"] = head
            else:
                vars["head"] = vars["head"] + head
        return content

    def web_response(self, content):
        return self.req().response(content)

    def web_response_global(self, content, vars):
        vars["content"] = content
        global_html = None
        try:
            global_html = self.req().global_html
        except:
            global_html = self.call("web.global_html")
        if global_html is None:
            global_html = "global.html"
        return self.call("web.response", self.call("web.parse_template", global_html, vars))

    def web_response_template(self, filename, vars):
        return self.call("web.response_global", self.call("web.parse_template", filename, vars), vars)

    def web_parse_layout(self, filename, vars):
        content = self.call("web.parse_template", filename, vars)
        tokens = self.re_hooks_split.split(content)
        i = 1
        while i < len(tokens):
            m = self.re_hook_parse.match(tokens[i])
            if not m:
                raise RuntimeError("'%s' could not be parsed as a hook tag" % tokens[i])
            (hook_name, hook_args) = m.group(1, 2)
            args = {}
            for key, value in self.re_hook_args.findall(hook_args):
                args[key] = value
            res = None
            try:
                res = self.call(hook_name, vars, **args)
            except BaseException, e:
                res = "file=<strong>%s</strong><br />token=<strong>%s</strong><br />error=<strong>%s</strong>" % (cgi.escape(filename), cgi.escape(tokens[i]), cgi.escape(str(e)))
            tokens[i] = str(res)
            i = i + 2
        return "".join(tokens)

    def web_parse_hook_layout(self, hook, vars):
        return self.call("web.parse_layout", self.call(hook, vars), vars)

    def web_response_layout(self, filename, vars):
        return self.call("web.response_global", self.call("web.parse_layout", filename, vars), vars)

    def web_response_hook_layout(self, hook, vars):
        return self.call("web.response_global", self.call("web.parse_hook_layout", hook, vars), vars)

