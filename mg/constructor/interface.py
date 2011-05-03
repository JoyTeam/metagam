from mg import *
from mg.constructor import *
from mg.constructor.design import Design
from mg.constructor.players import DBPlayer, DBCharacter, DBCharacterList
import re
import hashlib
import mg

caching = False

class Dynamic(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-dyn-mg.indexpage.js", self.indexpage_js, priv="public")
        self.rhook("ext-dyn-mg.indexpage.css", self.indexpage_css, priv="public")
        self.rhook("auth.char-form-changed", self.char_form_changed)

    def indexpage_js_mcid(self):
        ver = self.int_app().config.get("application.version", 0)
        return "indexpage-js-%s" % ver

    def char_form_changed(self):
        for mcid in [self.indexpage_js_mcid(), self.indexpage_css_mcid()]:
            self.app().mc.delete(mcid)

    def indexpage_js(self):
        lang = self.call("l10n.lang")
        mcid = self.indexpage_js_mcid()
        data = self.app().mc.get(mcid)
        if not data or not caching:
            mg_path = mg.__path__[0]
            vars = {
                "includes": [
                    "%s/../static/js/prototype.js" % mg_path,
                    "%s/../static/js/gettext.js" % mg_path,
                    "%s/../static/constructor/gettext-%s.js" % (mg_path, lang),
                ],
                "game_domain": self.app().canonical_domain
            }
            self.call("indexpage.render", vars)
            data = self.call("web.parse_template", "game/indexpage.js", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/javascript; charset=utf-8")

    def indexpage_css_mcid(self):
        ver = self.int_app().config.get("application.version", 0)
        return "indexpage-css--%s" % ver

    def indexpage_css(self):
        mcid = self.indexpage_css_mcid()
        data = self.app().mc.get(mcid)
        if not data or not caching:
            mg_path = mg.__path__[0]
            vars = {
                "game_domain": self.app().canonical_domain
            }
            data = self.call("web.parse_template", "game/indexpage.css", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/css")

class Interface(ConstructorModule):
    def register(self):
        Module.register(self)
        self.rhook("ext-index.index", self.index, priv="public")
        self.rhook("game.response", self.game_response)
        self.rhook("game.response_external", self.game_response_external)
        self.rhook("game.error", self.game_error)
        self.rhook("game.form", self.game_form)
        self.rhook("auth.form", self.game_form)
        self.rhook("auth.messages", self.auth_messages)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-gameinterface.layout", self.gameinterface_layout, priv="design")
        self.rhook("ext-interface.index", self.interface_index, priv="logged")
        self.rhook("gameinterface.render", self.game_interface_render, priority=1000000000)
        self.rhook("gameinterface.gamejs", self.game_js)
        self.rhook("gameinterface.blocks", self.blocks)
        self.rhook("gamecabinet.render", self.game_cabinet_render)
        
    def auth_messages(self, msg):
        msg["name_unknown"] = self._("Character not found")
        msg["user_inactive"] = self._("Character is not active. Check your e-mail and follow activation link")

    def index(self):
        req = self.req()
        session_param = req.param("session")
        if session_param and req.environ.get("REQUEST_METHOD") == "POST":
            session = req.session()
            if session.uuid != session_param:
                self.call("web.redirect", "/")
            user = session.get("user")
            if not user:
                self.call("web.redirect", "/")
            userobj = self.obj(User, user)
            if userobj.get("name") is not None:
                character = self.character(userobj.uuid)
                return self.game_interface(character)
            else:
                player = self.player(userobj.uuid)
                return self.game_cabinet(player)
        if self.app().project.get("inactive"):
            self.call("web.redirect", "http://www.%s/cabinet" % self.app().inst.config["main_host"])
        interface = self.conf("indexpage.design")
        design = self.obj(Design, interface) if interface else None
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
            "game_domain": self.app().canonical_domain
        }
        links = []
        self.call("indexpage.links", links)
        if len(links):
            links.sort(cmp=lambda x, y: cmp(x.get("order"), y.get("order")))
            links[-1]["lst"] = True
            vars["links"] = links
        self.call("design.response", design, "index.html", "", vars)

    def game_error(self, msg):
        vars = {
            "title": self._("Error"),
        }
        self.call("game.response_external", "error.html", vars, msg)

    def game_form(self, form, vars):
        self.call("game.response_external", "form.html", vars, form.html(vars))

    def game_response(self, template, vars, content=""):
        interface = self.conf("gameinterface.design")
        if interface:
            design = self.obj(Design, interface)
        else:
            design = None
        self.call("design.response", design, template, content, vars)

    def game_response_external(self, template, vars, content=""):
        interface = self.conf("gameinterface.design")
        if interface:
            design = self.obj(Design, interface)
        else:
            design = None
        content = self.call("design.parse", design, template, content, vars)
        self.call("design.response", design, "external.html", content, vars)

    def game_cabinet(self, player):
        characters = []
        lst = self.objlist(DBCharacterList, query_index="player", query_equal=player.uuid)
        lst = self.objlist(UserList, lst.uuids())
        lst.load()
        for ent in lst:
            characters.append({
                "uuid": ent.uuid,
                "name": htmlescape(ent.get("name")),
            })
        vars = {
            "title": self._("Game cabinet"),
            "characters": characters if len(characters) else None,
            "create": self.conf("auth.multicharing"),
        }
        self.call("gamecabinet.render", vars)
        self.call("game.response_external", "cabinet.html", vars)

    def game_cabinet_render(self, vars):
        vars["SelectYourCharacter"] = self._("Select your character")
        vars["Logout"] = self._("Logout")
        vars["CreateNewCharacter"] = self._("Create a new character")

    def game_interface_render(self, character, vars, design):
        req = self.req()
        session = req.session()
        main_host = self.app().inst.config["main_host"]
        mg_path = mg.__path__[0]
        project = self.app().project
        vars["title"] = htmlescape("%s - %s" % (character.name, project.get("title_full")))
        vars["design_root"] = design.get("uri") if design else ""
        vars["main_host"] = main_host
        vars["game_domain"] = self.app().canonical_domain
        vars["layout"] = {
            "scheme": self.conf("gameinterface.layout-scheme", 1),
            "marginleft": self.conf("gameinterface.margin-left", 0),
            "marginright": self.conf("gameinterface.margin-right", 0),
            "margintop": self.conf("gameinterface.margin-top", 0),
            "marginbottom": self.conf("gameinterface.margin-bottom", 0),
        }
        vars["domain"] = req.host()
        vars["app"] = self.app().tag
        vars["js_modules"] = set(["game-interface"])
        vars["js_init"] = ["Game.setup_game_layout();"]
        vars["main_init"] = "/interface"

    def game_interface(self, character):
        # setting up design
        interface = self.conf("gameinterface.design")
        design = self.obj(Design, interface) if interface else None
        vars = {}
        self.call("gameinterface.render", character, vars, design)
        self.call("gameinterface.gamejs", character, vars, design)
        self.call("gameinterface.blocks", character, vars, design)
        req = self.req()
        session = req.session()
        self.call("stream.login", session.uuid, character.uuid)
        self.call("web.response", self.call("web.parse_template", "game/frameset.html", vars))

    def menu_design_index(self, menu):
        req = self.req()
        if req.has_access("design"):
            menu.append({"id": "gameinterface/layout", "text": self._("Game interface layout"), "leaf": True, "order": 2})

    def gameinterface_layout(self):
        req = self.req()
        if req.ok():
            config = self.app().config_updater()
            errors = {}
            # scheme
            scheme = intz(req.param("scheme"))
            if scheme < 1 or scheme > 3:
                errors["scheme"] = self._("Invalid selection")
            else:
                config.set("gameinterface.layout-scheme", scheme)
            # margin-left
            marginleft = req.param("marginleft")
            if not valid_nonnegative_int(marginleft):
                errors["marginleft"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-left", marginleft)
            # margin-right
            marginright = req.param("marginright")
            if not valid_nonnegative_int(marginright):
                errors["marginright"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-right", marginright)
            # margin-top
            margintop = req.param("margintop")
            if not valid_nonnegative_int(margintop):
                errors["margintop"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-top", margintop)
            # margin-bottom
            marginbottom = req.param("marginbottom")
            if not valid_nonnegative_int(marginbottom):
                errors["marginbottom"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-bottom", marginbottom)
            # analysing errors
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            scheme = self.conf("gameinterface.layout-scheme", 1)
            marginleft = self.conf("gameinterface.margin-left", 0)
            marginright = self.conf("gameinterface.margin-right", 0)
            margintop = self.conf("gameinterface.margin-top", 0)
            marginbottom = self.conf("gameinterface.margin-bottom", 0)
        fields = [
            {"id": "scheme0", "name": "scheme", "type": "radio", "label": self._("General layout scheme"), "value": 1, "checked": scheme == 1, "boxLabel": '<img src="/st/constructor/gameinterface/layout0.png" alt="" />' },
            {"id": "scheme1", "name": "scheme", "type": "radio", "label": "&nbsp;", "value": 2, "checked": scheme == 2, "boxLabel": '<img src="/st/constructor/gameinterface/layout1.png" alt="" />', "inline": True},
            {"id": "scheme2", "name": "scheme", "type": "radio", "label": "&nbsp;", "value": 3, "checked": scheme == 3, "boxLabel": '<img src="/st/constructor/gameinterface/layout2.png" alt="" />', "inline": True},
            {"type": "label", "label": self._("Page margins (0 - margin is disabled):")},
            {"type": "html", "html": '<img src="/st/constructor/gameinterface/margins.png" style="margin: 3px 0 5px 0" />'},
            {"name": "marginleft", "label": self._("Left"), "value": marginleft},
            {"name": "marginright", "label": self._("Right"), "value": marginright, "inline": True},
            {"name": "margintop", "label": self._("Top"), "value": margintop, "inline": True},
            {"name": "marginbottom", "label": self._("Bottom"), "value": marginbottom, "inline": True},
        ]
        self.call("admin.form", fields=fields)

    def blocks(self, character, vars, design):
        if design:
            obj = self.httpfile("%s/blocks.html" % design.get("uri"))
            vars["blocks"] = self.call("web.parse_template", obj, vars)

    def game_js(self, character, vars, design):
        req = self.req()
        session = req.session()
        # js modules
        vars["js_modules"] = [{"name": mod} for mod in vars["js_modules"]]
        if len(vars["js_modules"]):
            vars["js_modules"][-1]["lst"] = True
        vars["game_js"] = self.call("web.parse_template", "game/interface.js", vars)

    def interface_index(self):
        self.call("web.response_global", "OK", {})
