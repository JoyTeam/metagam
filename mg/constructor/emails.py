from mg.constructor import *
from mg.core.projects import Project
from mg.core.auth import User
from mg.core.emails import BulkEmailMessage
import cStringIO
import re

re_action = re.compile(r'^([a-f0-9]+)/(confirm|reject)$')
re_newline = re.compile(r'[\r\n]+')
re_img_1 = re.compile(r'<img[^>]+src="([^"]+)"[^>]*>', re.IGNORECASE)
re_img_2 = re.compile(r'\[img:([^\]]+)\]')
re_br = re.compile('<br\s*\/?>', re.IGNORECASE)

class DBBulkEmailQueue(CassandraObject):
    clsname = "BulkEmailQueue"
    indexes = {
        "waiting": [["waiting"], "created"],
    }

class DBBulkEmailQueueList(CassandraObjectList):
    objcls = DBBulkEmailQueue

class EmailSenderAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-email.index", self.menu_email_index)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-admin-email.moderation", self.admin_moderation, priv="email.moderation")
        self.rhook("headmenu-admin-email.moderation", self.headmenu_moderation)

    def permissions_list(self, perms):
        perms.append({"id": "email.moderation", "name": self._("Emails moderation")})

    def menu_email_index(self, menu):
        req = self.req()
        if req.has_access("email.moderation"):
            menu.append({"id": "email/moderation", "text": self._("Moderation"), "leaf": True, "order": 5})

    def objclasses_list(self, objclasses):
        objclasses["BulkEmailQueue"] = (DBBulkEmailQueue, DBBulkEmailQueueList)

    def headmenu_moderation(self, args):
        if args:
            m = re_action.match(args)
            if m:
                uuid, act = m.group(1, 2)
                if act == "reject":
                    return [self._("Reject"), "email/moderation/%s" % uuid]
                elif act == "confirm":
                    return [self._("Sending"), "email/moderation/%s" % uuid]
            else:
                try:
                    ent = self.obj(DBBulkEmailQueue, args)
                except ObjectNotFoundException:
                    pass
                else:
                    params = ent.get("params")
                    return [htmlescape(params.get("subject")), "email/moderation"]
        return self._("Emails moderation")

    def admin_moderation(self):
        req = self.req()
        if req.args:
            m = re_action.match(req.args)
            if m:
                uuid, act = m.group(1, 2)
                if act == "confirm":
                    # storing
                    try:
                        ent = self.obj(DBBulkEmailQueue, uuid)
                    except ObjectNotFoundException:
                        self.call("admin.redirect", "email/moderation")
                    else:
                        app = self.app().inst.appfactory.get_by_tag(ent.get("app"))
                        message = app.obj(BulkEmailMessage, ent.uuid)
                        errors = {}
                        cond = message.get("cond", 1)
                        def grep(params):
                            char = params.get("char")
                            if not char:
                                return False
                            return app.hooks.call("script.evaluate-expression", cond, globs={"char": char}, description=lambda: self._("Script condition whether to deliver an e-mail"))
                        app.modules.load(["mg.core.emails.EmailSender", "mg.constructor.emails.EmailSender"])
                        info = app.hooks.call("admin-email-sender.actual-deliver", message, ent.get("params"), errors, grep=grep)
                        if errors:
                            self.call("admin.response", u'<br />'.join(errors.values()), {})
                        ent.delkey("waiting")
                        send_history = ent.get("send_history", [])
                        ent.set("send_history", send_history)
                        message.set("sent", self.now())
                        message.set("users_sent", info["sent"])
                        message.set("users_skipped", info["skipped"])
                        send_history.append(self.now())
                        message.delkey("moderation")
                        ent.store()
                        message.store()
                        self.call("admin.response", info["status"], {})
                    self.call("admin.redirect", "email/moderation")
                elif act == "reject":
                    if req.ok():
                        errors = {}
                        # reason
                        reason = req.param("reason").strip()
                        if not reason:
                            errors["reason"] = self._("This field is mandatory")
                        # processing errors
                        if errors:
                            self.call("web.response_json", {"success": False, "errors": errors})
                        # storing
                        try:
                            ent = self.obj(DBBulkEmailQueue, uuid)
                        except ObjectNotFoundException:
                            self.call("admin.redirect", "email/moderation")
                        else:
                            message = self.app().inst.appfactory.get_by_tag(ent.get("app")).obj(BulkEmailMessage, ent.uuid)
                            ent.delkey("waiting")
                            message.delkey("moderation")
                            message.set("reject_reason", reason)
                            ent.store()
                            message.store()
                        self.call("admin.redirect", "email/moderation")
                    fields = [
                        {"name": "reason", "label": self._("Reject reason")},
                    ]
                    self.call("admin.form", fields=fields)
            try:
                ent = self.obj(DBBulkEmailQueue, req.args)
            except ObjectNotFoundException:
                self.call("admin.redirect", "email/moderation")
            params = ent.get("params")
            vars = {
                "email": {
                    "id": ent.uuid,
                    "subject": re_img_2.sub(r'<img src="\1" alt="" />', re_newline.sub('<br />', htmlescape(re_img_1.sub(r'[img:\1]', re_br.sub("\n", params.get("subject")))))),
                    "content": re_img_2.sub(r'<img src="\1" alt="" />', re_newline.sub('<br />', htmlescape(re_img_1.sub(r'[img:\1]', re_br.sub("\n", params.get("content")))))),
                },
                "Confirm": self._("Confirm"),
                "Reject": self._("Reject"),
                "EmailSubject": self._("Email subject"),
                "EmailContent": self._("Email content"),
            }
            self.call("admin.response_template", "admin/emails/moderation.html", vars)
        lst = self.objlist(DBBulkEmailQueueList, query_index="waiting", query_equal="1")
        lst.load(silent=True)
        rows = []
        for ent in lst:
            try:
                project = self.int_app().obj(Project, ent.get("app"))
            except ObjectNotFoundException:
                continue
            owner = self.obj(User, project.get("owner"))
            params = ent.get("params")
            rows.append([
                u'<hook:admin.link href="constructor/project-dashboard/%s" title="%s" /><br />%s: <hook:admin.link href="auth/user-dashboard/%s" title="%s" />' % (
                    project.uuid, htmlescape(project.get("title_short")),
                    self._("Game owner"),
                    owner.uuid, htmlescape(owner.get("name")),
                ),
                self.call("l10n.time_local", ent.get("created")),
                htmlescape(params["subject"]),
                u'<hook:admin.link href="email/moderation/%s" title="%s" />' % (ent.uuid, self._("open"))
            ])
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Game"),
                        self._("Created"),
                        self._("Subject"),
                        self._("Opening"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

class EmailSender(ConstructorModule):
    def register(self):
        self.rhook("admin-email-sender.command-hints", self.command_hints)
        self.rhook("admin-email-sender.parse", self.parse, priority=10)
        self.rhook("admin-email-sender.format", self.format, priority=10)
        self.rhook("admin-email-sender.sample-params", self.sample_params)
        self.rhook("admin-email-sender.user-params", self.user_params)
        self.rhook("admin-email-sender.delivery-form", self.delivery_form)
        self.rhook("admin-email-sender.deliver", self.deliver, priority=10)
        self.rhook("admin-email-sender.message-form-render", self.message_form_render)
        self.rhook("admin-email-sender.message-form-validate", self.message_form_validate)
        self.rhook("advice-admin-email.sender", self.advice)

    def advice(self, args, advice):
        advice.append({"title": self._("Email sender documentation"), "content": self._('You can find detailed information on the email sending system in the <a href="//www.%s/doc/emailsender" target="_blank">email sender page</a> in the reference manual.') % self.main_host})

    def message_form_render(self, message, fields):
        fields.append({"name": "cond", "label": self._("Script condition to evaluate whether a character must receive this letter") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", message.get("cond", 1))})

    def message_form_validate(self, message, errors):
        req = self.req()
        char = self.character(req.user())
        message.set("cond", self.call("script.admin-expression", "cond", errors, globs={"char": char}))

    def format(self, val, params):
        try:
            req = self.req()
        except AttributeError:
            pass
        else:
            req.templates_parsed = 0
            req.templates_len = 0
        if "description" in params:
            description = params["description"]
        try:
            retval = self.call("web.parse_template", cStringIO.StringIO(utf2str(val)), {"char": ScriptTemplateObject(params.get("char"))})
        except TemplateException as e:
            retval = None
        raise Hooks.Return(retval)

    def command_hints(self, commands):
        del commands[:]
        commands.append(self._("[% ... %] will be parsed by the templating engine"))
        commands.append(self._("[% char.name %] is a character's name"))
        self.call("admin.advice", {"title": self._("Templating engine"), "content": self._('You can find detailed information on the templating engine in the <a href="//www.%s/doc/design/templates" target="_blank">templating engine</a> in the reference manual.') % self.main_host, "order": 10})

    def sample_params(self, params):
        req = self.req()
        char = self.character(req.user())
        params["char"] = char
        params["recipient_name"] = char.name
        params["recipient_sex"] = char.sex

    def user_params(self, user, params):
        char = self.character(user.uuid)
        if char.valid:
            params["char"] = char
            params["recipient_name"] = char.name
            params["recipient_sex"] = char.sex

    def delivery_form(self, fields):
        i = 0
        while i < len(fields):
            f = fields[i]
            if f["name"] == "name" or f["name"] == "sex":
                del fields[i]
            else:
                i += 1

    def parse(self, param, val, errors):
        req = self.req()
        char = self.character(req.user())
        try:
            self.call("web.parse_template", cStringIO.StringIO(utf2str(val)), {"char": ScriptTemplateObject(char)})
        except TemplateException as e:
            if param == "content":
                param = "error"
            errors[param] = self._("Error parsing template: %s") % str(e)

    def deliver(self, message, params, errors):
        req = self.req()
        main_app = self.main_app()
        obj = main_app.obj(DBBulkEmailQueue, message.uuid, silent=True)
        obj.set("app", self.app().tag)
        obj.set("waiting", 1)
        obj.set("user", req.user())
        obj.set("created", self.now())
        obj.set("params", params)
        message.set("moderation", self.now())
        message.delkey("reject_reason")
        message.delkey("sent")
        obj.store()
        message.store()
        email = self.int_app().config.get("email.moderation")
        if email:
            self.int_app().hooks.call("email.send", email, self._("Emails moderator"), self._("E-mail moderation request"), self._("New e-mail moderation request received. Go to the admin panel please and perform required moderation actions:\n{protocol}://www.{domain}/admin#email/moderation").format(protocol=self.main_app().protocol, domain=self.main_host), immediately=True)
        raise Hooks.Return({
            "status": u'<span class="yes">%s</span>' % self._("You email was enqueued to be checked by the moderator")
        })
