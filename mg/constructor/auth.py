# -*- coding: utf-8 -*-

from mg import *
from mg.constructor import *
from mg.core.auth import Captcha, AutoLogin
from mg.constructor.players import DBCharacter, DBCharacterList, DBPlayer, DBPlayerList, DBCharacterForm, DBCharacterOnline, DBCharacterOnlineList, Character
import hashlib
import copy
import random
import time

class AppSession(CassandraObject):
    clsname = "AppSession"
    indexes = {
        "timeout": [[], "timeout"],
        "character": [["character"]],
    }

class AppSessionList(CassandraObjectList):
    objcls = AppSession

class AuthAdmin(ConstructorModule):
    def register(self):
        self.rhook("menu-admin-cluster.monitoring", self.menu_cluster_monitoring)
        self.rhook("ext-admin-sessions.monitor", self.sessions_monitor, priv="monitoring")
        self.rhook("headmenu-admin-sessions.monitor", self.headmenu_sessions_monitor)
        self.rhook("stream.idle", self.stream_idle)

    def menu_cluster_monitoring(self, menu):
        req = self.req()
        if req.has_access("monitoring"):
            menu.append({"id": "sessions/monitor", "text": self._("Sessions"), "leaf": True})

    def sessions_monitor(self):
        rows = []
        vars = {
            "tables": [
                {
                    "header": [self._("Application"), self._("Session"), self._("Character"), self._("State"), self._("Timeout")],
                    "rows": rows
                }
            ]
        }
        lst = self.main_app().objlist(AppSessionList, query_index="timeout")
        lst.load(silent=True)
        for ent in lst:
            state = {1: self._("authorized"), 2: self._("online"), 3: self._("disconnected")}.get(ent.get("state"), ent.get("state"))
            rows.append(['<hook:admin.link href="constructor/project-dashboard/{0}" title="{0}" />'.format(ent.get("app")), ent.get("session"), ent.get("character"), state, ent.get("timeout")])
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_sessions_monitor(self, args):
        return self._("Sessions monitor")

    def stream_idle(self):
        try:
            now = self.now()
            appsessions = self.objlist(AppSessionList, query_index="timeout", query_finish=now)
            appsessions.load(silent=True)
            for appsession in appsessions:
                app_tag = appsession.get("app")
                app = self.app().inst.appfactory.get_by_tag(app_tag)
                if not app:
                    return
                session_uuid = appsession.get("session")
                with app.lock(["session.%s" % session_uuid]):
                    try:
                        appsession.load()
                    except ObjectNotFoundException:
                        pass
                    else:
                        if appsession.get("timeout") < now:
                            try:
                                session = app.obj(Session, session_uuid)
                            except ObjectNotFoundException as e:
                                appsession.remove()
                            else:
                                old_state = appsession.get("state")
                                if old_state == 1 or old_state == 2:
                                    # online session disconnected on timeout
                                    self.debug("Session %s timed out. State: %s => 3" % (session_uuid, old_state))
                                    appsession.set("state", 3)
                                    appsession.set("timeout", self.now(3600))
                                    character_uuid = appsession.get("character")
                                    # updating session
                                    user = session.get("user")
                                    if user:
                                        session.set("semi_user", user)
                                        session.delkey("user")
                                        self.call("session.log", act="disconnect", session=session.uuid, user=user, ip=session.get("ip"))
                                    session.delkey("character")
                                    session.delkey("authorized")
                                    session.set("updated", self.now())
                                    # storing
                                    session.store()
                                    appsession.store()
                                    # character offline on timeout
                                    with app.lock(["Character.%s" % character_uuid]):
                                        try:
                                            obj = app.obj(DBCharacterOnline, character_uuid)
                                        except ObjectNotFoundException:
                                            pass
                                        else:
                                            obj.remove()
                                            app.hooks.call("session.character-offline", Character(app, character_uuid))
                                else:
                                    # disconnected session destroyed on timeout
                                    self.debug("Session %s destroyed on timeout. State: %s => None" % (session_uuid, old_state))
                                    # updating session
                                    user = session.get("user")
                                    if user:
                                        session.set("semi_user", user)
                                        session.delkey("user")
                                    session.delkey("character")
                                    session.delkey("authorized")
                                    session.set("updated", self.now())
                                    # storing
                                    session.store()
                                    appsession.remove()
        except Exception as e:
            self.exception(e)

class Auth(ConstructorModule):
    def register(self):
        self.rhook("menu-admin-auth.index", self.menu_auth_index)
        self.rhook("ext-admin-players.auth", self.admin_players_auth, priv="players.auth")
        self.rhook("headmenu-admin-players.auth", self.headmenu_players_auth)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-player.login", self.player_login, priv="public")
        self.rhook("ext-player.register", self.player_register, priv="public")
        self.rhook("auth.form_params", self.auth_form_params)
        self.rhook("auth.registered", self.auth_registered, priority=5)
        self.rhook("auth.activated", self.auth_activated)
        self.rhook("ext-admin-characters.online", self.admin_characters_online, priv="users.authorized")
        self.rhook("ext-auth.logout", self.ext_logout, priv="public", priority=10)
        self.rhook("ext-auth.login", (lambda: self.call("web.forbidden")), priv="disabled", priority=10)
        self.rhook("ext-auth.register", (lambda: self.call("web.forbidden")), priv="disabled", priority=10)
        self.rhook("stream.connected", self.stream_connected)
        self.rhook("stream.disconnected", self.stream_disconnected)
        self.rhook("stream.login", self.stream_login)
        self.rhook("stream.logout", self.stream_logout)
        self.rhook("ext-stream.ready", self.stream_ready, priv="public")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("session.require_login", self.require_login, priority=10)
        self.rhook("session.require_permission", self.require_permission, priority=10)
        self.rhook("auth.permissions", self.auth_permissions, priority=10)
        self.rhook("indexpage.render", self.indexpage_render)
        self.rhook("ext-auth.character", self.auth_character, priv="public")
        self.rhook("auth.login-before-activate", self.login_before_activate)
        self.rhook("ext-player.activated", self.player_activated, priv="public")
        self.rhook("character.form", self.character_form)
        self.rhook("ext-auth.autologin", self.ext_autologin, priv="public")
        self.rhook("auth.cleanup-inactive-users", self.cleanup_inactive_users, priority=10)
        self.rhook("auth.characters-tech-online", self.characters_tech_online)
        self.rhook("stream.character", self.stream_character)
        self.rhook("auth.user-auth-table", self.user_auth_table)
        self.rhook("auth.user-tables", self.user_tables, priority=-100)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("session.character-sessions", self.character_sessions)
        self.rhook("restraints.set", self.restraints_set)
        self.rhook("money-description.multicharing", self.money_description_multicharing)
        self.rhook("session.log-fix", self.log_fix)
        self.rhook("auth.remind-message", self.auth_remind_message)
        self.rhook("auth.password-reminder", self.password_reminder, priority=10)
        self.rhook("auth.password-user", self.password_user)
        self.rhook("auth.message", self.auth_message, priority=10)
        self.rhook("auth.remind_email", self.remind_email)
        self.rhook("menu-admin-game.index", self.menu_game_index)
        self.rhook("ext-admin-auth.close-project", self.close_project, priv="auth.close-project")
        self.rhook("ext-offer.index", self.offer, priv="public")
        self.rhook("advice-admin-auth.user-dashboard", self.advice_user_dashboard)
        self.rhook("library-grp-index.pages", self.library_index_pages)
        self.rhook("library-page-offer.content", self.library_page_offer)
        self.rhook("library-page-multicharing.content", self.library_page_multicharing)
        self.rhook("auth.name-changed", self.name_changed)
        self.rhook("user.email", self.user_email, priority=10)
        self.rhook("advice-admin-auth.index", self.advice_auth)

    def advice_auth(self, hook, args, advice):
        advice.append({"title": self._("Authentication documentation"), "content": self._('You can find detailed information on the authentication system in the <a href="//www.%s/doc/auth" target="_blank">authentication page</a> in the reference manual.') % self.main_host})
        advice.append({"title": self._("Permissions documentation"), "content": self._('You can find detailed information on the permissions system in the <a href="//www.%s/doc/permissions" target="_blank">permissions page</a> in the reference manual.') % self.main_host})

    def user_email(self, user_obj):
        email = user_obj.get("email")
        if email:
            raise Hooks.Return(email)
        char = self.character(user_obj.uuid)
        if char.player and char.player.valid:
            raise Hooks.Return(char.player.email)

    def name_changed(self, user, old_name, new_name):
        character = self.character(user.uuid)
        player = character.player
        self.call("email.send", player.email, old_name, self._("Your name has been changed"), self._("Name of your character '{name_from}' was changed to '{name_to}'").format(name_from=old_name, name_to=new_name))

    def library_index_pages(self, pages):
        pages.append({"page": "offer", "order": 1000})
        pages.append({"page": "multicharing", "order": 10})

    def library_page_multicharing(self, render_content):
        pageinfo = {
            "code": "multicharing",
            "title": self._("Multicharing in the game"),
            "keywords": self._("multicharing, players, characters"),
            "description": self._("Multicharing policy of the game"),
            "parent": "index",
        }
        if render_content:
            vars = {
                "multicharing": self.conf("auth.multicharing", 0),
                "free_chars": self.conf("auth.free_chars", 1),
                "max_chars": self.conf("auth.max_chars", 5),
            }
            multichar_price = self.conf("auth.multichar_price", 5)
            multichar_currency = self.conf("auth.multichar_currency")
            if multichar_price and multichar_currency:
                vars["multichar_price"] = self.call("money.price-html", multichar_price, multichar_currency)
            lang = self.call("l10n.lang")
            pageinfo["content"] = self.call("socio.parse", "library-multicharing.html", vars)
        return pageinfo

    def library_page_offer(self, render_content):
        pageinfo = {
            "code": "offer",
            "title": self._("Terms and conditions (public offer)"),
            "keywords": self._("public offer, terms and conditions"),
            "description": self._("This is the public offer"),
            "parent": "index",
        }
        if render_content:
            vars = {
                "title": self._("Terms and conditions (public offer)"),
            }
            lang = self.call("l10n.lang")
            pageinfo["content"] = self.call("web.parse_template", "constructor/offer-players-%s.html" % lang, vars)
        return pageinfo

    def advice_user_dashboard(self, args, advice):
        advice.append({"title": self._("Multicharing options"), "content": self._('You have powerful abilities to look for and punish players violating your multicharing rules. Before you begin enforcing the law <hook:admin.link href="players/auth" title="setup rules related to the multicharing" />.')})

    def offer(self):
        vars = {
            "title": self._("Terms and conditions (public offer)"),
        }
        lang = self.call("l10n.lang")
        content = self.call("web.parse_template", "constructor/offer-players-%s.html" % lang, vars)
        self.call("game.info", content, vars)

    def menu_game_index(self, menu):
        req = self.req()
        if req.has_access("auth.close-project"):
            menu.append({"id": "auth/close-project", "text": self._("Close project login"), "leaf": True, "order": 30, "even_unpublished": True})

    def close_project(self):
        req = self.req()
        if req.ok():
            config = self.app().config_updater()
            config.set("auth.closed", True if req.param("closed") else False)
            config.set("auth.close-message", req.param("close_message"))
            if req.param("closed"):
                self.call("project.closed")
            else:
                self.call("project.opened")
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        fields = [
            {"name": "closed", "type": "checkbox", "label": self._("Close game for all non-authorized users"), "checked": self.conf("auth.closed")},
            {"name": "close_message", "type": "textarea", "label": self._("Show this message to all non-authorized users"), "value": self.conf("auth.close-message"), "condition": "[closed]"},
        ]
        self.call("admin.form", fields=fields)

    def remind_email(self, params):
        params["content"] = self._("Someone possibly you requested password recovery on the {host} site.\n\n{content}")

    def auth_message(self, message, vars):
        self.call("game.info", message, vars)

    def auth_remind_message(self, user):
        content = u''
        player = self.player(user.uuid)
        for char in player.characters:
            content += self._("Your character name is '{name}'\n").format(name=char.name)
        content += self._("Your password is '{password}'\n").format(password=user.get("pass_reminder"))
        return content

    def password_reminder(self, password):
        raise Hooks.Return(password)

    def password_user(self):
        req = self.req()
        user = self.obj(User, req.user())
        if user.get("name"):
            return self.character(user.uuid).player.uuid
        else:
            return user.uuid

    def log_fix(self, args):
        if args.get("user"):
            char = self.character(args["user"])
            if char.valid:
                args["player"] = char.player.uuid
            else:
                player = self.player(args["user"])
                if player.valid:
                    args["player"] = args["user"]
                    del args["user"]

    def money_description_multicharing(self):
        return {
            "args": ["name"],
            "text": self._("New character: {name}"),
        }

    def restraints_set(self, user_uuid, *args, **kwargs):
        if kwargs.get("kind") == "ban":
            # Dropping session of banned user
            appsessions = self.main_app().objlist(AppSessionList, query_index="character", query_equal=user_uuid)
            appsessions.load(silent=True)
            for appsession in appsessions:
                session_uuid = appsession.get("session")
                with self.lock(["session.%s" % session_uuid]):
                    try:
                        appsession.load()
                    except ObjectNotFoundException:
                        pass
                    else:
                        old_state = appsession.get("state")
                        if old_state == 1 or old_state == 2:
                            if old_state:
                                self.debug("Session %s banned. State: %s => None" % (session_uuid, old_state))
                            try:
                                session = self.obj(Session, session_uuid)
                            except ObjectNotFoundException as e:
                                pass
                            else:
                                # updating session
                                user = session.get("user")
                                session.delkey("semiuser")
                                session.delkey("user")
                                session.delkey("character")
                                session.delkey("authorized")
                                session.set("updated", self.now())
                                # storing
                                session.store()
                        else:
                            self.debug("Session %s banned. Clearing it forced. State: %s => None" % (session_uuid, old_state))
                        appsession.remove()
                        # notifying session
                        self.call("stream.send", ["id_%s" % session_uuid], {"packets": [{"method_cls": "game", "method": "close"}]})

    def character_sessions(self, character, sessions):
        lst = self.objlist(SessionList, query_index="authorized_user", query_equal="1-%s" % character.uuid)
        sessions.extend(lst.uuids())

    def require_login(self):
        if not self.app().project.get("inactive"):
            req = self.req()
            session = req.session()
            if not session or not session.get("user") or not session.get("authorized"):
                if req.group.startswith("admin-"):
                    req.headers.append(('Content-type', req.content_type))
                    raise WebResponse(req.send_response("403 Admin Offline", req.headers, "<html><body><h1>403 %s</h1>%s</body></html>" % (self._("Admin Offline"), self._("To access this page you must enter the game from another browser window. Character with administrative rights must be online when using administrative interface."))))
                else:
                    self.call("game.error", self._("To access this page enter the game first"))
        raise Hooks.Return(None)

    def require_permission(self, priv):
        if self.app().project.get("inactive"):
            raise Hooks.Return(None)

    def auth_permissions(self, user_id):
        if self.app().project.get("inactive"):
            raise Hooks.Return({
                "admin": True,
                "project.admin": True
            })

    def auth_registered(self, user):
        raise Hooks.Return()

    def auth_activated(self, user, redirect):
        req = self.req()
        session = req.session()
        if session:
            self.call("stream.logout", session.uuid)

    def objclasses_list(self, objclasses):
        objclasses["AppSession"] = (AppSession, AppSessionList)
        objclasses["CharacterOnline"] = (DBCharacterOnline, DBCharacterOnlineList)

    def permissions_list(self, perms):
        perms.append({"id": "players.auth", "name": self._("Players authentication settings")})
        perms.append({"id": "users.authorized", "name": self._("Viewing list of authorized users")})
        perms.append({"id": "auth.close-project", "name": self._("Game login closing")})
        perms.append({"id": "auth.enter-closed", "name": self._("May enter even closed game")})

    def menu_auth_index(self, menu):
        req = self.req()
        if req.has_access("players.auth"):
            menu.append({"id": "players/auth", "text": self._("Authentication configuration"), "leaf": True, "order": 1})
        if req.has_access("users.authorized"):
            menu.append({"id": "characters/online", "text": self._("List of characters online"), "leaf": True, "order": 5})

    def headmenu_players_auth(self, args):
        return self._("Players authentication settings")

    def admin_players_auth(self):
        req = self.req()
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('You can find information on authentication setup in your game in the <a href="//www.%s/doc/auth" target="_blank">authentication manual</a>.') % self.main_host})
        currencies = {}
        self.call("currencies.list", currencies)
        if req.param("ok"):
            config = self.app().config_updater()
            errors = {}
            # multicharing
            multicharing = req.param("v_multicharing")
            if multicharing != "0" and multicharing != "1" and multicharing != "2":
                errors["multicharing"] = self._("Make valid selection")
            else:
                multicharing = int(multicharing)
                config.set("auth.multicharing", multicharing)
                if multicharing:
                    # free and max chars
                    free_chars = req.param("free_chars")
                    if not valid_nonnegative_int(free_chars):
                        errors["free_chars"] = self._("Invalid number")
                    else:
                        free_chars = int(free_chars)
                        if free_chars < 1:
                            errors["free_chars"] = self._("Minimal value is 1")
                        config.set("auth.free_chars", free_chars)
                    max_chars = req.param("max_chars")
                    if not valid_nonnegative_int(max_chars):
                        errors["max_chars"] = self._("Invalid number")
                    else:
                        max_chars = int(max_chars)
                        if max_chars < 2:
                            errors["max_chars"] = self._("Minimal value is 2")
                        config.set("auth.max_chars", max_chars)
                    if not errors.get("max_chars") and not errors.get("free_chars"):
                        if max_chars < free_chars:
                            errors["free_chars"] = self._("Free characters can't be greater than max characters")
                        elif max_chars > free_chars:
                            # multichars price
                            multichar_price = req.param("multichar_price")
                            multichar_currency = req.param("v_multichar_currency")
                            if self.call("money.valid_amount", multichar_price, multichar_currency, errors, "multichar_price", "v_multichar_currency"):
                                multichar_price = float(multichar_price)
                                config.set("auth.multichar_price", multichar_price)
                                config.set("auth.multichar_currency", multichar_currency)
                config.set("auth.cabinet", True if req.param("v_cabinet") == "1" else False)
            # email activation
            activate_email = True if req.param("activate_email") else False
            config.set("auth.activate_email", activate_email)
            if activate_email:
#                activate_email_level = req.param("activate_email_level")
#                if not valid_nonnegative_int(activate_email_level):
#                    errors["activate_email_level"] = self._("Invalid number")
#                else:
#                    activate_email_level = int(activate_email_level)
#                    config.set("auth.activate_email_level", activate_email_level)
                activate_email_days = req.param("activate_email_days")
                if not valid_nonnegative_int(activate_email_days):
                    errors["activate_email_days"] = self._("Invalid number")
                else:
                    activate_email_days = int(activate_email_days)
                    config.set("auth.activate_email_days", activate_email_days)
            # names validation
            validate_names = True if req.param("validate_names") else False
            config.set("auth.validate_names", validate_names)
            # processing
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            multicharing = self.conf("auth.multicharing", 0)
            free_chars = self.conf("auth.free_chars", 1)
            max_chars = self.conf("auth.max_chars", 5)
            multichar_price = self.conf("auth.multichar_price", 5)
            multichar_currency = self.conf("auth.multichar_currency")
            cabinet = self.conf("auth.cabinet", False)
            activate_email = self.conf("auth.activate_email", True)
#            activate_email_level = self.conf("auth.activate_email_level", 0)
            activate_email_days = self.conf("auth.activate_email_days", 7)
            validate_names = self.conf("auth.validate_names", False)
        fields = [
            {"name": "multicharing", "type": "combo", "label": self._("Are players allowed to play more than 1 character"), "value": multicharing, "values": [(0, self._("No")), (1, self._("Yes, but play them by turn")), (2, self._("Yes, play them simultaneously"))] },
            {"name": "free_chars", "label": self._("Number of characters per player allowed for free"), "value": free_chars, "condition": "[multicharing]>0" },
            {"name": "max_chars", "label": self._("Maximal number of characters per player allowed"), "value": max_chars, "inline": True, "condition": "[multicharing]>0" },
            {"name": "multichar_price", "label": self._("Price for one extra character over free limit"), "value": multichar_price, "condition": "[multicharing]>0 && [max_chars]>[free_chars]" },
            {"name": "multichar_currency", "label": self._("Currency"), "type": "combo", "value": multichar_currency, "values": [(code, info["name_plural"]) for code, info in currencies.iteritems()], "condition": "[multicharing]>0 && [max_chars]>[free_chars]", "inline": True},
            {"name": "cabinet", "type": "combo", "label": self._("Login sequence"), "value": cabinet, "condition": "![multicharing]", "values": [(0, self._("Enter the game immediately after login")), (1, self._("Open player cabinet after login"))]},
            {"name": "activate_email", "type": "checkbox", "label": self._("Require email activation"), "checked": activate_email},
#            {"name": "activate_email_level", "label": self._("Activation is required after this character level ('0' if require on registration)"), "value": activate_email_level, "condition": "[activate_email]"},
            {"name": "activate_email_days", "label": self._("Activation is required after this number of days ('0' if require on registration)"), "value": activate_email_days, "condition": "[activate_email]"},
            {"name": "validate_names", "type": "checkbox", "label": self._("Manual validation of every character name"), "checked": validate_names},
        ]
        self.call("admin.form", fields=fields)

    def ext_logout(self):
        req = self.req()
        session = req.session()
        if session:
            self.call("stream.logout", session.uuid)
        redirect = req.param("redirect")
        if redirect:
            self.call("web.redirect", redirect)
        self.call("web.redirect", "/")

    def character_form(self):
        fields = self.conf("auth.char_form", [])
        if not len(fields):
            fields.append({"std": 1, "code": "name", "name": self._("Name"), "order": 10.0, "reg": True, "description": self._("Character's name"), "prompt": self._("Enter your character name")})
            fields.append({"std": 2, "code": "sex", "name": self._("Sex"), "type": 1, "values": [["0", self._("Man")], ["1", self._("Woman")]], "order": 20.0, "reg": True, "description": self._("Character sex"), "prompt": self._("sex///Who is your character")})
            fields.append({"code": "motto", "name": self._("Motto"), "order": 30, "reg": True, "description": self._("Character's motto"), "prompt": self._("Enter your character's motto")})
            fields.append({"code": "legend", "name": self._("Legend"), "order": 40, "reg": True, "description": self._("Character's legend"), "prompt": self._("Enter your character's legend"), "type": 2})
        return copy.deepcopy(fields)

    def jsencode_character_form(self, lst):
        for fld in lst:
            fld["name"] = jsencode(fld.get("name"))
            fld["description"] = jsencode(fld.get("description"))
            fld["prompt"] = jsencode(fld.get("prompt"))
            if fld.get("values"):
                fld["values"] = [[jsencode(val[0]), jsencode(val[1])] for val in fld["values"]]
                fld["values"][-1].append(True)

    def indexpage_render(self, vars):
        fields = self.character_form()
        fields = [fld for fld in fields if not fld.get("deleted") and fld.get("reg")]
        self.jsencode_character_form(fields)
        fields.append({"code": "email", "prompt": self._("Your e-mail address")})
        fields.append({"code": "password", "prompt": self._("Your password")})
        fields.append({"code": "captcha", "prompt": self._("Enter numbers from the picture")})
        fields.insert(0, {"code": "offer", "prompt": self._('Do you accept <a href="/offer" target="_blank">the terms and conditions</a>?')})
        vars["register_fields"] = fields

    def player_register(self):
        req = self.req()
        if not self.app().project.get("published"):
            self.call("web.response_json", {"success": False, "error": self._("Registration in this game is disabled yet. To allow new players to register the game must be sent to moderation first.")})
        if self.conf("auth.closed"):
            self.call("web.response_json", {"success": False, "error": htmlescape(self.conf("auth.close-message") or self._("Game is closed for non-authorized users"))})
        # checking IP ban
        till = self.call("restraints.ip-banned", req.remote_addr())
        if till:
            self.call("web.response_json", {"success": False, "error": self._("You are banned till %s") % self.call("l10n.time_local", till)})
        session = req.session(True)
        # registragion form
        fields = self.character_form()
        fields = [fld for fld in fields if not fld.get("deleted") and fld.get("reg")]
        # auth params
        params = {}
        self.call("auth.form_params", params)
        # validating
        errors = {}
        values = {}
        for fld in fields:
            code = fld["code"]
            val = req.param(code).strip()
            if fld.get("mandatory_level") and not val:
                errors[code] = self._("This field is mandatory")
            elif fld.get("std") == 1:
                # character name. checking validity
                if not re.match(params["name_re"], val, re.UNICODE):
                    errors[code] = params["name_invalid_re"]
                elif self.call("session.find_user", val):
                    errors[code] = self._("This name is taken already")
            elif fld.get("type") == 1:
                if not val and not fld.get("std") and not fld.get("mandatory_level"):
                    # empty value is ok
                    val = None
                else:
                    # checking acceptable values
                    ok = False
                    for v in fld["values"]:
                        if v[0] == val:
                            ok = True
                            break
                    if not ok:
                        errors[code] = self._("Make a valid selection")
            values[code] = val
        email = req.param("email")
        if not email:
            errors["email"] = self._("Enter your e-mail address")
        elif not re.match(r'^[a-zA-Z0-9_\-+\.]+@[a-zA-Z0-9\-_\.]+\.[a-zA-Z0-9]+$', email):
            errors["email"] = self._("Enter correct e-mail")
        else:
            existing_email = self.objlist(UserList, query_index="email", query_equal=email.lower())
            existing_email.load(silent=True)
            if len(existing_email):
                errors["email"] = self._("There is another user with this email")
        password = req.param("password")
        if not password:
            errors["password"] = self._("Enter your password")
        elif len(password) < 6:
            errors["password"] = self._("Minimal password length - 6 characters")
        captcha = req.param("captcha")
        if not captcha:
            errors["captcha"] = self._("Enter numbers from the picture")
        else:
            try:
                cap = self.obj(Captcha, session.uuid)
                if cap.get("number") != captcha:
                    errors["captcha"] = self._("Incorrect number")
            except ObjectNotFoundException:
                errors["captcha"] = self._("Incorrect number")
        if len(errors):
            self.call("web.response_json", {"success": False, "errors": errors})
        # Registering player and character
        now = self.now()
        now_ts = "%020d" % time.time()
        # Creating player
        player = self.obj(DBPlayer)
        player.set("created", now)
        player_user = self.obj(User, player.uuid, {})
        player_user.set("created", now_ts)
        player_user.set("last_login", now_ts)
        player_user.set("email", email.lower())
        player_user.set("inactive", 1)
        # Activation code
        if self.conf("auth.activate_email", True):
            activation_code = uuid4().hex
            player_user.set("activation_code", activation_code)
            player_user.set("activation_redirect", "/player/activated")
        else:
            activation_code = None
        # Password
        salt = ""
        letters = "abcdefghijklmnopqrstuvwxyz"
        for i in range(0, 10):
            salt += random.choice(letters)
        player_user.set("salt", salt)
        player_user.set("pass_reminder", self.call("auth.password-reminder", password))
        m = hashlib.md5()
        m.update(salt + password.encode("utf-8"))
        player_user.set("pass_hash", m.hexdigest())
        player_user.set("reg_ip", req.remote_addr())
        player_user.set("reg_agent", req.environ.get("HTTP_USER_AGENT"))
        # Creating character
        character = self.obj(DBCharacter)
        character.set("created", now)
        character.set("player", player.uuid)
        character_user = self.obj(User, character.uuid, {})
        character_user.set("created", now_ts)
        character_user.set("last_login", now_ts)
        character_user.set("name", values["name"])
        character_user.set("name_lower", values["name"].lower())
        character_user.set("sex", intz(values["sex"]))
        if self.conf("auth.validate_names"):
            character_user.set("check", 1)
        character_form = self.obj(DBCharacterForm, character.uuid, {})
        for fld in fields:
            code = fld["code"]
            if code == "name" or code == "sex":
                continue
            val = values.get(code)
            if val is None:
                continue
            character_form.set(code, val)
        # Storing objects
        player.store()
        player_user.store()
        character.store()
        character_user.store()
        character_form.store()
        self.qevent("registered", char=self.character(character.uuid))
        # Sending activation e-mail
        if activation_code:
            params = {
                "subject": self._("Account activation"),
                "content": self._("Someone possibly you requested registration on the {host}. If you really want to do this enter the following activation code on the site:\n\n{code}\n\nor simply follow the link:\n\nhttp://{host}/auth/activate/{user}?code={code}"),
            }
            self.call("auth.activation_email", params)
            self.call("email.send", email, values["name"], params["subject"], params["content"].format(code=activation_code, host=req.host(), user=player_user.uuid))
        self.call("session.log", act="register", session=session.uuid, ip=req.remote_addr(), user=player.uuid)
        self.call("session.log", act="register", session=session.uuid, ip=req.remote_addr(), user=character_user.uuid)
        if activation_code and (not self.conf("auth.activate_email_days", 7)):
            # Require activation immediately after registration
            self.call("stream.logout", session.uuid)
            with self.lock(["session.%s" % session.uuid]):
                session.load()
                session.delkey("user")
                session.delkey("character")
                session.delkey("authorized")
                session.set("semi_user", player.uuid)
                session.set("ip", req.remote_addr())
                session.store()
            self.call("web.response_json", {"ok": 1, "redirect": "/auth/activate/%s" % player.uuid})
        else:
            with self.lock(["session.%s" % session.uuid]):
                session.load()
                session.set("ip", req.remote_addr())
                session.store()
            # First login without activation
            self.call("stream.login", session.uuid, character_user.uuid)
            self.call("web.response_json", {"ok": 1, "session": session.uuid})

    def auth_form_params(self, params):
        params["name_re"] = ur'^[A-Za-z0-9_\-абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ ]+$'
        params["name_invalid_re"] = self._("Invalid characters in the name. Only latin and russian letters, numbers, spaces, symbols '_', and '-' are allowed")

    def player_login(self):
        req = self.req()
        # checking IP ban
        if False:
            till = self.call("restraints.ip-banned", req.remote_addr())
            if till:
                self.call("web.response_json", {"error": self._("You are banned till %s") % self.call("l10n.time_local", till)})
        # logging in
        name = req.param("name") or req.param("email")
        password = req.param("password")
        msg = {}
        self.call("auth.messages", msg)
        if not name:
            self.call("web.response_json", {"error": msg["name_empty"]})
        user = self.call("session.find_user", name)
        if user is None:
            self.call("web.response_json", {"error": msg["name_unknown"]})
        if user.get("name"):
            # character user
            character = self.obj(DBCharacter, user.uuid)
            if character.get("player"):
                try:
                    user = self.obj(User, character.get("player"))
                except ObjectNotFoundException:
                    self.call("web.response_json", {"error": self._("No characters assigned to this player")})
        if not password:
            self.call("web.response_json", {"error": msg["password_empty"]})
        m = hashlib.md5()
        m.update(user.get("salt").encode("utf-8") + password.encode("utf-8"))
        if m.hexdigest() != user.get("pass_hash"):
            self.call("web.response_json", {"error": msg["password_incorrect"]})
        if self.conf("auth.closed"):
            access = False
            for character in self.player(user.uuid).characters:
                perms = self.call("auth.permissions", character.uuid)
                if "project.admin" in perms or "auth.enter-closed" in perms:
                    access = True
                    break
            if not access:
                self.call("web.response_json", {"success": False, "error": htmlescape(self.conf("auth.close-message") or self._("Game is closed for non-authorized users"))})
        session = req.session(True)
        if user.get("inactive") and self.conf("auth.activate_email", True):
            require_activation = False
            activate_days = self.conf("auth.activate_email_days", 7)
            if activate_days:
                days_since_reg = (time.time() - int(user.get("created"))) / 86400
                if days_since_reg >= activate_days:
                    require_activation = True
            if require_activation:
                self.call("stream.logout", session.uuid)
                with self.lock(["session.%s" % session.uuid]):
                    session.load()
                    session.delkey("user")
                    session.delkey("character")
                    session.delkey("authorized")
                    session.set("semi_user", user.uuid)
                    session.store()
                self.call("web.response_json", {"ok": 1, "redirect": "/auth/activate/%s" % user.uuid})
        if not self.conf("auth.multicharing") and not self.conf("auth.cabinet"):
            # Looking for character
            chars = self.objlist(DBCharacterList, query_index="player", query_equal=user.uuid)
            if len(chars):
                restraints = {}
                self.call("restraints.check", chars[0].uuid, restraints)
                if restraints.get("ban"):
                    self.call("web.response_json", {"error": self._("You are banned till %s") % self.call("l10n.time_local", restraints["ban"]["till"])})
                session = req.session(True)
                self.call("stream.login", session.uuid, chars[0].uuid)
                self.call("web.response_json", {"ok": 1, "session": session.uuid})
            if self.conf("auth.allow-create-first-character"):
                self.call("web.response_json", {"error": self._("No characters assigned to this player")})
        # Entering cabinet
        self.call("stream.logout", session.uuid)
        with self.lock(["session.%s" % session.uuid]):
            try:
                session.load()
            except ObjectNotFoundException:
                pass
            if not session.get("user"):
                session.set("user", user.uuid)
                session.set("updated", self.now())
                session.delkey("semi_user")
                session.set("ip", req.remote_addr())
                session.store()
                self.call("session.log", act="login", session=session.uuid, ip=req.remote_addr(), user=user.uuid)
                self.call("web.response_json", {"ok": 1, "session": session.uuid})
        # Everything failed
        self.call("web.response_json", {"error": self._("Error logging in")})

    def admin_characters_online(self):
        rows = []
        vars = {
            "tables": [
                {
                    "header": [self._("Character"), self._("Session updated")],
                    "rows": rows
                }
            ]
        }
        lst = self.objlist(SessionList, query_index="authorized", query_equal="1")
        lst.load(silent=True)
        for sess in lst:
            character = self.character(sess.get("user"))
            rows.append([character.html("admin"), self.call("l10n.time_local", sess.get("updated"))])
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def characters_tech_online(self, lst):
        dblst = self.objlist(DBCharacterOnlineList, query_index="all")
        lst.extend([self.character(uuid) for uuid in dblst.uuids()])

    def appsession(self, session_uuid):
        app_tag = self.app().tag
        sess = self.main_app().obj(AppSession, "%s-%s" % (app_tag, session_uuid), silent=True)
        sess.set("app", app_tag)
        sess.set("session", session_uuid)
        return sess

    def stream_connected(self, session_uuid):
        logout_others = False
        with self.lock(["session.%s" % session_uuid]):
            session = self.obj(Session, session_uuid, silent=True)
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            character_uuid = appsession.get("character")
            if old_state == 3 and session.get("semi_user") == character_uuid:
                # went online after disconnection
                self.debug("Session %s went online after disconnection. State: %s => 2" % (session_uuid, old_state))
                appsession.set("state", 2)
                appsession.set("timeout", self.now(3600))
                appsession.set("character", character_uuid)
                # updating session
                session.set("user", character_uuid)
                session.set("character", 1)
                session.set("authorized", 1)
                session.set("updated", self.now())
                session.delkey("semi_user")
                # storing
                session.store()
                appsession.store()
                self.call("session.log", act="reconnect", session=session.uuid, user=character_uuid, ip=session.get("ip"))
                self.stream_character_online(character_uuid)
                logout_others = True
                self.call("session.character-init", session.uuid, self.character(character_uuid))
        if logout_others:
            self.logout_others(session_uuid, character_uuid)

    def stream_character_online(self, character_uuid):
        with self.lock(["Character.%s" % character_uuid]):
            try:
                self.obj(DBCharacterOnline, character_uuid)
            except ObjectNotFoundException:
                obj = self.obj(DBCharacterOnline, character_uuid, data={})
                obj.dirty = True
                obj.store()
                self.call("session.character-online", self.character(character_uuid))

    def stream_character_offline(self, character_uuid):
        with self.lock(["Character.%s" % character_uuid]):
            try:
                obj = self.obj(DBCharacterOnline, character_uuid)
            except ObjectNotFoundException:
                pass
            else:
                obj.remove()
                self.call("session.character-offline", self.character(character_uuid))

    def logout_others(self, except_session_uuid, character_uuid):
        # log out other character sessions depending on multicharing policy, except given session_uuid
        if self.conf("auth.multicharing", 0) < 2:
            # dropping all character of the player
            char = self.obj(DBCharacter, character_uuid)
            chars = self.objlist(DBCharacterList, query_index="player", query_equal=char.get("player"))
            characters = chars.uuids()
        else:
            # dropping just this character
            characters = [character_uuid]
        appsessions = self.main_app().objlist(AppSessionList, query_index="character", query_equal=characters)
        appsessions.load(silent=True)
        for appsession in appsessions:
            session_uuid = appsession.get("session")
            if session_uuid == except_session_uuid:
                continue
            with self.lock(["session.%s" % session_uuid]):
                try:
                    appsession.load()
                except ObjectNotFoundException:
                    pass
                else:
                    old_state = appsession.get("state")
                    if old_state == 1 or old_state == 2:
                        if old_state:
                            self.debug("Session %s logged out forced. State: %s => None" % (session_uuid, old_state))
                        try:
                            session = self.obj(Session, session_uuid)
                        except ObjectNotFoundException as e:
                            pass
                        else:
                            # updating session
                            user = session.get("user")
                            if user:
                                session.set("semi_user", user)
                                session.delkey("user")
                            session.delkey("character")
                            session.delkey("authorized")
                            session.set("updated", self.now())
                            # storing
                            session.store()
                    else:
                        self.debug("Session %s is timed out. Clearing it forced. State: %s => None" % (session_uuid, old_state))
                    appsession.remove()
                    # notifying session
                    self.call("stream.send", ["id_%s" % session_uuid], {"packets": [{"method_cls": "game", "method": "close"}]})

    def stream_ready(self):
        req = self.req()
        session = req.session()
        if not session or not session.get("user"):
            self.call("web.response_json", {"logged_out": 1})
        ok = False
        logout_others = False
        with self.lock(["session.%s" % session.uuid]):
            session.load()
            # updating appsession
            appsession = self.appsession(session.uuid)
            character_uuid = appsession.get("character")
            if character_uuid:
                old_state = appsession.get("state")
                went_online = old_state == 3
                if old_state != 2:
                    self.debug("Session %s connection is ready. State: %s => 2" % (session.uuid, old_state))
                appsession.set("state", 2)
                appsession.set("timeout", self.now(3600))
                appsession.set("character", character_uuid)
                # updating session
                session.set("user", character_uuid)
                session.set("character", 1)
                session.set("authorized", 1)
                if went_online:
                    session.set("updated", self.now())
                    session.set("ip", req.remote_addr())
                session.delkey("semi_user")
                # storing
                session.store()
                appsession.store()
                if went_online:
                    self.call("session.log", act="ready", session=session.uuid, ip=req.remote_addr(), user=character_uuid)
                    self.stream_character_online(character_uuid)
                    logout_others = True
                ok = True
        if logout_others:
            self.logout_others(session.uuid, character_uuid)
        if ok:
            self.call("web.response_json", {"ok": 1})
        else:
            self.call("web.response_json", {"offline": 1})

    def stream_disconnected(self, session_uuid):
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                return
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            if old_state == 2:
                # online session disconnected
                self.debug("Session %s disconnected. State: %s => 3" % (session_uuid, old_state))
                appsession.set("state", 3)
                appsession.set("timeout", self.now(3600))
                character_uuid = appsession.get("character")
                # updating session
                user = session.get("user")
                if user:
                    session.set("semi_user", user)
                    session.delkey("user")
                session.delkey("character")
                session.delkey("authorized")
                session.set("updated", self.now())
                # storing
                session.store()
                appsession.store()
                self.call("session.log", act="disconnect", session=session.uuid, user=character_uuid, ip=session.get("ip"))
                self.stream_character_offline(character_uuid)

    def stream_login(self, session_uuid, character_uuid):
        logout_others = False
        with self.lock(["session.%s" % session_uuid]):
            session = self.obj(Session, session_uuid, silent=True)
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            old_character = appsession.get("character")
            if old_state == 1 and appsession.get("updated") > self.now(-10) and old_character == character_uuid:
                # Game interface is loaded immediately after character login
                # There is no need to update AppSession too fast
                return
            # updating appsession
            went_online = not old_state or old_state == 3 or (old_character and character_uuid != old_character)
            went_offline = old_character and character_uuid != old_character and (old_state == 1 or old_state == 2)
            self.debug("Session %s logged in. State: %s => 1" % (session_uuid, old_state))
            appsession.set("state", 1)
            appsession.set("timeout", self.now(120))
            appsession.set("character", character_uuid)
            # updating session
            session.set("user", character_uuid)
            session.set("character", 1)
            session.set("authorized", 1)
            session.set("updated", self.now())
            session.delkey("semi_user")
            # storing
            session.store()
            appsession.store()
            if went_offline:
                self.call("session.log", act="logout", session=session.uuid, user=old_character, ip=session.get("ip"))
                self.stream_character_offline(old_character)
            if went_online:
                self.call("session.log", act="login", session=session.uuid, user=character_uuid, ip=session.get("ip"))
                self.stream_character_online(character_uuid)
            logout_others = True
        if logout_others:
            self.logout_others(session_uuid, character_uuid)

    def stream_logout(self, session_uuid):
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                return
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            went_offline = old_state == 1 or old_state == 2
            self.debug("Session %s logged out. State: %s => None" % (session_uuid, old_state))
            character_uuid = appsession.get("character")
            # updating session
            user = session.get("user")
            if user:
                session.set("semi_user", user)
                session.delkey("user")
            session.delkey("character")
            session.delkey("authorized")
            session.set("updated", self.now())
            # storing
            session.store()
            appsession.remove()
            if went_offline:
                self.call("session.log", act="logout", session=session.uuid, user=character_uuid, ip=session.get("ip"))
                self.stream_character_offline(character_uuid)

    def gameinterface_render(self, character, vars, design):
        req = self.req()
        session = req.session()
        # initializing stream
        stream_marker = uuid4().hex
        vars["js_init"].append("Stream.run_realplexor('%s', %d);" % (stream_marker, time.time() - 3))
        self.call("stream.send", "id_%s" % session.uuid, {"marker": stream_marker})
        vars["js_modules"].add("realplexor-stream")
        self.call("session.character-init", session.uuid, character)

    def auth_character(self):
        req = self.req()
        session = req.session()
        if not session or not session.get("user"):
            self.call("web.redirect", "/")
        player = self.player(session.get("user"))
        if player.valid:
            if req.args == "new":
                if not self.conf("auth.multicharing"):
                    self.call("web.not_found")
                if len(player.characters) >= self.conf("auth.max_chars", 5):
                    self.call("game.error", self._("You can't create more characters"))
                paid = len(player.characters) >= self.conf("auth.free_chars", 1)
                return self.new_character(player, paid=paid)
            character = self.character(req.args)
            if not character.valid:
                self.call("web.forbidden")
            if character.player.uuid != player.uuid:
                self.error("Hacking attempt. Player %s requested access to character %s", player.uuid, req.args)
                self.call("web.forbidden")
            if character.restraints.get("ban"):
                self.call("game.error", self._("You are banned till %s") % self.call("l10n.time_local", character.restraints["ban"]["till"]))
            self.call("stream.login", session.uuid, character.uuid)
        self.call("web.post_redirect", "/", {"session": session.uuid})

    def new_character(self, player, paid):
        req = self.req()
        session = req.session()
        form = self.call("web.form")
        # list of possible payers
        if paid:
            valid_payers = set()
            for char in player.characters:
                valid_payers.add(char.uuid)
            payer = req.param("payer")
            pay_price = self.conf("auth.multichar_price", 5)
            pay_currency = self.conf("auth.multichar_currency")
        # registragion form
        fields = self.character_form()
        fields = [fld for fld in fields if not fld.get("deleted") and fld.get("reg")]
        values = {}
        if req.ok():
            # auth params
            params = {}
            self.call("auth.form_params", params)
            # validating
            for fld in fields:
                code = fld["code"]
                val = req.param(code).strip()
                if fld.get("mandatory_level") and not val:
                    form.error(code, self._("This field is mandatory"))
                elif fld.get("std") == 1:
                    # character name. checking validity
                    if not re.match(params["name_re"], val, re.UNICODE):
                        form.error(code, params["name_invalid_re"])
                    elif self.call("session.find_user", val):
                        form.error(code, self._("This name is taken already"))
                elif fld.get("type") == 1:
                    if not val and not std and not fld.get("mandatory_level"):
                        # empty value is ok
                        val = None
                    else:
                        # checking acceptable values
                        ok = False
                        for v in fld["values"]:
                            if v[0] == val:
                                ok = True
                                break
                        if not ok:
                            form.error(code, self._("Make a valid selection"))
                values[code] = val
            captcha = req.param("captcha")
            if not captcha:
                form.error("captcha", self._("Enter numbers from the picture"))
            else:
                try:
                    cap = self.obj(Captcha, session.uuid)
                    if cap.get("number") != captcha:
                        form.error("captcha", self._("Incorrect number"))
                except ObjectNotFoundException:
                    form.error("captcha", self._("Incorrect number"))
            if not form.errors and paid:
                if not payer:
                    form.error("payer", self._("Select a payer"))
                else:
                    found = False
                    for char in player.characters:
                        if char.uuid == payer:
                            found = True
                            if not char.money.debit(pay_price, pay_currency, "multicharing", name=values["name"]):
                                form.error("payer", self.call("money.not-enough-funds", pay_currency, character=char))
                    if not found:
                        form.error("payer", self._("Select a valid payer"))
            if not form.errors:
                now = self.now()
                now_ts = "%020d" % time.time()
                # Creating new character
                character = self.obj(DBCharacter)
                character.set("created", now)
                character.set("player", player.uuid)
                character_user = self.obj(User, character.uuid, {})
                character_user.set("created", now_ts)
                character_user.set("last_login", now_ts)
                character_user.set("name", values["name"])
                character_user.set("name_lower", values["name"].lower())
                character_user.set("sex", intz(values["sex"]))
                if self.conf("auth.validate_names"):
                    character_user.set("check", 1)
                character_form = self.obj(DBCharacterForm, character.uuid, {})
                for fld in fields:
                    code = fld["code"]
                    if code == "name" or code == "sex":
                        continue
                    val = values.get(code)
                    if val is None:
                        continue
                    character_form.set(code, val)
                # Storing objects
                character.store()
                character_user.store()
                character_form.store()
                self.qevent("registered", char=self.character(character.uuid))
                self.call("session.log", act="register", session=session.uuid, ip=req.remote_addr(), user=character.uuid)
                # Entering game
                self.call("web.post_redirect", "/", {"session": session.uuid})
        vars = {
            "title": self._("Create a new character")
        }
        for field in fields:
            tp = field.get("type")
            if tp == 1:
                options = [{"value": v, "description": d} for v, d in field["values"]]
                form.select(field["name"], field["code"], values.get(field["code"]), options)
            elif tp == 2:
                form.textarea(field["name"], field["code"], values.get(field["code"]))
            else:
                form.input(field["name"], field["code"], values.get(field["code"]))
        form.input('<img id="captcha" src="/auth/captcha" alt="" /><br />' + self._('Enter a number (6 digits) from the picture'), "captcha", "")
        if paid:
            first = True
            for char in player.characters:
                kwargs = {}
                if first:
                    kwargs["description"] = self._("Registration of the next character will cost you {price}<br />Select a character who will pay for the registration").format(price=self.call("money.price-html", pay_price, pay_currency))
                    first = False
                balance = char.money.available(pay_currency)
                donate = self.call("money.donate-message", pay_currency, character=char)
                if donate:
                    donate = ' &mdash; %s' % donate
                form.radio(self._('{name} &mdash; balance {balance}{donate}').format(name=char.html(), balance=self.call("money.price-html", balance, pay_currency), donate=donate), "payer", char.uuid, payer, **kwargs)
        form.submit(None, None, self._("Create a character"))
        self.call("game.external_form", form, vars)

    def login_before_activate(self, redirect):
        self.call("game.error", self._('You are not logged in. <a href="/">Please login</a> and retry activation'))

    def player_activated(self):
        req = self.req()
        session = req.session()
        if not session:
            # missing cookie
            self.call("web.redirect", "/")
        if not session.get("user"):
            # not authorized
            self.call("web.redirect", "/")
        user = self.obj(User, session.get("user"))
        if user.get("player"):
            # character user
            self.call("web.redirect", "/")
        if user.get("inactive"):
            # activation
            self.call("web.redirect", "/auth/activate/%s" % user.uuid)
        # Everything is OK. Redirecting user to the game interface or to the cabinet
        chars = self.objlist(DBCharacterList, query_index="player", query_equal=user.uuid)
        if len(chars):
            restraints = {}
            self.call("restraints.check", chars[0].uuid, restraints)
            if restraints.get("ban"):
                self.call("game.error", self._("You are banned till %s") % self.call("l10n.time_local", restraints["ban"]["till"]))
            self.call("stream.login", session.uuid, chars[0].uuid)
        if self.conf("auth.allow-create-first-character"):
            self.call("game.error", self._("No characters assigned to this player"))
        self.call("web.post_redirect", "/", {"session": session.uuid})

    def ext_autologin(self):
        req = self.req()
        session = req.session(True)
        try:
            autologin = self.obj(AutoLogin, req.args)
        except ObjectNotFoundException:
            pass
        else:
            restraints = {}
            self.call("restraints.check", autologin.get("user"), restraints)
            if restraints.get("ban"):
                self.call("game.error", self._("You are banned till %s") % self.call("l10n.time_local", restraints["ban"]["till"]))
            self.info("Autologging in character %s", autologin.get("user"))
            self.call("stream.login", session.uuid, autologin.get("user"))
            autologin.remove()
        self.call("web.post_redirect", "/", {"session": session.uuid})

    def cleanup_inactive_users(self):
        raise Hooks.Return(None)

    def stream_character(self, character, method_cls, method, **kwargs):
        ids = ["id_%s" % sess_uuid for sess_uuid in character.sessions]
        if ids:
            self.call("stream.packet", ids, method_cls, method, **kwargs)

    def user_auth_table(self, user, table):
        req = self.req()
        if user.get("name"):
            # character
            character = self.character(user.uuid)
            player = character.player
            table["rows"].append(["char.id", user.uuid])
            table["rows"].append([self._("Player account"), '<hook:admin.link href="auth/user-dashboard/{0}?active_tab=auth" title="{0}" />'.format(player.uuid)])
        else:
            #player
            table["rows"].append(["char.player.id", user.uuid])
            dbchars = self.objlist(DBCharacterList, query_index="player", query_equal=user.uuid)
            chars = [self.character(char.uuid) for char in dbchars]
            table["rows"].extend([[self._("Character %s") % char.uuid, char.html("admin")] for char in chars])
            player = self.player(user.uuid)
            character = None

    def user_tables(self, user, tables):
        if user.get("name"):
            # Character user
            i = 0
            while i < len(tables):
                tbl = tables[i]
                if tbl.get("links"):
                    j = 0
                    links = tbl["links"]
                    while j < len(links):
                        link = links[j]
                        lid = link.get("id")
                        if lid == "chpass":
                            del links[j:j+1]
                            continue
                        elif lid == "tracking":
                            link["text"] = self._("Track character")
                        j += 1
                i += 1
        else:
            # Player user
            i = 0
            while i < len(tables):
                tbl = tables[i]
                tp = tbl.get("type")
                if tp == "money" or tp == "money_locks" or tp == "socio" or tp == "restraints" or tp == "dossier":
                    del tables[i:i+1]
                    continue
                if tbl.get("links"):
                    j = 0
                    links = tbl["links"]
                    while j < len(links):
                        link = links[j]
                        lid = link.get("id")
                        if lid == "chname" or lid == "perms":
                            del links[j:j+1]
                            continue
                        elif lid == "tracking":
                            link["hook"] = "auth/track/player/%s" % user.uuid
                            link["text"] = self._("Track player")
                        j += 1
                i += 1

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "auth-logout",
            "onclick": "Game.logout()",
            "icon": "auth-logout.png",
            "title": self._("Logout"),
            "block": "top-menu",
            "order": 100,
        })
        buttons.append({
            "id": "game-reload",
            "onclick": "Game.reload()",
            "icon": "game-reload.png",
            "title": self._("Reload"),
            "block": "top-menu",
            "order": 95,
        })
        buttons.append({
            "id": "game-admin",
            "href": "/admin",
            "target": "_blank",
            "icon": "game-admin.png",
            "title": self._("Administrative interface"),
            "block": "top-menu",
            "condition": [".", ["glob", "char"], "anyperm"],
            "order": 90,
        })
