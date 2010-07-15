from mg.core import Module

class AdminInterface(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-admin.index", self.index)
        self.rhook("ext-admin.menu", self.menu)
        self.rhook("admin.response", self.response)

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

    def response(self, script, cls, data):
        req = self.req()
        return req.jresponse({
            "ver": self.call("core.ver"),
            "script": script,
            "cls": cls,
            "data": data
        })
