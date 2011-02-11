from mg import *
from mg.constructor.design import Design
from mg.core.auth import User
import re
import hashlib

class IndexPage(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-index.index", self.index)
        self.rhook("indexpage.error", self.error)
        self.rhook("indexpage.response_template", self.response_template)

    def index(self):
        req = self.req()
        email = req.param("email")
        if email:
            user = self.call("session.find_user", email)
            if user:
                password = req.param("password")
                m = hashlib.md5()
                m.update(user.get("salt").encode("utf-8") + password.encode("utf-8"))
                if m.hexdigest() == user.get("pass_hash"):
                    self.call("web.response", "ENTERING GAME", {})
        interface = self.conf("indexpage.design")
        if not interface:
            return self.call("indexpage.error", self._("Index page design is not configured"))
        design = self.obj(Design, interface)
        project = self.app().project
        author_name = self.conf("gameprofile.author_name")
        if not author_name:
            owner = self.main_app().obj(User, project.get("owner"))
            author_name = owner.get("name")
        vars = {
            "title": htmlescape(project.get("title_full")),
            "game": {
                "title_full": htmlescape(project.get("title_full")),
                "title_short": htmlescape(project.get("title_short")),
                "description": self.call("socio.format_text", self.conf("gameprofile.description")),
            },
            "htmlmeta": {
                "description": htmlescape(self.conf("gameprofile.indexpage_description")),
                "keywords": htmlescape(self.conf("gameprofile.indexpage_keywords")),
            },
            "year": re.sub(r'-.*', '', self.now()),
            "copyright": "Joy Team, %s" % htmlescape(author_name),
        }
        links = []
        self.call("indexpage.links", links)
        if len(links):
            links.sort(cmp=lambda x, y: cmp(x.get("order"), y.get("order")))
            links[-1]["lst"] = True
            vars["links"] = links
        self.call("design.response", design, "index.html", "", vars)

    def error(self, msg):
        vars = {
            "title": self._("Error"),
            "msg": msg,
        }
        self.call("indexpage.response_template", "constructor/index/error.html", vars)

    def response_template(self, template, vars):
        content = self.call("web.parse_template", template, vars)
        self.call("web.response_global", content, vars)
