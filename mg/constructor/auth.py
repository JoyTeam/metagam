from mg import *
from mg.constructor import *
import hashlib

class AppSession(CassandraObject):
    _indexes = {
        "timeout": [[], "timeout"],
        "character": [["character"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AppSession-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return AppSession._indexes

class AppSessionList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AppSession-"
        kwargs["cls"] = AppSession
        CassandraObjectList.__init__(self, *args, **kwargs)

class CharacterOnline(CassandraObject):
    _indexes = {
        "all": [[]]
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "CharacterOnline-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return CharacterOnline._indexes

class CharacterOnlineList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "CharacterOnline-"
        kwargs["cls"] = CharacterOnline
        CassandraObjectList.__init__(self, *args, **kwargs)

class Auth(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-users.index", self.menu_users_index)
        self.rhook("ext-admin-players.auth", self.admin_players_auth, priv="players.auth")
        self.rhook("headmenu-admin-players.auth", self.headmenu_players_auth)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-player.login", self.player_login, priv="public")
        self.rhook("auth.registered", self.auth_registered)
        self.rhook("auth.activated", self.auth_activated)
        self.rhook("ext-admin-characters.online", self.characters_online, priv="users.authorized")
        self.rhook("ext-auth.logout", self.ext_logout, priv="public", priority=10)
        self.rhook("ext-auth.login", (lambda self: None), priv="disabled", priority=10)
        self.rhook("session.character-online", self.character_online)
        self.rhook("session.character-offline", self.character_offline)
        self.rhook("stream.connected", self.stream_connected)
        self.rhook("stream.disconnected", self.stream_disconnected)
        self.rhook("stream.login", self.stream_login)
        self.rhook("stream.logout", self.stream_logout)
        self.rhook("ext-stream.ready", self.stream_ready, priv="public")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("session.require_login", self.require_login, priority=10)

    def require_login(self):
        session = self.call("session.get")
        if not session or not session.get("user"):
            self.call("indexpage.error", self._("To access this page enter the game first"))
        return session

    def auth_registered(self, user):
        req = self.req()
        project = self.app().project
        if not project.get("admin_confirmed") and project.get("domain") and req.has_access("project.admin"):
            project.set("admin_confirmed", True)
            project.store()
            self.app().store_config_hooks()

    def auth_activated(self, user, redirect):
        req = self.req()
        self.info("auth.activated: user=%s", user.uuid)
        session = self.call("session.get", True)
        chars = self.objlist(CharacterList, query_index="player", query_equal=user.uuid)
        chars.load(silent=True)
        admin = False
        if len(chars):
            with self.lock(["session.%s" % session.uuid]):
                session.load()
                session.set("user", chars[0].uuid)
                session.set("character", 1)
                session.set("authorized", 1)
                session.set("updated", self.now())
                session.delkey("semi_user")
                session.store()
            if chars[0].get("admin"):
                admin = True
        else:
            self.error("auth.activated(%s) called but no associated characters found", user.uuid)
        # redirect
        if redirect is not None and redirect != "":
            self.call("web.redirect", redirect)
        redirects = {}
        self.call("auth.redirects", redirects)
        if redirects.has_key("register"):
            self.call("web.redirect", redirects["register"])
        user = self.obj(User, req.user())
        if admin:
            self.call("web.redirect", "/admin")
        self.call("web.redirect", "/")

    def objclasses_list(self, objclasses):
        objclasses["AppSession"] = (AppSession, AppSessionList)
        objclasses["CharacterOnline"] = (CharacterOnline, CharacterOnlineList)

    def permissions_list(self, perms):
        perms.append({"id": "players.auth", "name": self._("Players authentication settings")})
        perms.append({"id": "users.authorized", "name": self._("Viewing list of authorized users")})

    def menu_users_index(self, menu):
        req = self.req()
        if req.has_access("players.auth"):
            menu.append({"id": "players/auth", "text": self._("Players authentication"), "leaf": True, "order": 10})
        if req.has_access("users.authorized"):
            menu.append({"id": "characters/online", "text": self._("List of characters online"), "leaf": True, "order": 30})

    def headmenu_players_auth(self, args):
        return self._("Players authentication settings")

    def admin_players_auth(self):
        req = self.req()
        config = self.app().config
        currencies = {}
        self.call("currencies.list", currencies)
        if req.param("ok"):
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
                        if max_chars < 1:
                            errors["max_chars"] = self._("Minimal value is 1")
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
                # cabinet
                config.set("auth.cabinet", True if req.param("cabinet") else False)
            # email activation
            activate_email = True if req.param("activate_email") else False
            config.set("auth.activate_email", activate_email)
            if activate_email:
                activate_email_level = req.param("activate_email_level")
                if not valid_nonnegative_int(activate_email_level):
                    errors["activate_email_level"] = self._("Invalid number")
                else:
                    activate_email_level = int(activate_email_level)
                    config.set("auth.activate_email_level", activate_email_level)
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
            multicharing = config.get("auth.multicharing", 0)
            free_chars = config.get("auth.free_chars", 1)
            max_chars = config.get("auth.max_chars", 5)
            multichar_price = config.get("auth.multichar_price", 5)
            multichar_currency = config.get("auth.multichar_currency")
            cabinet = config.get("auth.cabinet", 0)
            activate_email = config.get("auth.activate_email", True)
            activate_email_level = config.get("auth.activate_email_level", 0)
            activate_email_days = config.get("auth.activate_email_days", 7)
            validate_names = config.get("auth.validate_names", False)
        fields = [
            {"name": "multicharing", "type": "combo", "label": self._("Are players allowed to play more than 1 character"), "value": multicharing, "values": [(0, self._("No")), (1, self._("Yes, but play them by turn")), (2, self._("Yes, play them simultaneously"))] },
            {"name": "free_chars", "label": self._("Number of characters per player allowed for free"), "value": free_chars, "condition": "[multicharing]>0" },
            {"name": "max_chars", "label": self._("Maximal number of characters per player allowed"), "value": max_chars, "inline": True, "condition": "[multicharing]>0" },
            {"name": "multichar_price", "label": self._("Price for one extra character over free limit"), "value": multichar_price, "condition": "[multicharing]>0 && [max_chars]>[free_chars]" },
            {"name": "multichar_currency", "label": self._("Currency"), "type": "combo", "value": multichar_currency, "values": [(code, info["description"]) for code, info in currencies.iteritems()], "allow_blank": True, "condition": "[multicharing]>0 && [max_chars]>[free_chars]", "inline": True},
            {"name": "cabinet", "type": "combo", "label": self._("Login sequence"), "value": cabinet, "condition": "![multicharing]", "values": [(0, self._("Enter the game immediately after login")), (1, self._("Open player cabinet after login"))]},
            {"name": "activate_email", "type": "checkbox", "label": self._("Require email activation"), "checked": activate_email},
            {"name": "activate_email_level", "label": self._("Activation is required after this character level ('0' if require on registration)"), "value": activate_email_level, "condition": "[activate_email]"},
            {"name": "activate_email_days", "label": self._("Activation is required after this number of days ('0' if require on registration)"), "value": activate_email_days, "inline": True, "condition": "[activate_email]"},
            {"name": "validate_names", "type": "checkbox", "label": self._("Manual validation of every character name"), "checked": validate_names},
        ]
        self.call("admin.form", fields=fields)

    def ext_logout(self):
        session = self.call("session.get")
        if session is not None:
            self.call("stream.logout", session.uuid)
        req = self.req()
        redirect = req.param("redirect")
        if redirect:
            self.call("web.redirect", redirect)
        self.call("web.redirect", "/")

    def player_login(self):
        req = self.req()
        name = req.param("email")
        password = req.param("password")
        msg = {}
        self.call("auth.messages", msg)
        if not name:
            self.call("web.response_json", {"error": msg["name_empty"]})
        user = self.call("session.find_user", name, allow_email=True)
        if user is None:
            self.call("web.response_json", {"error": msg["name_unknown"]})
        if user.get("name"):
            # character user
            character = self.obj(Character, user.uuid)
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
#        if user.get("inactive"):
#            self.call("web.response_json", {"error": msg["user_inactive"]})
        # acquiring character user
        chars = self.objlist(CharacterList, query_index="player", query_equal=user.uuid)
        if len(chars):
            session = self.call("session.get", True)
            self.call("stream.login", session.uuid, chars[0].uuid)
            self.call("web.response_json", {"ok": 1, "session": session.uuid})
        self.call("web.response_json", {"error": self._("No characters assigned to this player")})

    def characters_online(self):
        rows = []
        vars = {
            "tables": [
                {
                    "header": [self._("Session"), self._("Character"), self._("Online"), self._("Updated")],
                    "rows": rows
                }
            ]
        }
        lst = self.objlist(SessionList, query_index="authorized", query_equal="1")
        lst.load(silent=True)
        for sess in lst:
            rows.append([sess.uuid, sess.get("user"), sess.get("online"), sess.get("updated")])
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def character_online(self, character_uuid):
        user = self.obj(User, character_uuid)
        self.call("stream.send", ["global"], {"packets": [{"cls": "chat", "method": "msg", "html": self._("%s online") % htmlescape(user.get("name"))}]})

    def character_offline(self, character_uuid):
        user = self.obj(User, character_uuid)
        self.call("stream.send", ["global"], {"packets": [{"cls": "chat", "method": "msg", "html": self._("%s offline") % htmlescape(user.get("name"))}]})

    def appsession(self, session_uuid):
        app_tag = self.app().tag
        sess = self.main_app().obj(AppSession, "%s-%s" % (app_tag, session_uuid), silent=True)
        sess.set("app", app_tag)
        sess.set("session", session_uuid)
        return sess

    def stream_connected(self, session_uuid):
        logout_others = False
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                self.exception(e)
                return
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            character_uuid = appsession.get("character")
            if old_state == 3 and session.get("semi_user") == character_uuid:
                # went online after disconnection
                self.debug("Session %s went online after disconnection. State: %s => 2" % (session_uuid, old_state))
                appsession.set("state", 2)
                appsession.set("timeout", self.now(3600))
                # updating session
                session.set("user", character_uuid)
                session.set("character", 1)
                session.set("authorized", 1)
                session.set("updated", self.now())
                session.delkey("semi_user")
                # storing
                session.store()
                appsession.store()
                self.stream_character_online(character_uuid)
                logout_others = True
        if logout_others:
            self.logout_others(session_uuid, character_uuid)

    def stream_character_online(self, character_uuid):
        with self.lock(["character.%s" % character_uuid]):
            try:
                self.obj(CharacterOnline, character_uuid)
            except ObjectNotFoundException:
                obj = self.obj(CharacterOnline, character_uuid, data={})
                obj.dirty = True
                obj.store()
                self.call("session.character-online", character_uuid)

    def stream_character_offline(self, character_uuid):
        with self.lock(["character.%s" % character_uuid]):
            try:
                obj = self.obj(CharacterOnline, character_uuid)
            except ObjectNotFoundException:
                pass
            else:
                obj.remove()
                self.call("session.character-offline", character_uuid)

    def logout_others(self, except_session_uuid, character_uuid):
        # log out other character sessions depending on multicharing policy, except given session_uuid
        if self.conf("auth.multicharing", 0) < 2:
            # dropping all character of the player
            char = self.obj(Character, character_uuid)
            chars = self.objlist(CharacterList, query_index="player", query_equal=char.get("player"))
            characters = chars.uuids()
        else:
            # dropping just this character
            characters = [character_uuid]
        self.debug("Dropping other sessions for characters %s", characters)
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
                    self.debug("Dropping session %s" % session_uuid)
                    old_state = appsession.get("state")
                    if old_state == 1 or old_state == 2:
                        self.debug("Session %s logged out forced. State: %s => None" % (session_uuid, old_state))
                        try:
                            session = self.obj(Session, session_uuid)
                        except ObjectNotFoundException as e:
                            self.exception(e)
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
                    self.call("stream.send", ["id_%s" % session_uuid], {"packets": [{"cls": "game", "method": "close"}]})

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
                session.delkey("semi_user")
                # storing
                session.store()
                appsession.store()
                if went_online:
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
                self.exception(e)
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
                self.stream_character_offline(character_uuid)

    def stream_login(self, session_uuid, character_uuid):
        logout_others = False
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                self.exception(e)
                return
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
                self.stream_character_offline(old_character)
            if went_online:
                self.stream_character_online(character_uuid)
            logout_others = True
        if logout_others:
            self.logout_others(session_uuid, character_uuid)

    def stream_logout(self, session_uuid):
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                self.exception(e)
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
                self.stream_character_offline(character_uuid)

    def gameinterface_render(self, vars, design):
        req = self.req()
        session = req.session()
        # initializing stream
        stream_marker = uuid4().hex
        vars["stream_marker"] = stream_marker
        self.call("stream.send", "id_%s" % session.uuid, {"marker": stream_marker})
        vars["js_modules"].add("realplexor-stream")
        vars["js_init"].append("Stream.run_realplexor('%s');" % stream_marker)

class AuthAdmin(Module):
    def register(self):
        Module.register(self)
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
                                self.exception(e)
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
                                    session.delkey("character")
                                    session.delkey("authorized")
                                    session.set("updated", self.now())
                                    # storing
                                    session.store()
                                    appsession.store()
                                    # character offline on timeout
                                    with app.lock(["character.%s" % character_uuid]):
                                        try:
                                            obj = app.obj(CharacterOnline, character_uuid)
                                        except ObjectNotFoundException:
                                            pass
                                        else:
                                            obj.remove()
                                            app.hooks.call("session.character-offline", character_uuid)
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

