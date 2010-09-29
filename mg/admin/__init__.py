from mg.core import Module
import cgi
import random
import re
import json

re_remove_admin = re.compile(r'^admin-')
re_split_3 = re.compile(r'^([^/]+)/([^/]+)/(.+)$')
re_split_2 = re.compile(r'^([^/]+)/([^/]+)$')

class AdminInterface(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-admin.index", self.index)
        self.rhook("admin.response_js", self.response_js)
        self.rhook("admin.response", self.response)
        self.rhook("admin.response_template", self.response_template)
        self.rhook("hook-admin.link", self.link)
        self.rhook("admin.form", self.form)

    def index(self):
        menu = self.makemenu("root.index", "Root")
        if not menu:
            self.call("web.forbidden")
        vars = {
            "menu": json.dumps(menu),
            "title": self._("Administration interface"),
        }
        self.call("web.response_template", "admin/index.html", vars)

    def makemenu(self, node, text):
        menu = []
        self.call("menu-admin-%s" % node, menu)
        result = []
        for ent in menu:
            if ent.get("leaf"):
                result.append(ent)
            else:
                submenu = self.makemenu(ent["id"], ent["text"])
                if submenu:
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
                menu.append(cgi.escape("headmenu-%s.%s" % (group, hook)))
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
        return " &bull; ".join(menu)

    def response_js(self, script, cls, data):
        req = self.req()
        self.call("web.response_json", {
            "ver": self.call("core.ver"),
            "script": script,
            "cls": cls,
            "data": data,
            "headmenu": self.headmenu()
        })

    def response(self, content, vars):
        req = self.req()
        req.global_html = "admin/response.html"
        vars["headmenu"] = self.headmenu()
        self.call("web.response_inline_layout", content, vars)

    def response_template(self, filename, vars):
        req = self.req()
        req.global_html = "admin/response.html"
        vars["headmenu"] = self.headmenu()
        self.call("web.response_layout", filename, vars)

    def link(self, vars, href=None, title=None):
        if type(href) == unicode:
            href = href.encode("utf-8")
        if type(title) == unicode:
            title = title.encode("utf-8")
        return '<a href="/admin?_nd={2}#{0}" onclick="adm(\'{0}\');return false;">{1}</a>'.format(cgi.escape(href), cgi.escape(title), random.randrange(0, 1000000000))

    def form(self, url=None, fields=None, buttons=None):
        if url is None:
            req = self.req()
            url = "/%s/%s/%s" % (req.group, req.hook, req.args)
        if fields is None:
            fields = []
        if buttons is None:
            buttons = [{"text": self._("Save")}]
        self.call("admin.response_js", "admin/form.js", "Form", {"url": url, "fields": fields, "buttons": buttons})
