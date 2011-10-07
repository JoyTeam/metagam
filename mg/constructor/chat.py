from mg import *
from mg.constructor import *
from uuid import uuid4
import datetime
import re

old_messages_limit = 10
old_private_messages_limit = 100
max_chat_message = 1000

re_chat_characters = re.compile(r'\[(chf|cht|ch):([a-f0-9]{32})\]')
re_chat_command = re.compile(r'^\s*/(\S+)\s*(.*)')
re_chat_recipient = re.compile(r'^\s*(to|private)\s*\[([^\]]+)\]\s*(.*)$')
re_loc_channel = re.compile(r'^loc-(\S+)$')
re_valid_command = re.compile(r'^/(\S+)$')
re_after_dash = re.compile(r'-.*')
re_unjoin = re.compile(r'^unjoin/(\S+)$')
re_character_name = re.compile(r'(<span class="char-name">.*?</span>)')
re_color = re.compile(r'^#[0-9a-f]{6}$')
re_curly = re.compile(r'[{}]')
re_valid_cls = re.compile(r'^[a-z][a-z\-]*$')
re_sharp = re.compile(r'#')
re_q = re.compile(r'q')
re_del = re.compile(r'^del/(.+)$')

class DBChatMessage(CassandraObject):
    "This object is created when the character is online and joined corresponding channel"
    clsname = "ChatMessage"
    indexes = {
        "created": [[], "created"],
        "channel": [["channel"], "created"],
    }

class DBChatMessageList(CassandraObjectList):
    objcls = DBChatMessage

class DBChatChannelCharacter(CassandraObject):
    "This object is created when the character is online and joined corresponding channel"
    clsname = "ChatChannelCharacter"
    indexes = {
        "channel": [["channel"]],
        "character": [["character"]],
    }

class DBChatChannelCharacterList(CassandraObjectList):
    objcls = DBChatChannelCharacter

class DBChatDebug(CassandraObject):
    "This object is created when the character is online and joined corresponding channel"
    clsname = "ChatDebug"
    indexes = {
        "all": [[]],
    }

class DBChatDebugList(CassandraObjectList):
    objcls = DBChatDebug

class Chat(ConstructorModule):
    def register(self):
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("menu-admin-chat.index", self.menu_chat_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-chat.config", self.headmenu_chat_config)
        self.rhook("ext-admin-chat.config", self.chat_config, priv="chat.config")
        self.rhook("headmenu-admin-chat.colors", self.headmenu_chat_colors)
        self.rhook("ext-admin-chat.colors", self.admin_chat_colors, priv="chat.colors")
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
        self.rhook("paidservices.available", self.paid_services_available)
        self.rhook("paidservices.chat_colours", self.srv_chat_colours)
        self.rhook("money-description.chat_colours", self.money_description_chat_colours)
        self.rhook("library-grp-index.pages", self.library_index_pages)
        self.rhook("library-page-chat.content", self.library_page_chat)
        self.rhook("character.name-invalidated", self.character_name_invalidated)

    def library_index_pages(self, pages):
        pages.append({"page": "chat", "order": 20})

    def library_page_chat(self):
        channel_commands = []
        if self.chatmode:
            if self.cmd_loc():
                channel_commands.append({"cmd": self.cmd_loc(), "title": self._("Location channel")})
            if self.cmd_wld():
                channel_commands.append({"cmd": self.cmd_wld(), "title": self._("Entire world channel")})
            if self.cmd_trd() and self.conf("chat.trade-channel"):
                channel_commands.append({"cmd": self.cmd_trd(), "title": self._("Trade channel")})
            if self.cmd_dip() and self.conf("chat.diplomacy-channel"):
                channel_commands.append({"cmd": self.cmd_dip(), "title": self._("Diplomacy channel")})
        vars = {
            "chatmode": self.chatmode,
            "channel_commands": channel_commands if channel_commands else None,
        }
        return {
            "code": "chat",
            "title": self._("Game chat"),
            "keywords": self._("chat"),
            "description": self._("This page is about game chat"),
            "content": self.call("socio.parse", "library-chat.html", vars),
            "parent": "index",
        }

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
        if self.chatmode:
            msg = self.msg_entered_location()
            if msg:
                self.call("chat.message", html=self.call("script.evaluate-text", msg, {"char": character, "loc_from": character.location, "loc_to": new_location}, description="Character entered location"), channel="loc-%s" % new_location.uuid, cls="move")

    def location_after_set(self, character, old_location, instance):
        if self.chatmode:
            msg = self.msg_left_location()
            if msg:
                self.call("chat.message", html=self.call("script.evaluate-text", msg, {"char": character, "loc_from": old_location, "loc_to": character.location}, description="Character left location"), channel="loc-%s" % old_location.uuid, cls="move")
            self.call("stream.character", character, "chat", "clear_loc")
            # old messages
            msgs = self.objlist(DBChatMessageList, query_index="channel", query_equal="loc-%s" % character.location.uuid, query_reversed=True, query_limit=old_messages_limit)
            msgs.load(silent=True)
            if len(msgs):
                msg = self.msg_location_messages()
                if msg:
                    self.call("stream.character", character, "chat", "current_location", html=self.call("script.evaluate-text", msg, {"char": character, "loc_from": old_location, "loc_to": character.location}, description="Location messages"), scroll_disable=True)
                messages = [{
                    "channel": "loc",
                    "cls": msg.get("cls"),
                    "html": msg.get("html"),
                } for msg in reversed(msgs)]
                self.call("stream.character", character, "chat", "msg_list", messages=messages, scroll_disable=True)
            # current location message
            msg = self.msg_you_entered_location()
            if msg:
                self.call("stream.character", character, "chat", "current_location", html=self.call("script.evaluate-text", msg, {"char": character, "loc_from": old_location, "loc_to": character.location}, description=self._("You entered location")), scroll_disable=True)
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
                menu.append({"id": "chat/debug", "text": self._("Debug chat channel"), "leaf": True, "order": 12})
        if req.has_access("chat.colors"):
            menu.append({"id": "chat/colors", "text": self._("Chat colors"), "leaf": True, "order": 11})

    def permissions_list(self, perms):
        perms.append({"id": "chat.config", "name": self._("Chat configuration editor")})
        perms.append({"id": "chat.colors", "name": self._("Chat colors configuration")})
        self.call("permissions.chat", perms)

    def headmenu_chat_config(self, args):
        return self._("Chat configuration")

    def chat_config(self):
        req = self.req()
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('You can find information on chat configuration in the <a href="//www.%s/doc/chat" target="_blank">chat manual</a>.') % self.app().inst.config["main_host"]})
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
            char = self.character(req.user())
            config.set("chat.msg_went_online", self.call("script.admin-text", "msg_went_online", errors, globs={"char": char}, require_glob=["char"]))
            config.set("chat.msg_went_offline", self.call("script.admin-text", "msg_went_offline", errors, globs={"char": char}, require_glob=["char"]))
            config.set("chat.msg_entered_location", self.call("script.admin-text", "msg_entered_location", errors, globs={"char": char, "loc_from": char.location, "loc_to": char.location}, require_glob=["char"]))
            config.set("chat.msg_left_location", self.call("script.admin-text", "msg_left_location", errors, globs={"char": char, "loc_from": char.location, "loc_to": char.location}, require_glob=["char"]))
            config.set("chat.msg_you_entered_location", self.call("script.admin-text", "msg_you_entered_location", errors, globs={"char": char, "loc_from": char.location, "loc_to": char.location}, require_glob=["loc_to"]))
            config.set("chat.msg_location_messages", self.call("script.admin-text", "msg_location_messages", errors, globs={"char": char, "loc_from": char.location, "loc_to": char.location}))
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
            {"name": "auth_msg_channel", "label": self._("Should online/offline messages be visible worldwide"), "type": "checkbox", "checked": auth_msg_channel=="wld", "condition": "[chatmode]>0"},
            {"name": "msg_went_online", "label": self._("Message about character went online") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", self.msg_went_online())},
            {"name": "msg_went_offline", "label": self._("Message about character went offline") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", self.msg_went_offline())},
            {"name": "msg_entered_location", "label": self._("Message about character entered location") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", self.msg_entered_location())},
            {"name": "msg_left_location", "label": self._("Message about character left location") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", self.msg_left_location())},
            {"name": "msg_you_entered_location", "label": self._("Message about your character entered location") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", self.msg_you_entered_location())},
            {"name": "msg_location_messages", "label": self._("Message heading messages from new location") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", self.msg_location_messages())},
        ]
        self.call("admin.form", fields=fields)

    def headmenu_chat_colors(self, args):
        if args == "new":
            return [self._("New color"), "chat/colors"]
        if args:
            args = re_q.sub('#', args)
            colors = self.chat_colors()
            for col in colors:
                if col["id"] == args:
                    return [htmlescape(col["name"]), "chat/colors"]
        return self._("Chat colors")

    def admin_chat_colors(self):
        req = self.req()
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('You can find information on chat colors configuration in the <a href="//www.%s/doc/chat-colors" target="_blank">chat colors manual</a>.') % self.app().inst.config["main_host"]})
        colors = self.chat_colors()
        if req.args:
            m = re_del.match(req.args)
            if m:
                uuid = m.group(1)
                uuid = re_q.sub('#', uuid)
                # deleting
                colors = [col for col in colors if col.get("id") != uuid]
                config = self.app().config_updater()
                config.set("chat.colors", colors)
                config.store()
                self.call("admin.redirect", "chat/colors")
            uuid = re_q.sub('#', req.args)
            if uuid == "new":
                info = {
                    "id": uuid4().hex
                }
                order = 0.0
                for ent in colors:
                    if ent.get("order", 0.0) >= order:
                        order = ent.get("order", 0.0) + 10
                info["order"] = order
            else:
                info = None
                for ent in colors:
                    if ent.get("id") == uuid:
                        info = ent
                        break
                if info is None:
                    self.call("admin.redirect", "chat/colors")
            if req.ok():
                errors = {}
                new_info = {
                    "id": info.get("id"),
                }
                tp = intz(req.param("v_tp"))
                if tp == 0:
                    color = req.param("color")
                    if not color:
                        errors["color"] = self._("This field is mandatory")
                    elif not re_color.match(color):
                        errors["color"] = self._("Invalid color format")
                    else:
                        new_info["color"] = color
                elif tp == 1:
                    style = req.param("style").strip()
                    if re_curly.search(style):
                        errors["style"] = self._("Curly brackets are not allowed here")
                    else:
                        new_info["style"] = style
                elif tp == 2:
                    cls = req.param("class")
                    if not re_valid_cls.match(cls):
                        errors["class"] = self._("Invalid class name. It must begin with a small latin letter a-z. Other letters must be a-z or '-'")
                    else:
                        new_info["class"] = cls
                else:
                    errors["v_tp"] = self._("Make valid selection")
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    new_info["name"] = name
                # order
                new_info["order"] = floatz(req.param("order"))
                # condition
                if req.param("condition").strip() != "":
                    char = self.character(req.user())
                    new_info["condition"] = self.call("script.admin-expression", "condition", errors, globs={"char": char})
                # error
                new_info["error"] = req.param("error").strip()
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                # store colors
                colors = [col for col in colors if col.get("id") != new_info["id"]]
                colors.append(new_info)
                colors.sort(cmp=lambda x, y: cmp(x.get("order", 0.0), y.get("order", 0.0)) or cmp(x.get("name", ""), y.get("name", "")))
                config = self.app().config_updater()
                config.set("chat.colors", colors)
                config.store()
                self.call("admin.redirect", "chat/colors")
            # show form
            if info.get("class"):
                tp = 2
            elif info.get("style") is not None:
                tp = 1
            else:
                tp = 0
            fields = [
                {"name": "name", "label": self._("Color name"), "value": info.get("name")},
                {"name": "order", "label": self._("Sorting order"), "value": info.get("order", 0.0)},
                {"name": "tp", "label": self._("Color type"), "value": tp, "values": [(0, self._("Simple colour")), (1, self._("CSS style declaration")), (2, self._("CSS class name"))], "type": "combo"},
                {"name": "color", "label": self._("Color (example: '#012def')"), "value": info.get("color"), "condition": "[tp]==0"},
                {"name": "style", "label": self._("Style declaration (example: 'font-weight: bold; border: solid 2px #ff0000; padding: 3px; margin: 3px 0 3px 0')"), "value": info.get("style"), "condition": "[tp]==1"},
                {"name": "class", "label": self._("CSS class name"), "value": info.get("class"), "condition": "[tp]==2"},
                {"name": "condition", "label": '%s%s' % (self._("Characters allowed to use this color (empty field means characters with the corresponding paid service)"), self.call("script.help-icon-expressions")), "value": self.call("script.unparse-expression", info["condition"]) if info.get("condition") is not None else None},
                {"name": "error", "label": self._("Error message when attempting to use a color with false condition (HTML allowed)"), "value": info.get("error")},
            ]
            self.call("admin.form", fields=fields)
        rows = []
        for col in colors:
            col_id = re_sharp.sub('q', col.get("id"))
            rows.append([
                htmlescape(col.get("name")),
                col.get("order", 0.0),
                htmlescape(col.get("color") or col.get("style") or '.%s' % col.get("class")),
                '<hook:admin.link href="chat/colors/%s" title="%s" />' % (col_id, self._("edit")),
                '<hook:admin.link href="chat/colors/del/%s" title="%s" confirm="%s" />' % (col_id, self._("delete"), self._("Are you sure want to delete this color?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "chat/colors/new", "text": self._("New color"), "lst": True},
                    ],
                    "header": [
                        self._("Color name"),
                        self._("Order"),
                        self._("Style"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def auth_msg_channel(self, character=None):
        if self.chatmode == 0:
            return "wld"
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
        restraints = {}
        self.call("restraints.check", user, restraints)
        if restraints.get("chat-silence"):
            self.call("web.response_json", {"error": self._("Silence till %s") % self.call("l10n.time_local", restraints["chat-silence"].get("till")), "hide_title": True})
        author = self.character(user)
        text = req.param("text") 
        if len(text) > max_chat_message:
            self.call("web.response_json", {"error": self._("Maximal message length - {max} characters ({sent} sent)").format(max=max_chat_message, sent=len(text)), "hide_title": True})
        prefixes = []
        prefixes.append("[chf:%s] " % user)
        channel = req.param("channel")
        if self.chatmode == 0:
            channel = "wld"
        elif channel == "sys" or channel == "":
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
                self.call("stream.character", author, "game", "main_open", uri="//%s/empty" % self.app().canonical_domain)
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
        body_html = "".join(token["html"] if "html" in token else htmlescape(token["text"]) for token in tokens)
        # chat color
        color_att = None
        color = author.settings.get("chat_color")
        if color:
            for col in self.chat_colors():
                if col["id"] == color:
                    if col.get("condition") is not None:
                        if not self.call("script.evaluate-expression", col["condition"], globs={"char": author}, description=self._("Color condition")):
                            break
                    else:
                        paid_colours_support = self.call("paidservices.chat_colours")
                        if paid_colours_support:
                            paid_colours_support = self.conf("paidservices.enabled-chat_colours", paid_colours_support["default_enabled"])
                        if paid_colours_support and not self.call("modifiers.kind", author.uuid, "chat_colours"):
                            break
                    if col.get("color"):
                        color_att = 'style="color: %s"' % col["color"]
                    elif col.get("style"):
                        color_att = 'style="%s"' % htmlescape(col["style"])
                    elif col.get("class"):
                        color_att = 'class="%s"' % htmlescape(col["class"])
                    break
        html = u'{0}<span class="chat-msg-body">{1}</span>'.format("".join(prefixes), body_html)
        # sending message
        self.call("chat.message", html=html, channel=channel, recipients=recipients, private=private, author=author, manual=True, hl=True, div_attr=color_att)
        self.call("web.response_json", {"ok": True, "channel": self.channel2tab(channel)})

    def message(self, html=None, hide_time=False, channel=None, private=None, recipients=None, author=None, sound=None, manual=None, div_attr=None, **kwargs):
        try:
            req = self.req()
        except AttributeError:
            req = None
#        self.debug("Chat message: html=%s, hide_time=%s, channel=%s, private=%s, recipients=%s, author=%s, sound=%s, manual=%s, kwargs=%s", html, hide_time, channel, private, recipients, author, sound, manual, kwargs)
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
            sessions = self.objlist(SessionList, query_index="authorized_user", query_equal=["1-%s" % char.uuid for char in characters])
            # loading list of characters able to view the message
            viewers = {}
            for char_uuid, sess_uuid in sessions.index_values(5):
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
        if div_attr:
            html_head = u'<div %s>%s' % (div_attr, html_head)
            html_tail = u'%s</div>' % html_tail
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
                html = u'%s%s%s' % (html_head, u''.join([self.render_token(token, None, private) for token in tokens]), html_tail)
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
#            self.debug("Delivering chat messages: %s", [msg[0] for msg in messages])
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
            add_cls = u""
            add_tag = u""
            if token.get("missing"):
                add_cls += u" chat-msg-char-missing"
            recipients = ["'%s'" % jsencode(ch.name) for ch in token["mentioned"] if ch.uuid != viewer_uuid] if char.uuid == viewer_uuid else ["'%s'" % jsencode(char.name)]
            if recipients:
                add_cls += " clickable"
                js = u'Chat.click([%s]%s); return false' % (",".join(recipients), (", 1" if private else ""))
                add_tag += u' onclick="{0}" ondblclick="{0}"'.format(js)
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
        msg = self.conf("chat.msg_went_online")
        if type(msg) is list:
            return msg
        return [[".", ["glob", "char"], "chatname"], " ", ["index", [".", ["glob", "char"], "sex"], self._("maleonline///went"), self._("femaleonline///went")], " ", self._("went///online")]

    def msg_went_offline(self):
        msg = self.conf("chat.msg_went_offline")
        if type(msg) is list:
            return msg
        return [[".", ["glob", "char"], "chatname"], " ", ["index", [".", ["glob", "char"], "sex"], self._("maleoffline///went"), self._("femaleoffline///went")], " ", self._("went///offline")]

    def msg_entered_location(self):
        msg = self.conf("chat.msg_entered_location")
        if type(msg) is list:
            return msg
        return [[".", ["glob", "char"], "chatname"], " ", ["index", [".", ["glob", "char"], "sex"], self._("malefrom///has come"), self._("femalefrom///has come")], " ", self._("come///from"), " ", [".", ["glob", "loc_from"], "name_f"]]

    def msg_you_entered_location(self):
        msg = self.conf("chat.msg_you_entered_location")
        if type(msg) is list:
            return msg
        return [self._("location///You are now at the"), " ", [".", ["glob", "loc_to"], "name_w"]]

    def msg_location_messages(self):
        msg = self.conf("chat.msg_location_messages")
        if type(msg) is list:
            return msg
        return [self._("location///Messages from the"), " ", [".", ["glob", "loc_to"], "name_f"]]

    def msg_left_location(self):
        msg = self.conf("chat.msg_left_location")
        if type(msg) is list:
            return msg
        return [[".", ["glob", "char"], "chatname"], " ", ["index", [".", ["glob", "char"], "sex"], self._("male///has gone"), self._("female///has gone")], " ", self._("gone///to"), " ", [".", ["glob", "loc_to"], "name_t"]]

    def character_online(self, character):
        msg = self.msg_went_online()
        if msg:
            self.call("chat.message", html=self.call("script.evaluate-text", msg, {"char": character}, description=self._("Character went online")), channel=self.auth_msg_channel(character), cls="auth")
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
            elif channel["id"] == "sys" and self.chatmode == 0:
                channel_id = "wld"
            else:
                channel_id = channel["id"]
            # old messages
            msgs = self.objlist(DBChatMessageList, query_index="channel", query_equal=channel_id, query_reversed=True, query_limit=old_messages_limit)
            msgs.load(silent=True)
            for msg in msgs:
                messages.append(msg)
            # roster
            if channel.get("roster"):
                if self.chatmode == 0:
                    channel_id = "sys"
                lst = self.objlist(DBChatChannelCharacterList, query_index="channel", query_equal=channel_id)
                character_uuids = [re_after_dash.sub('', uuid) for uuid in lst.uuids()]
                self.debug("Character %s init. sending roster for channel %s: %s", character.name, channel_id, character_uuids)
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
            for msg in messages:
                self.call("stream.packet", syschannel, "chat", "msg", scroll_disable=True, **msg)
        self.call("stream.character", character, "chat", "scroll_bottom")
        self.call("stream.character", character, "chat", "open_default_channel")

    def character_offline(self, character):
        msg = self.msg_went_offline()
        if msg:
            self.call("chat.message", html=self.call("script.evaluate-text", msg, {"char": character}, description=self._("Character went offline")), channel=self.auth_msg_channel(character), cls="auth")
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
        self.debug("Character %s is attempting to join channel %s (chatmode %s)", character.name, channel_id, self.chatmode)
        if self.chatmode == 0 and channel_id != "sys":
            return
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
                self.debug("Character %s is joining channel %s with roster", character.name, channel_id)
                # list of characters subscribed to this channel
                lst = self.objlist(DBChatChannelCharacterList, query_index="channel", query_equal=channel_id)
                character_uuids = [re_after_dash.sub('', uuid) for uuid in lst.uuids()]
                if not send_myself:
                    character_uuids = [uuid for uuid in character_uuids if uuid != character.uuid]
                self.debug("Subscribed characters: %s", character_uuids)
                if len(character_uuids):
                    # load sessions of these characters
                    lst = self.objlist(SessionList, query_index="authorized_user", query_equal=["1-%s" % uuid for uuid in character_uuids])
                    characters_online = set()
                    syschannels = []
                    mychannels = []
                    for char_uuid, sess_uuid in lst.index_values(5):
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
                    lst = self.objlist(SessionList, query_index="authorized_user", query_equal=["1-%s" % uuid for uuid in character_uuids])
                    characters_online = set()
                    syschannels = []
                    for char_uuid, sess_uuid in lst.index_values(5):
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
            self.info("Unjoining character %s from channel %s", character.uuid, channel_id)
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
            if self.chatmode == 0:
                channel["roster"] = True
                channel["title"] = self._("channel///World")
            else:
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
        req = self.req()
        user_uuid = req.user()
        char = self.character(req.user())
        if action == "render":
            form.checkbox(self._("Character went online/offline"), "chat_auth", req.param("chat_auth") if req.ok() else settings.get("chat_auth", True), description=self._("System messages in the chat"))
            form.checkbox(self._("Other characters' movement"), "chat_move", req.param("chat_move") if req.ok() else settings.get("chat_move", True))
            colors = []
            colors.append({"value": "", "description": self._("Default")})
            for col in self.chat_colors():
                if col.get("condition") is not None:
                    if col.get("error"):
                        show = True
                    else:
                        show = self.call("script.evaluate-expression", col["condition"], globs={"char": char}, description=self._("Color condition"))
                else:
                    show = True
                if show:
                    colors.append({"value": col["id"], "description": col["name"], "bgcolor": col["color"] if col.get("color") else None})
            if len(colors) > 1:
                form.select(self._("Chat messages colour"), "chat_color", req.param("chat_color") if req.ok() else settings.get("chat_color", ""), colors)
        elif action == "validate":
            color = req.param("chat_color")
            if color:
                # condition=None - show always, use only with paid service
                # condition and error=None - show only if condition is True
                # condition and error - show always, use only if condition is True
                found = False
                for col in self.chat_colors():
                    if col["id"] == color:
                        if col.get("condition") is not None:
                            cond_val = self.call("script.evaluate-expression", col["condition"], globs={"char": char}, description=self._("Color condition"))
                            if col.get("error"):
                                found = True
                            else:
                                found = cond_val
                        else:
                            found = True
                        if found:
                            if col.get("condition") is not None:
                                if not cond_val:
                                    form.error("chat_color", col.get("error"))
                            else:
                                paid_colours_support = self.call("paidservices.chat_colours")
                                if paid_colours_support:
                                    paid_colours_support = self.conf("paidservices.enabled-chat_colours", paid_colours_support["default_enabled"])
                                if paid_colours_support and not self.call("modifiers.kind", user_uuid, "chat_colours"):
                                    form.error("chat_color", self._('To use colours in the chat <a href="/paidservices">subscribe to the corresponding service</a>'))
                        break
                if not found:
                    form.error("chat_color", self._("Select a valid colour"))
        elif action == "store":
            req = self.req()
            auth = True if req.param("chat_auth") else False
            move = True if req.param("chat_move") else False
            settings.set("chat_auth", auth)
            settings.set("chat_move", move)
            settings.set("chat_color", req.param("chat_color") or None)
            self.call("stream.packet", ["id_%s" % req.session().uuid], "chat", "filters", auth=auth, move=move)

    def chat_colors(self):
        colors = self.conf("chat.colors")
        if colors is None:
            colors = [
                '#000000',
                '#806080',
                '#800000',
                '#006000',
                '#000080',
                '#806000',
                '#006080',
                '#800080',
                '#c06000',
                '#808000',
                '#0060c0',
                '#008080',
                '#8000c0',
                '#c00080',
            ]
        # replacing old colors format with the new one
        colors = [col if type(col) == dict else {"id": col, "name": col, "color": col} for col in colors]
        for col in colors:
            if not col.get("id"):
                col["id"] = uuid4().hex
        return colors

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

    def paid_services_available(self, services):
        services.append({"id": "chat_colours", "type": "main"})

    def money_description_chat_colours(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Colours in the chat for {period}"),
        }

    def srv_chat_colours(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        return {
            "id": "chat_colours",
            "name": self._("Colours in the chat"),
            "description": self._("Basically your can not use colours in the chat - all messages are the same colour. If you want to use arbitrary colours you can use this option"),
            "subscription": True,
            "type": "main",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 100 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "main_success_url": "/settings",
            "main_success_message": self._("Now select a colour for your messages"),
        }

    def character_name_invalidated(self, character, args):
        if args.get("update_chat", True):
            # notify every character subscribed to rosters with this character that character name has changed
            users = set()
            lst = self.objlist(DBChatChannelCharacterList, query_index="character", query_equal=character.uuid)
            lst.load(silent=True)
            for ent in lst:
                channel_id = ent.get("channel")
                info = self.channel_info(channel_id)
                if ent.get("roster"):
                    users_lst = self.objlist(DBChatChannelCharacterList, query_index="channel", query_equal=channel_id)
                    users_lst.load(silent=True)
                    for user_ent in users_lst:
                        users.add(user_ent.get("character"))
            channels = set()
            lst = self.objlist(SessionList, query_index="authorized_user", query_equal=["1-%s" % user for user in users])
            for char_uuid, sess_uuid in lst.index_values(5):
                channels.add('id_%s' % sess_uuid)
            self.call("stream.packet", [ch for ch in channels], "chat", "character_update", character=self.roster_info(character))
