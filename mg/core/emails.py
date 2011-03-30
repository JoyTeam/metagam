from mg import *
from mg.core.auth import User, UserList
from concurrence.io import Socket
from concurrence.io.buffered import Buffer, BufferedReader, BufferedWriter
from concurrence.smtp import *
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formatdate
import re
import sys
import datetime
import time
import traceback

class EmailAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-constructor.cluster", self.menu_constructor_cluster)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-constructor.email-settings", self.email_settings, priv="email.settings")
        self.rhook("headmenu-admin-constructor.email-settings", self.headmenu_email_settings)

    def permissions_list(self, perms):
        perms.append({"id": "email.settings", "name": self._("Email configuration")})

    def menu_constructor_cluster(self, menu):
        req = self.req()
        if req.has_access("email.settings"):
            menu.append({"id": "constructor/email-settings", "text": self._("E-mail"), "leaf": True})

    def email_settings(self):
        req = self.req()
        exceptions = req.param("exceptions")
        int_config = self.int_app().config
        if req.param("ok"):
            config = self.app().config
            int_config.set("email.exceptions", exceptions)
            config.store()
            int_config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
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
            "email": "aml@rulezz.ru",
            "name": "MG Robot",
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
            msg = MIMEText(content, _subtype=subtype, _charset="utf-8")
            msg["Subject"] = "%s%s" % (params["prefix"], Header(subject, "utf-8"))
            msg["From"] = "%s <%s>" % (Header(from_name, "utf-8"), from_email)
            msg["To"] = "%s <%s>" % (Header(to_name, "utf-8"), to_email)
            now = datetime.datetime.now()
            stamp = time.mktime(now.timetuple())
            msg["Date"] = formatdate(timeval=stamp, localtime=False, usegmt=True)
            s.sendmail("<%s>" % from_email, ["<%s>" % to_email], msg.as_string())
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
                msg = u"%s" % exception
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
                except RuntimeError:
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
