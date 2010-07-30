from mg.core import Module
import cgi
import random
import re

class AdminInterface(Module):
    def __init__(self, app, fqn):
        Module.__init__(self, app, fqn)
        self.re_remove_admin = re.compile(r'^admin-')
        self.re_split_3 = re.compile(r'^([^/]+)/([^/]+)/(.+)$')
        self.re_split_2 = re.compile(r'^([^/]+)/([^/]+)$')

    def register(self):
        Module.register(self)
        self.rhook("ext-admin.index", self.index)
        self.rhook("ext-admin.menu", self.menu)
        self.rhook("admin.response_js", self.response_js)
        self.rhook("admin.response_template", self.response_template)
        self.rhook("hook-admin.link", self.link)
        self.rhook("admin.form", self.form)

    def index(self):
        vars = {
            "title": self._("Administration interface")
        }
        return self.call("web.response_template", "admin/index.html", vars)

    def menu(self):
        req = self.req()
        menu = []
        self.call("menu-admin-%s" % req.param("node"), menu)
        return req.jresponse(menu)

    def headmenu(self):
        menu = []
        req = self.req()
        group = req.group
        hook = req.hook
        args = req.args
        href = "%s/%s" % (self.re_remove_admin.sub('', group), hook)
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
                        m = self.re_split_3.match(href)
                        if m:
                            group, hook, args = m.group(1, 2, 3)
                        else:
                            m = self.re_split_2.match(href)
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
        return " &bull; ".join(reversed(menu))

    def response_js(self, script, cls, data):
        req = self.req()
        return req.jresponse({
            "ver": self.call("core.ver"),
            "script": script,
            "cls": cls,
            "data": data,
            "headmenu": self.headmenu()
        })

    def response_template(self, filename, vars):
        req = self.req()
        req.global_html = "admin/response.html"
        vars["headmenu"] = self.headmenu()
        return self.call("web.response_layout", filename, vars)

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
        return self.call("admin.response_js", "admin/form.js", "Form", {"url": url, "fields": fields, "buttons": buttons})
