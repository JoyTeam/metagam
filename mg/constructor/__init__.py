from mg.core import Module
from mg.core.tools import *
import re
import time
from cassandra.ttypes import *
import json

class Constructor(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.web.Web", "mg.socio.Socio", "mg.socio.Forum", "mg.admin.AdminInterface", "mg.socio.ForumAdmin",
            "mg.core.auth.PasswordAuthentication", "mg.core.auth.CookieSession", "mg.core.cluster.Cluster", "mg.core.auth.Authorization",
            "mg.core.emails.Email"])
        self.rhook("web.global_html", self.web_global_html)
        self.rhook("ext-index.index", self.index)
        self.rhook("ext-constructor.subscribe", self.subscribe)
        self.rhook("ext-cabinet.index", self.cabinet_index)
        self.rhook("auth.redirects", self.redirects)
        self.rhook("forum.topmenu", self.forum_topmenu)
        self.rhook("ext-cabinet.settings", self.cabinet_settings)
        self.rhook("ext-documentation.index", self.documentation_index)

    def web_global_html(self):
        return "constructor/global.html"

    def redirects(self, tbl):
        tbl["login"] = "/cabinet"
        tbl["register"] = "/constructor/newgame"

    def forum_topmenu(self, topmenu):
        req = self.req()
        redirect = urlencode(req.uri())
        if req.user():
            topmenu.append({"href": "/auth/logout?redirect=%s" % redirect, "html": self._("Log out")})
            topmenu.append({"href": "/forum/settings?redirect=%s" % redirect, "html": self._("Settings")})
            topmenu.append({"href": "/cabinet", "html": self._("Cabinet"), "left": True})
            topmenu.append({"href": "/documentation", "html": self._("Documentation"), "left": True})
        else:
            topmenu.append({"href": "/auth/login?redirect=%s" % redirect, "html": self._("Log in")})
            topmenu.append({"href": "/auth/register?redirect=%s" % redirect, "html": self._("Register")})

    def index(self):
        req = self.req()
        vars = {
            "title": self._("Constructor of browser-based online games"),
#            "blog": self._("Project blog"),
#            "forum": self._("Project forum"),
#            "subscribe": self._("Send me email on something interesting"),
#            "project_info": self._("MMO Constructor is a web application giving everyone possibility to create their own browser-based online games. Creating a game is totally free. No subscription fees. We will share your games revenue with you on 50%/50% basis."),
#            "under_construction": self._("The project is currently under construction. If you want to subscribe to the development status information leave us your e-mail"),
            "online_games_constructor": self._("Constructor of browser-based online games"),
            "games_constructor": self._("Games constructor"),
            "slogan": self._("Create the world of your dreams"),
            "login": self._("log in"),
            "register": self._("register"),
            "forum": self._("forum"),
            "cabinet": self._("cabinet"),
            "logout": self._("log out"),
        }
        if req.user():
            vars["logged"] = True
        return self.call("web.response_template", "constructor/index.html", vars)

    def subscribe(self):
        request = self.req()
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

    def cabinet_index(self):
        req = self.req()
        session = self.call("session.require_login")
        perms = req.permissions()
        menu1 = []
        menu1.append({"href": "/documentation", "image": "constructor/cab_documentation.jpg", "text": self._("Documentation")})
        if len(perms):
            menu1.append({"href": "/admin", "image": "constructor/cab_admin.jpg", "text": self._("Administration")})
        menu1.append({"href": "/forum", "image": "constructor/cab_forum.jpg", "text": self._("Forum")})
        menu2 = []
        menu2.append({"href": "/constructor/newgame", "image": "constructor/cab_newgame.jpg", "text": self._("New game")})
        vars = {
            "title": self._("Cabinet"),
            "menu": [
                menu1,
                menu2,
                [
                    { "href": "/cabinet/settings", "image": "constructor/cab_settings.jpg", "text": self._("Settings") },
                    { "href": "/auth/logout", "image": "constructor/cab_logout.jpg", "text": self._("Log out") },
                ],
            ],
        }
        self.call("web.response_template", "constructor/cabinet.html", vars)

    def cabinet_settings(self):
        session = self.call("session.require_login")
        vars = {
            "title": self._("Settings"),
            "menu": [
                [
                    { "href": "/cabinet", "image": "constructor/cab_return.jpg", "text": self._("Return to the Cabinet") },
                ],
                [
                    { "href": "/auth/change", "image": "constructor/cab_changepass.jpg", "text": self._("Change password") },
                    { "href": "/forum/settings", "image": "constructor/cab_forumsettings.jpg", "text": self._("Forum settings") },
                    { "href": "/constructor/certificate", "image": "constructor/cab_certificate.jpg", "text": self._("WebMoney Certification") },
                ],
            ],
        }
        self.call("web.response_template", "constructor/cabinet.html", vars)

    def documentation_index(self):
        session = self.call("session.require_login")
        vars = {
            "title": self._("Documentation"),
            "menu": [
                [
                    { "href": "/cabinet", "image": "constructor/cab_return.jpg", "text": self._("Return to the Cabinet") },
                ],
            ],
        }
        self.call("web.response_template", "constructor/documentation.html", vars)

