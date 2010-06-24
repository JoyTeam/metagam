from mg.core import Module
from template import Template
from template.provider import Provider
from concurrence import Tasklet
import mg

class Web(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.tpl = None

    def register(self):
        Module.register(self)
        self.rhook("web.template", self.web_template, -1)
        self.rhook("web.response", self.web_response, -1)
        self.rhook("web.parse_template", self.parse_template, -1)
        self.rhook("web.set_global_html", self.set_global_html, -1)

    def parse_template(self, filename, struct):
        if self.tpl is None:
            conf = {
                "INCLUDE_PATH": [ mg.__path__[0] + "/templates" ],
                "ANYCASE": True,
            }
            try:
                conf["LOAD_TEMPLATES"] = self.app().inst.tpl_provider
            except AttributeError, e:
                provider = Provider(conf)
                self.app().inst.tpl_provider = provider
                conf["LOAD_TEMPLATES"] = provider
            self.tpl = Template(conf)
        return self.tpl.process(filename, struct)

    def set_global_html(self, global_html):
        Tasklet.current().req.global_html = global_html

    def web_template(self, filename, struct):
        struct["content"] = self.call("web.parse_template", filename, struct)
        self.call("web.response", self.call("web.parse_template", Tasklet.current().req.global_html, struct))

    def web_response(self, content):
        return Tasklet.current().req.uresponse(content)
