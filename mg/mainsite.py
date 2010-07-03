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
            "blog": self._("Project blog"),
            "project_info": self._("MMO Constructor is a web application giving everyone possibility to create their own browser-based online games. Creating a game is totally free. No subscription fees. We will share your games revenue with you on 50%/50% basis."),
            "under_construction": self._("The project is currently under construction. If you want to subscribe for development status information leave us your e-mail"),
        }
        return self.call("web.template", "mainsite/index.html", params)
