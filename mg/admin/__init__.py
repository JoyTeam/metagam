from mg import *
from mg.core.common import StaticUploadError
from concurrence.http import HTTPError
from concurrence import Timeout, TimeoutError
from PIL import Image
import urlparse
import cStringIO
import cgi
import random
import re
import json

re_remove_admin = re.compile(r'^admin-')
re_split_3 = re.compile(r'^([^/]+)/([^/\?]+)/([^\?]+)(?:|\?.*)$')
re_split_2 = re.compile(r'^([^/]+)/([^/\?]+)(?:|\?.*)$')
re_form_condition = re.compile(r'\[([a-z_][a-z0-9_\-]*)\]')

class AdminInterface(Module):
    def register(self):
        self.rhook("ext-admin.index", self.index, priv="logged")
        self.rhook("admin.response_js", self.response_js)
        self.rhook("admin.response_json", self.response_json)
        self.rhook("admin.response", self.response)
        self.rhook("admin.response_template", self.response_template)
        self.rhook("admin.update_menu", self.update_menu)
        self.rhook("admin.redirect", self.redirect)
        self.rhook("admin.redirect_top", self.redirect_top)
        self.rhook("hook-admin.link", self.link)
        self.rhook("hook-admin.area", self.area)
        self.rhook("admin.form", self.form)
        self.rhook("admin.advice", self.advice)
        self.rhook("ext-admin-image.upload", self.image, priv="logged")
        self.rhook("config.changed", self.config_changed)

    def config_changed(self):
        self.update_menu()

    def index(self):
        menu = self.makemenu()
        vars = {
            "menu": json.dumps(menu),
            "title": self._("Administration interface"),
            "main_host": self.main_host,
            "debug_ext": self.conf("debug.ext"),
        }
        if getattr(self.app(), "project", None):
            self.app().inst.appfactory.get_by_tag("main").hooks.call("xsolla.payment-params", vars, self.app().project.get("owner"))
        self.call("web.response_template", "admin/index.html", vars)

    def menu_compare(self, x, y):
        res = cmp(x.get("order"), y.get("order"))
        if res:
            return res
        return cmp(x.get("text"), y.get("text"))

    def sortleftmenu(self, menu):
        children = menu.get("children")
        if children is not None:
            children.sort(cmp=self.menu_compare)
            for child in children:
                self.sortleftmenu(child)

    def makemenu(self):
        leftmenu = self.leftmenunode("root.index", "Root")
        wizards = []
        self.call("wizards.call", "menu", wizards)
        if wizards:
            if not leftmenu:
                leftmenu = {"text": "Root", "children": []}
            leftmenu["children"] = wizards + leftmenu["children"]
        if not leftmenu:
            req = self.req()
            if not self.call("auth.permissions", req.user()):
                self.call("web.forbidden")
            leftmenu = []
        else:
            self.sortleftmenu(leftmenu)
        topmenu = []
        self.call("menu-admin-top.list", topmenu)
        title = self.call("project.title")
        if title is None:
            title = self.app().tag
        return {
            "left": leftmenu,
            "top": topmenu,
            "title": self._("%s administration interface") % title
        }

    def leftmenunode(self, node, text):
        menu = []
        self.call("menu-admin-%s" % node, menu)
        result = []
        for ent in menu:
            if ent.get("leaf"):
                project = getattr(self.app(), "project", None)
                if not project or not self.app().project.get("inactive"):
                    ent["href"] = "/admin#%s" % ent.get("id")
                    result.append(ent)
            else:
                submenu = self.leftmenunode(ent["id"], ent["text"])
                if submenu:
                    submenu["order"] = ent.get("order", 0)
                    result.append(submenu)
        return {"text": text, "children": result} if len(result) else None

    def headmenu(self):
        menu = []
        req = self.req()
        group = req.group
        hook = req.hook
        args = req.args
        href = "%s/%s" % (re_remove_admin.sub('', group), hook)
        if args != "":
            href = "%s/%s" % (href, args)
        first = True
        while group is not None:
            res = self.call("headmenu-%s.%s" % (group, hook), args)
            if res is None:
                break
            else:
                if type(res) == list:
                    if first:
                        menu.append({
                            "html": res[0]
                        })
                    else:
                        menu.append({
                            "html": res[0],
                            "href": href
                        })
                    if len(res) == 2:
                        href = res[1]
                        m = re_split_3.match(href)
                        if m:
                            group, hook, args = m.group(1, 2, 3)
                        else:
                            m = re_split_2.match(href)
                            if m:
                                group, hook = m.group(1, 2)
                                args = ""
                            else:
                                group = href
                                hook = "index"
                                args = ""
                        group = "admin-%s" % group
                    else:
                        break
                else:
                    if first:
                        menu.append({
                            "html": res
                        })
                    else:
                        menu.append({
                            "href": href,
                            "html": res
                        })
                    break
            first = False
        menu.reverse()
        return menu

    def response_params(self):
        return {
            "ver": self.inst.dbconfig.get("application.version", 10000),
            "success": True,
        }

    def advice(self, *args):
        req = self.req()
        try:
            req.admin_advice.extend(args)
        except AttributeError:
            req.admin_advice = list(args)

    def params_page(self, params):
        params["headmenu"] = self.headmenu()
        req = self.req()
        advice = []
        admin_advice = getattr(req, "admin_advice", None)
        if admin_advice is not None:
            advice.extend(admin_advice)
        self.call("advice-%s.%s" % (req.group, req.hook), req.args, advice)
        self.call("advice-%s.index" % req.group, req.hook, req.args, advice)
        self.call("advice.all", req.group, req.hook, req.args, advice)
        advice.sort(lambda x, y: cmp(x.get("order", 0), y.get("order", 0)))
        if len(advice):
            for adv in advice:
                adv["content"] = self.call("web.parse_inline_layout", adv["content"], {})
            advice[-1]["lst"] = True
        params["advice"] = advice

    def params_menu(self, params):
        if getattr(self.req(), "admin_update_menu", False):
            params["menu"] = self.makemenu()

    def response_js(self, script, cls, data):
        params = self.response_params()
        params["script"] = script
        params["cls"] = cls
        params["data"] = data
        self.params_page(params)
        self.params_menu(params)
        self.call("web.response_json", params)

    def response_json(self, data):
        params = self.response_params()
        for key, val in data.iteritems():
            params[key] = val
        self.params_page(params)
        self.params_menu(params)
        self.call("web.response_json", params)

    def response(self, content, vars):
        params = self.response_params()
        params["content"] = self.call("web.parse_inline_layout", content, vars)
        self.params_page(params)
        self.params_menu(params)
        self.call("web.response_json", params)

    def response_template(self, filename, vars):
        params = self.response_params()
        params["content"] = self.call("web.parse_layout", filename, vars)
        self.params_page(params)
        self.params_menu(params)
        self.call("web.response_json", params)

    def redirect(self, id, parameters=None):
        params = self.response_params()
        params["redirect"] = id
        params["success"] = True
        params["parameters"] = parameters
        self.params_menu(params)
        self.call("web.response_json", params)

    def redirect_top(self, href):
        params = self.response_params()
        params["redirect_top"] = href
        params["success"] = True
        self.call("web.response_json", params)

    def link(self, vars, href=None, title=None, confirm=None):
        if type(href) == unicode:
            href = href.encode("utf-8")
        if type(title) == unicode:
            title = title.encode("utf-8")
        onclick = "adm('%s');" % jsencode(href)
        if confirm is not None:
            onclick = "if (confirm('%s')) {%s}" % (jsencode(confirm), onclick)
        return '<a href="/admin?_nd={2}#{0}" onclick="{3}return false;">{1}</a>'.format(utf2str(htmlescape(href)), utf2str(title), random.randrange(0, 1000000000), utf2str(onclick))

    def area(self, vars, href=None, confirm=None, polygon=None):
        if type(href) == unicode:
            href = href.encode("utf-8")
        onclick = "adm('%s');" % jsencode(href)
        if confirm is not None:
            onclick = "if (confirm('%s')) {%s}" % (jsencode(confirm), onclick)
        return '<area href="/admin?_nd={1}#{0}" onclick="{2}return false;" shape="polygon" coords="{3}" />'.format(htmlescape(href), random.randrange(0, 1000000000), onclick, polygon)

    def form_condition(self, m):
        return "form_value('%s')" % m.group(1)

    def form(self, url=None, fields=None, buttons=None, title=None, modules=None, menu=None):
        if url is None:
            req = self.req()
            url = "/%s/%s/%s" % (req.group, req.hook, req.args)
        if fields is None:
            fields = []
        if buttons is None:
            buttons = [{"text": self._("Save")}]
        for field in fields:
            condition = field.get("condition")
            if condition is not None:
                field["condition"] = re_form_condition.sub(self.form_condition, condition)
        self.call("admin.response_js", "admin-form", "Form", {"url": url, "fields": fields, "buttons": buttons, "title": title, "modules": modules, "menu": menu})

    def update_menu(self):
        try:
            self.req().admin_update_menu = True
        except AttributeError:
            pass

    def image(self):
        self.call("web.upload_handler")
        req = self.req()
        url = req.param("url")
        image_field = "image"
        errors = {}
        image = req.param_raw("image")
        if not image and url:
            url_obj = urlparse.urlparse(url.encode("utf-8"), "http", False)
            if url_obj.scheme != "http":
                errors["url"] = self._("Scheme '%s' is not supported") % htmlescape(url_obj.scheme)
            elif url_obj.hostname is None:
                errors["url"] = self._("Enter correct URL")
            else:
                cnn = HTTPConnection()
                try:
                    with Timeout.push(50):
                        cnn.set_limit(20000000)
                        port = url_obj.port
                        if port is None:
                            port = 80
                        cnn.connect((url_obj.hostname, port))
                        request = cnn.get(url_obj.path + url_obj.query)
                        request.add_header("Connection", "close")
                        response = cnn.perform(request)
                        if response.status_code != 200:
                            if response.status_code == 404:
                                errors["url"] = self._("Remote server response: Resource not found")
                            elif response.status_code == 403:
                                errors["url"] = self._("Remote server response: Access denied")
                            elif response.status_code == 500:
                                errors["url"] = self._("Remote server response: Internal server error")
                            else:
                                errors["url"] = self._("Download error: %s") % htmlescape(response.status)
                        else:
                            image = response.body
                            image_field = "url"
                except TimeoutError as e:
                    errors["url"] = self._("Timeout on downloading image. Time limit - 30 sec")
                except Exception as e:
                    errors["url"] = self._("Download error: %s") % htmlescape(str(e))
                finally:
                    try:
                        cnn.close()
                    except Exception:
                        pass
        if image:
            try:
                image_obj = Image.open(cStringIO.StringIO(image))
            except IOError:
                errors[image_field] = self._("Image format not recognized")
            if not errors:
                format = image_obj.format
                if format == "GIF":
                    ext = "gif"
                    content_type = "image/gif"
                    target_format = "GIF"
                elif format == "PNG":
                    ext = "png"
                    content_type = "image/png"
                    target_format = "PNG"
                else:
                    target_format = "JPEG"
                    ext = "jpg"
                    content_type = "image/jpeg"
                if target_format != format:
                    im_data = cStringIO.StringIO()
                    image_obj.save(im_data, target_format)
                    im_data = im_data.getvalue()
                else:
                    im_data = image
                uri = self.call("cluster.static_upload", "socio", ext, content_type, im_data)
                self.call("web.response_json_html", {"success": True, "uri": uri})
        elif not errors:
            errors["image"] = self._("Upload an image")
        if errors:
            self.call("web.response_json_html", {"success": False, "errors": errors})
        else:
            self.call("web.response_json_html", {"success": False, "errmsg": self._("Unknown error uploading image")})
