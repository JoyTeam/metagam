from mg.core import Module
import cgi
import random

class AdminInterface(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-admin.index", self.index)
        self.rhook("ext-admin.menu", self.menu)
        self.rhook("admin.response_js", self.response_js)
        self.rhook("admin.response_template", self.response_template)
        self.rhook("admin.link", self.link)
        self.rhook("admin.form", self.form)

    def index(self):
        vars = {
            "title": self._("Administration interface")
        }
        return self.call("web.response_template", "admin/index.html", vars)

    def menu(self):
        req = self.req()
        menu = []
        self.call("admin.menu-%s" % req.param("node"), menu)
        return req.jresponse(menu)

    def response_js(self, script, cls, data):
        req = self.req()
        return req.jresponse({
            "ver": self.call("core.ver"),
            "script": script,
            "cls": cls,
            "data": data
        })

    def response_template(self, filename, vars):
        req = self.req()
        req.global_html = ""
        return self.call("web.response_layout", filename, vars)

    def link(self, vars, href=None, title=None):
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
