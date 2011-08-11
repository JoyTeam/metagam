from mg import *
from mg.constructor import *
from mg.constructor.design import Design
from mg.constructor.players import DBPlayer, DBCharacter, DBCharacterList
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
import cStringIO
import re
import hashlib
import mg
from uuid import uuid4
from interface_classes import *

caching = False

re_block_del = re.compile('^del\/(\S+)\/(\S+)$')
re_block_edit = re.compile('^(\S+)\/(\S+)$')
re_del = re.compile('^del\/(\S+)$')
re_valid_class = re.compile('^[a-z][a-z0-9\-]*[a-z0-9]$')

default_icons = set([])

class DBFirstVisit(CassandraObject):
    _indexes = {
        "all": [[]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "FirstVisit-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBFirstVisit._indexes

class DBFirstVisitList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "FirstVisit-"
        kwargs["cls"] = DBFirstVisit
        CassandraObjectList.__init__(self, *args, **kwargs)

class Dynamic(Module):
    def register(self):
        self.rhook("ext-dyn-mg.indexpage.js", self.indexpage_js, priv="public")
        self.rhook("ext-dyn-mg.indexpage.css", self.indexpage_css, priv="public")
        self.rhook("auth.char-form-changed", self.invalidate)
        self.rhook("project.published", self.invalidate)
        self.rhook("project.unpublished", self.invalidate)
        self.rhook("project.opened", self.invalidate)
        self.rhook("project.closed", self.invalidate)

    def indexpage_js_mcid(self):
        ver = self.int_app().config.get("application.version", 0)
        return "indexpage-js-%s" % ver

    def invalidate(self):
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
                "game_domain": self.app().canonical_domain,
                "closed": self.conf("auth.closed"),
                "close_message": jsencode(htmlescape(self.conf("auth.close-message") or self._("Game is closed for non-authorized users"))),
                "published": self.app().project.get("published"),
                "NotPublished": self._("Registration in this game is disabled yet. To allow new players to register the game must be sent to moderation first."),
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
        self.rhook("ext-index.index", self.index, priv="public")
        self.rhook("game.response", self.game_response)
        self.rhook("game.response_external", self.game_response_external)
        self.rhook("game.response_internal", self.game_response_internal)
        self.rhook("game.info", self.game_info)
        self.rhook("game.error", self.game_error)
        self.rhook("game.internal_form", self.game_internal_form)
        self.rhook("game.external_form", self.game_external_form)
        self.rhook("auth.form", self.game_external_form)
        self.rhook("auth.messages", self.auth_messages)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-gameinterface.index", self.menu_gameinterface_index)
        self.rhook("ext-admin-gameinterface.layout", self.gameinterface_layout, priv="design")
        self.rhook("headmenu-admin-gameinterface.panels", self.headmenu_panels)
        self.rhook("ext-admin-gameinterface.panels", self.gameinterface_panels, priv="design")
        self.rhook("headmenu-admin-gameinterface.popups", self.headmenu_popups)
        self.rhook("ext-admin-gameinterface.popups", self.gameinterface_popups, priv="design")
        self.rhook("headmenu-admin-gameinterface.blocks", self.headmenu_blocks)
        self.rhook("ext-admin-gameinterface.blocks", self.gameinterface_blocks, priv="design")
        self.rhook("headmenu-admin-gameinterface.buttons", self.headmenu_buttons)
        self.rhook("ext-admin-gameinterface.buttons", self.admin_gameinterface_buttons, priv="design")
        self.rhook("ext-interface.settings", self.settings, priv="logged")
        self.rhook("ext-project.status", self.project_status, priv="logged")
        self.rhook("gameinterface.render", self.game_interface_render, priority=1000000000)
        self.rhook("gameinterface.gamejs", self.game_js)
        self.rhook("gameinterface.blocks", self.blocks)
        self.rhook("gamecabinet.render", self.game_cabinet_render)
        self.rhook("main-frame.error", self.main_frame_error)
        self.rhook("main-frame.info", self.main_frame_info)
        self.rhook("main-frame.form", self.main_frame_form)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-empty.index", self.empty, priv="logged")
        self.rhook("sociointerface.buttons", self.buttons)
        self.rhook("advice-admin-gameinterface.index", self.advice_gameinterface)

    def advice_gameinterface(self, hook, args, advice):
        advice.append({"title": self._("Game interface structure"), "content": self._('You can find detailed information on the game interface rendering in the <a href="http://%s/doc/design/gameinterface-structure" target="_blank">game interface structure documentation</a>.') % self.app().inst.config["main_host"]})

    def buttons(self, buttons):
        buttons.append({
            "id": "forum-game",
            "href": "/",
            "title": self._("Game"),
            "target": "_self",
            "block": "forum",
            "order": -10,
            "left": True,
        })
        buttons.append({
            "id": "forum-search",
            "search": True,
            "title": self._("Search"),
            "block": "forum",
            "order": -10,
        })
        buttons.append({
            "id": "library-game",
            "href": "/",
            "title": self._("Game"),
            "target": "_self",
            "block": "library",
            "order": -10,
            "left": True,
        })

    def empty(self):
        self.call("game.response_internal", "empty.html", {})

    def objclasses_list(self, objclasses):
        objclasses["CharacterSettings"] = (DBCharacterSettings, DBCharacterSettingsList)
        objclasses["Popup"] = (DBPopup, DBPopupList)
        objclasses["FirstVisit"] = (DBFirstVisit, DBFirstVisitList)

    def auth_messages(self, msg):
        msg["name_unknown"] = self._("Character not found")
        msg["user_inactive"] = self._("Character is not active. Check your e-mail and follow activation link")

    def index(self):
        req = self.req()
        session = req.session()
        if not session:
            obj = self.obj(DBFirstVisit, req.remote_addr(), silent=True)
            obj.touch()
            obj.store()
        session_param = req.param("session")
        if session_param and req.environ.get("REQUEST_METHOD") == "POST":
            if not session or session.uuid != session_param:
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
        design = self.design("indexpage")
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

    def main_frame_info(self, msg):
        vars = {
        }
        self.call("game.response_internal", "info.html", vars, msg)

    def main_frame_error(self, msg):
        vars = {
        }
        self.call("game.response_internal", "error.html", vars, msg)

    def game_info(self, msg, vars=None):
        if vars is None:
            vars = {}
        if not vars.get("title"):
            vars["title"] = self._("Info")
        self.call("game.response_external", "info.html", vars, msg)

    def game_error(self, msg):
        vars = {
            "title": self._("Error"),
        }
        self.call("game.response_external", "error.html", vars, msg)

    def game_internal_form(self, form, vars):
        self.call("game.response_internal", "form.html", vars, form.html(vars))

    def game_external_form(self, form, vars):
        self.call("game.response_external", "form.html", vars, form.html(vars))

    def main_frame_form(self, form, vars):
        self.call("game.response_internal", "form.html", vars, form.html(vars))

    def game_response(self, template, vars, content=""):
        design = self.design("gameinterface")
        self.call("design.response", design, template, content, vars)

    def game_response_external(self, template, vars, content=""):
        design = self.design("gameinterface")
        content = self.call("design.parse", design, template, content, vars)
        self.call("design.response", design, "external.html", content, vars)

    def game_response_internal(self, template, vars, content=""):
        design = self.design("gameinterface")
        content = self.call("design.parse", design, template, content, vars)
        self.call("design.response", design, "internal.html", content, vars)

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
        vars["character"] = character.uuid
        vars["layout"] = {
            "scheme": self.conf("gameinterface.layout-scheme", 1),
            "marginleft": self.conf("gameinterface.margin-left", 0),
            "marginright": self.conf("gameinterface.margin-right", 0),
            "margintop": self.conf("gameinterface.margin-top", 0),
            "marginbottom": self.conf("gameinterface.margin-bottom", 0),
            "panel_top": self.conf("gameinterface.panel-top", True),
            "panel_main_left": self.conf("gameinterface.panel-main-left", True),
            "panel_main_right": self.conf("gameinterface.panel-main-right", False),
        }
        vars["domain"] = req.host()
        vars["app"] = self.app().tag
        vars["js_modules"] = set(["game-interface"])
        vars["js_init"] = ["Game.setup_game_layout();"]
        vars["send"] = self._("send")
        if project.get("published"):
            vars["main_init"] = "/location"
        else:
            vars["main_init"] = "/project/status"
        if self.conf("debug.ext"):
            vars["debug_ext"] = True
        # Rendering buttons
        generated = set([btn["id"] for btn in self.generated_buttons()])
        layout = self.buttons_layout()
        # Rendering panels
        globs = {"char": character}
        panels = []
        for panel in self.panels():
            rblocks = []
            for block in panel["blocks"]:
                html = block.get("html")
                if html:
                    html = self.call("web.parse_inline_layout", html, {})
                rblock = {
                    "id": block["id"],
                    "tp": block["type"],
                    "width": block.get("width"),
                    "flex": block.get("flex"),
                    "html": jsencode(html),
                    "cls": jsencode(block.get("class")),
                }
                if block["type"] == "buttons":
                    buttons = []
                    btn_list = layout.get(block["id"])
                    if btn_list:
                        for btn in btn_list:
                            rbtn = self.render_button(btn, layout, design, generated, block.get("class"), globs=globs)
                            if rbtn:
                                buttons.append(rbtn)
                    if buttons:
                        buttons[-1]["lst"] = True
                    rblock["buttons"] = buttons
                    if design and "%s-left.png" % block.get("class") in design.get("files"):
                        rblock["buttons_left"] = True
                    if design and "%s-right.png" % block.get("class") in design.get("files"):
                        rblock["buttons_right"] = True
                    if design and "%s-top.png" % block.get("class") in design.get("files"):
                        rblock["buttons_top"] = True
                    if design and "%s-bottom.png" % block.get("class") in design.get("files"):
                        rblock["buttons_bottom"] = True
                elif block["type"] == "progress":
                    progress_types = [{"id": jsencode(pt)} for pt in block.get("progress_types", [])]
                    if progress_types:
                        progress_types[-1]["lst"] = True
                    rblock["progress_types"] = progress_types
                rblocks.append(rblock)
            if rblocks:
                rblocks[-1]["lst"] = True
            rpanel = {
                "id": panel["id"],
                "blocks": rblocks
            }
            panels.append(rpanel)
        if panels:
            panels[-1]["lst"] = True
            vars["panels"] = panels
        # Rendering popups
        globs = {"char": character}
        lst = self.objlist(DBPopupList, query_index="all")
        lst.load()
        popups = []
        for popup in lst:
            rpopup = {
                "id": popup.uuid
            }
            buttons = []
            btn_list = layout.get(popup.uuid)
            if btn_list:
                for btn in btn_list:
                    rbtn = self.render_button(btn, layout, design, generated, None, globs=globs)
                    if rbtn:
                        buttons.append(rbtn)
            if buttons:
                buttons[-1]["lst"] = True
            rpopup["buttons"] = buttons
            popups.append(rpopup)
        if popups:
            popups[-1]["lst"] = True
            vars["popups"] = popups

    def render_button(self, btn, layout, design, generated, cls, globs):
        try:
            if btn.get("condition") and not self.call("script.evaluate-expression", btn["condition"], globs, description=self._("Game interface menu")):
                return None
            title = self.call("script.evaluate-text", btn["title"], globs, description=self._("Game interface menu")) if btn.get("title") else None
        except ScriptError as e:
            self.call("exception.report", e)
            return None
        # Primary image
        image = btn.get("image")
        if not image.startswith("http://"):
            # If some module is disabled we should hide
            # all its buttons
            if btn["id"] not in generated:
                return None
            if design and image in design.get("files"):
                image = "%s/%s" % (design.get("uri"), image)
            elif design and cls and btn.get("icon"):
                if self.call("design.prepare_button", design, image, "%s-bg.png" % cls, btn["icon"], over="%s-over.png" % cls):
                    image = "%s/%s" % (design.get("uri"), image)
                else:
                    image = "/st/icons/%s" % btn["icon"]
            elif not design and btn.get("icon") and btn["icon"] in default_icons:
                image = "/st-mg/game/default-interface/%s" % btn["icon"]
            elif btn.get("icon"):
                image = "/st/icons/%s" % btn["icon"]
            else:
                image = "/st/game/invalid.png"
        rbtn = {
            "id": btn["id"],
            "image": image,
            "title": jsencode(htmlescape(title)),
            "popup": jsencode(btn.get("popup")),
        }
        # Secondary image
        image = btn.get("icon2")
        if image:
            if design and image in design.get("files"):
                image = "%s/%s" % (design.get("uri"), image)
            elif design and cls:
                if self.call("design.prepare_button", design, image, "%s-bg.png" % cls, image, over="%s-over.png" % cls):
                    image = "%s/%s" % (design.get("uri"), image)
                else:
                    image = "/st/icons/%s" % image
            elif not design and image in default_icons:
                image = "/st-mg/game/default-interface/%s" % image
            else:
                image = "/st/icons/%s" % image
            rbtn["image2"] = image
        # Button actions
        if btn.get("onclick"):
            rbtn["onclick"] = jsencode(htmlescape(btn.get("onclick")))
        elif btn.get("href"):
            if btn["target"] == "main":
                rbtn["onclick"] = jsencode(htmlescape("Game.main_open('%s')" % jsencode(btn.get("href"))))
            else:
                rbtn["href"] = jsencode(htmlescape(btn.get("href")))
                rbtn["target"] = jsencode(htmlescape(btn.get("target")))
        return rbtn

    def game_interface(self, character):
        design = self.design("gameinterface")
        vars = {}
        self.call("gameinterface.render", character, vars, design)
        self.call("gameinterface.gamejs", character, vars, design)
        self.call("gameinterface.blocks", character, vars, design)
        req = self.req()
        session = req.session()
        self.call("stream.login", session.uuid, character.uuid)
        self.call("web.response", self.call("web.parse_template", "game/frameset.html", vars))

    def menu_root_index(self, menu):
        menu.append({"id": "indexpage.index", "text": self._("Index page"), "order": 10})
        menu.append({"id": "gameinterface.index", "text": self._("Game interface"), "order": 13})

    def menu_gameinterface_index(self, menu):
        req = self.req()
        if req.has_access("design"):
            menu.append({"id": "gameinterface/layout", "text": self._("Layout scheme"), "leaf": True, "order": 4})
            menu.append({"id": "gameinterface/panels", "text": self._("Interface panels"), "leaf": True, "order": 7})
            menu.append({"id": "gameinterface/popups", "text": self._("Popup menus"), "leaf": True, "order": 10})
            menu.append({"id": "gameinterface/buttons", "text": self._("Buttons editor"), "leaf": True, "order": 12})

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
            config.set("debug.ext", True if req.param("debug_ext") else False)
            # panels
            config.set("gameinterface.panel-top", True if req.param("panel_top") else False)
            config.set("gameinterface.panel-main-left", True if req.param("panel_main_left") else False)
            config.set("gameinterface.panel-main-right", True if req.param("panel_main_right") else False)
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
            debug_ext = self.conf("debug.ext")
            panel_top = self.conf("gameinterface.panel-top", True)
            panel_main_left = self.conf("gameinterface.panel-main-left", True)
            panel_main_right = self.conf("gameinterface.panel-main-right", False)
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
            {"name": "debug_ext", "type": "checkbox", "label": self._("Debugging version of ExtJS (for advanced JavaScript programming)"), "checked": debug_ext},
            {"name": "panel_top", "type": "checkbox", "label": self._("Enable panel on the top of the screen (code 'top')"), "checked": panel_top},
            {"name": "panel_main_left", "type": "checkbox", "label": self._("Enable panel to the left of the main frame (code 'main-left')"), "checked": panel_main_left},
            {"name": "panel_main_right", "type": "checkbox", "label": self._("Enable panel to the right of the main frame (code 'main-right')"), "checked": panel_main_right},
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

    def panels(self):
        panels = []
        if self.conf("gameinterface.panel-top", True):
            panels.append({
                "id": "top",
                "title": self._("Top panel"),
                "order": 1,
            })
        if self.conf("gameinterface.panel-main-left", True):
            panels.append({
                "id": "main-left",
                "title": self._("Left of the main frame"),
                "vert": True,
                "order": 2,
            })
        if self.conf("gameinterface.panel-main-right", False):
            panels.append({
                "id": "main-right",
                "title": self._("Right of the main frame"),
                "vert": True,
                "order": 3,
            })
        if self.conf("gameinterface.panel-top", True):
            panels.append({
                "id": "roster-buttons",
                "title": self._("Roster buttons panel"),
                "order": 4,
            })
        for panel in panels:
            panel["blocks"] = self.panel_blocks(panel["id"])
            panel["blocks"].sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
        return panels

    def panel_blocks(self, panel_id):
        blocks = self.conf("gameinterface.blocks-%s" % panel_id)
        if blocks is not None:
            return blocks
        blocks = []
        if panel_id == "top":
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 0,
                "width": 90,
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "header",
                "html": self._('You are in the <hook:location.name />'),
                "order": 20,
                "flex": 1,
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 40,
                "width": 10,
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "progress",
                "progress_types": ["location-movement"],
                "order": 60,
                "flex": 1,
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 80,
                "width": 10,
            })
            blocks.append({
                "id": "top-menu",
                "type": "buttons",
                "order": 100,
                "title": self._("Top menu"),
                "class": "horizontal",
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 120,
                "width": 10,
            })
        elif panel_id == "roster-buttons":
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 0,
                "flex": 1,
            })
            blocks.append({
                "id": "roster-buttons-menu",
                "type": "buttons",
                "order": 10,
                "title": self._("Roster buttons"),
                "class": "roster-buttons",
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 100,
                "flex": 1,
            })
        elif panel_id == "main-left":
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 0,
                "flex": 1,
            })
            blocks.append({
                "id": "left-menu",
                "type": "buttons",
                "order": 10,
                "title": self._("Left menu"),
                "class": "vertical",
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 100,
                "flex": 1,
            })
        elif panel_id == "main-right":
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 0,
                "flex": 1,
            })
            blocks.append({
                "id": "right-menu",
                "type": "buttons",
                "order": 10,
                "title": self._("Right menu"),
                "class": "vertical",
            })
            blocks.append({
                "id": uuid4().hex,
                "type": "empty",
                "order": 100,
                "flex": 1,
            })
        config = self.app().config_updater()
        config.set("gameinterface.blocks-%s" % panel_id, blocks)
        config.store()
        return blocks

    def gameinterface_panels(self):
        vars = {
            "NewPanel": self._("New panel"),
            "Code": self._("Code"),
            "Title": self._("Title"),
            "Editing": self._("Editing"),
            "edit": self._("edit"),
        }
        panels = []
        for panel in self.panels():
            panels.append({
                "id": panel["id"],
                "title": panel["title"],
            })
        vars["panels"] = panels
        self.call("admin.response_template", "admin/gameinterface/panels.html", vars)

    def headmenu_panels(self, args):
        return self._("Panels")

    def gameinterface_blocks(self):
        req = self.req()
        # delete panel
        m = re_block_del.match(req.args)
        if m:
            panel_id, block_id = m.group(1, 2)
            for p in self.panels():
                if p["id"] == panel_id:
                    blocks = [blk for blk in p["blocks"] if blk["id"] != block_id]
                    config = self.app().config_updater()
                    config.set("gameinterface.blocks-%s" % panel_id, blocks)
                    config.store()
                    self.call("admin.redirect", "gameinterface/blocks/%s" % panel_id)
            self.call("admin.redirect", "gameinterface/panels")
        # edit panel
        m = re_block_edit.match(req.args)
        if m:
            panel_id, block_id = m.group(1, 2)
            panel = None
            block = None
            for panel in self.panels():
                if panel["id"] == panel_id:
                    if block_id == "new":
                        return self.block_editor(panel, None)
                    for block in panel["blocks"]:
                        if block["id"] == block_id:
                            return self.block_editor(panel, block)
                    self.call("admin.redirect", "gameinterface/blocks/%s" % panel_id)
            self.call("admin.redirect", "gameinterface/panels")
        # list of panels
        panel = None
        for p in self.panels():
            if p["id"] == req.args:
                panel = p
                break
        if not panel:
            self.call("admin.redirect", "gameinterface/panels")
        vars = {
            "NewBlock": self._("New block"),
            "ButtonsEditor": self._("Go to the buttons editor"),
            "Type": self._("Type"),
            "Width": self._("Height") if panel.get("vert") else self._("Width"),
            "Order": self._("Order"),
            "Editing": self._("Editing"),
            "Deletion": self._("Deletion"),
            "Title": self._("Title"),
            "edit": self._("edit"),
            "delete": self._("delete"),
            "ConfirmDelete": self._("Are you sure want to delete this block?"),
            "panel": req.args,
        }
        types = {
            "buttons": self._("Buttons"),
            "empty": self._("Empty space"),
            "html": self._("Raw HTML"),
            "header": self._("Header"),
            "progress": self._("Progress bar"),
        }
        blocks = []
        for block in panel["blocks"]:
            blk = {
                "id": block["id"],
                "type": types.get(block["type"]) or block["type"],
                "order": block["order"],
                "title": htmlescape(block.get("title")),
            }
            if block.get("width"):
                blk["width"] = "%s px" % block["width"]
            elif block.get("flex"):
                blk["width"] = "flex=%s" % block["flex"]
            elif block["type"] == "buttons":
                blk["width"] = self._("auto") 
            blocks.append(blk)
        vars["blocks"] = blocks
        self.call("admin.response_template", "admin/gameinterface/blocks.html", vars)

    def headmenu_blocks(self, args):
        m = re_block_edit.match(args)
        if m:
            panel_id, block_id = m.group(1, 2)
            if block_id == "new":
                return [self._("New block"), "gameinterface/blocks/%s" % panel_id]
            else:
                for panel in self.panels():
                    if panel["id"] == panel_id:
                        for blk in panel["blocks"]:
                            if blk["id"] == block_id:
                                return [blk.get("title") or blk.get("id"), "gameinterface/blocks/%s" % panel_id]
                return [self._("Block %s") % block_id, "gameinterface/blocks/%s" % panel_id]
        for panel in self.panels():
            if panel["id"] == args:
                return [panel["title"], "gameinterface/panels"]
        return [htmlescape(args), "gameinterface/panels"]

    def block_editor(self, panel, block):
        req = self.req()
        if req.ok():
            if block:
                block = {
                    "id": block["id"],
                    "type": block["type"],
                }
            else:
                block = {
                    "id": uuid4().hex,
                    "type": req.param("v_type"),
                }
            errors = {}
            if block["type"] == "buttons":
                if not req.param("title"):
                    errors["title"] = self._("Specify block title")
            else:
                width_type = req.param("v_width_type")
                if width_type == "static":
                    width_static = req.param("width_static")
                    if not valid_nonnegative_int(width_static):
                        errors["width_static"] = self._("Invalid value")
                    else:
                        block["width"] = intz(width_static)
                elif width_type == "flex":
                    width_flex = req.param("width_flex")
                    if not valid_nonnegative_int(width_flex):
                        errors["width_flex"] = self._("Invalid value")
                    else:
                        block["flex"] = intz(width_flex)
                else:
                    errors["v_width_type"] = self._("Select valid type")
            if block["type"] == "html" or block["type"] == "header":
                block["html"] = req.param("html")
            if block["type"] == "progress":
                block["progress_types"] = [s.strip() for s in req.param("progress_types").strip().split(",")]
            block["order"] = intz(req.param("order"))
            block["title"] = req.param("title")
            cls = req.param("class")
            if not cls:
                if block["type"] == "buttons":
                    errors["class"] = self._("Specify CSS class")
            elif not re_valid_class.match(cls):
                errors["class"] = self._("Class name must begin with a symbol a-z, continue with symbols a-z, 0-9 and '-' and end with a symbol a-z or a digit")
            else:
                block["class"] = cls
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            # Deleting old block and adding new block to the end
            blocks = [blk for blk in panel["blocks"] if blk["id"] != block["id"]]
            blocks.append(block)
            config = self.app().config_updater()
            config.set("gameinterface.blocks-%s" % panel["id"], blocks)
            config.store()
            self.call("admin.redirect", "gameinterface/blocks/%s" % panel["id"])
        else:
            width_type = "static"
            width_static = 30
            width_flex = 1
            if block:
                tp = block["type"]
                if block.get("width"):
                    width_type = "static"
                    width_static = block["width"]
                elif block.get("flex"):
                    width_type = "flex"
                    width_flex = block["flex"]
                html = block.get("html")
                order = block.get("order")
                title = block.get("title")
                cls = block.get("class")
                progress_types = block.get("progress_types")
                if progress_types is not None:
                    progress_types = ','.join(progress_types)
            else:
                tp = "buttons"
                html = ""
                order = 0
                for b in panel["blocks"]:
                    if b["order"] >= order:
                        order = b["order"] + 10
                title = ""
                cls = ""
                progress_types = ""
        progress_values = []
        self.call("admin-interface.progress-bars", progress_values)
        progress_values = ''.join(['<li><strong>%s</strong> &mdash; %s</li>' % (t["code"], t["description"]) for t in progress_values])
        fields = [
            {"name": "title", "label": self._("Block title (visible to administrators only)"), "value": title},
            {"name": "class", "label": self._("CSS class name:<ul><li>horizontal &mdash; standard horizontal menu</li><li>vertical &mdash; standard vertical menu</li><li>any other value &mdash; user specific style</li></ul>"), "value": cls, "remove_label_separator": True},
            {"type": "combo", "name": "type", "label": self._("Block type"), "value": tp, "values": [("buttons", self._("Buttons")), ("header", self._("Header")), ("empty", self._("Empty space")), ("html", self._("Raw HTML")), ("progress", self._("Progress bar"))], "disabled": True if block else False},
            {"type": "combo", "name": "width_type", "label": self._("Block height") if panel.get("vert") else self._("Block width"), "value": width_type, "values": [("static", self._("width///Static")), ("flex", self._("width///Flexible"))], "condition": "[type]!='buttons'"},
            {"name": "width_static", "label": self._("Height in pixels") if panel.get("vert") else self._("Width in pixels"), "value": width_static, "condition": "[type]!='buttons' && [width_type]=='static'", "inline": True},
            {"name": "width_flex", "label": self._("Relative height") if panel.get("vert") else self._("Relative width"), "value": width_flex, "condition": "[type]!='buttons' && [width_type]=='flex'", "inline": True},
            {"type": "textarea", "name": "html", "label": self._("HTML content"), "value": html, "condition": "[type]=='html' || [type]=='header'"},
            {"name": "progress_types", "label": '%s<ul>%s</ul>' % (self._("Progress bars in this block (delimited by commas). Valid values are:"), progress_values), "value": progress_types, "condition": "[type]=='progress'", "remove_label_separator": True},
            {"name": "order", "label": self._("Sort order"), "value": order},
        ]
        self.call("admin.form", fields=fields)

    def generated_buttons(self):
        buttons = []
        self.call("gameinterface.buttons", buttons)
        buttons.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
        return buttons

    def admin_gameinterface_buttons(self):
        req = self.req()
        if req.args == "new":
            return self.button_editor(None)
        m = re_del.match(req.args)
        if m:
            button_id = m.group(1)
            # Removing button from the layout
            layout = self.buttons_layout()
            for block_id, btn_list in layout.items():
                for btn in btn_list:
                    if btn["id"] == button_id:
                        btn_list = [ent for ent in btn_list if ent["id"] != button_id]
                        if btn_list:
                            layout[block_id] = btn_list
                        else:
                            del layout[block_id]
            config = self.app().config_updater()
            config.set("gameinterface.buttons-layout", layout)
            config.store()
            self.call("admin.redirect", "gameinterface/buttons")
        if req.args:
            # Buttons in the layout
            for block_id, btn_list in self.buttons_layout().iteritems():
                for btn in btn_list:
                    if btn["id"] == req.args:
                        return self.button_editor(btn)
            # Unused buttons
            for btn in self.generated_buttons():
                if btn["id"] == req.args:
                    return self.button_editor(btn)
            self.call("admin.redirect", "gameinterface/buttons")
        vars = {
            "NewButton": self._("New button"),
            "Button": self._("Button"),
            "Action": self._("Action"),
            "Order": self._("Order"),
            "Editing": self._("Editing"),
            "Deletion": self._("Deletion"),
            "delete": self._("delete"),
            "ConfirmDelete": self._("Are you sure want to delete this button?"),
            "NA": self._("n/a"),
        }
        # Loading list of button blocks that present in existing panels
        # Every such block is marked as 'valid'
        valid_blocks = {}
        vars["blocks"] = []
        for panel in self.panels():
            for block in panel["blocks"]:
                if block["type"] == "buttons":
                    show_block = {
                        "title": self._("Button block: %s") % htmlescape(block.get("title")),
                        "buttons": []
                    }
                    vars["blocks"].append(show_block)
                    valid_blocks[block["id"]] = show_block
        popups = self.objlist(DBPopupList, query_index="all")
        popups.load()
        for popup in popups:
            show_block = {
                "title": self._("Popup menu: %s") % htmlescape(popup.get("title")),
                "buttons": []
            }
            vars["blocks"].append(show_block)
            valid_blocks[popup.uuid] = show_block
        # Looking at the buttons layout and assigning buttons to the panels
        # Remebering assigned buttons
        assigned_buttons = {}
        generated = set([btn["id"] for btn in self.generated_buttons()])
        for block_id, btn_list in self.buttons_layout().iteritems():
            show_block = valid_blocks.get(block_id)
            if show_block:
                for btn in btn_list:
                    if btn["image"].startswith("http://") or btn["id"] in generated:
                        show_btn = btn.copy()
                        assigned_buttons[btn["id"]] = show_btn
                        show_block["buttons"].append(show_btn)
                        show_btn["edit"] = self._("edit")
        # Loading full list of generated buttons and showing missing buttons
        # as unused
        unused_buttons = []
        for btn in self.generated_buttons():
            if not btn["id"] in assigned_buttons:
                show_btn = btn.copy()
                assigned_buttons[btn["id"]] = show_btn
                unused_buttons.append(show_btn)
                show_btn["edit"] = self._("show")
        # Preparing buttons to rendering
        for btn in assigned_buttons.values():
            btn["title"] = htmlescape(self.call("script.unparse-text", btn.get("title")))
            if btn.get("href"):
                btn["action"] = self._("href///<strong>{0}</strong> to {1}").format(btn["href"], btn.get("target"))
            elif btn.get("onclick"):
                btn["action"] = btn["onclick"]
            elif btn.get("popup"):
                try:
                    popup = self.obj(DBPopup, btn.get("popup"))
                except ObjectNotFoundException:
                    btn["action"] = self._("open invalid popup menu")
                else:
                    btn["action"] = self._('open popup menu <strong><hook:admin.link href="gameinterface/popups/{0}" title="{1}" /></strong>').format(popup.uuid, htmlescape(popup.get("title")))
            btn["may_delete"] = True
            if btn.get("image") and btn["image"].startswith("http://"):
                btn["image"] = '<img src="%s" alt="" title="%s" />' % (btn["image"], btn.get("title"))
            if not btn.get("image") and btn.get("icon"):
                btn["image"] = "<strong>%s-</strong>%s" % (self._("wildcard///block-class"), btn["icon"])
        # Rendering unused buttons
        if unused_buttons:
            unused_buttons.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            vars["blocks"].append({
                "title": self._("Unused buttons"),
                "buttons": unused_buttons,
                "hide_order": True,
                "hide_deletion": True,
            })
        self.call("admin.response_template", "admin/gameinterface/buttons.html", vars)

    def headmenu_buttons(self, args):
        if args:
            layout = self.buttons_layout()
            for block_id, btn_list in layout.iteritems():
                for btn in btn_list:
                    if btn["id"] == args:
                        return [htmlescape(self.call("script.unparse-text", btn["title"])), "gameinterface/buttons"]
            return [self._("Button editor"), "gameinterface/buttons"]
        return self._("Game interface buttons")

    def buttons_layout(self):
        layout = self.conf("gameinterface.buttons-layout")
        if layout is not None:
            return layout
        # Loading available blocks
        blocks = {}
        for panel in self.panels():
            for blk in panel["blocks"]:
                if blk["type"] == "buttons":
                    blocks[blk["id"]] = blk
        # Default button layout
        layout = {}
        for btn in self.generated_buttons():
            block_id = btn["block"]
            blk = blocks.get(block_id)
            if blk:
                btn_list = layout.get(block_id)
                if btn_list is None:
                    btn_list = []
                    layout[block_id] = btn_list
                lbtn = btn.copy()
                lbtn["image"] = "%s-%s" % (blk["class"], btn["icon"])
                btn_list.append(lbtn)
        for block_id, btn_list in layout.iteritems():
            btn_list.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
        return layout

    def button_editor(self, button):
        req = self.req()
        layout = self.buttons_layout()
        if req.ok():
            self.call("web.upload_handler")
            errors = {}
            if button:
                button_id = button["id"]
                image = button.get("image")
                old_image = image
                # Removing button from the layout
                for block_id, btn_list in layout.items():
                    for btn in btn_list:
                        if btn["id"] == button["id"]:
                            btn_list = [ent for ent in btn_list if ent["id"] != button["id"]]
                            if btn_list:
                                layout[block_id] = btn_list
                            else:
                                del layout[block_id]
            else:
                button_id = uuid4().hex
                image = None
                old_image = None
            # Trying to find button prototype in generated buttons
            user = True
            if button:
                for btn in self.generated_buttons():
                    if btn["id"] == button["id"]:
                        prototype = btn
                        user = False
                        break
            # Input parameters
            block = req.param("v_block")
            order = intz(req.param("order"))
            title = req.param("title")
            action = req.param("v_action")
            href = req.param("href")
            target = req.param("v_target")
            onclick = req.param("onclick")
            popup = req.param("v_popup")
            # Creating new button
            char = self.character(req.user())
            btn = {
                "id": button_id,
                "order": order,
                "title": self.call("script.admin-text", "title", errors, globs={"char": char}),
                "condition": self.call("script.admin-expression", "condition", errors, globs={"char": char}) if req.param("condition").strip() else None,
            }
            # Button action
            if action == "javascript":
                if not onclick:
                    errors["onclick"] = self._("Specify JavaScript action")
                else:
                    btn["onclick"] = onclick
            elif action == "href":
                if not href:
                    errors["href"] = self._("Specify URL")
                elif target != "_blank" and not href.startswith("/"):
                    errors["href"] = self._("Ingame URL must be relative (start with '/' symbol)")
                else:
                    btn["href"] = href
                    btn["target"] = target
            elif action == "popup":
                if not popup:
                    errors["v_popup"] = self._("Select a popup menu")
                else:
                    btn["popup"] = popup
            else:
                errors["v_action"] = self._("Select an action")
            # Button block
            if not block:
                errors["v_block"] = self._("Select buttons block where to place the button")
            else:
                btn_list = layout.get(block)
                if not btn_list:
                    btn_list = []
                    layout[block] = btn_list
                btn_list.append(btn)
                btn_list.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
            # Button image
            image_data = req.param_raw("image")
            if image_data:
                image_obj = Image.open(cStringIO.StringIO(image_data))
                try:
                    image_obj.verify()
                except Exception:
                    errors["image"] = self._("Unknown image format")
                else:
                    if image_obj.format == "JPEG":
                        content_type = "image/jpeg"
                        ext = "jpg"
                    elif image_obj.format == "PNG":
                        content_type = "image/png"
                        ext = "png"
                    elif image_obj.format == "GIF":
                        content_type = "image/gif"
                        ext = "gif"
                    else:
                        content_type = None
                        errors["image"] = self._("Image must be JPEG, PNG or GIF")
                    if content_type:
                        image = self.call("cluster.static_upload", "button", ext, content_type, image_data)
            # Changing image name according to the prototype
            if not image_data and not user and (not image or not image.startswith("http://")):
                found = False
                for panel in self.panels():
                    for blk in panel["blocks"]:
                        if blk["id"] == block:
                            image = "%s-%s" % (blk["class"], prototype["icon"])
                            btn["icon"] = prototype["icon"]
                            if prototype.get("icon2"):
                                btn["icon2"] = prototype["icon2"]
                            found = True
                if not found:
                    try:
                        pop = self.obj(DBPopup, block)
                    except ObjectNotFoundException:
                        pass
                    else:
                        image = prototype["icon"]
                        btn["icon"] = image
                        try:
                            del btn["icon2"]
                        except KeyError:
                            pass

            if not image:
                errors["image"] = self._("You must upload an image")
            else:
                btn["image"] = image
            # Storing button
            if len(errors):
                self.call("web.response_json_html", {"success": False, "errors": errors})
            config = self.app().config_updater()
            config.set("gameinterface.buttons-layout", layout)
            config.store()
            if old_image and old_image.startswith("http://") and image_data:
                self.call("cluster.static_delete", old_image)
            self.call("web.response_json_html", {"success": True, "redirect": "gameinterface/buttons"})
        else:
            if button:
                block = button.get("block")
                order = button["order"]
                title = button.get("title")
                user = False
                for block_id, btn_list in layout.iteritems():
                    for btn in btn_list:
                        if btn["id"] == button["id"]:
                            block = block_id
                            break
                href = button.get("href")
                onclick = button.get("onclick")
                popup = button.get("popup")
                condition = button.get("condition")
                if onclick:
                    action = "javascript"
                    target = "_blank"
                elif popup:
                    action = "popup"
                    target = "_blank"
                else:
                    action = "href"
                    target = button.get("target")
                # Valid blocks
                if block:
                    valid_block = False
                    for panel in self.panels():
                        for blk in panel["blocks"]:
                            if blk["id"] == block and blk["type"] == "buttons":
                                valid_block = True
                                break
                        if valid_block:
                            break
                    if not valid_block:
                        try:
                            self.obj(DBPopup, block)
                        except ObjectNotFoundException:
                            block = ""
            else:
                block = ""
                order = 50
                title = ""
                user = True
                href = ""
                onclick = ""
                target = "_blank"
                action = "href"
                popup = ""
                condition = None
        blocks = []
        for panel in self.panels():
            for blk in panel["blocks"]:
                if blk["type"] == "buttons":
                    blocks.append((blk["id"], self._("Button block: %s") % (blk.get("title") or blk["id"])))
        lst = self.objlist(DBPopupList, query_index="all")
        lst.load()
        popups = []
        for p in lst:
            blocks.append((p.uuid, self._("Popup menu: %s") % p.get("title")))
            popups.append((p.uuid, p.get("title")))
        fields = [
            {"name": "block", "type": "combo", "label": self._("Buttons block"), "values": blocks, "value": block},
            {"name": "order", "label": self._("Sort order"), "value": order, "inline": True},
            {"type": "fileuploadfield", "name": "image", "label": self._("Button image")},
            {"name": "condition", "label": self._("Condition (when to show the button)") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", condition) if condition else None},
            {"name": "title", "label": self._("Button hint") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", title)},
            {"type": "combo", "name": "action", "label": self._("Button action"), "value": action, "values": [("href", self._("Open hyperlink")), ("javascript", self._("Execute JavaScript")), ("popup", self._("Open popup menu"))]},
            {"name": "href", "label": self._("Button href"), "value": href, "condition": "[[action]]=='href'"},
            {"type": "combo", "name": "target", "label": self._("Target frame"), "value": target, "values": [("main", self._("Main game frame")), ("_blank", self._("New window"))], "condition": "[[action]]=='href'", "inline": True},
            {"type": "combo", "name": "popup", "label": self._("Popup menu"), "value": popup, "values": popups, "condition": "[[action]]=='popup'"},
            {"name": "onclick", "label": self._("Javascript onclick"), "value": onclick, "condition": "[[action]]=='javascript'"},
        ]
        self.call("admin.form", fields=fields, modules=["FileUploadField"])

    def project_status(self):
        project = self.app().project
        if project.get("moderation"):
            text = self._('<p>Your game is currently on moderation. You may continue setting it up.</p><p><a href="/admin" target="_blank">Administrative interface</a></p>')
        else:
            text = self._('<h1>Welcome to your new game!</h1><p>Now you can open <a href="/admin" target="_blank">Administrative interface</a> and follow several steps to launch your game.</p><p>Welcome to the world of creative game development and good luck!</p>')
        self.call("main-frame.info", text)

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "settings",
            "href": "/interface/settings",
            "target": "main",
            "icon": "settings.png",
            "title": self._("Settings"),
            "block": "top-menu",
            "order": 10,
        })

    def settings(self):
        req = self.req()
        form = self.call("web.form")
        character = self.character(req.user())
        if req.ok():
            self.call("interface.settings-form", form, "validate", character.settings)
            if not form.errors:
                self.call("interface.settings-form", form, "store", character.settings)
                character.settings.store()
                self.call("web.redirect", "/location")
        self.call("interface.settings-form", form, "render", character.settings)
        form.add_message_bottom('<a href="/auth/change" target="_blank">%s</a>' % self._("Change your password"))
        self.call("main-frame.form", form, {})

    def gameinterface_popups(self):
        req = self.req()
        if req.args:
            m = re_del.match(req.args)
            if m:
                popup_id = m.group(1)
                try:
                    self.obj(DBPopup, popup_id).remove()
                except ObjectNotFoundException:
                    pass
                self.call("admin.redirect", "gameinterface/popups")
                
            if req.args == "new":
                popup = self.obj(DBPopup)
            else:
                try:
                    popup = self.obj(DBPopup, req.args)
                except ObjectNotFoundException:
                    self.call("admin.redirect", "gameinterface/popups")
            if req.ok():
                errors = {}
                title = req.param("title")
                if not title:
                    errors["title"] = self._("This parameter is mandatory")
                else:
                    popup.set("title", title)
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                popup.store()
                self.call("admin.redirect", "gameinterface/popups")
            fields = [
                {"name": "title", "label": self._("Popup menu title (visible to administrators only)"), "value": popup.get("title")},
            ]
            self.call("admin.form", fields=fields)
        vars = {
            "NewPopup": self._("New popup menu"),
            "ButtonsEditor": self._("Go to the buttons editor"),
            "Code": self._("Code"),
            "Title": self._("Title"),
            "Editing": self._("Editing"),
            "Deletion": self._("Deletion"),
            "edit": self._("edit"),
            "delete": self._("delete"),
            "ConfirmDelete": self._("Are you sure want to delete this popup menu?"),
        }
        popups = []
        lst = self.objlist(DBPopupList, query_index="all")
        lst.load()
        for ent in lst:
            popups.append({
                "id": ent.uuid,
                "title": ent.get("title"),
            })
        vars["popups"] = popups
        self.call("admin.response_template", "admin/gameinterface/popups.html", vars)

    def headmenu_popups(self, args):
        return self._("Popup menus")
