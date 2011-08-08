from mg import *

class Telegram(CassandraObject):
    _indexes = {
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Telegram-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Telegram._indexes

class TelegramList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Telegram-"
        kwargs["cls"] = Telegram
        CassandraObjectList.__init__(self, *args, **kwargs)

class TelegramUser(CassandraObject):
    _indexes = {
        "contragent": [["user", "contragent"], "sent"],
        "unread": [["user", "unread"]],
        "telegram": [["telegram"]]
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "TelegramUser-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return TelegramUser._indexes

class TelegramUserList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "TelegramUser-"
        kwargs["cls"] = TelegramUser
        CassandraObjectList.__init__(self, *args, **kwargs)

class TelegramContragent(CassandraObject):
    _indexes = {
        "user": [["user"], "last_telegram"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "TelegramContragent-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return TelegramContragent._indexes

class TelegramContragentList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "TelegramContragent-"
        kwargs["cls"] = TelegramContragent
        CassandraObjectList.__init__(self, *args, **kwargs)

class Telegrams(Module):
    def register(self):
        self.rhook("telegrams.menu", self.menu)
        self.rhook("telegrams.send", self.send)
        self.rhook("ext-telegrams.list", self.telegrams_list, priv="logged")
        self.rhook("ext-telegrams.send", self.telegrams_send, priv="logged")
        self.rhook("ext-telegrams.user", self.telegrams_user, priv="logged")

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
                {"href": "/telegrams/send", "html": params.get("send_telegram", self._("Send new telegram")), "lst": True}
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
                {"html": params.get("send_telegram", self._("Send new telegram")), "lst": True}
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
        self.call("email.users", [recipient_uuid], self._("New message"), self._("You have received a new message.\n\nhttp://www.%s/telegrams/list") % self.app().domain, immediately=True)

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
