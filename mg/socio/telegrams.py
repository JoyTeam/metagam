#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

# -*- coding: utf-8 -*-
from mg import *
import re

re_newline = re.compile(r'\n')

ignore_list_max_name_length = 50
ignore_list_max_length = 1000

class Telegram(CassandraObject):
    clsname = "Telegram"

class TelegramList(CassandraObjectList):
    objcls = Telegram

class TelegramUser(CassandraObject):
    clsname = "TelegramUser"
    indexes = {
        "contragent": [["user", "contragent"], "sent"],
        "unread": [["user", "unread"]],
        "telegram": [["telegram"]]
    }

class TelegramUserList(CassandraObjectList):
    objcls = TelegramUser

class TelegramContragent(CassandraObject):
    clsname = "TelegramContragent"
    indexes = {
        "user": [["user"], "last_telegram"],
    }

class TelegramContragentList(CassandraObjectList):
    objcls = TelegramContragent
    
class TelegramUserSettings(CassandraObject):
    clsname = "TelegramUserSettings"

class TelegramsAdmin(Module):
    def register(self):
        self.rhook("admin-sociointerface.design-files", self.design_files)

    def design_files(self, files):
        files.append({"filename": "telegrams-contragents.html", "description": self._("List of contragents in the telegrams interface")})
        files.append({"filename": "telegrams-user.html", "description": self._("List of message with the specific user in the telegrams interface")})

class Telegrams(Module):
    def register(self):
        self.rhook("telegrams.menu", self.menu)
        self.rhook("telegrams.send", self.send)
        self.rhook("ext-telegrams.list", self.telegrams_list, priv="logged")
        self.rhook("ext-telegrams.send", self.telegrams_send, priv="logged")
        self.rhook("ext-telegrams.user", self.telegrams_user, priv="logged")
        self.rhook("socio.author_menu", self.socio_author_menu)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("telegrams.check-ignore-list", self.check_ignore_list)
        self.rhook("ext-telegrams.ignore", self.ext_ignore, priv="logged")

    def objclasses_list(self, objclasses):
        objclasses["Telegram"] = (Telegram, TelegramList)
        objclasses["TelegramUser"] = (TelegramUser, TelegramUserList)
        objclasses["TelegramContragent"] = (TelegramContragent, TelegramContragentList)

    def child_modules(self):
        return ["mg.socio.telegrams.TelegramsAdmin"]

    def menu(self, menu_lst):
        req = self.req()
        if req.user():
            params = {}
            self.call("telegrams.params", params)
            req = self.req()
            lst = self.objlist(TelegramUserList, query_index="unread", query_equal="%s-1" % req.user())
            if len(lst):
                suffix = " <strong>(%d)</strong>" % len(lst)
            else:
                suffix = None
            menu_lst.append({"href": "/telegrams/list" if req.group != "telegrams" or req.hook != "list" else None, "html": params.get("menu_title", self._("Telegrams")), "suffix": suffix})

    def telegrams_list(self):
        params = {}
        self.call("telegrams.params", params)
        req = self.req()
        user = req.user()
        lst = self.objlist(TelegramContragentList, query_index="user", query_equal=user, query_reversed=True)
        lst.load()
        users = [ent.get("contragent") for ent in lst]
        users = self.objlist(UserList, users)
        users.load()
        users = dict([(user.uuid, user) for user in users])
        rows = []
        for ent in lst:
            user = users.get(ent.get("contragent"))
            if user is None:
                continue
            rows.append({
                "bold": ent.get("unread"),
                "cols": [
                    {"html": htmlescape(user.get("name")), "class": "telegrams-user"},
                    {"html": '<a href="/telegrams/user/%s%s">%s</a>' % (user.uuid, "#unread" if ent.get("unread") else "", self.call("l10n.time_local", ent.get("last_telegram"))), "class": "telegrams-last"},
                    {"html": self._("Yes") if ent.get("unread") else self._("No"), "class": "telegrams-unread"}
                ]
            })
        vars = {
            "title": params.get("page_title", self._("Telegrams")),
            "list_cols": [params.get("user", self._("User")), params.get("last_telegram", self._("Last telegram")), self._("Unread")],
            "list_rows": rows if len(rows) else None,
            "menu_left": [
                {"html": params.get("all_telegrams", self._("All telegrams"))},
                {"href": "/telegrams/send", "html": params.get("send_telegram", self._("Send new telegram"))},
                {"href": "/telegrams/ignore", "html": params.get("ignore_list", self._("Ignore list")), "lst": True}
            ]
        }
        self.call("socio.response_template", "telegrams-contragents.html", vars)

    def telegrams_send(self):
        params = {}
        self.call("telegrams.params", params)
        req = self.req()
        form = self.call("web.form")
        cname = req.param("cname").strip()
        content = req.param("content").strip()
        user = req.user()
        restraints = {}
        self.call("restraints.check", user, restraints)
        silence = restraints.get("forum-silence") or restraints.get("chat-silence")
        if req.ok():
            if not cname:
                form.error("cname", self._("Enter recipient name"))
            else:
                recipient = self.call("session.find_user", cname)
                if not recipient:
                    form.error("cname", self._("No such user"))
                elif recipient.get("tag"):
                    form.error("cname", self._("You can't send messages to the system"))
            if not content:
                form.error("content", self._("Enter message content"))
            elif silence:
                message = self._("Silence till %s") % self.call("l10n.time_local", silence.get("till"))
                reason_user = silence.get("reason_user")
                if reason_user:
                    message += u'\n%s' % silence.get("reason_user")
                    message = htmlescape(message)
                    message = re_newline.sub('<br />', message)
                form.error("content", message)
            if not form.errors and self.call("telegrams.check-ignore-list", user, recipient.uuid):
                form.error("cname", self._("This user has forbidden you to send him private messages"))
            if not form.errors:
                self.call("telegrams.send", user, recipient.uuid, self.call("socio.format_text", content))
                self.call("web.redirect", "/telegrams/user/%s#reply-form" % recipient.uuid)
        form.input(params.get("recipient", self._("Recipient")), "cname", cname)
        form.texteditor(params.get("text", self._("Telegram text")), "content", content)
        form.submit(None, None, self._("Send"))
        vars = {
            "title": params.get("send_telegram", self._("Send new telegram")),
            "menu_left": [
                {"href": "/telegrams/list", "html": params.get("all_telegrams", self._("All telegrams"))},
                {"html": params.get("send_telegram", self._("Send new telegram"))},
                {"href": "/telegrams/ignore", "html": params.get("ignore_list", self._("Ignore list")), "lst": True}
            ]
        }
        self.call("socio.response", form.html(vars), vars)

    def system_user(self, tag, name):
        lst = self.objlist(UserList, query_index="tag", query_equal=tag)
        lst.load(silent=True)
        if len(lst):
            return lst[0]
        obj = self.obj(User)
        obj.set("name", name)
        obj.set("name_lower", name.lower())
        obj.set("tag", tag)
        obj.store()
        return obj

    def send(self, sender_uuid, recipient_uuid, content):
        if sender_uuid is None:
            params = {}
            self.call("telegrams.params", params)
            sender_uuid = self.system_user("system", params.get("system_name", self._("System"))).uuid
        now = self.now()
        # Telegram
        tel = self.obj(Telegram)
        tel.set("sender", sender_uuid)
        tel.set("recipient", recipient_uuid)
        tel.set("sent", now)
        tel.set("unread", "1")
        tel.set("html", content)
        # TelegramUser for sender
        tel_user_1 = self.obj(TelegramUser)
        tel_user_1.set("telegram", tel.uuid)
        tel_user_1.set("user", sender_uuid)
        tel_user_1.set("contragent", recipient_uuid)
        tel_user_1.set("sent", now)
        if recipient_uuid != sender_uuid:
            # TelegramUser for recipient
            tel_user_2 = self.obj(TelegramUser)
            tel_user_2.set("telegram", tel.uuid)
            tel_user_2.set("user", recipient_uuid)
            tel_user_2.set("contragent", sender_uuid)
            tel_user_2.set("sent", now)
            tel_user_2.set("unread", 1)
        # TelegramContragent for sender
        tel_cont_1 = self.obj(TelegramContragent, "%s-%s" % (sender_uuid, recipient_uuid), silent=True)
        tel_cont_1.set("user", sender_uuid)
        tel_cont_1.set("contragent", recipient_uuid)
        tel_cont_1.set("last_telegram", now)
        if recipient_uuid != sender_uuid:
            # TelegramContragent for recipient
            tel_cont_2 = self.obj(TelegramContragent, "%s-%s" % (recipient_uuid, sender_uuid), silent=True)
            tel_cont_2.set("user", recipient_uuid)
            tel_cont_2.set("contragent", sender_uuid)
            tel_cont_2.set("last_telegram", now)
            tel_cont_2.set("unread", 1)
        # Storing message
        tel.store()
        tel_user_1.store()
        tel_cont_1.store()
        if recipient_uuid != sender_uuid:
            tel_user_2.store()
            tel_cont_2.store()
        # Sending notification
        self.call("email.users", [recipient_uuid], self._("New message"), self._("You have received a new message.\n\n{protocol}://www.{host}/telegrams/list").format(protocol=self.app().protocol, host=self.app().domain), immediately=True)

    def telegrams_user(self):
        params = {}
        self.call("telegrams.params", params)
        req = self.req()
        try:
            contragent = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        user = req.user()
        lst = self.objlist(TelegramUserList, query_index="contragent", query_equal="%s-%s" % (user, req.args))
        lst.load()
        telegram_ids = [ent.get("telegram") for ent in lst]
        telegrams = self.objlist(TelegramList, telegram_ids)
        telegrams.load()
        rows = []
        unread = False
        for tel in telegrams:
            html = tel.get("html")
            if tel.get("recipient") == user:
                if tel.get("unread"):
                    if not unread:
                        unread = True
                        html = '<a name="unread"></a>' + html
                    tel.delkey("unread")
                rows.append([{"html": self.call("l10n.time_local", tel.get("sent")), "class": "telegrams-sent"}, {"html": html, "class": "telegrams-content telegrams-tome"}])
            else:
                rows.append([{"html": self.call("l10n.time_local", tel.get("sent")), "class": "telegrams-sent"}, None, {"html": html, "class": "telegrams-content telegrams-fromme"}])
        if unread:
            for ent in lst:
                ent.delkey("unread")
            telegrams.store()
            lst.store()
            try:
                cont = self.obj(TelegramContragent, "%s-%s" % (user, contragent.uuid))
            except ObjectNotFoundException:
                pass
            else:
                cont.delkey("unread")
                cont.store()
        read_only = True if contragent.get("tag") else False
        title = params.get("telegrams_with", self._("Telegrams with {0}")).format(htmlescape(contragent.get("name")))
        form = self.call("web.form", action="/telegrams/send")
        form.hidden("cname", contragent.get("name"))
        form.texteditor(params.get("text", self._("Telegram text")), "content", "")
        form.submit(None, None, self._("Send"))
        cols = [self._("Time"), self._("Received")]
        if not read_only:
            cols.append(self._("Sent"))
        vars = {
            "title": title,
            "list_cols": cols,
            "list_rows": rows if len(rows) else None,
            "menu_left": [
                {"href": "/telegrams/list", "html": params.get("all_telegrams", self._("All telegrams"))},
                {"html": title, "lst": True}
            ],
            "form": "" if read_only else form.html()
        }
        self.call("socio.response_template", "telegrams-user.html", vars)

    def socio_author_menu(self, author_uuid, author_name_html, menu):
        menu.append({"title": self._("Correspondence"), "href": "/telegrams/user/%s" % author_uuid})

    def ext_ignore(self):
        req = self.req()
        user_uuid = req.user()
        params = {}
        self.call("telegrams.params", params)
        try:
            settings = self.obj(TelegramUserSettings, user_uuid)
        except ObjectNotFoundException:
            settings = self.obj(TelegramUserSettings, user_uuid, {})
        form = self.call("web.form")
        
        ignore_list_raw = req.param("ignore_list")
        
        if req.ok():
            ignore_list = filter(lambda entry: True if entry else False, sorted(set(map(lambda entry: entry.strip().lower(), ignore_list_raw.split("\n")))))
            
            for entry in ignore_list:
                #if not re.match(ur'^[A-Za-z0-9_\-абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ ]+$', entry):
                #    form.error("ignore_list", self._("Name '%s' is incorrect") % entry)
                #    break
                if len(entry) > ignore_list_max_name_length:
                    form.error("ignore_list", self._("Name '%s' is incorrect") % entry)
                    break
                    
            if len(ignore_list) > ignore_list_max_length:
                form.error("ignore_list", self._("Your ignore list is too big"))
            
            if not form.errors:
                settings.set("ignore_list", ignore_list)
                settings.store()
                self.call("web.redirect", "/telegrams/list")
                
        if not ignore_list_raw:
            ignore_list_raw = "\n".join(settings.get("ignore_list", []))
        form.textarea(self._("Enter the names of users whose messages you do not wish to receive (one per line, case-insensitive)"), "ignore_list", ignore_list_raw)
        vars = {
            "title": self._("Ignore list"),
            "menu_left": [
                {"href": "/telegrams/list", "html": params.get("all_telegrams", self._("All telegrams"))},
                {"href": "/telegrams/send", "html": params.get("send_telegram", self._("Send new telegram"))},
                {"html": params.get("ignore_list", self._("Ignore list")), "lst": True}
            ]
        }
        self.call("socio.response", form.html(), vars)

    def check_ignore_list(self, uuid_from, uuid_to):
    
        if not (uuid_from and uuid_to):
            return False
        
        try:
            settings = self.obj(TelegramUserSettings, uuid_to)
        except ObjectNotFoundException:
            return False
        
        ignore_list = settings.get("ignore_list", [])
        
        try:
            user_from = self.obj(User, uuid_from)
        except ObjectNotFoundException:
            return False
            
        for entry in ignore_list:
            if entry.lower() == user_from.get("name").lower():
                return True

        return False
