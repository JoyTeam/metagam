from concurrence import Tasklet, http
from concurrence.http import server
from mg import *
from mg.core.tools import *
from template import Template, TemplateException
from template.provider import Provider
import urlparse
import cgi
import re
import json
import socket
import mg
import mg.core.tools
import logging
import math
import traceback
import Cookie
import time
import os
import random

re_set_cookie = re.compile(r'^Set-Cookie: ', re.IGNORECASE)
re_group_hook_args = re.compile(r'^([a-z0-9\-]+)/([a-z0-9\-\.]+)(?:/(.*)|)')
re_group_something_unparsed = re.compile(r'^([a-z0-9\-]+)\/(.+)$')
re_group = re.compile(r'^[a-z0-9\-]+')
re_protocol = re.compile(r'^[a-z]+://')

class Request(object):
    "HTTP request"

    def __init__(self, environ, start_response):
        self.environ = environ
        self._start_response = start_response
        self._params_loaded = None
        self._cookies_loaded = None
        self._set_cookies = None
        self.headers = []
        self.content_type = 'text/html; charset=utf-8'
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

    def param_raw(self, key):
        "Get specific parameter (both GET and POST) not attempting to decode"
        if self._params_loaded is None:
            self.load_params()
        val = self._params.get(key)
        if val is None:
            return None
        return val[0]

    def param(self, key, default=u''):
        "Get specific parameter (both GET and POST)"
        if self._params_loaded is None:
            self.load_params()
        val = self._params.get(key)
        if val is None:
            return default
        else:
            try:
                return unicode(val[0], "utf-8")
            except UnicodeDecodeError:
                raise WebResponse(self.bad_request())

    def param_int(self, key):
        try:
            return int(self.param(key))
        except ValueError:
            return 0

    def load_cookies(self):
        self._cookies_loaded = True
        header = self.environ.get("HTTP_COOKIE")
        self._cookies = Cookie.SimpleCookie()
        if header is not None:
            self._cookies.load(header)

    def cookies(self):
        "Get cookies of the query"
        if self._cookies_loaded is None:
            self.load_cookies()
        return self._cookies

    def cookie(self, name):
        cookie = self.cookies().get(name)
        if cookie is not None:
            return cookie.value
        else:
            return None

    def set_cookie(self, name, value, **kwargs):
        if self._set_cookies is None:
            self._set_cookies = []
        cookie = Cookie.SimpleCookie()
        cookie[str(name)] = str(value)
        for key, val in kwargs.iteritems():
            cookie[name][key] = val
        self._set_cookies.append(cookie)

    def remote_addr(self):
        ip = self.environ.get("HTTP_X_REAL_IP")
        if ip is None:
            ip = self.environ.get("REMOTE_ADDR")
        return ip
            
    def host(self):
        host = self.environ.get("HTTP_X_REAL_HOST")
        if host is None:
            return None
        return host.lower()
            
    def ok(self):
        return self.param("ok")

    def uri(self):
        "Get the URI requested"
        return self.environ['PATH_INFO']

    def send_response(self, status, headers, content):
        if type(content) == unicode:
            self.content = content.encode("utf-8")
        else:
            self.content = content
        if self._set_cookies is not None:
            for cookie in self._set_cookies:
                c = re_set_cookie.sub("", str(cookie))
                headers.append(("Set-Cookie", c))
        self.start_response(status, headers)
        return [self.content]

    def bad_request(self):
        "Return 400 Bad Request"
        return self.send_response("400 Bad Request", self.headers, "<html><body><h1>400 Bad Request</h1></body></html>")

    def not_found(self):
        "Return 404 Not Found"
        return self.send_response("404 Not Found", self.headers, "<html><body><h1>404 Not Found</h1></body></html>")

    def forbidden(self):
        "Return 403 Forbidden"
        return self.send_response("403 Forbidden", self.headers, "<html><body><h1>403 Forbidden</h1></body></html>")

    def internal_server_error(self):
        "Return 500 Internal Server Error"
        return self.send_response("500 Internal Server Error", self.headers, "<html><body><h1>500 Internal Server Error</h1></body></html>")

    def not_implemented(self):
        "Return 501 Not Implemented"
        return self.send_response("501 Not Implemented", self.headers, "<html><body><h1>501 Not Implemented</h1></body></html>")

    def bad_request(self):
        "Return 400 Bad Request"
        return self.send_response("400 Bad Request", self.headers, "<html><body><h1>400 Bad Request</h1></body></html>")

    def service_unavailable(self):
        "Return 503 Service Unavailable"
        return self.send_response("503 Service Unavailable", self.headers, "<html><body><h1>503 Service Unavailable</h1></body></html>")

    def response(self, content):
        "Return HTTP response. content will be returned to the client"
        self.headers.append(('Content-type', self.content_type))
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
        if type(uri) == unicode:
            uri = uri.encode("utf-8")
        self.headers.append(('Location', uri))
        return self.send_response("302 Found", self.headers, "")

    def session(self, create=False):
        try:
            if self._session:
                return self._session
            if not create:
                return None
        except AttributeError:
            pass
        try:
            self._session = self.app.hooks.call("session.get", create)
        except AttributeError:
            self._session = None
        return self._session

    def user(self):
        try:
            return self._user
        except AttributeError:
            pass
        sess = self.session()
        if sess is None:
            self._user = None
        else:
            self._user = sess.get("user")
        return self._user

    def permissions(self):
        try:
            return self._permissions
        except AttributeError:
            pass
        self._permissions = self.app.hooks.call("auth.permissions", self.user())
        return self._permissions

    def has_access(self, key):
        perms = self.permissions()
        if perms.get(key) or perms.get("project.admin") or perms.get("global.admin"):
            return True
        return False

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
        self.active_requests = 0

    def serve(self, addr):
        "Runs a WebDaemon instance listening given port"
        try:
            self.server.serve(addr)
            self.logger.info("serving %s:%d", addr[0], addr[1])
        except Exception as err:
            self.logger.error("Listen %s:%d: %s", addr[0], addr[1], err)
            os._exit(1)

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
                os._exit(1)
        self.logger.error("Couldn't find any unused port")
        os._exit(1)

    def req(self):
        try:
            return Tasklet.current().req
        except AttributeError:
            raise RuntimeError("Module.req() called outside of a web handler")

    def new_request_obj(self, environ, start_response):
        return Request(environ, start_response)

    def request(self, environ, start_response):
        "Process single HTTP request"
        try:
            self.active_requests += 1
            request = self.new_request_obj(environ, start_response)
            Tasklet.current().req = request
            try:
                # remove doubling, leading and trailing slashes, unquote and convert to utf-8
                try:
                    uri = re.sub(r'^/*(.*?)/*$', r'\1', re.sub(r'/{2+}', '/', mg.core.tools.urldecode(request.uri())))
                except UnicodeDecodeError:
                    request.send_response("404 Not Found", request.headers, "<html><body><h1>404 Not Found</h1></body></html>")
                return self.request_uri(request, uri)
            except RuntimeError as e:
                self.logger.error(e)
                e = u"%s" % e
                try:
                    if getattr(request, "upload_handler", None):
                        return request.uresponse(htmlescape(json.dumps({"success": False, "errormsg": e})))
                except Exception as e2:
                    self.logger.exception(e2)
                if type(e) == unicode:
                    e = e.encode("utf-8")
                return request.send_response("500 Internal Server Error", request.headers, "<html><body><h1>500 Internal Server Error</h1>%s</body></html>" % htmlescape(e))
            except Exception as e:
                try:
                    self.logger.exception(e)
                except Exception as e2:
                    print "Unhandled exception: %s" % e2
                try:
                    if getattr(request, "upload_handler", None):
                        return request.uresponse(htmlescape(json.dumps({"success": False, "errormsg": "Internal Server Error"})))
                except Exception as e2:
                    self.logger.exception(e2)
                return request.internal_server_error()
        finally:
            self.active_requests -= 1

    def request_uri(self, request, uri):
        "Process HTTP request after URI was extracted, normalized and converted to utf-8"
        # /
        if uri == "":
            res = self.req_handler(request, "index", "index", "")
            if res is not None:
                return res
        # /group/hook[/args]
        m = re_group_hook_args.match(uri)
        if m:
            (group, hook, args) = m.group(1, 2, 3)
            if args is None:
                args = ""
            res = self.req_handler(request, group, hook, args)
            if res is not None:
                return res
        # /group/<SOMETHING_UNHANDLED>
        m = re_group_something_unparsed.match(uri)
        if m:
            (group, args) = m.group(1, 2)
            res = self.req_handler(request, group, "handler", args)
            if res is not None:
                return res
        # /group
        m = re_group.match(uri)
        if m:
            res = self.req_handler(request, uri, "index", "")
            if res is not None:
                return res
        return request.not_found()

    def req_handler(self, request, group, hook, args):
        "Process HTTP request with parsed URI"
        if self.app is None:
            raise RuntimeError("No applications configured. Load some payload modules")
        try:
            return self.app.http_request(request, group, hook, args)
        except Exception as e:
            self.app.hooks.call("exception.report", e)
            raise

re_remove_ver = re.compile(r'(?:/|^)ver\d*(?:-\d+)?$')

class WebApplication(Application):
    """
    WebApplication is an Application that can handle http requests
    """
    def __init__(self, inst, tag, hook_prefix="ext"):
        """
        inst - Instance object
        tag - application tag
        hook_prefix - prefix for hook names, i.e. prefix "web" means that
           URL /group/hook will be mapped to hook name web-group.hook
        """
        Application.__init__(self, inst, tag)
        self.hook_prefix = hook_prefix
        if tag == "int":
            inst.int_app = self

    def http_request(self, request, group, hook, args):
        "Process HTTP request with parsed URI: /<group>/<hook>/<args>"
        request.app = self
        request.group = group
        request.hook = hook
        request.args = re_remove_ver.sub("", args)
        try:
            self.hooks.call("web.security_check")
            res = self.hooks.call("%s-%s.%s" % (self.hook_prefix, group, hook), check_priv=True)
        except WebResponse as res:
            res = res.content
        if getattr(request, "cache", None):
            res = ["".join([str(chunk) for chunk in res])]
            self.mc.set("page%s" % urldecode(request.uri()).encode("utf-8"), res[0])
            mcid = getattr(request, "web_cache_mcid", None)
            if mcid:
                self.mc.set("page%s" % mg.core.tools.urldecode(request.uri()).encode("utf-8"), res[0])
                self.mc.set(request.web_cache_mcid, res[0])
            lock = getattr(request, "web_cache_lock", None)
            if lock:
                lock.__exit__(None, None, None)
        self.hooks.call("web.request_processed")
        return res

re_content = re.compile(r'^(.*)===HEAD===(.*)$', re.DOTALL)
re_hooks_split = re.compile(r'(<hook:[a-z0-9_-]+\.[a-z0-9_\.-]+(?:\s+[a-z0-9_-]+="[^"]*")*\s*/>|\[hook:[a-z0-9_-]+\.[a-z0-9_\.-]+(?:\s+[a-z0-9_-]+="[^"]*")*\s*\])')
re_hook_parse = re.compile(r'^(<|\[)hook:([a-z0-9_-]+\.[a-z0-9_\.-]+)((?:\s+[a-z0-9_-]+="[^"]*")*)\s*(/>|\])$')
re_hook_args = re.compile(r'\s+([a-z0-9_-]+)="([^"]*)"')

class Web(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.tpl = None
        self.last_ping = None

    def register(self):
        self.rdep(["mg.core.l10n.L10n"])
        self.rhook("int-core.ping", self.core_ping, priv="public")
        self.rhook("int-core.abort", self.core_abort, priv="public")
        self.rhook("core.check_last_ping", self.check_last_ping)
        self.rhook("int-core.reload", self.core_reload, priv="public")
        self.rhook("int-core.reload-hard", self.core_reload_hard, priv="public")
        self.rhook("int-core.appconfig", self.core_appconfig, priv="public")
        self.rhook("web.parse_template", self.web_parse_template)
        self.rhook("web.cache", self.web_cache)
        self.rhook("web.cache_invalidate", self.web_cache_invalidate)
        self.rhook("web.response", self.web_response)
        self.rhook("web.response_global", self.web_response_global)
        self.rhook("web.response_template", self.web_response_template)
        self.rhook("web.parse_layout", self.web_parse_layout)
        self.rhook("web.parse_inline_layout", self.web_parse_inline_layout)
        self.rhook("web.parse_hook_layout", self.web_parse_hook_layout)
        self.rhook("web.response_layout", self.web_response_layout)
        self.rhook("web.response_inline_layout", self.web_response_inline_layout)
        self.rhook("web.response_hook_layout", self.web_response_hook_layout)
        self.rhook("web.response_json", self.web_response_json)
        self.rhook("web.response_json_html", self.web_response_json_html)
        self.rhook("web.form", self.web_form)
        self.rhook("web.not_found", self.web_not_found)
        self.rhook("web.forbidden", self.web_forbidden)
        self.rhook("web.internal_server_error", self.web_internal_server_error)
        self.rhook("web.not_implemented", self.web_not_implemented)
        self.rhook("web.service_unavailable", self.web_service_unavailable)
        self.rhook("web.bad_request", self.web_bad_request)
        self.rhook("web.redirect", self.web_redirect)
        self.rhook("web.security_check", self.security_check)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("web.post_redirect", self.post_redirect)
        self.rhook("ext-robots.txt.index", self.robots_txt, priv="public")
        self.rhook("web.upload_handler", self.web_upload_handler)

    def web_upload_handler(self):
        self.req().upload_handler = True

    def robots_txt(self):
        req = self.req()
        disallow = []
        if self.conf("indexing.enabled", True):
            self.call("web.robots-txt", disallow)
        else:
            disallow.append("/")
        req.headers.append(('Content-type', "text/plain"))
        raise WebResponse(req.send_response("200 OK", req.headers, "User-agent: *\n%s" % "".join(["Disallow: %s\n" % line for line in disallow])))

    def objclasses_list(self, objclasses):
        objclasses["HookGroupModules"] = (HookGroupModules, HookGroupModulesList)

    def core_reload(self):
        request = self.req()
        config = request.param("config")
        if config:
            self.app().inst.config = json.loads(config)
        errors = self.app().inst.reload()
        if errors:
            self.call("web.response_json", { "errors": errors })
        else:
            self.call("core.application_reloaded")
            self.call("web.response_json", { "ok": 1 })

    def reload_hard(self):
        self.call("core.reloading_hard")
        Tasklet.sleep(2);
        for i in range(0, 60):
            active_requests = {}
            self.call("web.active_requests", active_requests)
            cnt = 0
            for val in active_requests.values():
                cnt += val
            self.debug("active_requests: %s, cnt=%d" % (active_requests, cnt))
            if cnt == 0:
                break
            Tasklet.sleep(1)
        os._exit(0)

    def core_reload_hard(self):
        try:
            if self.app().inst.reloading:
                self.call("web.response_json", { "ok": 1 })
        except AttributeError:
            pass
        self.app().inst.reloading = True
        Tasklet.new(self.reload_hard)()
        self.call("web.response_json", { "ok": 1 })

    def core_abort(self):
        os._exit(3)

    def core_ping(self):
        request = self.req()
        response = {"ok": 1}
        try:
            response["server_id"] = self.app().inst.server_id
        except AttributeError:
            pass
        self.last_ping = time.time()
        self.call("web.ping_response", response)
        self.call("web.response_json", response)

    def check_last_ping(self):
        if self.last_ping is None:
            self.last_ping = time.time()
        elif time.time() > self.last_ping + 86400:
            self.error("Director missing since %d. Exiting", self.last_ping)
            os._exit(2)

    def core_appconfig(self):
        req = self.req()
        factory = self.app().inst.appfactory
        app = factory.get_by_tag(req.args, False)
        if app:
            if app.hooks.dynamic:
                factory.remove_by_tag(req.args)
            else:
                app.reload()
        self.call("web.response_json", {"ok": 1})

    def web_parse_template(self, filename, vars, config=None):
        try:
            req = self.req()
        except AttributeError:
            req = False
        if req:
            if req.templates_parsed >= 100:
                return "<too-much-templates />"
            if req.templates_len >= 10000000:
                return "<too-long-templates />"
            req.templates_parsed = req.templates_parsed + 1
        if self.tpl and config is None:
            tpl_engine = self.tpl
        else:
            include_path = [ mg.__path__[0] + "/templates" ]
            self.call("core.template_path", include_path)
            conf = {
                "INCLUDE_PATH": include_path,
                "ANYCASE": True,
                "PRE_CHOMP": 1,
                "POST_CHOMP": 1,
                "PLUGIN_BASE": ["Unexistent"],
                "PLUGINS": {
                    "datafile": "Template::Plugin::Disabled::datafile",
                    "date": "Template::Plugin::Disabled::date",
                    "directory": "Template::Plugin::Disabled::directory",
                    "file": "Template::Plugin::Disabled::file",
                    "filter": "Template::Plugin::Disabled::filter",
                    "format": "Template::Plugin::Disabled::format",
                    "html": "Template::Plugin::Disabled::html",
                    "image": "Template::Plugin::Disabled::image",
                    "iterator": "Template::Plugin::Disabled::iterator",
                    "math_plugin": "Template::Plugin::Disabled::math_plugin",
                    "string": "Template::Plugin::Disabled::string",
                    "table": "Template::Plugin::Disabled::table",
                    "url": "Template::Plugin::Disabled::url",
                    "view": "Template::Plugin::Disabled::view",
                    "wrap": "Template::Plugin::Disabled::wrap",
                },
            }
            if config is not None:
                for key, val in config.iteritems():
                    conf[key] = val
            if config is None:
                try:
                    conf["LOAD_TEMPLATES"] = self.app().inst.tpl_provider
                except AttributeError, e:
                    provider = Provider(conf)
                    self.app().inst.tpl_provider = provider
                    conf["LOAD_TEMPLATES"] = provider
            else:
                conf["LOAD_TEMPLATES"] = Provider(conf)
            tpl_engine = Template(conf)
            if config is None:
                self.tpl = tpl_engine
        if vars.get("universal_variables") is None:
            vars["ver"] = self.int_app().config.get("application.version", 0)
            vars["universal_variables"] = True
            try:
                try:
                    vars["domain"] = self.app().canonical_domain
                except AttributeError:
                    vars["domain"] = self.app().domain
            except AttributeError:
                pass
            self.call("web.universal_variables", vars)
        if type(filename) == unicode:
            filename = filename.encode("utf-8")
        try:
            content = tpl_engine.process(filename, vars)
        except ImportError as e:
            raise TemplateException("security", unicode(e))
        if req:
            req.templates_len = req.templates_len + len(content)
        m = re_content.match(content)
        if m:
            # everything before ===HEAD=== delimiter will pass to the header
            (head, content) = m.group(1, 2)
            if vars.get("head") is None:
                vars["head"] = head
            else:
                vars["head"] = vars["head"] + head
        return content

    def web_cache(self):
        req = self.req()
        req.cache = True
        if False:
            uri = mg.core.tools.urldecode(req.uri()).encode("utf-8")
            mc = self.app().mc
            mcid_ver = "pagever%s" % uri
            ver = mc.get(mcid_ver)
            if ver is None:
                ver = random.randrange(0, 1000000000)
                mc.set(mcid_ver, ver)
            mcid = "pagecache%d%s" % (ver, uri)
            data = mc.get(mcid)
            if data is not None:
                req.cache = False
                self.call("web.response", data)
            req.web_cache_lock = self.lock([uri], patience=random.randrange(15, 25))
            req.web_cache_lock.__enter__()
            ver = mc.get(mcid_ver)
            mcid = "pagecache%d%s" % (ver, uri)
            data = mc.get(mcid)
            if data is not None:
                req.cache = False
                self.call("web.response", data)
            req.web_cache_mcid = mcid

    def web_cache_invalidate(self, uri):
        mc = self.app().mc
        #mc.incr("pagever%s" % uri)
        mc.delete("page%s" % uri)

    def web_response(self, content, content_type=None):
        if content_type is not None:
            self.req().content_type = content_type
        raise WebResponse(self.req().response(content))

    def web_response_global(self, content, vars):
        vars["content"] = content
        self.call("web.setup_design", vars)
        if vars.get("global_html"):
            self.call("web.response", self.call("web.parse_layout", vars["global_html"], vars))
        else:
            self.call("web.response", vars["content"])

    def web_response_template(self, filename, vars):
        raise WebResponse(self.call("web.response_global", self.call("web.parse_template", filename, vars), vars))

    def web_parse_layout(self, filename, vars, config=None):
        content = self.call("web.parse_template", filename, vars, config=config)
        return self.call("web.parse_inline_layout", content, vars)

    def web_parse_inline_layout(self, content, vars):
        tokens = re_hooks_split.split(content)
        i = 1
        while i < len(tokens):
            m = re_hook_parse.match(tokens[i])
            if not m:
                raise RuntimeError("'%s' could not be parsed as a hook tag" % tokens[i])
            (delimiter, hook_name, hook_args) = m.group(1, 2, 3)
            if delimiter == "<" or vars.get("allow_bracket_hooks"):
                args = {}
                for key, value in re_hook_args.findall(hook_args):
                    args[key] = mg.core.tools.htmldecode(value)
                res = None
                try:
                    res = self.call("hook-%s" % hook_name, vars, **args)
                except WebResponse:
                    raise
                except Exception as e:
                    self.error(traceback.format_exc())
                    res = htmlescape('%s %s' % (e.__class__, e))
                if res is None:
                    res = ""
                tokens[i] = res
            i = i + 2
        for i in range(0, len(tokens)):
            if type(tokens[i]) == unicode:
                tokens[i] = tokens[i].encode("utf-8")
        return "".join(tokens)

    def web_parse_hook_layout(self, hook, vars):
        return self.call("web.parse_layout", self.call(hook, vars), vars)

    def web_response_layout(self, filename, vars):
        raise WebResponse(self.call("web.response_global", self.call("web.parse_layout", filename, vars), vars))

    def web_response_inline_layout(self, content, vars):
        raise WebResponse(self.call("web.response_global", self.call("web.parse_inline_layout", content, vars), vars))

    def web_response_hook_layout(self, hook, vars):
        raise WebResponse(self.call("web.response_global", self.call("web.parse_hook_layout", hook, vars), vars))

    def web_response_json(self, data):
        req = self.req()
        if getattr(req, "upload_handler", None):
            raise WebResponse(self.req().uresponse(htmlescape(json.dumps(data))))
        else:
            raise WebResponse(self.req().jresponse(data))

    def web_response_json_html(self, data):
        raise WebResponse(self.req().uresponse(htmlescape(json.dumps(data))))

    def web_form(self, template="common/form.html", action=None):
        return WebForm(self, template, action)

    def web_forbidden(self):
        raise WebResponse(self.req().forbidden())

    def web_internal_server_error(self):
        raise WebResponse(self.req().internal_server_error())

    def web_not_implemented(self):
        raise WebResponse(self.req().not_implemented())

    def web_bad_request(self):
        raise WebResponse(self.req().bad_request())

    def web_service_unavailable(self):
        raise WebResponse(self.req().service_unavailable())

    def web_not_found(self):
        raise WebResponse(self.req().not_found())

    def web_redirect(self, uri):
        raise WebResponse(self.req().redirect(uri))

    def security_check(self):
        req = self.req()
        if req.param("ok"):
            if req.environ.get("REQUEST_METHOD") != "POST":
                self.error("Security alert: request %s with method %s", req.uri(), req.environ.get("REQUEST_METHOD"))
                req.headers.append(('Content-type', req.content_type))
                raise WebResponse(req.send_response("403 Required POST", req.headers, "<html><body><h1>403 %s</h1>%s</body></html>" % (self._("Forbidden"), self._("Security failure: POST method required"))))
            ref = req.environ.get("HTTP_REFERER")
            if ref:
                ref = re_protocol.sub('', ref)
                host = req.host()
                if host is not None:
                    required_prefix = host + "/"
                    if not ref.startswith(required_prefix):
                        self.error("Security alert: request %s to host %s from invalid referrer: %s", req.uri(), req.host(), req.environ.get("HTTP_REFERER"))
                        req.headers.append(('Content-type', req.content_type))
                        raise WebResponse(req.send_response("403 Invalid Referer", req.headers, "<html><body><h1>403 %s</h1>%s</body></html>" % (self._("Forbidden"), self._("Security failure: Valid Referer required"))))

    def post_redirect(self, uri, params={}):
        params = [u'<input type="hidden" name="%s" value="%s" />' % (htmlescape(key), htmlescape(val)) for key, val in params.iteritems()]
        content = '<html><body><form action="%s" method="post" name="autoform">%s</form><script type="text/javascript">document.autoform.submit();</script></body></html>' % (htmlescape(uri), u''.join(params))
        self.call("web.response", content)

class WebForm(object):
    """
    WebForm offers interface to create HTML forms
    """
    def __init__(self, module, template, action=None):
        self.module = module
        self.template = template
        if action is None:
            self.action = module.req().uri()
        else:
            self.action = action
        self.cols = 30
        self.textarea_cols = 80
        self.textarea_rows = 15
        self._hidden = []
        self.rows = []
        self._error = {}
        self.hidden("ok", 1)
        self.submit_created = False
        self.messages_top = None
        self.messages_bottom = None
        self.texteditors = False
        self.errors = False
        self.errors_on_top = False

    def control(self, desc, name, **kwargs):
        """
        Add a control to the form.
        name - parameter name
        desc - human-readable description (html enabled)
        inline=True - control will be appended to the last row
        """
        if kwargs.get("name") is None:
            kwargs["name"] = name
        if kwargs.get("desc") is None:
            kwargs["desc"] = desc
        err = self._error.get(name)
        if err is not None:
            kwargs["error"] = {
                "text": err
            }
            del self._error[name]
        put = False
        try:
            if kwargs.get("inline"):
                self.rows[-1]["cols"].append(kwargs)
                put = True
        except KeyError:
            pass
        if not put:
            self.rows.append({"cols": [kwargs]})
        last_row = self.rows[-1]
        last_row["width"] = int(math.floor(100 / len(last_row["cols"])))
        if kwargs.get("desc") or kwargs.get("error") or kwargs.get("element_submit"):
            last_row["show_header"] = True

    def html(self, add_vars={}):
        """
        Return cooked HTML form
        """
        if not self.submit_created:
            self.submit(None, None, self.module._("Save"))
        if self.rows:
            self.rows[0]["fst"] = True
            self.rows[-1]["lst"] = True
            for row in self.rows:
                padding_top_requested = False
                any_desc = False
                for col in row["cols"]:
                    if col.get("padding_top"):
                        padding_top_requested = True
                    if col.get("desc") or col.get("error"):
                        any_desc = True
                if padding_top_requested and not any_desc:
                    row["padding_top"] = True
                        
        vars = {
            "form_action": self.action,
            "form_hidden": self._hidden,
            "form_top": self.messages_top,
            "form_bottom": self.messages_bottom,
            "form_rows": self.rows,
            "form_cols": self.cols,
            "form_textarea_cols": self.textarea_cols,
            "form_textarea_rows": self.textarea_rows,
            "bold": self.module._("Bold"),
            "italic": self.module._("Italic"),
            "underline": self.module._("Underline"),
            "strike": self.module._("Strike"),
            "quote": self.module._("Quote"),
            "red": self.module._("Red"),
            "green": self.module._("Green"),
            "blue": self.module._("Blue"),
            "dark_green": self.module._("Dark green"),
            "magenta": self.module._("Magenta"),
            "yellow": self.module._("Yellow"),
            "orange": self.module._("Orange"),
            "image": self.module._("Image"),
            "insert_image": self.module._("Insert image"),
            "translit": self.module._("Translit"),
            "transliterate_to_russian": self.module._("Transliterate to Russian"),
            "errors_on_top": self.errors_on_top,
        }
        for k, v in add_vars.iteritems():
            vars[k] = v
        if self.texteditors:
            smiles = self.module.call("smiles.form")
            if smiles is not None:
                vars["smile_categories"] = smiles
            vars["form_texteditors"] = True
        return self.module.call("web.parse_template", self.template, vars)

    def error(self, name, text):
        """
        Mark field 'name' containing error 'text'
        """
        self.errors = True
        self._error[name] = text

    def hidden(self, name, value):
        """
        <input type="hidden" />
        """
        self._hidden.append({"name": name, "value": htmlescape(unicode(value))})

    def raw(self, desc, name, html, **kwargs):
        """
        raw html control
        """
        kwargs["html"] = html
        kwargs["element_html"] = True
        self.control(desc, name, **kwargs)

    def input(self, desc, name, value, **kwargs):
        """
        <input />
        """
        kwargs["value"] = htmlescape(value)
        kwargs["element_input"] = True
        self.control(desc, name, **kwargs)

    def select(self, desc, name, value, options, **kwargs):
        """
        <select />
        """
        kwargs["options"] = [{"value": opt.get("value", ""), "text": htmlescape(opt.get("description")), "selected": (unicode(opt.get("value", "")) == unicode(value)), "bgcolor": opt.get("bgcolor")} for opt in options]
        kwargs["element_select"] = True
        self.control(desc, name, **kwargs)

    def password(self, desc, name, value, **kwargs):
        """
        <input type="password" />
        """
        kwargs["value"] = htmlescape(value)
        kwargs["element_password"] = True
        self.control(desc, name, **kwargs)

    def checkbox(self, desc, name, value, **kwargs):
        """
        <input type="checkbox" />
        """
        kwargs["checked"] = True if value else None
        kwargs["text"] = desc
        kwargs["element_checkbox"] = True
        if kwargs.has_key("description"):
            desc = kwargs["description"]
            del kwargs["description"]
        else:
            desc = None
        self.control(desc, name, **kwargs)

    def radio(self, desc, name, this_value, value, **kwargs):
        """
        <input type="radio" />
        """
        kwargs["checked"] = True if value == this_value else None
        kwargs["text"] = desc
        kwargs["element_radio"] = True
        kwargs["value"] = htmlescape(unicode(this_value))
        if kwargs.has_key("description"):
            desc = kwargs["description"]
            del kwargs["description"]
        else:
            desc = None
        self.control(desc, name, **kwargs)

    def textarea(self, desc, name, value, **kwargs):
        """
        <textarea />
        """
        kwargs["value"] = htmlescape(value)
        kwargs["element_textarea"] = True
        self.control(desc, name, **kwargs)

    def textarea_fixed(self, desc, name, value, **kwargs):
        """
        <textarea />
        """
        kwargs["value"] = htmlescape(value)
        kwargs["element_textarea_fixed"] = True
        self.control(desc, name, **kwargs)

    def submit(self, desc, name, value, **kwargs):
        """
        <input type="submit" />
        """
        kwargs["value"] = htmlescape(value)
        if name is not None:
            kwargs["submit_name"] = name
        kwargs["element_submit"] = True
        kwargs["padding_top"] = True
        self.control(desc, name, **kwargs)
        self.submit_created = True

    def texteditor(self, desc, name, value, **kwargs):
        """
        <textarea /> with formatting buttons
        """
        kwargs["value"] = htmlescape(value)
        kwargs["attaches"] = not kwargs.get("no_attaches")
        kwargs["show_smiles"] = not kwargs.get("no_smiles")
        if kwargs.get("fixed"):
            kwargs["fixed_ok"] = True
        else:
            kwargs["fixed_not_ok"] = True
        kwargs["element_texteditor"] = True
        self.control(desc, name, **kwargs)
        self.texteditors = True

    def file(self, desc, name, **kwargs):
        kwargs["element_file"] = True
        self.control(desc, name, **kwargs)

    def add_message_top(self, html):
        """
        Write a html in the top of a form
        """
        if self.messages_top is None:
            self.messages_top = []
        self.messages_top.append(html)

    def add_message_bottom(self, html):
        """
        Write a html in the bottom of a form
        """
        if self.messages_bottom is None:
            self.messages_bottom = []
        self.messages_bottom.append(html)
