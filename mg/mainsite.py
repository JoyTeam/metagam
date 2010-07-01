from mg.core import Module

class MainSite(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.web.Web"])
        self.rhook("web.template", self.web_template, 5)
        self.rhook("ext-index.index", self.mainsite_index)

    def web_template(self, filename, struct):
        self.call("web.set_global_html", "mainsite/global.html")

    def mainsite_index(self, args, request):
        params = {
            "title": self._("Constructor of browser based online games"),
        }
        return self.call("web.template", "mainsite/index.html", params)
