from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from mg.core import Module
from uuid import uuid4
from wsgiref.handlers import format_date_time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from mg.core.bezier import make_bezier
from mg.core.tools import *
from operator import itemgetter
import cStringIO
import time
import re
import random
import hashlib
import cgi

class User(CassandraObject):
    _indexes = {
        "created": [[], "created"],
        "last_login": [[], "last_login"],
        "name": [["name_lower"]],
        "inactive": [["inactive"], "created"],
        "email": [["email"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "User-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return User._indexes

class UserList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "User-"
        kwargs["cls"] = User
        CassandraObjectList.__init__(self, *args, **kwargs)

class UserPermissions(CassandraObject):
    _indexes = {
        "any": [["any"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserPermissions-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return UserPermissions._indexes

    def sync(self):
        self.set("any", "1")

class UserPermissionsList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserPermissions-"
        kwargs["cls"] = UserPermissions
        CassandraObjectList.__init__(self, *args, **kwargs)

class Session(CassandraObject):
    _indexes = {
        "valid_till": [[], "valid_till"],
        "user": [["user"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Session-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Session._indexes

    def user(self):
        return self.get("user")

    def semi_user(self):
        user = self.get("user")
        if user is not None:
            return user
        return self.get("semi_user")

class SessionList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Session-"
        kwargs["cls"] = Session
        CassandraObjectList.__init__(self, *args, **kwargs)

class Captcha(CassandraObject):
    _indexes = {
        "valid_till": [[], "valid_till"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Captcha-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Captcha._indexes

class CaptchaList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Captcha-"
        kwargs["cls"] = Captcha
        CassandraObjectList.__init__(self, *args, **kwargs)

class Sessions(Module):
    "The mostly used authentication functions. It must load very fast"
    def register(self):
        Module.register(self)
        self.rhook("session.get", self.get_session)
        self.rhook("session.require_login", self.require_login)
        self.rhook("session.find_user", self.find_user)
        self.rhook("session.require_permission", self.require_permission)

    def find_session(self, sid):
        try:
            return self.obj(Session, sid)
        except ObjectNotFoundException:
            return None

    def get_session(self, create=False, cache=True, domain=None):
        req = self.req()
        if cache:
            try:
                return req._session
            except AttributeError:
                pass
        cookie_name = "mgsess-%s" % self.app().tag
        sid = req.cookie(cookie_name)
        if sid is not None:
            mcid = "SessionCache-%s" % sid
            val = self.app().mc.get(mcid)
            if val is not None:
                session = self.obj(Session, sid, val)
                if cache:
                    req._session = session
                return session
            session = self.find_session(sid)
            if session is not None:
                session.set("valid_till", "%020d" % (time.time() + 90 * 86400))
                session.store()
                self.app().mc.set(mcid, session.data)
                if cache:
                    req._session = session
                return session
        sid = uuid4().hex
        args = {}
        if domain is None:
            domain = req.environ.get("HTTP_X_REAL_HOST")
        if domain is not None:
            domain = re.sub(r'^www\.', '', domain)
            args["domain"] = "." + domain
        args["path"] = "/"
        args["expires"] = format_date_time(time.mktime(datetime.datetime.now().timetuple()) + 90 * 86400)
        req.set_cookie(cookie_name, sid, **args)
        session = self.obj(Session, sid, {})
        if create:
            # newly created session is stored for 24 hour only
            # this interval is increased after the next successful 'get'
            session.set("valid_till", "%020d" % (time.time() + 86400))
            session.store()
        if cache:
            req._session = session
        return session

    def require_login(self):
        session = self.call("session.get")
        if session is None or session.get("user") is None:
            req = self.req()
            self.call("web.redirect", "/auth/login?redirect=%s" % urlencode(req.uri()))
        return session

    def find_user(self, name, allow_email=False):
        name = name.lower()
        users = self.objlist(UserList, query_index="name", query_equal=name)
        if len(users):
            users.load()
            return users[0]
        if allow_email:
            users = self.objlist(UserList, query_index="email", query_equal=name)
            if len(users):
                users.load()
                return users[0]
        return None

    def require_permission(self, perm):
        req = self.req()
        if not req.has_access(perm):
            self.call("web.forbidden")

class Interface(Module):
    "Functions used in special interfaces (user and admin)"
    def register(self):
        Module.register(self)
        self.rhook("auth.permissions", self.auth_permissions)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-users.index", self.menu_users_index)
        self.rhook("ext-admin-auth.permissions", self.admin_permissions)
        self.rhook("headmenu-admin-auth.permissions", self.headmenu_permissions)
        self.rhook("ext-admin-auth.editpermissions", self.admin_editpermissions)
        self.rhook("headmenu-admin-auth.editpermissions", self.headmenu_editpermissions)
        self.rhook("ext-admin-auth.edituserpermissions", self.admin_edituserpermissions)
        self.rhook("headmenu-admin-auth.edituserpermissions", self.headmenu_edituserpermissions)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("security.list-roles", self.list_roles)
        self.rhook("security.users-roles", self.users_roles)
        self.rhook("all.schedule", self.schedule)
        self.rhook("auth.cleanup", self.cleanup)
        self.rhook("ext-auth.register", self.ext_register)
        self.rhook("ext-auth.captcha", self.ext_captcha)
        self.rhook("ext-auth.logout", self.ext_logout)
        self.rhook("ext-auth.login", self.ext_login)
        self.rhook("auth.messages", self.messages, priority=10)
        self.rhook("ext-auth.ajax-login", self.ext_ajax_login)
        self.rhook("ext-auth.activate", self.ext_activate)
        self.rhook("ext-auth.remind", self.ext_remind)
        self.rhook("ext-auth.change", self.ext_change)
        self.rhook("ext-auth.email", self.ext_email)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-admin-auth.user-find", self.ext_user_find)
        self.rhook("ext-admin-auth.user-dashboard", self.ext_user_dashboard)
        self.rhook("ext-admin-auth.user-lastreg", self.ext_user_lastreg)
        self.rhook("headmenu-admin-auth.user-dashboard", self.headmenu_user_dashboard)

    def schedule(self, sched):
        sched.add("auth.cleanup", "5 1 * * *", priority=10)

    def cleanup(self):
        sessions = self.objlist(SessionList, query_index="valid_till", query_finish="%020d" % time.time())
        sessions.remove()
        captchas = self.objlist(CaptchaList, query_index="valid_till", query_finish="%020d" % time.time())
        captchas.remove()
        users = self.objlist(UserList, query_index="inactive", query_equal="1", query_finish="%020d" % (time.time() - 86400 * 3))
        users.remove()

    def objclasses_list(self, objclasses):
        objclasses["User"] = (User, UserList)
        objclasses["UserPermissions"] = (UserPermissions, UserPermissionsList)
        objclasses["Session"] = (Session, SessionList)
        objclasses["Captcha"] = (Captcha, CaptchaList)

    def ext_register(self):
        req = self.req()
        session = self.call("session.get", True)
        form = self.call("web.form", "common/form.html")
        name = req.param("name")
        sex = req.param("sex")
        email = req.param("email")
        password1 = req.param("password1")
        password2 = req.param("password2")
        captcha = req.param("captcha")
        redirect = req.param("redirect")
        params = {
            "name_re": r'^[A-Za-z0-9_-]+$',
            "name_invalid_re": self._("Invalid characters in the name. Only latin letters, numbers, symbols '_' and '-' are allowed"),
        }
        self.call("auth.form_params", params)
        if req.ok():
            if not name:
                form.error("name", self._("Enter your user name"))
            elif not re.match(params["name_re"], name, re.UNICODE):
                form.error("name", params["name_invalid_re"])
            elif self.call("session.find_user", name, allow_email=True):
                form.error("name", self._("This name is taken already"))
            if not password1:
                form.error("password1", self._("Enter your password"))
            elif len(password1) < 6:
                form.error("password1", self._("Minimal password length - 6 characters"))
            elif not password2:
                form.error("password2", self._("Retype your password"))
            elif password1 != password2:
                form.error("password2", self._("Password don't match. Try again, please"))
                password1 = ""
                password2 = ""
            if sex != "0" and sex != "1":
                form.error("sex", self._("Select your sex"))
            if not email:
                form.error("email", self._("Enter your e-mail address"))
            elif not re.match(r'^[a-zA-Z0-9_\-+\.]+@[a-zA-Z0-9\-_\.]+\.[a-zA-Z0-9]+$', email):
                form.error("email", self._("Enter correct e-mail"))
            else:
                existing_email = self.objlist(UserList, query_index="email", query_equal=email.lower())
                existing_email.load(silent=True)
                if len(existing_email):
                    form.error("email", self._("There is another user with this email"))
            if not captcha:
                form.error("captcha", self._("Enter numbers from the picture"))
            else:
                try:
                    cap = self.obj(Captcha, session.uuid)
                    if cap.get("number") != captcha:
                        form.error("captcha", self._("Incorrect number"))
                except ObjectNotFoundException:
                    form.error("captcha", self._("Incorrect number"))
            self.call("auth.register-form", form, "validate")
            if not form.errors:
                email = email.lower()
                user = self.obj(User)
                now = "%020d" % time.time()
                user.set("created", now)
                user.set("last_login", now)
                user.set("sex", sex)
                user.set("name", name)
                user.set("name_lower", name.lower())
                user.set("email", email.lower())
                user.set("inactive", 1)
                activation_code = uuid4().hex
                user.set("activation_code", activation_code)
                user.set("activation_redirect", redirect)
                salt = ""
                letters = "abcdefghijklmnopqrstuvwxyz"
                for i in range(0, 10):
                    salt += random.choice(letters)
                user.set("salt", salt)
                user.set("pass_reminder", re.sub(r'^(..).*$', r'\1...', password1))
                m = hashlib.md5()
                m.update(salt + password1.encode("utf-8"))
                user.set("pass_hash", m.hexdigest())
                user.store()
                params = {
                    "subject": self._("Account activation"),
                    "content": self._("Someone possibly you requested registration on the {host}. If you really want to do this enter the following activation code on the site:\n\n{code}\n\nor simply follow the link:\n\nhttp://{host}/auth/activate/{user}?code={code}"),
                }
                self.call("auth.activation_email", params)
                self.call("email.send", email, name, params["subject"], params["content"].format(code=activation_code, host=req.host(), user=user.uuid))
                self.call("web.redirect", "/auth/activate/%s" % user.uuid)
        if redirect is not None:
            form.hidden("redirect", redirect)
        form.input(self._("User name"), "name", name)
        form.select(self._("Sex"), "sex", sex, [{"value": 0, "description": self._("Male")}, {"value": 1, "description": self._("Female")}])
        form.input(self._("E-mail"), "email", email)
        form.password(self._("Password"), "password1", password1)
        form.password(self._("Confirm password"), "password2", password2)
        form.input('<img id="captcha" src="/auth/captcha" alt="" /><br />' + self._('Enter a number (6 digits) from the picture'), "captcha", "")
        self.call("auth.register-form", form, "render")
        form.submit(None, None, self._("Register"))
        vars = {
            "title": self._("User registration"),
            "ret": {
                "href": "/",
                "title": self._("Cancel"),
            },
        }
        self.call("web.response_global", form.html(vars), vars)

    def ext_activate(self):
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        if not user.get("inactive"):
            redirects = {}
            self.call("auth.redirects", redirects)
            if redirects.has_key("register"):
                self.call("web.redirect", redirects["register"])
            self.call("web.redirect", "/")
        session = self.call("session.get", True)
        form = self.call("web.form", "common/form.html")
        code = req.param("code")
        if req.ok():
            if not code:
                form.error("code", self._("Enter activation code from your e-mail box"))
            elif code != user.get("activation_code"):
                form.error("code", self._("Invalid activation code"))
            if not form.errors:
                redirect = user.get("activation_redirect")
                user.delkey("inactive")
                user.delkey("activation_code")
                user.delkey("activation_redirect")
                user.store()
                self.call("auth.registered", user)
                session.set("user", user.uuid)
                session.delkey("semi_user")
                session.store()
                self.app().mc.delete("SessionCache-%s" % session.uuid)
                if redirect is not None and redirect != "":
                    self.call("web.redirect", redirect)
                redirects = {}
                self.call("auth.redirects", redirects)
                if redirects.has_key("register"):
                    self.call("web.redirect", redirects["register"])
                self.call("web.redirect", "/")
        form.input(self._("Activation code"), "code", code)
        form.submit(None, None, self._("Activate"))
        form.add_message_top(self._("A message was sent to your mailbox. Enter the activation code from this message."))
        vars = {
            "title": self._("User activation"),
        }
        self.call("web.response_global", form.html(), vars)

    def ext_remind(self):
        req = self.req()
        form = self.call("web.form", "common/form.html")
        email = req.param("email")
        redirect = req.param("redirect")
        if req.ok():
            if not email:
                form.error("email", self._("Enter your e-mail"))
            if not form.errors:
                list = self.objlist(UserList, query_index="email", query_equal=email.lower())
                if not len(list):
                    form.error("email", self._("No users with this e-mail"))
            if not form.errors:
                list.load()
                name = ""
                content = ""
                for user in list:
                    content += self._("User '{user}' has password '{password}'\n").format(user=user.get("name"), password=user.get("pass_reminder"))
                    name = user.get("name")
                params = {
                    "subject": self._("Password reminder"),
                    "content": self._("Someone possibly you requested password recovery on the {host} site. Accounts registered with your e-mail are:\n\n{content}\nIf you still can't remember your password feel free to contact our support.")
                }
                self.call("auth.remind_email", params)
                self.call("email.send", email, name, params["subject"], params["content"].format(content=content.encode("utf-8"), host=req.host()))
                if redirect is not None and redirect != "":
                    self.call("web.redirect", "/auth/login?redirect=%s" % urlencode(redirect))
                self.call("web.redirect", "/auth/login")
        form.hidden("redirect", redirect)
        form.input(self._("Your e-mail"), "email", email)
        form.submit(None, None, self._("Remind"))
        vars = {
            "title": self._("Password reminder"),
        }
        self.call("web.response_global", form.html(), vars)

    def ext_captcha(self):
        session = self.call("session.get")
        if session is None:
            self.call("web.forbidden")
        field = 25
        char_w = 35
        char_h = 40
        step = 20
        digits = 6
        jitter = 0.15
        image = Image.new("RGB", (step * (digits - 1) + char_w + field * 2, char_h + field * 2), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        number = ""
        ts = [t / 50.0 for t in range(51)]
        for i in range(0, digits):
            digit = random.randint(0, 9)
            number += str(digit)
            off_x = i * step + field
            off_y = field + char_h * random.uniform(-0.1, 0.1)
            if digit == 0:
                splines = [
                    ((0, 0.33), (0.33, -0.1), (0.67, -0.1), (1, 0.33), (1, 0.67)),
                    ((1, 0.67), (0.67, 1.1), (0.33, 1.1), (0, 0.67), (0, 0.33)),
                ]
            elif digit == 1:
                splines = [
                    ((0, 0.5), (0.6, 0)),
                    ((0.6, 0), (0.6, 1)),
                ]
            elif digit == 2:
                splines = [
                    ((0.1, 0.33), (0.33, -0.1), (0.67, -0.1), (0.9, 0.33)),
                    ((0.9, 0.33), (0.9, 0.66), (0.1, 0.95)),
                    ((0.1, 0.95), (1, 1)),
                ]
            elif digit == 3:
                splines = [
                    ((0, 0.33), (0.33, -0.1), (0.67, -0.1), (1, 0.25), (1, 0.5), (0.33, 0.5)),
                    ((0.33, 0.5), (1, 0.5), (1, 0.75), (0.66, 1.1), (0.33, 1.1), (0, 0.67)),
                ]
            elif digit == 4:
                splines = [
                    ((0, 0), (0, 0.5), (0.8, 0.5)),
                    ((0.8, 0), (0.8, 0.5), (0.8, 1)),
                ]
            elif digit == 5:
                splines = [
                    ((0.8, 0), (0.2, 0), (0.2, 0.5)),
                    ((0.2, 0.5), (0.6, 0.5), (0.8, 0.75), (0.6, 1), (0.2, 1)),
                ]
            elif digit == 6:
                splines = [
                    ((1, 0), (0.67, -0.1), (0.33, -0.1), (0, 0.33), (0, 0.67)),
                    ((0, 0.67), (0.33, 1.1), (0.67, 1.1), (1, 0.67)),
                    ((1, 0.67), (0.67, 0.33), (0.33, 0.33), (0, 0.67))
                ]
            elif digit == 7:
                splines = [
                    ((0, 0), (0.67, 0), (1, 0.33)),
                    ((1, 0.33), (0.5, 0.5), (0.5, 1)),
                ]
            elif digit == 8:
                splines = [
                    ((0.5, 0.5), (0.2, 0.5), (-0.2, 0.67), (0.2, 1), (0.5, 1)),
                    ((0.5, 1), (0.8, 1), (1.2, 0.67), (0.8, 0.5), (0.5, 0.5)),
                    ((0.5, 0.5), (0.2, 0.5), (-0.2, 0.33), (0.2, 0), (0.5, 0)),
                    ((0.5, 0), (0.8, 0), (1.2, 0.33), (0.8, 0.5), (0.5, 0.5)),
                ]
            elif digit == 9:
                splines = [
                    ((0, 1), (0.33, 1.1), (0.67, 1.1), (1, 0.67), (1, 0.33)),
                    ((1, 0.33), (0.67, -0.1), (0.33, -0.1), (0, 0.33)),
                    ((0, 0.33), (0.33, 0.67), (0.67, 0.67), (1, 0.33))
                ]
            points = []
            corrections = {}
            for spline in splines:
                corr = corrections.get(spline[0])
                if corr is None:
                    x1 = spline[0][0] + random.uniform(-jitter, jitter)
                    y1 = spline[0][1] + random.uniform(-jitter, jitter)
                    corrections[spline[0]] = (x1, y1)
                else:
                    x1 = corr[0]
                    y1 = corr[1]
                xys = [(x1, y1)]
                for i in range(1, len(spline)):
                    corr = corrections.get(spline[i])
                    if corr is None:
                        x2 = spline[i][0] + random.uniform(-jitter, jitter)
                        y2 = spline[i][1] + random.uniform(-jitter, jitter)
                        corrections[spline[i]] = (x2, y2)
                    else:
                        x2 = corr[0]
                        y2 = corr[1]
                    xys.append((x2, y2))
                    x1 = x2
                    y1 = y2
                xys = [(x * char_w + off_x, y * char_h + off_y) for x, y in xys]
                bezier = make_bezier(xys)
                points.extend(bezier(ts))
            draw.line(points, fill=(119, 119, 119), width=1)
        del draw
        try:
            captcha = self.obj(Captcha, session.uuid)
        except ObjectNotFoundException:
            captcha = self.obj(Captcha, session.uuid, {})
        captcha.set("number", number)
        captcha.set("valid_till", "%020d" % (time.time() + 86400))
        captcha.store()
        data = cStringIO.StringIO()
        image = image.filter(ImageFilter.MinFilter(3))
        image.save(data, "JPEG")
        self.call("web.response", data.getvalue(), "image/jpeg")

    def ext_logout(self):
        session = self.call("session.get")
        user = session.get("user")
        if session is not None and user:
            session.set("semi_user", user)
            session.delkey("user")
            session.store()
            self.app().mc.delete("SessionCache-%s" % session.uuid)
            req = self.req()
            redirect = req.param("redirect")
            if redirect is not None and redirect != "":
                self.call("web.redirect", redirect)
        self.call("web.redirect", "/")

    def ext_ajax_login(self):
        req = self.req()
        name = req.param("email")
        password = req.param("password")
        msg = {}
        self.call("auth.messages", msg)
        if not name:
            self.call("web.response_json", {"error": msg["name_empty"]})
        user = self.call("session.find_user", name, allow_email=True)
        if user is None:
            self.call("web.response_json", {"error": msg["name_unknown"]})
        elif user.get("inactive"):
            self.call("web.response_json", {"error": msg["user_inactive"]})
        if not password:
            self.call("web.response_json", {"error": msg["password_empty"]})
        m = hashlib.md5()
        m.update(user.get("salt").encode("utf-8") + password.encode("utf-8"))
        if m.hexdigest() != user.get("pass_hash"):
            self.call("web.response_json", {"error": msg["password_incorrect"]})
        session = self.call("session.get", True)
        session.set("user", user.uuid)
        session.delkey("semi_user")
        session.store()
        self.app().mc.delete("SessionCache-%s" % session.uuid)
        self.call("web.response_json", {"ok": 1, "session": session.uuid})

    def messages(self, msg):
        msg["name_empty"] = self._("Enter your name or email")
        msg["name_unknown"] = self._("User not found")
        msg["user_inactive"] = self._("User is not active. Check your e-mail and enter activation code")
        msg["password_empty"] = self._("Enter your password")
        msg["password_incorrect"] = self._("Incorrect password")

    def ext_login(self):
        req = self.req()
        form = self.call("web.form", "common/form.html")
        name = req.param("name")
        password = req.param("password")
        redirect = req.param("redirect")
        msg = {}
        self.call("auth.messages", msg)
        if req.ok():
            if not name:
                form.error("name", msg["name_empty"])
            else:
                user = self.call("session.find_user", name)
                if user is None:
                    form.error("name", msg["name_unknown"])
                elif user.get("inactive"):
                    form.error("name", msg["user_inactive"])
            if not password:
                form.error("password", msg["password_empty"])
            if not form.errors:
                m = hashlib.md5()
                m.update(user.get("salt").encode("utf-8") + password.encode("utf-8"))
                if m.hexdigest() != user.get("pass_hash"):
                    form.error("password", msg["password_incorrect"])
            if not form.errors:
                session = self.call("session.get", True)
                session.set("user", user.uuid)
                session.delkey("semi_user")
                session.store()
                self.app().mc.delete("SessionCache-%s" % session.uuid)
                if redirect is not None and redirect != "":
                    self.call("web.redirect", redirect)
                redirects = {}
                self.call("auth.redirects", redirects)
                if redirects.has_key("login"):
                    self.call("web.redirect", redirects["login"])
                self.call("web.redirect", "/")
        if redirect is not None:
            form.hidden("redirect", redirect)
        form.input(self._("User name"), "name", name)
        form.password(self._("Password"), "password", password)
        form.submit(None, None, self._("Log in"))
        form.add_message_bottom(self._("If this is your first visit, %s.") % ('<a href="/auth/register?redirect=%s">%s</a>' % (urlencode(redirect), self._("register please"))))
        form.add_message_bottom('<a href="/auth/remind?redirect=%s">%s</a>' % (urlencode(redirect), self._("Forgotten your password?")))
        vars = {
            "title": self._("User login"),
            "ret": {
                "href": "/",
                "title": self._("Cancel"),
            },
        }
        self.call("web.response_global", form.html(vars), vars)

    def ext_change(self):
        self.call("session.require_login")
        ret = "/"
        redirects = {}
        self.call("auth.redirects", redirects)
        if redirects.has_key("change"):
            ret = redirects["change"]
        req = self.req()
        form = self.call("web.form", "common/form.html")
        if req.ok():
            prefix = req.param("prefix")
        else:
            prefix = uuid4().hex
        password = req.param(prefix + "_p")
        password1 = req.param(prefix + "_p1")
        password2 = req.param(prefix + "_p2")
        if req.ok():
            user = self.obj(User, req.user())
            if not password:
                form.error(prefix + "_p", self._("Enter your old password"))
            if not form.errors:
                m = hashlib.md5()
                m.update(user.get("salt").encode("utf-8") + password.encode("utf-8"))
                if m.hexdigest() != user.get("pass_hash"):
                    form.error(prefix + "_p", self._("Incorrect old password"))
            if not password1:
                form.error(prefix + "_p1", self._("Enter your new password"))
            elif len(password1) < 6:
                form.error(prefix + "_p1", self._("Minimal password length - 6 characters"))
            elif not password2:
                form.error(prefix + "_p2", self._("Retype your new password"))
            elif password1 != password2:
                form.error(prefix + "_p2", self._("Password don't match. Try again, please"))
                password1 = ""
                password2 = ""
            if not form.errors:
                salt = ""
                letters = "abcdefghijklmnopqrstuvwxyz"
                for i in range(0, 10):
                    salt += random.choice(letters)
                user.set("salt", salt)
                user.set("pass_reminder", re.sub(r'^(..).*$', r'\1...', password1))
                m = hashlib.md5()
                m.update(salt + password1.encode("utf-8"))
                user.set("pass_hash", m.hexdigest())
                user.store()
                my_session = req.session()
                sessions = self.objlist(SessionList, query_index="user", query_equal=user.uuid)
                sessions.load()
                for sess in sessions:
                    if sess.uuid != my_session.uuid:
                        sess.delkey("user")
                        sess.delkey("semi_user")
                sessions.store()
                for sess in sessions:
                    if sess.uuid != my_session.uuid:
                        self.app().mc.delete("SessionCache-%s" % sess.uuid)
                self.call("auth.password-changed", user, password1)
                self.call("web.redirect", ret)
        form.hidden("prefix", prefix)
        form.password(self._("Old password"), prefix + "_p", password)
        form.password(self._("New password"), prefix + "_p1", password1)
        form.password(self._("Confirm new password"), prefix + "_p2", password2)
        form.submit(None, None, self._("Change"))
        vars = {
            "title": self._("Password change"),
        }
        self.call("web.response_global", form.html(vars), vars)

    def ext_email(self):
        self.call("session.require_login")
        req = self.req()
        user = self.obj(User, req.user())
        if req.args == "confirm":
            form = self.call("web.form", "common/form.html")
            code = req.param("code")
            redirect = req.param("redirect")
            if req.ok():
                if not code:
                    form.error("code", self._("Enter your code"))
                else:
                    if user.get("email_change"):
                        if user.get("email_confirmation_code") != code:
                            form.error("code", self._("Invalid code"))
                        else:
                            existing_email = self.objlist(UserList, query_index="email", query_equal=user.get("email_change"))
                            existing_email.load(silent=True)
                            if len(existing_email):
                                form.error("code", self._("There is another user with this email"))
                            else:
                                user.set("email", user.get("email_change"))
                                user.delkey("email_change")
                                user.delkey("email_confirmation_code")
                                user.store()
                if not form.errors:
                    redirects = {}
                    self.call("auth.redirects", redirects)
                    if redirects.has_key("change"):
                        self.call("web.redirect", redirects["change"])
                    self.call("web.redirect", "/")
            form.input(self._("Confirmation code from your post box"), "code", code)
            form.submit(None, None, self._("btn///Confirm"))
            vars = {
                "title": self._("E-mail confirmation"),
            }
            self.call("web.response_global", form.html(), vars)
        form = self.call("web.form", "common/form.html")
        if req.ok():
            prefix = req.param("prefix")
        else:
            prefix = uuid4().hex
        password = req.param(prefix + "_p")
        email = req.param("email")
        if req.ok():
            if not password:
                form.error(prefix + "_p", self._("Enter your old password"))
            if not form.errors:
                m = hashlib.md5()
                m.update(user.get("salt").encode("utf-8") + password.encode("utf-8"))
                if m.hexdigest() != user.get("pass_hash"):
                    form.error(prefix + "_p", self._("Incorrect old password"))
            if not email:
                form.error("email", self._("Enter new e-mail address"))
            elif not re.match(r'^[a-zA-Z0-9_\-+\.]+@[a-zA-Z0-9\-_\.]+\.[a-zA-Z0-9]+$', email):
                form.error("email", self._("Enter correct e-mail"))
            else:
                existing_email = self.objlist(UserList, query_index="email", query_equal=email.lower())
                existing_email.load(silent=True)
                if len(existing_email):
                    form.error("email", self._("There is another user with this email"))
            if not form.errors:
                user.set("email_change", email.lower())
                code = uuid4().hex
                user.set("email_confirmation_code", code)
                user.store()
                params = {
                    "subject": self._("E-mail confirmation"),
                    "content": self._("Someone possibly you requested e-mail change on the {host}. If you really want to do this enter the following confirmation code on the site:\n\n{code}\n\nor simply follow the link:\n\nhttp://{host}/auth/email/confirm?code={code}"),
                }
                self.call("auth.email_change_email", params)
                self.call("email.send", email, user.get("name"), params["subject"], params["content"].format(code=code, host=req.host()))
                self.call("web.redirect", "/auth/email/confirm")
        form.hidden("prefix", prefix)
        form.input(self._("New e-mail address"), "email", email)
        form.password(self._("Your current password"), prefix + "_p", password)
        form.submit(None, None, self._("Change"))
        ret = "/"
        redirects = {}
        self.call("auth.redirects", redirects)
        if redirects.has_key("change"):
            ret = redirects["change"]
        vars = {
            "title": self._("E-mail change"),
        }
        self.call("web.response_global", form.html(vars), vars)

    def permissions_list(self, perms):
        perms.append({"id": "permissions", "name": self._("User permissions editor")})
        perms.append({"id": "users", "name": self._("User profiles")})

    def auth_permissions(self, user_id):
        perms = {}
        if user_id:
            if user_id == self.app().inst.config.get("admin_user"):
                perms["admin"] = True
            try:
                p = self.obj(UserPermissions, user_id)
                for key in p.get("perms").keys():
                    perms[key] = True
            except ObjectNotFoundException:
                pass
        return perms

    def menu_root_index(self, menu):
        menu.append({"id": "users.index", "text": self._("Users"), "order": 500})

    def menu_users_index(self, menu):
        req = self.req()
        if req.has_access("permissions") or req.has_access("admin"):
            menu.append({"id": "auth/permissions", "text": self._("Permissions"), "leaf": True})
        if req.has_access("users"):
            menu.append({"id": "auth/user-dashboard/%s" % req.user(), "text": self._("My dashboard"), "leaf": True})
            menu.append({"id": "auth/user-find", "text": self._("Find user"), "leaf": True})
            menu.append({"id": "auth/user-lastreg", "text": self._("Last registered users"), "leaf": True})

    def admin_permissions(self):
        req = self.req()
        if not req.has_access("permissions") and not req.has_access("admin"):
            self.call("web.forbidden")
        permissions_list = []
        self.call("permissions.list", permissions_list)
        users = []
        user_permissions = self.objlist(UserPermissionsList, query_index="any", query_equal="1")
        if len(user_permissions):
            user_permissions.load()
            perms = dict([(obj.uuid, obj.get("perms")) for obj in user_permissions])
            usr = self.objlist(UserList, perms.keys())
            usr.load()
            for u in usr:
                grant_list = []
                p = perms[u.uuid]
                for perm in permissions_list:
                    if p.get(perm["id"]):
                        grant_list.append(perm["name"])
                users.append({"id": u.uuid, "name": cgi.escape(u.get("name")), "permissions": "<br />".join(grant_list)})
        vars = {
            "editpermissions": self._("Edit permissions of a user"),
            "user_name": self._("User name"),
            "permissions": self._("Permissions"),
            "edit": self._("edit"),
            "editing": self._("Editing"),
            "users": users,
        }
        self.call("admin.response_template", "admin/auth/permissions.html", vars)

    def headmenu_permissions(self, args):
        return self._("User permissions")

    def admin_editpermissions(self):
        req = self.req()
        if not req.has_access("permissions") and not req.has_access("admin"):
            self.call("web.forbidden")
        req = self.req()
        name = req.param("name")
        if req.ok():
            errors = {}
            if not name:
                errors["name"] = self._("Enter user name")
            else:
                user = self.call("session.find_user", name)
                if not user:
                    errors["name"] = self._("User not found")
                else:
                    self.call("admin.redirect", "auth/edituserpermissions/%s" % user.uuid)
            self.call("web.response_json", {"success": False, "errors": errors})
        fields = [
            {"name": "name", "label": self._("User name"), "value": name},
        ]
        buttons = [{"text": self._("Search")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def headmenu_editpermissions(self, args):
        return [self._("Edit permissions of a user"), "auth/permissions"]

    def admin_edituserpermissions(self):
        req = self.req()
        if not req.has_access("permissions") and not req.has_access("admin"):
            self.call("web.forbidden")
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        perms = []
        self.call("permissions.list", perms)
        try:
            user_permissions = self.obj(UserPermissions, req.args)
        except ObjectNotFoundException:
            user_permissions = self.obj(UserPermissions, req.args, {})
        if req.ok():
            perm_values = {}
            for perm in perms:
                if req.param("perm%s" % perm["id"]):
                    perm_values[perm["id"]] = True
            if perm_values:
                user_permissions.set("perms", perm_values)
                user_permissions.sync()
                user_permissions.store()
            else:
                user_permissions.remove()
            if req.args == req.user():
                del req._permissions
                self.call("admin.update_menu")
            self.call("admin.redirect", "auth/permissions")
        else:
            perm_values = user_permissions.get("perms")
            if not perm_values:
                perm_values = {}
        fields = []
        for perm in perms:
            fields.append({"name": "perm%s" % perm["id"], "label": perm["name"], "type": "checkbox", "checked": perm_values.get(perm["id"])})
        self.call("admin.form", fields=fields)

    def headmenu_edituserpermissions(self, args):
        user = self.obj(User, args)
        return [cgi.escape(user.get("name")), "auth/editpermissions"]

    def list_roles(self, roles):
        permissions_list = []
        roles.append(("all", self._("Everybody")))
        roles.append(("logged", self._("Logged in")))
        roles.append(("notlogged", self._("Not logged in")))
        self.call("permissions.list", permissions_list)
        has_priv = self._("Privilege: %s")
        for perm in permissions_list:
            roles.append(("perm:%s" % perm["id"], has_priv % perm["name"]))

    def users_roles(self, users, roles):
        list = self.objlist(UserPermissionsList, users)
        list.load(silent=True)
        perms = ["all", "logged"]
        for user in users:
            try:
                roles[user].extend(perms)
            except KeyError:
                roles[user] = ["all", "logged"]
        for user in list:
            perms = user.get("perms")
            if perms is not None:
                perms = ["perm:%s" % perm for perm in perms.keys()]
                try:
                    roles[user.uuid].extend(perms)
                except KeyError:
                    roles[user.uuid] = perms

    def headmenu_user_dashboard(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("User %s") % cgi.escape(user.get("name"))]

    def ext_user_find(self):
        self.call("session.require_permission", "users")
        req = self.req()
        name = req.param("name")
        if req.ok():
            errors = {}
            if not name:
                errors["name"] = self._("Enter user name")
            else:
                user = self.call("session.find_user", name)
                if not user:
                    errors["name"] = self._("User not found")
                else:
                    self.call("admin.redirect", "auth/user-dashboard/%s" % user.uuid)
            self.call("web.response_json", {"success": False, "errors": errors})
        fields = [
            {"name": "name", "label": self._("User name"), "value": name},
        ]
        buttons = [{"text": self._("Search")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def ext_user_dashboard(self):
        self.call("session.require_permission", "users")
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        vars = {
            "user": {
                "uuid": user.uuid,
            },
            "Update": self._("Update"),
        }
        tables = []
        self.call("auth.user-tables", user, tables)
        if len(tables):
            vars["tables"] = tables
        options = []
        self.call("auth.user-options", user, options)
        if len(options):
            vars["options"] = options
        self.call("admin.response_template", "admin/auth/user-dashboard.html", vars)

    def ext_user_lastreg(self):
        self.call("session.require_permission", "users")
        tables = []
        users = self.objlist(UserList, query_index="created", query_reversed=True, query_limit=30)
        users.load()
        tables.append({
            "header": [self._("ID"), self._("Name"), self._("Active")],
            "rows": [('<hook:admin.link href="auth/user-dashboard/{0}" title="{0}" />'.format(u.uuid), htmlescape(u.get("name")), self._("no") if u.get("inactive") else self._("yes")) for u in users]
        })
        vars = {
            "tables": tables
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

re_permissions_args = re.compile(r'^([a-f0-9]+)(?:(.+)|)$', re.DOTALL)

class PermissionsEditor(Module):
    """ PermissionsEditor is a interface to grant and revoke permissions, view actual permissions """
    def __init__(self, app, objclass, permissions, default_rules=None):
        Module.__init__(self, app, "mg.core.PermissionsEditor")
        self.objclass = objclass
        self.permissions = permissions
        self.default_rules = default_rules

    def request(self, args=None):
        if args is None:
            args = self.req().args
        m = re_permissions_args.match(args)
        if not m:
            self.call("web.not_found")
        uuid, args = m.group(1, 2)
        self.uuid = uuid
        try:
            self.perms = self.obj(self.objclass, uuid)
        except ObjectNotFoundException:
            rules = []
            if self.default_rules:
                self.call(self.default_rules, rules)
            self.perms = self.obj(self.objclass, uuid, {"rules": rules})
        if args == "" or args is None:
            self.index()
        m = re.match(r'^/del/(\d+)$', args)
        if m:
            self.delete(intz(m.groups(1)[0]))
        self.call("web.not_found")

    def index(self):
        roles = []
        self.call("security.list-roles", roles)
        fields = []
        req = self.req()
        if req.param("ok"):
            roles_dict = dict(roles)
            permissions_dict = dict(self.permissions)
            errors = {}
            rules_cnt = intz(req.param("rules"))
            if rules_cnt > 1000:
                rules_cnt = 1000
            new_rules = []
            ord = intz(req.param("ord"))
            role = req.param("v_role")
            perm = req.param("v_perm")
            if role or perm:
                if not role or not roles_dict.get(role):
                    errors["role"] = self._("Select valid role")
                if not perm or not permissions_dict.get(perm):
                    errors["perm"] = self._("Select valid permission")
                new_rules.append((ord, role, perm))
            for n in range(0, rules_cnt):
                ord = intz(req.param("ord%d" % n))
                role = req.param("v_role%d" % n)
                perm = req.param("v_perm%d" % n)
                if not role or not roles_dict.get(role):
                    errors["role%d" % n] = self._("Select valid role")
                if not perm or not permissions_dict.get(perm):
                    errors["perm%d" % n] = self._("Select valid permission")
                new_rules.append((ord, role, perm))
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            new_rules.sort(key=itemgetter(0))
            new_rules = [(role, perm) for ord, role, perm in new_rules]
            self.perms.set("rules", new_rules)
            self.perms.store()
            self.call("admin.redirect", "forum/access/%s" % self.uuid)
        rules = self.perms.get("rules")
        for n in range(0, len(rules)):
            rule = rules[n]
            fields.append({"name": "ord%d" % n, "value": n + 1, "width": 100})
            fields.append({"name": "role%d" % n, "type": "combo", "values": roles, "value": rule[0], "inline": True})
            fields.append({"name": "perm%d" % n, "type": "combo", "values": self.permissions, "value": rule[1], "inline": True})
            fields.append({"type": "button", "width": 100, "text": self._("Delete"), "action": "forum/access/%s/del/%d" % (self.uuid, n), "inline": True})
        fields.append({"name": "ord", "value": len(rules) + 1, "label": self._("Add") if rules else None, "width": 100})
        fields.append({"name": "role", "type": "combo", "values": roles, "label": "&nbsp;" if rules else None, "allow_blank": True, "inline": True})
        fields.append({"name": "perm", "type": "combo", "values": self.permissions, "label": "&nbsp;" if rules else None, "allow_blank": True, "inline": True})
        fields.append({"type": "empty", "width": 100, "inline": True})
        fields[0]["label"] = self._("Order")
        fields[1]["label"] = self._("Role")
        fields[2]["label"] = self._("Permission")
        fields[3]["label"] = "&nbsp;"
        fields.append({"type": "hidden", "name": "rules", "value": len(rules)})
        self.call("admin.form", fields=fields)

    def delete(self, index):
        rules = self.perms.get("rules")
        try:
            del rules[index]
            self.perms.touch()
            self.perms.store()
        except IndexError:
            pass
        self.call("admin.redirect", "forum/access/%s" % self.uuid)
