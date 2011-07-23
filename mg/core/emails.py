from mg import *
from concurrence.io import Socket
from concurrence.io.buffered import Buffer, BufferedReader, BufferedWriter
from concurrence.smtp import *
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.header import Header
from email.utils import formatdate
import re
import sys
import datetime
import time
import traceback

re_sender_actions = re.compile(r'^(options)/(\S+)$');
re_format_name = re.compile(r'\[name\]')
re_image = re.compile(r'(<img[^>]*src="[^>]*>)', re.IGNORECASE)
re_image_src = re.compile(r'^(<img.*src=")([^"]+)(".*>)', re.IGNORECASE)
re_image_type = re.compile(r'^image/(.+)$')

class BulkEmailMessage(CassandraObject):
    _indexes = {
        "created": [[], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BulkEmailMessage-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return BulkEmailMessage._indexes

class BulkEmailMessageList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BulkEmailMessage-"
        kwargs["cls"] = BulkEmailMessage
        CassandraObjectList.__init__(self, *args, **kwargs)

class EmailAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-email.index", self.menu_email_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-email.settings", self.email_settings, priv="email.settings")
        self.rhook("headmenu-admin-email.settings", self.headmenu_email_settings)
        self.rhook("objclasses.list", self.objclasses_list)
        
    def objclasses_list(self, objclasses):
        objclasses["BulkEmailMessage"] = (BulkEmailMessage, BulkEmailMessageList)

    def permissions_list(self, perms):
        perms.append({"id": "email.settings", "name": self._("Email configuration")})

    def menu_root_index(self, menu):
        menu.append({"id": "email.index", "text": self._("E-mail"), "order": 32})

    def menu_email_index(self, menu):
        req = self.req()
        if req.has_access("email.settings"):
            menu.append({"id": "email/settings", "text": self._("Settings"), "leaf": True, "order": 1})

    def email_settings(self):
        req = self.req()
        exceptions = req.param("exceptions")
        if req.param("ok"):
            config = self.app().config_updater()
            int_config = self.int_app().config_updater()
            # setting
            int_config.set("email.exceptions", exceptions)
            # storing
            config.store()
            int_config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            int_config = self.int_app().config
            exceptions = int_config.get("email.exceptions")
        fields = [
            {"name": "exceptions", "label": self._("Send software exceptions to this e-mail"), "value": exceptions},
        ]
        self.call("admin.form", fields=fields)

    def headmenu_email_settings(self, args):
        return self._("E-mail settings")

class Email(Module):
    def register(self):
        Module.register(self)
        self.rhook("email.send", self.email_send)
        self.rhook("email.users", self.email_users)
        self.rhook("exception.report", self.exception_report)

    def email_send(self, to_email, to_name, subject, content, from_email=None, from_name=None, immediately=False, subtype="plain", signature=True):
        if not immediately:
            return self.call("queue.add", "email.send", {
                "to_email": to_email,
                "to_name": to_name,
                "subject": subject,
                "content": content,
                "from_email": from_email,
                "from_name": from_name,
                "immediately": True,
                "subtype": subtype,
                "signature": signature,
            }, retry_on_fail=True)
        params = {
            "email": "robot@%s" % self.app().inst.config["main_host"],
            "name": "Metagam Robot",
            "prefix": "[mg] ",
        }
        self.call("email.sender", params)
        if from_email is None or from_name is None:
            from_email = params["email"]
            from_name = params["name"]
        self.info("To %s <%s>: %s", to_name, to_email, subject)
        s = SMTP(self.app().inst.config["smtp_server"])
        try:
            if type(content) == unicode:
                content = content.encode("utf-8")
            if type(from_email) == unicode:
                from_email = from_email.encode("utf-8")
            if type(to_email) == unicode:
                to_email = to_email.encode("utf-8")
            if signature and subtype == "plain" and params.get("signature"):
                sig = params.get("signature")
                if type(sig) == unicode:
                    sig = sig.encode("utf-8")
                    content += "\n\n--\n%s" % sig
            if subtype == "raw":
                body = content
            else:
                msg = MIMEText(content, _subtype=subtype, _charset="utf-8")
                msg["Subject"] = "%s%s" % (params["prefix"], Header(subject, "utf-8"))
                msg["From"] = "%s <%s>" % (Header(from_name, "utf-8"), from_email)
                msg["To"] = "%s <%s>" % (Header(to_name, "utf-8"), to_email)
                now = datetime.datetime.now()
                stamp = time.mktime(now.timetuple())
                msg["Date"] = formatdate(timeval=stamp, localtime=False, usegmt=True)
                body = msg.as_string()
            s.sendmail("<%s>" % from_email, ["<%s>" % to_email], body)
        except SMTPRecipientsRefused as e:
            self.warning(e)
        except SMTPException as e:
            self.error(e)
            self.call("web.service_unavailable")
        finally:
            s.quit()

    def email_users(self, users, subject, content, from_email=None, from_name=None, immediately=False, subtype="plain", signature=True):
        if not immediately:
            return self.call("queue.add", "email.users", {
                "users": users,
                "subject": subject,
                "content": content,
                "from_email": from_email,
                "from_name": from_name,
                "immediately": True,
                "subtype": subtype,
                "signature": signature,
            }, retry_on_fail=True)
        usr = self.objlist(UserList, users)
        usr.load(silent=True)
        for user in usr:
            self.email_send(user.get("email"), user.get("name"), subject, content, from_email, from_name, immediately=True)

    def exception_report(self, exception):
        try:
            dump = traceback.format_exc()
            try:
                msg = u"%s %s" % (exception.__class__.__name__, exception)
            except Exception as e:
                msg = "Unhandled exception"
            email = self.int_app().config.get("email.exceptions")
            if email:
                try:
                    tag = self.app().tag
                except AttributeError:
                    tag = "NOTAG"
                vars = {}
                try:
                    req = self.req()
                except AttributeError:
                    pass
                else:
                    params = []
                    for key, values in req.param_dict().iteritems():
                        params.append({"key": htmlescape(key), "values": []})
                        for val in values:
                            params[-1]["values"].append(htmlescape(val))
                    if len(params):
                        vars["params"] = params
                    cookies = []
                    for name, cookie in req.cookies().iteritems():
                        cookies.append({"name": htmlescape(name), "value": htmlescape(cookie.value)})
                    if len(cookies):
                        vars["cookies"] = cookies
                    vars["host"] = htmlescape(req.host())
                    tag = req.host()
                    vars["uri"] = htmlescape(req.uri())
                    session = req.session()
                    if session:
                        vars["session"] = session.data_copy()
                    vars["environ"] = []
                    for key, value in req.environ.iteritems():
                        try:
                            value = unicode(value)
                        except Exception as e:
                            value = "[unicode conversion error: %s]" % e
                        if len(value) > 1000:
                            value = value[0:1000] + "..."
                        vars["environ"].append({"key": htmlescape(key), "value": htmlescape(value)})
                vars["dump"] = htmlescape(dump)
                vars["msg"] = htmlescape(msg)
                content = self.call("web.parse_template", "common/exception.html", vars)
                self.int_app().hooks.call("email.send", email, self._("Software engineer"), "%s: %s" % (tag, msg), content, immediately=True, subtype="html")
        except Exception as e:
            self.critical("Exception during exception reporting: %s", traceback.format_exc())

class EmailSender(Module):
    def register(self):
        Module.register(self)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-email.index", self.menu_email_index)
        self.rhook("ext-admin-email.sender", self.email_sender, priv="email.sender")
        self.rhook("headmenu-admin-email.sender", self.headmenu_email_sender, priv="email.sender")

    def permissions_list(self, perms):
        perms.append({"id": "email.sender", "name": self._("Email bulk sending")})

    def menu_email_index(self, menu):
        req = self.req()
        if req.has_access("email.sender"):
            menu.append({"id": "email/sender", "text": self._("Bulk sender"), "leaf": True, "order": 2})

    def headmenu_email_sender(self, args):
        m = re_sender_actions.match(args)
        if m:
            action, uuid = m.group(1, 2)
            if action == "options":
                return [self._("Sender options"), "email/sender/%s" % uuid]
        if args == "new":
            return [self._("New message"), "email/sender"]
        elif args:
            try:
                message = self.obj(BulkEmailMessage, args)
            except ObjectNotFoundException:
                return [self._("Message editor"), "email/sender"]
            else:
                return [htmlescape(message.get("subject")), "email/sender"]
            return [self._("Message editor"), "email/sender"]
        else:
            return self._("Email bulk sending")

    def email_sender(self):
        req = self.req()
        m = re_sender_actions.match(req.args)
        if m:
            action, uuid = m.group(1, 2)
            if action == "options":
                return self.email_sender_options(uuid)
        if req.args:
            if req.args != "new":
                try:
                    message = self.obj(BulkEmailMessage, req.args)
                except ObjectNotFoundException:
                    self.call("admin.redirect", "email/sender")
            else:
                message = self.obj(BulkEmailMessage, data={})
                message.set("created", self.now())
            if req.ok():
                errors = {}
                # subject
                subject = req.param("subject").strip()
                if not subject:
                    errors["subject"] = self._("Specify message subject")
                # content
                content = req.param("content")
                if not content:
                    errors["content"] = self._("Specify message content")
                # errors
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                # storing
                message.set("subject", subject)
                message.set("content", content)
                message.store()
                self.call("admin.redirect", "email/sender")
            else:
                if req.args == "new":
                    subject = ""
                    content = ""
                else:
                    subject = message.get("subject")
                    content = message.get("content")
            fields = [
                {"type": "html", "html": '%s<ul><li>%s</li><li>%s</li></ul>' % (self._("To customize your letter you may use the following commands in the subject and message content"), self._("[name] will be replaced with recipient's name"), self._("[gender?FEMALE:MALE] will be replaced with FEMALE if recipient is female and MALE if recipient is male"))},
                {"name": "subject", "value": subject, "label": self._("Message subject")},
                {"name": "content", "value": content, "type": "htmleditor", "label": self._("Message content")},
            ]
            self.call("admin.form", fields=fields, modules=["HtmlEditorPlugins"])
        rows = []
        lst = self.objlist(BulkEmailMessageList, query_index="created", query_reversed=True)
        lst.load()
        for ent in lst:
            rows.append([
                self.call("l10n.timeencode2", ent.get("created")),
                self.call("l10n.timeencode2", ent.get("sent")) if ent.get("sent") else None,
                htmlescape(ent.get("subject")),
                '<hook:admin.link href="email/sender/%s" title="%s" />' % (ent.uuid, self._("open")),
                '<hook:admin.link href="email/sender/options/%s" title="%s" />' % (ent.uuid, self._("delivery options")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "email/sender/new",
                            "text": self._("New message"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Created"),
                        self._("Sent"),
                        self._("Subject"),
                        self._("Opening"),
                        self._("Send options"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def email_sender_options(self, uuid):
        try:
            message = self.obj(BulkEmailMessage, uuid)
        except ObjectNotFoundException:
            self.call("admin.redirect", "email/sender")
        req = self.req()
        status = None
        if req.ok():
            errors = {}
            email = req.param("email")
            sex = intz(req.param("v_sex"))
            name = req.param("name")
            mode = intz(req.param("v_mode"))
            if mode == 1:
                if not email:
                    errors["email"] = self._("Enter e-mail")
                if not name:
                    errors["name"] = self._("Enter name")
                if sex != 0 and sex != 1:
                    errors["v_sex"] = self._("Invalid sex specified")
            elif mode == 2:
                pass
            else:
                errors["v_mode"] = self._("Select delivery mode")
            # errors
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            # extracting images
            content = '<font face="Tahoma">%s</font>' % message.get("content")
            tokens = re_image.split(content)
            image_num = 0
            parts = []
            if len(tokens) > 1:
                content = u""
                for token in tokens:
                    m = re_image_src.match(token)
                    if m:
                        before, src, after = m.group(1, 2, 3)
                        if type(src) == unicode:
                            src = src.encode("utf-8")
                        url_obj = urlparse.urlparse(src, "http", False)
                        if url_obj.scheme != "http" or url_obj.hostname is None:
                            errors["v_mode"] = self._("Image URL %s is incorrect") % src
                        else:
                            cnn = HTTPConnection()
                            try:
                                with Timeout.push(50):
                                    cnn.set_limit(20000000)
                                    port = url_obj.port
                                    if port is None:
                                        port = 80
                                    cnn.connect((url_obj.hostname, port))
                                    request = cnn.get(url_obj.path + url_obj.query)
                                    response = cnn.perform(request)
                                    if response.status_code != 200:
                                        if response.status_code == 404:
                                            errors["v_mode"] = self._("%s Resource not found") % src
                                        elif response.status_code == 403:
                                            errors["v_mode"] = self._("%s: Access denied") % src
                                        elif response.status_code == 500:
                                            errors["v_mode"] = self._("%s: Internal server error") % src
                                        else:
                                            errors["v_mode"] = "%s: %s" % (src, htmlescape(response.status))
                                    else:
                                        content_type = ""
                                        for header in response.headers:
                                            if header[0].lower() == "content-type":
                                                content_type = header[1]
                                                break
                                        m = re_image_type.match(content_type)
                                        if m:
                                            subtype = m.group(1)
                                            image_num += 1
                                            part = MIMEImage(response.body, subtype)
                                            part.add_header("Content-ID", "<image%d>" % image_num)
                                            filename = src.split("/")[-1]
                                            part.add_header("Content-Disposition", "attachment; filename=%s" % filename)
                                            parts.append(part)
                                            content += u'%scid:image%d%s' % (before, image_num, after)
                                        else:
                                            errors["v_mode"] = self._("URL %s is not an image") % src
                            except TimeoutError as e:
                                errors["v_mode"] = self._("Timeout on downloading %s. Time limit - 30 sec") % src
                            except Exception as e:
                                errors["v_mode"] = "%s: %s" % (src, htmlescape(str(e)))
                            finally:
                                try:
                                    cnn.close()
                                except Exception:
                                    pass
                    else:
                        content += token
            # errors
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            # delivery
            subject = message.get("subject")
            params = {
                "email": "robot@%s" % self.app().inst.config["main_host"],
                "name": "Metagam Robot",
                "prefix": "[mg] ",
            }
            self.call("email.sender", params)
            # sending
            if mode == 1:
                self.send(params, parts, email, name, sex, subject, content, immediately=True)
                status = '<span class="yes">%s</span>' % self._("Message was sent successfully")
            elif mode == 2:
                lst = self.objlist(UserList, query_index="created")
                lst.load(silent=True)
                n = 0
                for ent in lst:
                    if ent.get("email"):
                        self.send(params, parts, ent.get("email"), ent.get("name"), ent.get("sex"), subject, content, immediately=False)
                        n += 1
                status = '<span class="yes">%s</span>' % ("%d %s" % (n, self.call("l10n.literal_value", n, self._("message was queued for delivery/messages were queued for delivery"))))
        else:
            user = self.obj(User, req.user())
            email = user.get("email")
            sex = user.get("sex")
            name = user.get("name")
            mode = 1
        fields = [
            {"name": "mode", "value": mode, "type": "combo", "values": [(1, self._("Test delivery (to the administrator)")), (2, self._("Mass delivery (to all users)"))]},
            {"name": "email", "value": email, "label": self._("Destination email"), "condition": "[mode]==1"},
            {"name": "name", "value": name, "label": self._("Recipient's name"), "condition": "[mode]==1"},
            {"name": "sex", "value": sex, "label": self._("Recipient's sex"), "condition": "[mode]==1", "type": "combo", "values": [(0, self._("Male")), (1, self._("Female"))]},
        ]
        buttons = [
            {"text": self._("Send")},
        ]
        if status:
            fields.append({"type": "header", "html": status})
        self.call("admin.form", fields=fields, buttons=buttons)

    def send(self, params, parts, email, name, sex, subject, content, immediately=False):
        subject = format_gender(sex, subject)
        subject = re_format_name.sub(name, subject)
        content = format_gender(sex, content)
        content = re_format_name.sub(name, content)
        # converting data
        if type(content) == unicode:
            content = content.encode("utf-8")
        print content
        # making MIME message
        multipart = MIMEMultipart("related");
        multipart["Subject"] = "%s%s" % (params["prefix"], Header(subject, "utf-8"))
        multipart["From"] = "%s <%s>" % (Header(params["name"], "utf-8"), params["email"])
        multipart["To"] = "%s <%s>" % (Header(name, "utf-8"), email)
        multipart["type"] = "text/html"
        now = datetime.datetime.now()
        stamp = time.mktime(now.timetuple())
        multipart["Date"] = formatdate(timeval=stamp, localtime=False, usegmt=True)
        # HTML part
        html_part = MIMEText(content, _subtype="html", _charset="utf-8")
        # Assembling multipart
        multipart.attach(html_part)
        for part in parts:
            multipart.attach(part)
        body = multipart.as_string()
        self.call("email.send", email, name, subject, body, subtype="raw", immediately=immediately)
