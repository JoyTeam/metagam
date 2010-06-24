from mg.core import Module
import cgi

class Director(Module):
    def register(self):
        Module.register(self)
        self.rhook("int-director.ready", self.ready)
        self.rhook("int-director.test", self.test)
        self.rhook("int-director.reload", self.reload)

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
