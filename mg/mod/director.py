from mg.core import Module
import cgi

class Director(Module):
    def register(self):
        Module.register(self)
        self.rdep(["web.Web"])
        self.rhook("int-director.ready", self.ready)
        self.rhook("int-director.test", self.test)
        self.rhook("int-director.reload", self.reload)
        self.rhook("int-index.index", self.index)
        self.rhook("web.template", self.web_template, 5)
        self.app().lang = "ru"

    def test(self, args, request):
        args = cgi.escape(args)
        param = request.param('param')
        param = cgi.escape(param)
        return request.uresponse('<html><body>Director test handler: args=%s, param=%s</body></html>' % (args, param))

    def ready(self, args, request):
        return request.jresponse({ "ok": 1 })

    def reload(self, args, request):
        self.app().reload()
        return request.jresponse({ "ok": 1 })

    def web_template(self, filename, struct):
        self.call("web.set_global_html", "director/global.html")

    def index(self, args, request):
        return self.call("web.template", "director/index.html", {
            "title": self._("Welcome to the Director control center"),
            "setup": self._("Change director settings")
        })
