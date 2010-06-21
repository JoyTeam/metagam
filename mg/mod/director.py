from mg.core import Module
import cgi

class Director(Module):
    def register(self):
        Module.register(self)
        self.rhook("web-director.test", self.test)

    def test(self, args, request):
        args = cgi.escape(args)
        param = request.param('param')
        param = cgi.escape(param)
        return request.uresponse('<html><body>Director test handler! args=%s, param=%s</body></html>' % (args, param))
