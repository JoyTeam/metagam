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

from mg import *
from concurrence.io import Socket
from concurrence.io.buffered import Buffer, BufferedReader, BufferedWriter
from concurrence.smtp import *
from concurrence import Timeout
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
import hashlib

re_sender_actions = re.compile(r'^(options)/(\S+)$');
re_format_name = re.compile(r'\[name\]')
re_image = re.compile(r'(<img[^>]*src="[^>]*>)', re.IGNORECASE)
re_image_src = re.compile(r'^(<img.*src=")([^"]+)(".*>)', re.IGNORECASE)
re_image_type = re.compile(r'^image/(.+)$')

MAX_SIMILAR_EMAILS = 10

class BulkEmailMessage(CassandraObject):
    clsname = "BulkEmailMessage"
    indexes = {
        "created": [[], "created"],
    }

class BulkEmailMessageList(CassandraObjectList):
    objcls = BulkEmailMessage

class UnsubscribeCode(CassandraObject):
    clsname = "UnsubscribeCode"
    indexes = {
        "created": [[], "created"],
        "email": [["email"], "created"],
    }

class UnsubscribeCodeList(CassandraObjectList):
    objcls = UnsubscribeCode

class EmailBlackList(CassandraObject):
    clsname = "EmailBlackList"
    indexes = {
        "created": [[], "created"],
    }

class EmailBlackListList(CassandraObjectList):
    objcls = EmailBlackList

class EmailAdmin(Module):
    def register(self):
        self.rhook("menu-admin-email.index", self.menu_email_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-email.settings", self.email_settings, priv="email.settings")
        self.rhook("headmenu-admin-email.settings", self.headmenu_email_settings)

    def permissions_list(self, perms):
        perms.append({"id": "email.settings", "name": self._("Email configuration")})

    def menu_email_index(self, menu):
        req = self.req()
        if req.has_access("email.settings"):
            menu.append({"id": "email/settings", "text": self._("Settings"), "leaf": True, "order": 1})

    def email_settings(self):
        req = self.req()
        if req.param("ok"):
            config = self.app().config_updater()
            int_config = self.int_app().config_updater()
            # setting
            int_config.set("email.exceptions", req.param("exceptions"))
            int_config.set("email.moderation", req.param("moderation"))
            # storing
            config.store()
            int_config.store()
            self.call("admin.response", self._("Settings stored"), {})
        int_config = self.int_app().config
        fields = [
            {"name": "exceptions", "label": self._("Send software exceptions to this e-mail"), "value": int_config.get("email.exceptions")},
            {"name": "moderation", "label": self._("Send email moderation requests to this e-mail"), "value": int_config.get("email.moderation")},
        ]
        self.call("admin.form", fields=fields)

    def headmenu_email_settings(self, args):
        return self._("E-mail settings")

class Email(Module):
    def register(self):
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("email.send", self.email_send)
        self.rhook("email.users", self.email_users)
        self.rhook("exception.report", self.exception_report)
        self.rhook("email.unsubscribe-code", self.unsubscribe_code)
        self.rhook("email.unsubscribe-text", self.unsubscribe_text)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("email.cleanup", self.cleanup)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-email.unsubscribe", self.unsubscribe, priv="public")
        self.rhook("email.unblacklist", self.unblacklist)

    def objclasses_list(self, objclasses):
        objclasses["BulkEmailMessage"] = (BulkEmailMessage, BulkEmailMessageList)
        objclasses["EmailBlackList"] = (EmailBlackList, EmailBlackListList)
        objclasses["UnsubscribeCode"] = (UnsubscribeCode, UnsubscribeCodeList)
        
    def schedule(self, sched):
        sched.add("email.cleanup", "5 1 * * *", priority=10)

    def cleanup(self):
        self.objlist(UnsubscribeCodeList, query_index="created", query_finish=self.now(-86400 * 7)).remove()

    def menu_root_index(self, menu):
        menu.append({"id": "email.index", "text": self._("E-mail"), "order": 32})

    def email_send(self, to_email, to_name, subject, content, from_email=None, from_name=None, immediately=False, subtype="plain", signature=True, headers={}):
        with Timeout.push(30):
            fingerprint = utf2str(from_email) + "/" + utf2str(to_email) + "/" + utf2str(subject)
            m = hashlib.md5()
            m.update(fingerprint)
            fingerprint = m.hexdigest()
            mcid = "email-sent-%s" % fingerprint
            sent = intz(self.app().mc.get(mcid))
            if sent < 0:
                return
            if sent >= MAX_SIMILAR_EMAILS:
                self.warning("Blocked email flood to %s: %s", to_email, subject)
                self.app().mc.set(mcid, -1, 3600)
                return
            self.app().mc.set(mcid, sent + 1, 600)
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
                    "headers": headers,
                })
            params = {
                "email": "robot@%s" % self.main_host,
                "name": "Metagam Robot",
                "prefix": "[mg] ",
            }
            self.call("email.sender", params)
            if from_email is None or from_name is None:
                from_email = params["email"]
                from_name = params["name"]
            self.info("%s: To %s <%s>: %s", mcid, utf2str(to_name), utf2str(to_email), utf2str(subject))
            s = SMTP(self.clconf("smtp_server", "127.0.0.1"))
            try:
                if type(content) == unicode:
                    content = content.encode("utf-8")
                if type(from_email) == unicode:
                    from_email = from_email.encode("utf-8")
                if type(to_email) == unicode:
                    to_email = to_email.encode("utf-8")
                if signature and subtype == "plain":
                    sig = params.get("signature") or ""
                    sig = str2unicode(sig)
                    # unsubscribe
                    if sig:
                        sig += "\n"
                    if to_name:
                        sig += self._('Your name is {user_name}').format(
                            user_name=to_name
                        )
                    if getattr(self.app(), "canonical_domain", None):
                        sig += "\n"
                        sig += self._("Remind password - {href}").format(
                            href="{protocol}://{domain}/auth/remind".format(
                                protocol=self.app().protocol,
                                domain=self.app().canonical_domain,
                            ),
                        )
                        sig += "\n"
                        sig += self.call("email.unsubscribe-text", to_email)
                    if sig:
                        content += "\n\n--\n%s" % utf2str(sig)
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
                    try:
                        msg["X-Metagam-Project"] = self.app().tag
                    except AttributeError:
                        pass
                    for key, val in headers.iteritems():
                        msg[key] = val
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
            })
        usr = self.objlist(UserList, users)
        usr.load(silent=True)
        for user in usr:
            self.email_send(self.call("user.email", user), user.get("name"), subject, content, from_email, from_name, immediately=True)

    def exception_report(self, exception, e_type=None, e_value=None, e_traceback=None):
        try:
            if e_type is None:
                e_type, e_value, e_traceback = sys.exc_info()
            dump = "".join(traceback.format_exception(e_type, e_value, e_traceback))
            try:
                msg = u"%s %s" % (exception.__class__.__name__, exception)
            except Exception as e:
                msg = "Unhandled exception"
            email = self.int_app().config.get("email.exceptions")
            if email:
                try:
                    app = self.app()
                    try:
                        tag = app.tag
                    except AttributeError:
                        tag = "NOTAG"
                    try:
                        project = app.project
                    except AttributeError:
                        project = None
                except AttributeError:
                    tag = "NOAPP"
                    app = None
                    project = None
                vars = {}
                # project owner
                if project:
                    vars["project"] = project.uuid
                    vars["project_title"] = htmlescape(project.get("title_short"))
                    vars["project_owner"] = project.get("owner")
                    if vars["project_owner"]:
                        try:
                            owner = self.main_app().obj(User, vars["project_owner"])
                        except ObjectNotFoundException:
                            pass
                        else:
                            vars["project_owner_name"] = htmlescape(owner.get("name"))
                    vars["main_host"] = self.main_host
                    vars["main_protocol"] = self.main_app().protocol
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

    def unsubscribe_code(self, email):
        obj = self.obj(UnsubscribeCode)
        obj.set("email", email)
        obj.set("created", self.now())
        obj.store()
        return obj.uuid

    def unsubscribe_text(self, email):
        code = self.call("email.unsubscribe-code", email)
        return self._("Unsubscribe - {protocol}://{domain}/email/unsubscribe/{code}").format(protocol=self.app().protocol, domain=self.app().canonical_domain, code=code)

    def unsubscribe(self):
        vars = {
            "title": self._("Email unsubscription"),
            "ret": {
                "href": "/",
                "title": self._("Cancel"),
            },
        }
        req = self.req()
        code = req.args
        if not code:
            self.call("web.not_found")
        try:
            obj = self.obj(UnsubscribeCode, code)
        except ObjectNotFoundException:
            self.call("auth.message", self._("This unsubscription link has expired already"), vars)
        if req.param("confirm"):
            block = self.obj(EmailBlackList, obj.get("email"), silent=True)
            block.set("created", self.now())
            block.store()
            self.call("auth.message", self._("No more letters will be delivered to {email}, sorry for inconvinience.").format(email=htmlescape(obj.get("email"))), vars)
        self.call("auth.message", u'<a href="/email/unsubscribe/%s?confirm=1">%s</a>' % (code, self._("Disable sending letters to {email}").format(email=htmlescape(obj.get("email")))), vars)

    def unblacklist(self, email):
        if not email:
            return
        try:
            self.obj(EmailBlackList, email).remove()
        except ObjectNotFoundException:
            pass

class EmailSender(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-email.index", self.menu_email_index)
        self.rhook("ext-admin-email.sender", self.email_sender, priv="email.sender")
        self.rhook("headmenu-admin-email.sender", self.headmenu_email_sender, priv="email.sender")
        self.rhook("admin-email-sender.format", self.format)
        self.rhook("admin-email-sender.parse", self.parse)
        self.rhook("admin-email-sender.deliver", self.deliver)
        self.rhook("admin-email-sender.actual-deliver", self.deliver)

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
                else:
                    subject = self.call("admin-email-sender.parse", "subject", subject, errors)
                # content
                content = req.param("content")
                if not content:
                    errors["content"] = self._("Specify message content")
                else:
                    content = self.call("admin-email-sender.parse", "content", content, errors)
                self.call("admin-email-sender.message-form-validate", message, errors)
                # errors
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors, "error": errors.get("error")})
                # storing
                message.set("subject", subject)
                message.set("content", content)
                message.store()
                self.call("admin.redirect", "email/sender/options/%s" % message.uuid)
            else:
                if req.args == "new":
                    subject = ""
                    content = ""
                else:
                    subject = message.get("subject")
                    content = message.get("content")
            commands = []
            commands.append(self._("[name] will be replaced with recipient's name"))
            commands.append(self._("[gender?FEMALE:MALE] will be replaced with FEMALE if recipient is female and MALE if recipient is male"))
            self.call("admin-email-sender.command-hints", commands)
            commands = ''.join([u'<li>%s</li>' % cmd for cmd in commands])
            fields = [
                {"type": "html", "html": '%s<ul>%s</ul>' % (self._("To customize your letter you may use the following commands in the subject and message content"), commands)},
                {"name": "subject", "value": subject, "label": self._("Message subject")},
                {"name": "content", "value": content, "type": "htmleditor", "label": self._("Message content")},
            ]
            self.call("admin-email-sender.message-form-render", message, fields)
            self.call("admin.advice", {
                "title": self._("How to write perfect e-mail"),
                "content": self._("Try to use as much personalisation as possible. A player should feel that e-mail is not just a bulk e-mail delivery, but a directed email to himself. Greet a player personally: 'Hello [%char.name%]', use correct sex, character class and so on: 'Dear fairy Maria'."),
                "order": 20
            })
            self.call("admin.form", fields=fields, modules=["HtmlEditorPlugins"])
        rows = []
        lst = self.objlist(BulkEmailMessageList, query_index="created", query_reversed=True)
        lst.load()
        for ent in lst:
            if ent.get("moderation"):
                sent = self._("on moderation")
            elif ent.get("sent"):
                sent = u'<span class="yes">%s</span>' % (self.call("l10n.time_local", ent.get("sent")))
                sent += u'<br />%s: %s' % (self._("letters sent"), ent.get("users_sent"))
                if ent.get("users_skipped"):
                    sent += u'<br />%s: %s' % (self._("users skipped"), ent.get("users_skipped"))
            elif ent.get("reject_reason"):
                sent = u'<span class="no">%s</span>' % (self._("Rejected by moderator: %s") % htmlescape(ent.get("reject_reason")))
            else:
                sent = None
            rows.append([
                self.call("l10n.time_local", ent.get("created")),
                sent,
                htmlescape(ent.get("subject")),
                '<hook:admin.link href="email/sender/%s" title="%s" />' % (ent.uuid, self._("edit")),
                '<hook:admin.link href="email/sender/options/%s" title="%s" />' % (ent.uuid, self._("delivery options")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "email/sender",
                            "text": self._("Update"),
                        },
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
                        self._("Editing"),
                        self._("Delivery options"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def parts(self, params, errors):
        tokens = re_image.split(params["content"])
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
                                request.add_header("Connection", "close")
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
            params["content"] = content
        params["parts"] = parts

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
            elif mode == 2:
                pass
            else:
                errors["v_mode"] = self._("Select delivery mode")
            # errors
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            # extracting images
            content = '<font face="Tahoma">%s</font>' % message.get("content")
            subject = message.get("subject")
            params = {
                "email": "robot@%s" % self.main_host,
                "name": "Metagam Robot",
                "prefix": "[mg] ",
                "content": content,
                "subject": subject,
            }
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # delivery
            self.call("email.sender", params)
            # sending
            if mode == 1:
                self.parts(params, errors)
                params["recipient_name"] = name
                params["recipient_sex"] = sex
                self.call("admin-email-sender.sample-params", params)
                self.send(params, email, immediately=True)
                status = '<span class="yes">%s</span>' % self._("Message was sent successfully")
            elif mode == 2:
                info = self.call("admin-email-sender.deliver", message, params, errors)
                status = info.get("status")
        else:
            user = self.obj(User, req.user())
            email = self.call("user.email", user)
            sex = user.get("sex")
            name = user.get("name")
            mode = 1
        fields = [
            {"name": "mode", "value": mode, "type": "combo", "values": [(1, self._("Test delivery (to the administrator)")), (2, self._("Mass delivery (to all users)"))]},
            {"name": "email", "value": email, "label": self._("Destination email"), "condition": "[mode]==1"},
            {"name": "name", "value": name, "label": self._("Recipient's name"), "condition": "[mode]==1"},
            {"name": "sex", "value": sex, "label": self._("Recipient's sex"), "condition": "[mode]==1", "type": "combo", "values": [(0, self._("Male")), (1, self._("Female"))]},
        ]
        self.call("admin-email-sender.delivery-form", fields)
        buttons = [
            {"text": self._("Send")},
        ]
        if status:
            fields.append({"type": "header", "html": status})
        self.call("admin.form", fields=fields, buttons=buttons)

    def deliver(self, message, params, errors, grep=None):
        params = params.copy()
        self.parts(params, errors)
        lst = self.objlist(UserList, query_index="created")
        lst.load(silent=True)
        sent = 0
        skipped = 0
        for ent in lst:
            email = self.call("user.email", ent)
            if email:
                name = ent.get("name")
                if name:
                    par = params.copy()
                    par["recipient_name"] = name
                    par["recipient_sex"] = ent.get("sex")
                    self.call("admin-email-sender.user-params", ent, par)
                    if grep and not grep(par):
                        skipped += 1
                        continue
                    self.send(par, email, immediately=False)
                    sent += 1
        return {
            "sent": sent,
            "skipped": skipped,
            "status": '<span class="yes">%s</span>' % ("%d %s" % (sent, self.call("l10n.literal_value", sent, self._("message was queued for delivery/messages were queued for delivery"))))
        }

    def parse(self, param, val, errors):
        return val

    def format(self, val, params):
        val = format_gender(params["recipient_sex"], val)
        val = re_format_name.sub(params["recipient_name"], val)
        return val

    def send(self, params, email, immediately=False):
        # checking for blacklisting
        try:
            obj = self.obj(EmailBlackList, email)
        except ObjectNotFoundException:
            pass
        else:
            # blacklisted
            return
        content = params["content"]
        subject = params["subject"]
        parts = params["parts"]
        params["description"] = self._("Email subject")
        subject = self.call("admin-email-sender.format", subject, params)
        if subject is None or not subject.strip():
            return
        params["description"] = self._("Email content")
        content = self.call("admin-email-sender.format", content, params)
        if content is None or not content.strip():
            return
        # converting data
        content = str2unicode(content)
        domain = self.app().canonical_domain
        protocol = self.app().protocol
        content += u'<br>--<br>{project_title} &mdash; <a href="{protocol}://{domain}/" target="_blank">{protocol}://{domain}</a><br>{your_name}<br>{unsubscribe}'.format(
            protocol=protocol,
            domain=domain,
            project_title=htmlescape(self.call("project.title")),
            your_name=self._('Your name is {user_name} &mdash; <a href="{href}" target="_blank">remind password</a>').format(
                user_name=htmlescape(params.get("recipient_name")),
                href="{protocol}://{domain}/auth/remind?email={email}".format(
                    protocol=protocol,
                    domain=domain,
                    email=urlencode(email),
                ),
            ),
            unsubscribe=self._('To stop receiving letters press <a href="{href}" target="_blank">here</a>').format(
                href="{protocol}://{domain}/email/unsubscribe/{code}".format(
                    protocol=protocol,
                    domain=domain,
                    code=self.call("email.unsubscribe-code", email),
                ),
            ),
        )
        content = utf2str(content)
        # making MIME message
        multipart = MIMEMultipart("related");
        multipart["Subject"] = "%s%s" % (params["prefix"], Header(subject, "utf-8"))
        multipart["From"] = "%s <%s>" % (Header(params["name"], "utf-8"), params["email"])
        multipart["To"] = "%s <%s>" % (Header(params["recipient_name"], "utf-8"), email)
        multipart["type"] = "text/html"
        try:
            multipart["X-Metagam-Project"] = self.app().tag
        except AttributeError:
            pass
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
        self.call("email.send", email, params["recipient_name"], subject, body, subtype="raw", immediately=immediately)
