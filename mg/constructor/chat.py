from mg import *
from mg.constructor import *
import datetime
import re

old_messages_limit = 10
old_private_messages_limit = 100

re_chat_characters = re.compile(r'\[(chf|cht|ch):([a-f0-9]{32})\]')
re_chat_command = re.compile(r'^\s*/(\S+)\s*(.*)')
re_chat_recipient = re.compile(r'^\s*(to|private)\s*\[([^\]]+)\]\s*(.*)$')
re_loc_channel = re.compile(r'^loc-(\S+)$')
re_valid_command = re.compile(r'^/(\S+)$')
re_after_dash = re.compile(r'-.*')
re_unjoin = re.compile(r'^unjoin/(\S+)$')
re_character_name = re.compile(r'(<span class="char-name">.*?</span>)')

class DBChatMessage(CassandraObject):
    "This object is created when the character is online and joined corresponding channel"
    _indexes = {
        "created": [[], "created"],
        "channel": [["channel"], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ChatMessage-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBChatMessage._indexes

class DBChatMessageList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ChatMessage-"
        kwargs["cls"] = DBChatMessage
        CassandraObjectList.__init__(self, *args, **kwargs)

class DBChatChannelCharacter(CassandraObject):
    "This object is created when the character is online and joined corresponding channel"
    _indexes = {
        "channel": [["channel"]],
        "character": [["character"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ChatChannelCharacter-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBChatChannelCharacter._indexes

class DBChatChannelCharacterList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ChatChannelCharacter-"
        kwargs["cls"] = DBChatChannelCharacter
        CassandraObjectList.__init__(self, *args, **kwargs)

class DBChatDebug(CassandraObject):
    "This object is created when the character is online and joined corresponding channel"
    _indexes = {
        "all": [[]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ChatDebug-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBChatDebug._indexes

class DBChatDebugList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ChatDebug-"
        kwargs["cls"] = DBChatDebug
        CassandraObjectList.__init__(self, *args, **kwargs)

class Chat(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("menu-admin-chat.index", self.menu_chat_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-chat.config", self.headmenu_chat_config)
        self.rhook("ext-admin-chat.config", self.chat_config, priv="chat.config")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("admin-gameinterface.design-files", self.gameinterface_advice_files)
        self.rhook("ext-chat.post", self.post, priv="logged")
        self.rhook("chat.message", self.message)
        self.rhook("session.character-online", self.character_online)
        self.rhook("session.character-offline", self.character_offline)
        self.rhook("session.character-init", self.character_init)
        self.rhook("chat.channel-info", self.channel_info)
        self.rhook("chat.channel-join", self.channel_join)
        self.rhook("chat.channel-unjoin", self.channel_unjoin)
        self.rhook("objclasses.list", self.objclasses_list)
        if self.conf("chat.debug-channel"):
            self.rhook("headmenu-admin-chat.debug", self.headmenu_chat_debug)
            self.rhook("ext-admin-chat.debug", self.chat_debug, priv="chat.config")
        self.rhook("chat.character-channels", self.character_channels)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("locations.character_before_set", self.location_before_set)
        self.rhook("locations.character_after_set", self.location_after_set)
        self.rhook("interface.settings-form", self.settings_form)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("chat.cleanup", self.cleanup)
        self.rhook("characters.name-purposes", self.name_purposes)
        self.rhook("characters.name-purpose-chat", self.name_purpose_chat)
        self.rhook("characters.name-purpose-roster", self.name_purpose_roster)
        self.rhook("characters.name-fixup", self.name_fixup)

    def name_purpose_chat(self):
        return {"id": "chat", "title": self._("Chat"), "order": 10, "default": "[{NAME}]"}

    def name_purpose_roster(self):
        return {"id": "roster", "title": self._("Roster"), "order": 20, "default": "{NAME} {INFO}"}

    def name_purposes(self, purposes):
        purposes.append(self.name_purpose_chat())
        purposes.append(self.name_purpose_roster())

    def name_fixup(self, character, purpose, params):
        if purpose == "roster":
            js = "Chat.click(['%s']); return false" % jsencode(character.name)
            params["NAME"] = ur'<span class="chat-roster-char chat-clickable" onclick="{0}" ondblclick="{0}">{1}</span>'.format(js, params["NAME"])

    def schedule(self, sched):
        sched.add("chat.cleanup", "10 1 * * *", priority=10)

    def cleanup(self):
        msgs = self.objlist(DBChatMessageList, query_index="created", query_finish=self.now(-86400))
        msgs.remove()

    def location_before_set(self, character, new_location, instance):
        msg = self.msg_entered_location()
        if msg:
            self.call("chat.message", html=self.call("quest.format_text", msg, character=character, location=character.location), channel="loc-%s" % new_location.uuid, cls="move")

    def location_after_set(self, character, old_location, instance):
        msg = self.msg_left_location()
        if msg:
            self.call("chat.message", html=self.call("quest.format_text", msg, character=character, location=character.location), channel="loc-%s" % old_location.uuid, cls="move")
        self.call("stream.character", character, "chat", "clear_loc")
        # old messages
        msgs = self.objlist(DBChatMessageList, query_index="channel", query_equal="loc-%s" % character.location.uuid, query_reversed=True, query_limit=old_messages_limit)
        msgs.load(silent=True)
        if len(msgs):
            msg = self.msg_location_messages()
            if msg:
                self.call("stream.character", character, "chat", "current_location", html=self.call("quest.format_text", msg, character=character, location=character.location), scroll_disable=True)
            messages = [{
                "channel": "loc",
                "cls": msg.get("cls"),
                "html": msg.get("html"),
            } for msg in reversed(msgs)]
            self.call("stream.character", character, "chat", "msg_list", messages=messages, scroll_disable=True)
        # current location message
        msg = self.msg_you_entered_location()
        if msg:
            self.call("stream.character", character, "chat", "current_location", html=self.call("quest.format_text", msg, character=character, location=character.location), scroll_disable=True)
        self.call("stream.character", character, "chat", "scroll_bottom")

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "roster-clear",
            "onclick": "Chat.clear()",
            "icon": "roster-clear.png",
            "title": self._("Clear chat"),
            "block": "roster-buttons-menu",
            "order": 10,
        })
        if self.call("l10n.lang") == "ru":
            buttons.append({
                "id": "roster-translit",
                "onclick": "Chat.translit()",
                "icon": "roster-translit-off.png",
                "icon2": "roster-translit-on.png",
                "title": self._("Transliteration"),
                "block": "roster-buttons-menu",
                "order": 15,
            })

    def objclasses_list(self, objclasses):
        objclasses["ChatChannelCharacter"] = (DBChatChannelCharacter, DBChatChannelCharacterList)
        objclasses["ChatDebug"] = (DBChatDebug, DBChatDebugList)

    def menu_socio_index(self, menu):
        menu.append({"id": "chat.index", "text": self._("Chat"), "order": 5})

    def menu_chat_index(self, menu):
        req = self.req()
        if req.has_access("chat.config"):
            menu.append({"id": "chat/config", "text": self._("Chat configuration"), "leaf": True, "order": 10})
            if self.conf("chat.debug-channel"):
                menu.append({"id": "chat/debug", "text": self._("Debug chat channel"), "leaf": True, "order": 11})

    def permissions_list(self, perms):
        perms.append({"id": "chat.config", "name": self._("Chat configuration editor")})
        self.call("permissions.chat", perms)

    def headmenu_chat_config(self, args):
        return self._("Chat configuration")

    def chat_config(self):
        req = self.req()
        if req.param("ok"):
            config = self.app().config_updater()
            errors = {}
            location_separate = True if req.param("location-separate") else False
            config.set("chat.location-separate", location_separate)
            debug_channel = True if req.param("debug-channel") else False
            config.set("chat.debug-channel", debug_channel)
            trade_channel = True if req.param("trade-channel") else False
            config.set("chat.trade-channel", trade_channel)
            diplomacy_channel = True if req.param("diplomacy-channel") else False
            config.set("chat.diplomacy-channel", diplomacy_channel)
            # chatmode
            chatmode = intz(req.param("v_chatmode"))
            if chatmode < 0 or chatmode > 2:
                errors["chatmode"] = self._("Invalid selection")
            else:
                config.set("chat.channels-mode", chatmode)
            # channel selection commands
            if chatmode > 0:
                cmd_wld = req.param("cmd-wld")
                if cmd_wld != "":
                    m = re_valid_command.match(cmd_wld)
                    if m:
                        config.set("chat.cmd-wld", m.group(1))
                    else:
                        errors["cmd-wld"] = self._("Chat command must begin with / and must not contain whitespace characters")
                else:
                    config.set("chat.cmd-wld", "")
                cmd_loc = req.param("cmd-loc")
                if cmd_loc != "":
                    m = re_valid_command.match(cmd_loc)
                    if m:
                        config.set("chat.cmd-loc", m.group(1))
                    else:
                        errors["cmd-loc"] = self._("Chat command must begin with / and must not contain whitespace characters")
                else:
                    config.set("chat.cmd-loc", "")
                if trade_channel:
                    cmd_trd = req.param("cmd-trd")
                    if cmd_trd != "":
                        m = re_valid_command.match(cmd_trd)
                        if m:
                            config.set("chat.cmd-trd", m.group(1))
                        else:
                            errors["cmd-trd"] = self._("Chat command must begin with / and must not contain whitespace characters")
                    else:
                        config.set("chat.cmd-trd", "")
                if diplomacy_channel:
                    cmd_dip = req.param("cmd-dip")
                    if cmd_dip != "":
                        m = re_valid_command.match(cmd_dip)
                        if m:
                            config.set("chat.cmd-dip", m.group(1))
                        else:
                            errors["cmd-dip"] = self._("Chat command must begin with / and must not contain whitespace characters")
                    else:
                        config.set("chat.cmd-dip", "")
            # chat messages
            config.set("chat.msg_went_online", req.param("msg_went_online"))
            config.set("chat.msg_went_offline", req.param("msg_went_offline"))
            config.set("chat.msg_entered_location", req.param("msg_entered_location"))
            config.set("chat.msg_left_location", req.param("msg_left_location"))
            config.set("chat.msg_you_entered_location", req.param("msg_you_entered_location"))
            config.set("chat.msg_location_messages", req.param("msg_location_messages"))
            config.set("chat.auth-msg-channel", "wld" if req.param("auth_msg_channel") else "loc")
            # analysing errors
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Chat configuration stored"), {})
        else:
            location_separate = self.conf("chat.location-separate")
            debug_channel = self.conf("chat.debug-channel")
            trade_channel = self.conf("chat.trade-channel")
            diplomacy_channel = self.conf("chat.diplomacy-channel")
            chatmode = self.chatmode
            cmd_wld = self.cmd_wld()
            if cmd_wld != "":
                cmd_wld = "/%s" % cmd_wld
            cmd_loc = self.cmd_loc()
            if cmd_loc != "":
                cmd_loc = "/%s" % cmd_loc
            cmd_trd = self.cmd_trd()
            if cmd_trd != "":
                cmd_trd = "/%s" % cmd_trd
            cmd_dip = self.cmd_dip()
            if cmd_dip != "":
                cmd_dip = "/%s" % cmd_dip
            msg_went_online = self.msg_went_online()
            msg_went_offline = self.msg_went_offline()
            msg_entered_location = self.msg_entered_location()
            msg_left_location = self.msg_left_location()
            msg_you_entered_location = self.msg_you_entered_location()
            msg_location_messages = self.msg_location_messages()
            auth_msg_channel = self.auth_msg_channel()
        fields = [
            {"name": "chatmode", "label": self._("Chat channels mode"), "type": "combo", "value": chatmode, "values": [(0, self._("Channels disabled")), (1, self._("Every channel on a separate tab")), (2, self._("Channel selection checkboxes"))]},
            {"name": "location-separate", "type": "checkbox", "label": self._("Location chat is separated from the main channel"), "checked": location_separate, "condition": "[chatmode]>0"},
            {"name": "debug-channel", "type": "checkbox", "label": self._("Debugging channel enabled"), "checked": debug_channel, "condition": "[chatmode]>0"},
            {"name": "trade-channel", "type": "checkbox", "label": self._("Trading channel enabled"), "checked": trade_channel, "condition": "[chatmode]>0"},
            {"name": "diplomacy-channel", "type": "checkbox", "label": self._("Diplomacy channel enabled"), "checked": diplomacy_channel, "condition": "[chatmode]>0"},
            {"name": "cmd-wld", "label": self._("Chat command for writing to the entire world channel"), "value": cmd_wld, "condition": "[chatmode]>0"},
            {"name": "cmd-loc", "label": self._("Chat command for writing to the current location channel"), "value": cmd_loc, "condition": "[chatmode]>0"},
            {"name": "cmd-trd", "label": self._("Chat command for writing to the trading channel"), "value": cmd_trd, "condition": "[chatmode]>0 && [trade-channel]"},
            {"name": "cmd-dip", "label": self._("Chat command for writing to the trading channel"), "value": cmd_dip, "condition": "[chatmode]>0 && [diplomacy-channel]"},
            {"name": "auth_msg_channel", "label": self._("Should online/offline messages be visible worldwide"), "type": "checkbox", "checked": auth_msg_channel=="wld"},
            {"name": "msg_went_online", "label": self._("Message about character went online"), "value": msg_went_online},
            {"name": "msg_went_offline", "label": self._("Message about character went offline"), "value": msg_went_offline},
            {"name": "msg_entered_location", "label": self._("Message about character entered location"), "value": msg_entered_location},
            {"name": "msg_left_location", "label": self._("Message about character left location"), "value": msg_left_location},
            {"name": "msg_you_entered_location", "label": self._("Message about your character entered location"), "value": msg_you_entered_location},
            {"name": "msg_location_messages", "label": self._("Message heading messages from new location"), "value": msg_location_messages},
        ]
        self.call("admin.form", fields=fields)

    def auth_msg_channel(self, character=None):
        channel = self.conf("chat.auth-msg-channel", "loc")
        if channel == "loc" and character:
            channel = "loc-%s" % (character.location.uuid if character.location else None)
        return channel

    @property
    def chatmode(self):
        try:
            return self._chatmode
        except AttributeError:
            self._chatmode = self.conf("chat.channels-mode", 1)
            return self._chatmode

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("chat")
        vars["js_init"].append("Chat.initialize();")
#        # list of channels
#        channels = []
#        self.call("chat.character-channels", character, channels)
#        for ch in channels:
#            if re_loc_channel.match(ch["id"]):
#                ch["id"] = "loc"
        chatmode = self.chatmode
        vars["js_init"].append("Chat.mode = %d;" % chatmode)
        if chatmode:
            vars["layout"]["chat_channels"] = True
        move = "true" if character.db_settings.get("chat_move", True) else "false"
        auth = "true" if character.db_settings.get("chat_auth", True) else "false"
        vars["js_init"].append("Chat.filters({move: %s, auth: %s});" % (move, auth));

    def gameinterface_advice_files(self, files):
        chatmode = self.chatmode
        channels = []
        self.call("chat.character-channels", None, channels)
        if len(channels) >= 2:
            for ch in channels:
                if ch.get("chatbox") or ch.get("switchable"):
                    files.append({"filename": "chat-%s-off.png" % ch["id"], "description": self._("Chat channel '%s' disabled") % ch["title"]})
                    files.append({"filename": "chat-%s-on.png" % ch["id"], "description": self._("Chat channel '%s' enabled") % ch["title"]})
                    files.append({"filename": "chat-%s-new.png" % ch["id"], "description": self._("Chat channel '%s' has new messages") % ch["title"]})
            files.append({"filename": "chat-channel-button-on.png", "description": self._("Chat channel button template: state ON")})
            files.append({"filename": "chat-channel-button-off.png", "description": self._("Chat channel button template: state OFF")})
            files.append({"filename": "chat-channel-button-new.png", "description": self._("Chat channel button template: state NEW")})

    def cmd_loc(self):
        return self.conf("chat.cmd-loc", "loc")

    def cmd_wld(self):
        return self.conf("chat.cmd-wld", "wld")

    def cmd_trd(self):
        return self.conf("chat.cmd-trd", "trd")

    def cmd_dip(self):
        return self.conf("chat.cmd-dip", "dip")

    def post(self):
        req = self.req()
        user = req.user()
        limits = {}
        self.call("limits.check", user, limits)
        if limits.get("chat-silence"):
            self.call("web.response_json", {"error": self._("Silence till %s") % self.call("l10n.timeencode2", limits["chat-silence"].get("till")), "hide_title": True})
        author = self.character(user)
        text = req.param("text") 
        prefixes = []
        prefixes.append("[chf:%s] " % user)
        channel = req.param("channel")
        if channel == "sys" or channel == "":
            if self.conf("chat.location-separate"):
                channel = "wld"
            else:
                channel = "loc"
        # extracting commands
        while True:
            m = re_chat_command.match(text)
            if not m:
                break
            cmd, text = m.group(1, 2)
            if cmd == self.cmd_loc():
                channel = "loc"
            elif cmd == self.cmd_wld():
                channel = "wld"
            elif cmd == self.cmd_trd() and self.conf("chat.trade-channel"):
                channel = "trd"
            elif cmd == self.cmd_dip() and self.conf("chat.diplomacy-channel"):
                channel = "dip"
            elif cmd == "empty":
                self.call("stream.character", author, "game", "main_open", uri="http://%s/empty" % self.app().canonical_domain)
                self.call("web.response_json", {"ok": True})
            else:
                self.call("web.response_json", {"error": self._("Unrecognized command: /%s") % htmlescape(cmd)})
        # extracting recipients
        private = False
        recipient_names = []
        while True:
            m = re_chat_recipient.match(text)
            if not m:
                break
            mode, name, text = m.group(1, 2, 3)
            if mode == "private":
                private = True
            if not name in recipient_names:
                recipient_names.append(name)
        # searching recipient names
        recipients = []
        for name in recipient_names:
            char = self.find_character(name)
            if not char:
                self.call("web.response_json", {"error": self._("Character '%s' not found") % htmlescape(name)})
            if private:
                prefixes.append("private [cht:%s] " % char.uuid)
            else:
                prefixes.append("to [cht:%s] " % char.uuid)
            recipients.append(char)
        if author not in recipients:
            recipients.append(author)
        # access control
        if channel == "wld" or channel == "loc":
            pass
        elif channel == "trd" and self.conf("chat.trade-channel"):
            pass
        elif channel == "dip" and self.conf("chat.diplomacy-channel"):
            pass
        elif channel == "dbg" and self.conf("chat.debug-channel") and self.debug_access(author):
            pass
        else:
            self.call("web.response_json", {"error": self._("No access to the '%s' chat channel") % htmlescape(channel)})
        # translating channel name
        if channel == "loc":
            character = self.character(user)
            channel = "loc-%s" % (character.location.uuid if character.location else None)
        # formatting html
        tokens = [{"text": text}]
        self.call("chat.parse", tokens)
        html = u'{0}<span class="chat-msg-body">{1}</span>'.format("".join(prefixes), "".join(token["html"] if "html" in token else htmlescape(token["text"]) for token in tokens))
        # sending message
        self.call("chat.message", html=html, channel=channel, recipients=recipients, private=private, author=author, manual=True, hl=True)
        self.call("web.response_json", {"ok": True, "channel": self.channel2tab(channel)})

    def message(self, html=None, hide_time=False, channel=None, private=None, recipients=None, author=None, sound=None, manual=None, **kwargs):
        try:
            req = self.req()
        except AttributeError:
            req = None
        # channel
        if not channel:
            channel = "sys"
        # translate channel name
        if channel == "sys":
            viewers = None
        else:
            # preparing list of characters to receive
            characters = []
            if private:
                characters = recipients
            elif channel == "wld" or channel == "trd" or channel == "dip":
                characters = self.characters.tech_online
            else:
                lst = self.objlist(DBChatChannelCharacterList, query_index="channel", query_equal=channel)
                character_uuids = [re_after_dash.sub('', uuid) for uuid in lst.uuids()]
                characters = [self.character(uuid) for uuid in character_uuids]
            # loading list of sessions corresponding to the characters
            sessions = self.objlist(SessionList, query_index="authorized-user", query_equal=["1-%s" % char.uuid for char in characters])
            # loading list of characters able to view the message
            viewers = {}
            for char_uuid, sess_uuid in sessions.index_values(2):
                try:
                    viewers[char_uuid].append(sess_uuid)
                except KeyError:
                    viewers[char_uuid] = [sess_uuid]
        tokens = []
        mentioned_uuids = set()         # characters uuids mentioned in the message
        mentioned = set()               # characters mentioned in the message
        # time
        sysnow = self.now()
        if not hide_time:
            now = time_to_human(self.now_local())
            tokens.append({"time": now, "mentioned": mentioned})
        # replacing character tags [chf:UUID], [cht:UUID], [ch:UUID] etc
        start = 0
        for match in re_chat_characters.finditer(html):
            match_start, match_end = match.span()
            if match_start > start:
                tokens.append({"html": html[start:match_start]})
            start = match_end
            tp, character = match.group(1, 2)
            mentioned_uuids.add(character)
            character = self.character(character)
            mentioned.add(character)
            if tp == "chf" or tp == "cht" or tp == "ch":
                token = {"character": character, "mentioned": mentioned, "type": tp}
                if tp != "ch" and viewers is not None and character.uuid not in viewers:
                    token["missing"] = True
                tokens.append(token)
        if len(html) > start:
            tokens.append({"html": html[start:]})
        message = kwargs
        message["channel"] = self.channel2tab(channel)
        message["priv"] = private
        html_head = u''
        html_tail = u''
        if viewers is not None:
            # enumerating all recipients and preparing HTML version of the message for everyone
            universal = []
            messages = []
            for char_uuid, sessions in viewers.iteritems():
                if char_uuid in mentioned_uuids:
                    # make specific HTML for this character
                    html = u''.join([self.render_token(token, char_uuid, private) for token in tokens])
                    messages.append((["id_%s" % sess_uuid for sess_uuid in sessions], html))
                else:
                    # these sessions need universal HTML
                    universal.extend(sessions)
            if manual or universal:
                # generating universal HTML
                html = u''.join([self.render_token(token, None, private) for token in tokens])
                # store chat message
                if manual:
                    if private:
                        for char in recipients:
                            dbmsg = self.obj(DBChatMessage)
                            dbmsg.set("created", sysnow)
                            dbmsg.set("channel", "char-%s" % char.uuid)
                            dbmsg.set("real_channel", channel)
                            dbmsg.set("html", html)
                            dbmsg.set("priv", True)
                            dbmsg.set("cls", message.get("cls"))
                            dbmsg.store()
                    else:
                        dbmsg = self.obj(DBChatMessage)
                        dbmsg.set("created", sysnow)
                        dbmsg.set("channel", channel)
                        dbmsg.set("html", html)
                        dbmsg.set("cls", message.get("cls"))
                        dbmsg.store()
                # does anyone want universal HTML?
                if universal:
                    messages.append((["id_%s" % sess_uuid for sess_uuid in universal], html))
            for msg in messages:
                # sending message
                message["html"] = html_head + msg[1] + html_tail
                self.call("stream.packet", msg[0], "chat", "msg", **message)
        else:
            # system message
            message["html"] = html_head + u''.join([self.render_token(token, None) for token in tokens]) + html_tail
            self.call("stream.packet", "global", "chat", "msg", **message)

    def render_token(self, token, viewer_uuid, private=False):
        html = token.get("html")
        if html:
            return html
        char = token.get("character")
        if char:
            add_cls = ""
            add_tag = ""
            if token.get("missing"):
                add_cls += " chat-msg-char-missing"
            recipients = ["'%s'" % jsencode(ch.name) for ch in token["mentioned"] if ch.uuid != viewer_uuid] if char.uuid == viewer_uuid else ["'%s'" % jsencode(char.name)]
            if recipients:
                add_cls += " clickable"
                js = 'Chat.click([%s]%s); return false' % (",".join(recipients), (", 1" if private else ""))
                add_tag += ' onclick="{0}" ondblclick="{0}"'.format(js)
            return re_character_name.sub(ur'<span class="chat-msg-char%s"%s>\1</span>' % (add_cls, add_tag), char.html("chat"))
        now = token.get("time")
        if now:
            recipients = [char for char in token["mentioned"] if char.uuid != viewer_uuid] if viewer_uuid else token["mentioned"]
            if recipients:
                recipient_names = ["'%s'" % jsencode(char.name) for char in recipients]
                js = "Chat.click([%s]); return false" % ",".join(recipient_names)
                return u'<span class="chat-msg-time clickable" onclick="{0}" ondblclick="{0}">{1}</span> '.format(js, now)
            else:
                return u'<span class="chat-msg-time">%s</span> ' % now

    def channel2tab(self, channel):
        if re_loc_channel.match(channel):
            channel = "loc"
        if channel == "sys" and self.chatmode == 1:
            channel = "wld"
        if channel == "wld" and not self.conf("chat.location-separate"):
            channel = "loc"
        return channel

    def msg_went_online(self):
        return self.conf("chat.msg_went_online", self._("{NAME_CHAT} {GENDER:went,went} online"))

    def msg_went_offline(self):
        return self.conf("chat.msg_went_offline", self._("{NAME_CHAT} {GENDER:went,went} offline"))

    def msg_entered_location(self):
        return self.conf("chat.msg_entered_location", self._("{NAME_CHAT} has {GENDER:come,come} from {LOCATION}"))

    def msg_you_entered_location(self):
        return self.conf("chat.msg_you_entered_location", self._("You moved to the {LOCATION}"))

    def msg_location_messages(self):
        return self.conf("chat.msg_location_messages", self._("Messages from the {LOCATION}"))

    def msg_left_location(self):
        return self.conf("chat.msg_left_location", self._("{NAME_CHAT} has {GENDER:gone,gone} to {LOCATION}"))

    def character_online(self, character):
        msg = self.msg_went_online()
        if msg:
            self.call("chat.message", html=self.call("quest.format_text", msg, character=character), channel=self.auth_msg_channel(character), cls="auth")
        # joining channels
        channels = []
        self.call("chat.character-channels", character, channels)
        # joining character to all channels
        for channel in channels:
            self.call("chat.channel-join", character, channel, send_myself=False)

    def character_init(self, session_uuid, character):
        channels = []
        self.call("chat.character-channels", character, channels)
        # reload_channels resets destroyes all channels not listed in the 'channels' list and unconditionaly clears online lists
        show_channels = []
        for ch in channels:
            if re_loc_channel.match(ch["id"]):
                ch_copy = ch.copy()
                ch_copy["id"] = "loc"
                show_channels.append(ch_copy)
            else:
                show_channels.append(ch)
        self.call("stream.character", character, "chat", "reload_channels", channels=show_channels)
        # send information about all characters on all subscribed channels
        # also load old messages
        syschannel = "id_%s" % session_uuid
        messages = []
        for channel in channels:
            if channel["id"] == "loc":
                channel_id = "loc-%s" % (character.location.uuid if character.location else None)
            else:
                channel_id = channel["id"]
            # old messages
            msgs = self.objlist(DBChatMessageList, query_index="channel", query_equal=channel_id, query_reversed=True, query_limit=old_messages_limit)
            msgs.load(silent=True)
            for msg in msgs:
                messages.append(msg)
            # roster
            if channel.get("roster"):
                lst = self.objlist(DBChatChannelCharacterList, query_index="channel", query_equal=channel_id)
                character_uuids = [re_after_dash.sub('', uuid) for uuid in lst.uuids()]
                for char_uuid in character_uuids:
                    char = self.character(char_uuid)
                    self.call("stream.packet", syschannel, "chat", "roster_add", character=self.roster_info(char), channel=channel["id"])
        # loading old personal messages
        msgs = self.objlist(DBChatMessageList, query_index="channel", query_equal="char-%s" % character.uuid, query_reversed=True, query_limit=old_private_messages_limit)
        msgs.load(silent=True)
        for msg in msgs:
            msg.set("channel", msg.get("real_channel", "loc"))
            messages.append(msg)
        # send old messages
        if len(messages):
            messages.sort(cmp=lambda x, y: cmp(x.get("created"), y.get("created")))
            messages = [{
                "channel": self.channel2tab(msg.get("channel")),
                "cls": msg.get("cls"),
                "html": msg.get("html"),
                "priv": msg.get("priv"),
            } for msg in messages]
            self.call("stream.packet", syschannel, "chat", "msg_list", messages=messages, scroll_disable=True)
#        # current location
#        msg = self.msg_you_entered_location()
#        if msg:
#            self.call("stream.character", character, "chat", "current_location", html=self.call("quest.format_text", msg, character=character, location=character.location), scroll_disable=True)
        self.call("stream.character", character, "chat", "scroll_bottom")
        self.call("stream.character", character, "chat", "open_default_channel")

    def character_offline(self, character):
        msg = self.msg_went_offline()
        if msg:
            self.call("chat.message", html=self.call("quest.format_text", msg, character=character), channel=self.auth_msg_channel(character), cls="auth")
        # unjoining all channels
        lst = self.objlist(DBChatChannelCharacterList, query_index="character", query_equal=character.uuid)
        lst.load(silent=True)
        for ent in lst:
            channel_id = ent.get("channel")
            info = self.channel_info(channel_id)
            if ent.get("roster"):
                info["roster"] = True
            self.call("chat.channel-unjoin", character, info)

    def channel_join(self, character, channel, send_myself=True):
        channel_id = channel["id"]
        if channel_id == "loc":
            channel_id = "loc-%s" % (character.location.uuid if character.location else None)
            roster_channel_id = "loc"
        else:
            roster_channel_id = channel_id
        with self.lock(["chat-channel.%s" % channel_id]):
            obj = self.obj(DBChatChannelCharacter, "%s-%s" % (character.uuid, channel_id), silent=True)
            obj.set("character", character.uuid)
            obj.set("channel", channel_id)
            if channel.get("roster"):
                obj.set("roster", True)
                obj.set("roster_info", self.roster_info(character))
            obj.store()
            if channel.get("roster"):
                # list of characters subscribed to this channel
                lst = self.objlist(DBChatChannelCharacterList, query_index="channel", query_equal=channel_id)
                character_uuids = [re_after_dash.sub('', uuid) for uuid in lst.uuids()]
                if not send_myself:
                    character_uuids = [uuid for uuid in character_uuids if uuid != character.uuid]
                if len(character_uuids):
                    # load sessions of these characters
                    lst = self.objlist(SessionList, query_index="authorized-user", query_equal=["1-%s" % uuid for uuid in character_uuids])
                    characters_online = set()
                    syschannels = []
                    mychannels = []
                    for char_uuid, sess_uuid in lst.index_values(2):
                        characters_online.add(char_uuid)
                        syschannels.append("id_%s" % sess_uuid)
                        if send_myself and character.uuid == char_uuid:
                            mychannels.append("id_%s" % sess_uuid)
                    if send_myself and len(mychannels):
                        self.call("stream.packet", mychannels, "chat", "channel_create", **channel)
                    if syschannels:
                        self.call("stream.packet", syschannels, "chat", "roster_add", character=self.roster_info(character), channel=roster_channel_id)
                    for char_uuid in character_uuids:
                        if char_uuid in characters_online:
                            if send_myself and char_uuid != character.uuid and len(mychannels):
                                char = self.character(char_uuid)
                                for ch in mychannels:
                                    self.call("stream.packet", ch, "chat", "roster_add", character=self.roster_info(char), channel=roster_channel_id)
                        else:
                            # dropping obsolete database record
                            self.info("Unjoining offline character %s from channel %s", char_uuid, channel_id)
                            obj = self.obj(DBChatChannelCharacter, "%s-%s" % (char_uuid, channel_id), silent=True)
                            obj.remove()
            else:
                self.call("stream.character", character, "chat", "channel_create", **channel)

    def channel_unjoin(self, character, channel):
        channel_id = channel["id"]
        if channel_id == "loc":
            roster_channel_id = "loc"
            channel_id = "loc-%s" % (character.location.uuid if character.location else None)
        elif re_loc_channel.match(channel_id):
            roster_channel_id = "loc"
        else:
            roster_channel_id = channel_id
        with self.lock(["chat-channel.%s" % channel_id]):
            if channel.get("roster"):
                # list of characters subscribed to this channel
                lst = self.objlist(DBChatChannelCharacterList, query_index="channel", query_equal=channel_id)
                character_uuids = [re_after_dash.sub('', uuid) for uuid in lst.uuids()]
                if len(character_uuids):
                    # load sessions of these characters
                    lst = self.objlist(SessionList, query_index="authorized-user", query_equal=["1-%s" % uuid for uuid in character_uuids])
                    characters_online = set()
                    syschannels = []
                    for char_uuid, sess_uuid in lst.index_values(2):
                        characters_online.add(char_uuid)
                        syschannels.append("id_%s" % sess_uuid)
                    if syschannels:
                        self.call("stream.packet", syschannels, "chat", "roster_remove", character=character.uuid, channel=roster_channel_id)
                    characters_online.add(character.uuid)
                    # dropping obsolete database records
                    for char_uuid in character_uuids:
                        if char_uuid not in characters_online:
                            self.info("Unjoining offline character %s from channel %s", char_uuid, channel_id)
                            obj = self.obj(DBChatChannelCharacter, "%s-%s" % (char_uuid, channel_id), silent=True)
                            obj.remove()
            # dropping database record
            obj = self.obj(DBChatChannelCharacter, "%s-%s" % (character.uuid, channel_id), silent=True)
            obj.remove()

    def headmenu_chat_debug(self, args):
        if args == "join":
            return [self._("Joining character"), "chat/debug"]
        return self._("Chat debug channel")

    def chat_debug(self):
        req = self.req()
        if req.args == "join":
            if req.ok():
                errors = {}
                name = req.param("name")
                if not name:
                    errors["name"] = self._("Enter character name")
                else:
                    char = self.find_character(name)
                    if not char:
                        errors["name"] = self._("Character not found")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                obj = self.obj(DBChatDebug, char.uuid, data={})
                obj.dirty = True
                obj.store()
                if char.tech_online:
                    self.call("chat.channel-join", char, self.channel_info("dbg"))
                self.call("admin.redirect", "chat/debug")
            fields = [
                {"name": "name", "label": self._("Character name")},
            ]
            self.call("admin.form", fields=fields)
        m = re_unjoin.match(req.args)
        if m:
            char_uuid = m.group(1)
            obj = self.obj(DBChatDebug, char_uuid, silent=True)
            obj.remove()
            char = self.character(char_uuid)
            if char.tech_online:
                self.call("chat.channel-unjoin", char, self.channel_info("dbg"))
            self.call("admin.redirect", "chat/debug")
        rows = []
        lst = self.objlist(DBChatDebugList, query_index="all")
        for char_uuid in lst.uuids():
            char = self.character(char_uuid)
            rows.append([char.html("admin"), '<hook:admin.link href="chat/debug/unjoin/%s" title="%s" />' % (char.uuid, self._("unjoin"))])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "chat/debug/join",
                            "text": self._("Join character"),
                            "lst": True
                        }
                    ],
                    "header": [self._("Character"), self._("Unjoining")],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def character_channels(self, char, channels):
        channels.append(self.channel_info("sys"))
        if self.chatmode:
            channels.append(self.channel_info("wld"))
            channels.append(self.channel_info("loc"))
            if self.conf("chat.trade-channel"):
                channels.append(self.channel_info("trd"))
            if self.conf("chat.diplomacy-channel"):
                channels.append(self.channel_info("dip"))
            if self.conf("chat.debug-channel"):
                if self.debug_access(char):
                    channels.append(self.channel_info("dbg"))

    def debug_access(self, character):
        if not character:
            return True
        try:
            self.obj(DBChatDebug, character.uuid)
        except ObjectNotFoundException:
            return False
        else:
            return True

    def channel_info(self, channel_id):
        channel = {
            "id": channel_id
        }
        if channel_id == "sys":
            channel["title"] = self._("channel///System")
        elif channel_id == "wld":
            location_separate = True if self.conf("chat.location-separate") else False
            channel["title"] = self._("channel///World")
            channel["chatbox"] = location_separate
            channel["switchable"] = location_separate
            channel["writable"] = True
        elif channel_id == "trd":
            channel["title"] = self._("channel///Trade")
            channel["chatbox"] = True
            channel["switchable"] = True
            channel["writable"] = True
        elif channel_id == "dip":
            channel["title"] = self._("channel///Diplomacy")
            channel["chatbox"] = True
            channel["switchable"] = True
            channel["writable"] = True
        elif channel_id == "dbg":
            channel["title"] = self._("channel///Debug")
            channel["chatbox"] = True
            channel["switchable"] = True
            channel["writable"] = True
            channel["roster"] = True
        elif channel_id == "loc":
            channel["title"] = self._("channel///Location")
            channel["writable"] = True
            channel["roster"] = True
            channel["switchable"] = True
            channel["chatbox"] = True
            channel["permanent"] = True
        if channel.get("chatbox") or channel.get("switchable"):
            # default channel button image
            channel["button_image"] = "/st/game/chat/chat-channel"
            design = self.design("gameinterface")
            filename = "chat-%s" % channel_id
            if design:
                # design-specific channel button image
                ok = True
                res = self.call("design.prepare_button", design, "%s-on.png" % filename, "chat-channel-button-on.png", "chat-%s.png" % channel_id)
                if res is None:
                    raise RuntimeError(self._("Error generating %s-on.png") % filename)
                if not res:
                    ok = False
                res = self.call("design.prepare_button", design, "%s-off.png" % filename, "chat-channel-button-off.png", "chat-%s.png" % channel_id)
                if res is None:
                    raise RuntimeError(self._("Error generating %s-off.png") % filename)
                if not res:
                    ok = False
                res = self.call("design.prepare_button", design, "%s-new.png" % filename, "chat-channel-button-new.png", "chat-%s.png" % channel_id)
                if res is None:
                    raise RuntimeError(self._("Error generating %s-new.png") % filename)
                if not res:
                    ok = False
                if ok:
                    channel["button_image"] = "%s/%s" % (design.get("uri"), filename)
        self.call("chat.generate-channel-info", channel)
        return channel

    def settings_form(self, form, action, settings):
        if action == "render":
            form.checkbox(self._("Character went online/offline"), "chat_auth", settings.get("chat_auth", True), description=self._("System messages in the chat"))
            form.checkbox(self._("Other characters' movement"), "chat_move", settings.get("chat_move", True))
        elif action == "store":
            req = self.req()
            auth = True if req.param("chat_auth") else False
            move = True if req.param("chat_move") else False
            settings.set("chat_auth", auth)
            settings.set("chat_move", move)
            self.call("stream.packet", ["id_%s" % req.session().uuid], "chat", "filters", auth=auth, move=move)

    def roster_info(self, character):
        try:
            return character._roster_info
        except AttributeError:
            character._roster_info = {
                "id": character.uuid,
                "name": character.name,
                "html": character.html("roster"),
            }
            return character._roster_info

