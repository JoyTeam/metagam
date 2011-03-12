from mg.core import Module
from mg.core.auth import User, UserList
from concurrence.io import Socket
from concurrence.io.buffered import Buffer, BufferedReader, BufferedWriter
import re
from concurrence.smtp import *
import sys
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formatdate
import datetime
import time

class Email(Module):
    def register(self):
        Module.register(self)
        self.rhook("email.send", self.email_send)
        self.rhook("email.users", self.email_users)

    def email_send(self, to_email, to_name, subject, content, from_email=None, from_name=None, immediately=False):
        if not immediately:
            return self.call("queue.add", "email.send", {
                "to_email": to_email,
                "to_name": to_name,
                "subject": subject,
                "content": content,
                "from_email": from_email,
                "from_name": from_name,
                "immediately": True,
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
            msg = MIMEText(content, _charset="utf-8")
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

    def email_users(self, users, subject, content, from_email=None, from_name=None, immediately=False):
        if not immediately:
            return self.call("queue.add", "email.users", {
                "users": users,
                "subject": subject,
                "content": content,
                "from_email": from_email,
                "from_name": from_name,
                "immediately": True,
            }, retry_on_fail=True)

        usr = self.objlist(UserList, users)
        usr.load(silent=True)
        for user in usr:
            self.email_send(user.get("email"), user.get("name"), subject, content, from_email, from_name, immediately=True)

