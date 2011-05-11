from mg import *
import cgi
import random
import re
import json

re_remove_admin = re.compile(r'^admin-')
re_split_3 = re.compile(r'^([^/]+)/([^/]+)/(.+)$')
re_split_2 = re.compile(r'^([^/]+)/([^/]+)$')
re_form_condition = re.compile(r'\[([a-z_][a-z0-9_\-]*)\]')

class AdminInterface(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-admin.index", self.index, priv="logged")
        self.rhook("admin.response_js", self.response_js)
        self.rhook("admin.response_json", self.response_json)
        self.rhook("admin.response", self.response)
        self.rhook("admin.response_template", self.response_template)
        self.rhook("admin.update_menu", self.update_menu)
        self.rhook("admin.redirect", self.redirect)
        self.rhook("admin.redirect_top", self.redirect_top)
        self.rhook("hook-admin.link", self.link)
        self.rhook("admin.form", self.form)
        self.rhook("admin.advice", self.advice)

    def index(self):
        menu = self.makemenu()
        vars = {
            "menu": json.dumps(menu),
            "title": self._("Administration interface"),
            "main_host": self.app().inst.config["main_host"],
        }
        if getattr(self.app(), "project", None):
            self.app().inst.appfactory.get_by_tag("main").hooks.call("2pay.payment-params", vars, self.app().project.get("owner"))
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
            if not req.has_access("project.admin"):
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
                #menu.append(htmlescape("headmenu-%s.%s" % (group, hook)))
                break
            else:
                if type(res) == list:
                    if first:
                        if type(res[0]) == unicode:
                            menu.append(res[0].encode("utf-8"))
                        else:
                            menu.append(res[0])
                    else:
                        menu.append(self.link([], href, res[0]))
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
                        if type(res) == unicode:
                            menu.append(res.encode("utf-8"))
                        else:
                            menu.append(res)
                    else:
                        menu.append(self.link([], href, res))
                    break
            first = False
        menu.reverse()
        return " / ".join(menu)

    def response_params(self):
        return {
            "ver": self.int_app().config.get("application.version", 0),
            "success": True,
        }

    def advice(self, *args):
        req = self.req()
        try:
            req.admin_advice.extend(args)
        except AttributeError:
            req.admin_advice = args

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

    def redirect(self, id):
        params = self.response_params()
        params["redirect"] = id
        params["success"] = True
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
        return '<a href="/admin?_nd={2}#{0}" onclick="{3}return false;">{1}</a>'.format(htmlescape(href), title, random.randrange(0, 1000000000), onclick)

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
