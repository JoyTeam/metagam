from mg.core import Module
import re
import time
from cassandra.ttypes import *
import json

class MainSite(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.web.Web"])
        self.rhook("web.template", self.web_template, 5)
        self.rhook("ext-index.index", self.index)
        self.rhook("ext-mainsite.subscribe", self.subscribe)

    def web_template(self, filename, struct):
        self.call("web.set_global_html", "mainsite/global.html")

    def index(self, args, request):
        params = {
            "title": self._("Constructor of browser-based online games"),
            "blog": self._("Project blog"),
            "forum": self._("Project forum"),
            "subscribe": self._("Send me email on something interesting"),
            "project_info": self._("MMO Constructor is a web application giving everyone possibility to create their own browser-based online games. Creating a game is totally free. No subscription fees. We will share your games revenue with you on 50%/50% basis."),
            "under_construction": self._("The project is currently under construction. If you want to subscribe to the development status information leave us your e-mail"),
        }
        return self.call("web.template", "mainsite/index.html", params)

    def subscribe(self, args, request):
        email = request.param("email")
        errors = {}
        if email is None or email == "":
            errors["email"] = self._("Enter your e-mail address")
        elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors["email"] = self._("Invalid e-mail format")
        if len(errors):
            return request.jresponse({"success": False, "errors": errors});
        db = self.db()
        timestamp = time.time() * 1000
        db.insert("NewsSubscriptions", ColumnParent("Core"), Column(email, json.dumps({"lang": self.call("l10n.lang")}), Clock(timestamp)), ConsistencyLevel.ONE)
        return request.jresponse({"success": True})
