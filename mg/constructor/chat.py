from mg import *
from mg.constructor import *
import datetime
import re

re_chat_characters = re.compile(r'\[(chf|ch):([a-f0-9]{32})\]')
re_chat_command = re.compile(r'^\s*/(\S+)\s*(.*)')
re_chat_recipient = re.compile(r'^\s*(to|private)\s*\[([^\]]+)\]\s*(.*)$')
re_loc_channel = re.compile(r'^loc-(\S+)$')
re_valid_command = re.compile(r'^/(\S+)$')

class Chat(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("menu-admin-game.index", self.menu_game_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-chat.config", self.headmenu_chat_config)
        self.rhook("ext-admin-chat.config", self.chat_config, priv="chat.config")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("admin-gameinterface.design-files", self.gameinterface_advice_files)
        self.rhook("ext-chat.post", self.post, priv="logged")
        self.rhook("chat.message", self.message)

    def menu_game_index(self, menu):
        req = self.req()
        if req.has_access("chat.config"):
            menu.append({"id": "chat/config", "text": self._("Chat configuration"), "leaf": True, "order": 10})

    def permissions_list(self, perms):
        perms.append({"id": "chat.config", "name": self._("Chat configuration editor")})

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
                        errors["cmd-wld"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                else:
                    config.set("chat.cmd-wld", "")
                cmd_loc = req.param("cmd-loc")
                if cmd_loc != "":
                    m = re_valid_command.match(cmd_loc)
                    if m:
                        config.set("chat.cmd-loc", m.group(1))
                    else:
                        errors["cmd-loc"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                else:
                    config.set("chat.cmd-loc", "")
                if trade_channel:
                    cmd_trd = req.param("cmd-trd")
                    if cmd_trd != "":
                        m = re_valid_command.match(cmd_trd)
                        if m:
                            config.set("chat.cmd-trd", m.group(1))
                        else:
                            errors["cmd-trd"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                    else:
                        config.set("chat.cmd-trd", "")
                if diplomacy_channel:
                    cmd_dip = req.param("cmd-dip")
                    if cmd_dip != "":
                        m = re_valid_command.match(cmd_dip)
                        if m:
                            config.set("chat.cmd-dip", m.group(1))
                        else:
                            errors["cmd-dip"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                    else:
                        config.set("chat.cmd-dip", "")
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
            chatmode = self.chatmode()
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
        ]
        self.call("admin.form", fields=fields)

    def chatmode(self):
        return self.conf("chat.channels-mode", 1)

    def channels(self, chatmode):
        channels = []
        channels.append({
            "id": "main",
            "short_name": self._("channel///Main"),
            "switchable": True,
            "writable": True,
        })
        if chatmode:
            # channels enabled
            if self.conf("chat.location-separate"):
                channels.append({
                    "id": "loc",
                    "short_name": self._("channel///Location"),
                    "writable": True,
                    "switchable": True
                })
            else:
                channels[0]["writable"] = True
            if self.conf("chat.trade-channel"):
                channels.append({
                    "id": "trd",
                    "short_name": self._("channel///Trade"),
                    "switchable": True,
                    "writable": True
                })
            if self.conf("chat.diplomacy-channel"):
                channels.append({
                    "id": "dip",
                    "short_name": self._("channel///Diplomacy"),
                    "switchable": True,
                    "writable": True
                })
            if self.conf("chat.debug-channel"):
                channels.append({
                    "id": "dbg",
                    "short_name": self._("channel///Debug"),
                    "switchable": True,
                    "writable": True
                })
        else:
            channels[0]["writable"] = True
        return channels

    def gameinterface_render(self, vars, design):
        vars["js_modules"].add("chat")
        # list of channels
        chatmode = self.chatmode()
        channels = self.channels(chatmode)
        vars["js_init"].append("Chat.mode = %d;" % chatmode)
        if chatmode == 2:
            vars["js_init"].append("Chat.active_channel = 'main';")
        for ch in channels:
            vars["js_init"].append("Chat.channel_new({id: '%s', title: '%s'});" % (ch["id"], jsencode(ch["short_name"])))
        if chatmode and len(channels):
            vars["layout"]["chat_channels"] = True
            buttons = []
            state = None
            if chatmode == 1:
                for ch in channels:
                    buttons.append({
                        "id": ch["id"],
                        "state": "on" if ch["id"] == "main" else "off",
                        "onclick": "return Chat.tab_open('%s');" % ch["id"],
                        "hint": htmlescape(ch["short_name"])
                    })
            elif chatmode == 2:
                for ch in channels:
                    if ch.get("switchable"):
                        buttons.append({
                            "id": ch["id"],
                            "state": "on",
                            "onclick": "return Chat.channel_toggle('%s');" % ch["id"],
                            "hint": htmlescape(ch["short_name"])
                        })
            if len(buttons):
                for btn in buttons:
                    filename = "chat-%s" % btn["id"]
                    if design and (("%s-on.gif" % filename) in design.get("files")) and (("%s-off.gif" % filename) in design.get("files")):
                        btn["image"] = "%s/%s" % (design.get("uri"), filename)
                    else:
                        btn["image"] = "/st/game/chat/chat-channel"
                    vars["js_init"].append("Chat.button_images['%s'] = '%s';" % (btn["id"], btn["image"]))
                    btn["id"] = "chat-channel-button-%s" % btn["id"]
                buttons[-1]["lst"] = True
                vars["chat_buttons"] = buttons
        if chatmode == 1:
            vars["js_init"].append("Chat.tab_open('main');")
        vars["chat_channels"] = channels

    def gameinterface_advice_files(self, files):
        chatmode = self.chatmode()
        channels = self.channels(chatmode)
        if len(channels) >= 2:
            for ch in channels:
                if chatmode == 1 or ch.get("switchable"):
                    files.append({"filename": "chat-%s-off.gif" % ch["id"], "description": self._("Chat channel '%s' disabled") % ch["short_name"]})
                    files.append({"filename": "chat-%s-on.gif" % ch["id"], "description": self._("Chat channel '%s' enabled") % ch["short_name"]})

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
        author = self.character(user)
        text = req.param("text") 
        prefixes = []
        prefixes.append("[[chf:%s]] " % user)
        channel = req.param("channel")
        if channel == "main" or channel == "":
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
                prefixes.append("private [[ch:%s]] " % char.uuid)
            else:
                prefixes.append("to [[ch:%s]] " % char.uuid)
            recipients.append(char)
        if author not in recipients:
            recipients.append(author)
        # access control
        if channel == "wld" or channel == "loc" or channel == "trd" and self.conf("chat.trade-channel") or channel == "dip" and self.conf("chat.diplomacy-channel"):
            pass
        else:
            self.call("web.response_json", {"error": self._("No access to the chat channel %s") % htmlescape(channel)})
        # translating channel name
        if channel == "loc":
            # TODO: convert to loc-%s format
            pass
        # formatting html
        html = u'{0}<span class="chat-msg-body">{1}</span>'.format("".join(prefixes), htmlescape(text))
        # sending message
        self.call("chat.message", html=html, channel=channel, recipients=recipients, private=private, author=author)
        self.call("web.response_json", {"ok": True, "channel": self.channel2tab(channel)})

    def message(self, html=None, hide_time=False, channel=None, private=None, recipients=None, author=None):
        try:
            req = self.req()
        except AttributeError:
            req = None
        # channel
        if not channel:
            channel = "sys"
        # store chat message
        # TODO: store chat message
        # translate channel name
        if channel == "sys":
            viewers = None
        else:
            print "channel: %s" % channel
            # preparing list of characters to receive
            characters = []
            if private:
                characters = recipients
            elif channel == "wld" or channel == "trd" or channel == "dip":
                characters = self.characters.tech_online
            else:
                m = re_loc_channel.match(channel)
                if m:
                    loc_uuid = m.group(1)
                    # TODO: load location list
            # loading list of sessions corresponding to the characters
            print "characters: %s" % characters
            sessions = self.objlist(SessionList, query_index="authorized-user", query_equal=["1-%s" % char.uuid for char in characters])
            print "index_rows: %s" % sessions.index_rows
            print "index_data: %s" % sessions.index_data
            print "sessions: %s" % sessions
            # loading list of characters able to view the message
            viewers = {}
            for char_uuid, sess_uuid in sessions.index_values(2):
                print "session %s => character %s (%s)" % (sess_uuid, char_uuid, self.character(char_uuid).name)
                try:
                    viewers[char_uuid].append(sess_uuid)
                except KeyError:
                    viewers[char_uuid] = [sess_uuid]
            print "effective viewers: %s" % viewers
        tokens = []
        # time
        if not hide_time:
            now = datetime.datetime.utcnow().strftime("%H:%M:%S")
            tokens.append({"time": now, "recipients": recipients})
        # replacing character tags [chf:UUID], [ch:UUID] etc
        mentioned = set()       # characters mentioned in the message
        start = 0
        for match in re_chat_characters.finditer(html):
            match_start, match_end = match.span()
            if match_start > start:
                tokens.append({"html": html[start:match_start]})
            start = match_end
            tp, character = match.group(1, 2)
            mentioned.add(character)
            character = self.character(character)
            if tp == "chf" or tp == "ch":
                token = {"character": character, "recipients": recipients}
                if character.uuid not in viewers:
                    token["missing"] = True
                tokens.append(token)
        if len(html) > start:
            tokens.append({"html": html[start:]})
        print "formed tokens: %s" % tokens
        message = {
            "channel": self.channel2tab(channel),
        }
        print "mentioned: %s" % mentioned
        if viewers is not None:
            # enumerating all recipients and preparing HTML version of the message for everyone
            universal = []
            messages = []
            for char_uuid, sessions in viewers.iteritems():
                if char_uuid in mentioned:
                    # make specific HTML for this character
                    html = u''.join([self.render_token(token, char_uuid, private) for token in tokens])
                    messages.append((["id_%s" % sess_uuid for sess_uuid in sessions], html))
                else:
                    # these sessions need universal HTML
                    universal.extend(sessions)
            if universal:
                # anyone wants universal HTML
                html = u''.join([self.render_token(token, None, private) for token in tokens])
                messages.append((["id_%s" % sess_uuid for sess_uuid in universal], html))
            for msg in messages:
                # sending message
                print "sending chat message to syschannel %s: %s" % (msg[0], msg[1])
                message["html"] = msg[1]
                self.call("stream.packet", msg[0], "chat", "msg", **message)
        else:
            # system message
            message["html"] = u''.join([self.render_token(token, None) for token in tokens])
            print "sending chat message to syschannel global"
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
            recipients = ["'%s'" % jsencode(ch.name) for ch in token["recipients"] if ch.uuid != viewer_uuid] if char.uuid == viewer_uuid else ["'%s'" % jsencode(char.name)]
            if recipients:
                add_cls += " clickable"
                add_tag += ' onclick="Chat.click([%s]%s)"' % (",".join(recipients), (", 1" if private else ""))
            return u'<span class="chat-msg-char%s"%s>%s</span>' % (add_cls, add_tag, char.html_chat)
        now = token.get("time")
        if now:
            recipients = [char for char in token["recipients"] if char.uuid != viewer_uuid] if viewer_uuid else token["recipients"]
            if recipients:
                recipient_names = ["'%s'" % jsencode(char.name) for char in recipients]
                return u'<span class="chat-msg-time clickable" onclick="Chat.click([%s])">%s</span> ' % (",".join(recipient_names), now)
            else:
                return u'<span class="chat-msg-time">%s</span> ' % now

    def channel2tab(self, channel):
        if channel == "sys" or channel == "wld" or channel == "loc" and not self.conf("chat.location-separate"):
            return "main"
        if re_loc_channel.match(channel):
            if self.conf("chat.location-separate"):
                return "loc"
            else:
                return "main"
        return channel
