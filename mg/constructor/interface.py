from mg import *
from mg.constructor.design import Design
from mg.core.auth import User
from mg.constructor.players import Player, Character, CharacterList
import re
import hashlib
import mg

class Dynamic(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-dyn-mg.indexpage.js", self.indexpage_js)
        self.rhook("ext-dyn-mg.indexpage.css", self.indexpage_css)
        self.rhook("auth.char-form-changed", self.char_form_changed)

    def indexpage_js_mcid(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        ver = self.int_app().config.get("application.version", 0)
        return "indexpage-js-%s-%s-%s" % (main_host, lang, ver)

    def char_form_changed(self):
        mcid = self.indexpage_js_mcid()
        self.app().mc.delete(mcid)

    def indexpage_js(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        mcid = self.indexpage_js_mcid()
        data = self.app().mc.get(mcid)
        if not data:
            mg_path = mg.__path__[0]
            vars = {
                "includes": [
                    "%s/../static/js/prototype.js" % mg_path,
                    "%s/../static/js/gettext.js" % mg_path,
                    "%s/../static/constructor/gettext-%s.js" % (mg_path, lang),
                ],
                "main_host": main_host
            }
            self.call("indexpage.render", vars)
            data = self.call("web.parse_template", "constructor/index/indexpage.js", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/javascript; charset=utf-8")

    def indexpage_css_mcid(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        ver = self.int_app().config.get("application.version", 0)
        return "indexpage-css-%s-%s-%s" % (main_host, lang, ver)

    def indexpage_css(self):
        main_host = self.app().inst.config["main_host"]
        mcid = self.indexpage_css_mcid()
        data = self.app().mc.get(mcid)
        if not data:
            mg_path = mg.__path__[0]
            vars = {
                "main_host": main_host
            }
            data = self.call("web.parse_template", "constructor/index/indexpage.css", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/css")

class IndexPage(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-index.index", self.index)
        self.rhook("indexpage.error", self.index_error)
        self.rhook("indexpage.response_template", self.response_template)
        self.rhook("auth.messages", self.auth_messages)

    def auth_messages(self, msg):
        msg["name_unknown"] = self._("Character not found")
        msg["user_inactive"] = self._("Character is not active. Check your e-mail and follow activation link")

    def index(self):
        req = self.req()
        session_param = req.param("session")
        if session_param:
            session = self.call("session.get")
            if session.uuid != session_param:
                self.call("web.redirect", "/")
            user = session.get("user")
            if not user:
                self.call("web.redirect", "/")
            if self.conf("auth.multicharing") or self.conf("auth.cabinet"):
                return self.game_cabinet(user)
            else:
                return self.game_interface_default_character(user)

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

    def index_error(self, msg):
        vars = {
            "title": self._("Error"),
            "msg": msg,
        }
        self.call("indexpage.response_template", "constructor/index/error.html", vars)

    def response_template(self, template, vars):
        content = self.call("web.parse_template", template, vars)
        self.call("web.response_global", content, vars)

    def game_cabinet(self, player_uuid):
        self.index_error("The cabinet is not implemented yet")

    def game_interface_default_character(self, player_uuid):
        try:
            player = self.obj(Player, player_uuid)
        except ObjectNotFoundException:
            self.index_error(self._("Missing player %s record in the database") % player_uuid)
        chars = self.objlist(CharacterList, query_index="player", query_equal=player_uuid, query_reversed=True)
        if not len(chars):
            self.call("web.redirect", "/character/create")
        return self.game_interface(chars[0].uuid)

    def game_interface(self, character_uuid):
        try:
            character = self.obj(Character, character_uuid)
        except ObjectNotFoundException:
            self.index_error(self._("Missing character %s record in the database") % character_uuid)
        project = self.app().project
        vars = {
            "title": htmlescape(project.get("title_full")),
            "global_html": "game/frameset.html"
        }
        self.call("web.response_global", "", vars)
