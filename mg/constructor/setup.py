from mg import *
from mg.core.auth import UserPermissions, UserPermissionsList
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
from concurrence.dns import *
from mg.constructor.players import DBCharacterList, DBCharacter, DBPlayer, DBCharacterForm
import re
import cgi
import cStringIO
import random
import time
import hashlib

re_bad_symbols = re.compile(r'.*[\'"<>&\\]')

class ProjectSetupWizard(Wizard):
    def new(self, **kwargs):
        super(ProjectSetupWizard, self).new(**kwargs)
        self.config.set("state", "intro")
        
    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Setup wizard"), "leaf": True, "admin_index": True, "order": 10, "icon": "/st-mg/menu/wizard.png"})

    def request(self, cmd):
        req = self.req()
        self.call("admin.advice", {"title": self._("How to launch the game"), "content": self._('Step-by-step tutorial about creating the game to launch you can read in the <a href="//www.%s/doc/newgame" target="_blank">reference manual</a>.') % self.main_host})
        state = self.config.get("state")
        project = self.app().project
        if state == "intro":
            if cmd == "next":
                self.config.set("state", "offer")
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            fields = [
                {"type": "html", "html": self.call("web.parse_template", "constructor/setup/intro-%s.html" % self.call("l10n.lang"), {})},
                {"type": "button", "text": self._("Next"), "action": "wizard/call/%s/next" % self.uuid},
            ]
            self.call("admin.form", fields=fields, buttons=[])
        elif state == "offer":
            if cmd == "agree":
                self.config.set("state", "name")
                self.config.set("reg_ip", req.remote_addr())
                self.config.set("reg_agent", req.environ.get("HTTP_USER_AGENT"))
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            self.call("admin.advice", {"title": self._("Law importance"), "content": self._("There are some very important points in the contract. At least read information in the red panel.")})
            author = self.main_app().obj(User, project.get("owner"))
            vars = {
                "author": htmlescape(author.get("name")),
                "main_protocol": self.main_app().protocol,
                "main_host": self.main_host,
            }
            fields = [
                {"type": "html", "html": self.call("web.parse_template", "constructor/setup/offer-%s.html" % self.call("l10n.lang"), vars)},
                {"type": "button", "text": self._("I don't agree"), "action": "project/destroy/admin"},
                {"type": "button", "text": self._("I agree to the terms and conditions"), "action": "wizard/call/%s/agree" % self.uuid, "inline": True},
            ]
            self.call("admin.form", fields=fields, buttons=[])
        elif state == "name":
            if req.ok():
                errors = {}
                title_full = req.param("title_full")
                title_short = req.param("title_short")
                title_code = req.param("title_code")

                if not title_full:
                    errors["title_full"] = self._("Enter full title")
                elif len(title_full) > 50:
                    errors["title_full"] = self._("Maximal length - 50 characters")
                elif re_bad_symbols.match(title_full):
                    errors["title_full"] = self._("Bad symbols in the title")

                if not title_short:
                    errors["title_short"] = self._("Enter short title")
                elif len(title_short) > 17:
                    errors["title_short"] = self._("Maximal length - 17 characters")
                elif re_bad_symbols.match(title_short):
                    errors["title_short"] = self._("Bad symbols in the title")

                if not title_code:
                    errors["title_code"] = self._("Enter code")
                elif len(title_code) > 5:
                    errors["title_code"] = self._("Maximal length - 5 characters")
                elif re.match(r'[^a-z0-9A-Z]', title_code):
                    errors["title_code"] = self._("You can use digits and latin letters only")

                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                self.config.set("title_full", title_full)
                self.config.set("title_short", title_short)
                self.config.set("title_code", title_code)
                self.config.set("state", "logo")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            fields = [
                {
                    "name": "title_full",
                    "label": self._("Full title of your game (ex: Eternal Forces: call of daemons)"),
                    "value": self.config.get("title_full"),
                },
                {
                    "name": "title_short",
                    "label": self._("Short title of your game (ex: Eternal Forces)"),
                    "value": self.config.get("title_short"),
                },
                {
                    "name": "title_code",
                    "label": self._("Short abbreviated code of the game (ex: EF)"),
                    "value": self.config.get("title_code"),
                    "inline": True,
                },
            ]
            self.call("admin.advice", {"title": self._("Choosing titles"), "content": self._("Titles should be short and descriptive. Try to avoid long words, especially in short title. Otherwize you can introduce lines wrapping problems")})
            self.call("admin.form", fields=fields, title=self._("Title of the game"))
        elif state == "logo":
            wizs = self.call("wizards.find", "logo")
            if cmd == "upload":
                self.call("web.upload_handler")
                image = req.param_raw("image")
                uri = self.call("admin-logo.uploader", image, self.config.get("title_short"))
                self.config.set("logo", uri)
                self.config.store()
                self.call("web.response_json_html", {"success": True, "logo_preview": uri})
            elif cmd == "prev":
                self.config.set("state", "name")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            elif cmd == "constructor":
                if len(wizs):
                    self.call("admin.redirect", "wizard/call/%s" % wizs[0].uuid)
                wiz = self.call("wizards.new", "mg.constructor.logo.LogoWizard", target=["wizard", self.uuid, "constructed", ""], redirect_fail="wizard/call/%s" % self.uuid, title=self.config.get("title_short"))
                self.call("admin.redirect", "wizard/call/%s" % wiz.uuid)
            elif cmd == "next":
                if self.config.get("logo"):
                    for wiz in wizs:
                        wiz.finish()
                    self.config.set("state", "admin")
                    self.config.store()
                    self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            vars = {
                "GameLogo": self._("Game logo"),
                "HereYouCan": self._("Here you have to create unique logo for your project."),
                "FromFile": self._("Upload pre-made logo file"),
                "FromConstructor": self._("Alternative 2. Launch logo constructor"),
                "wizard": self.uuid,
                "logo": self.config.get("logo"),
                "ImageFormat": self._("Upload image: 100x100, without animation"),
                "UploadNote": self._("Note your image will be postprocessed - corners will be rounded, 1px border added, black padding added, title written on the black padding."),
                "LaunchConstructor": self._("Launch the constructor"),
            }
            self.call("admin.response_template", "constructor/setup/logo.html", vars)
        elif state == "indexpage":
            # Leaved here to keep an example how to create admin.form inside a wizard
            if cmd == "submit":
                errors = {"variant": "UHAHA"}
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
            elif cmd == "prev":
                self.config.set("state", "logo")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            form_data = {
                "url": "/admin-wizard/call/%s/submit" % self.uuid,
                "title": "Setup",
                "fields": [{"name": "test", "label": "Test", "value": "123"}],
                "buttons": [{"text": self._("Save")}],
            }
            vars = {
                "form_data": jsencode(json.dumps(form_data)),
                "wizard": self.uuid,
            }
            self.call("admin.response_template", "constructor/setup/indexpage.html", vars)
        elif state == "admin":
            if cmd == "submit":
                # auth settings
                params = {}
                self.call("auth.form_params", params)
                # loading params
                name = req.param("name")
                password1 = req.param("password1")
                password2 = req.param("password2")
                email = req.param("email").lower()
                sex = intz(req.param("v_sex"))
                # validating params
                errors = {}
                if not name:
                    errors["name"] = self._("This field is mandatory")
                elif not re.match(params["name_re"], name, re.UNICODE):
                    errors["name"] = params["name_invalid_re"]
                if not email:
                    errors["email"] = self._("Enter your e-mail address")
                elif not re.match(r'^[a-zA-Z0-9_\-+\.]+@[a-zA-Z0-9\-_\.]+\.[a-zA-Z0-9]+$', email):
                    errors["email"] = self._("Enter correct e-mail")
                if not password1:
                    errors["password1"] = self._("Enter your password")
                elif len(password1) < 6:
                    errors["password1"] = self._("Minimal password length - 6 characters")
                if not errors.get("password1"):
                    if not password2:
                        errors["password2"] = self._("Repeat your password")
                    elif password1 != password2:
                        errors["password2"] = self._("Passwords do not match")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                self.config.set("admin_name", name)
                self.config.set("admin_password", password1)
                self.config.set("admin_email", email)
                self.config.set("admin_sex", sex)
                self.activate_project()
            elif cmd == "prev":
                self.config.set("state", "logo")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            owner = self.main_app().obj(User, self.app().project.get("owner"))
            name = self.config.get("admin_name", owner.get("name"))
            password1 = self.config.get("admin_password")
            password2 = self.config.get("admin_password")
            email = self.config.get("admin_email", owner.get("email"))
            sex = self.config.get("admin_sex", owner.get("sex"))
            form_data = {
                "url": "/admin-wizard/call/%s/submit" % self.uuid,
                "title": self._("Character for the game administrator"),
                "fields": [
                    {"name": "name", "label": self._("Name of the administrative character in your game"), "value": name},
                    {"name": "sex", "type": "combo", "label": self._("Sex"), "value": sex, "values": [(0, self._("Male")), (1, self._("Female"))]},
                    {"name": "password1", "type": "password", "label": self._("Administrator's password"), "value": password1},
                    {"name": "password2", "type": "password", "label": self._("Repeat password"), "value": password2, "inline": True},
                    {"name": "email", "label": self._("Administrator's e-mail"), "value": email},
                ],
                "buttons": [{"text": self._("Save")}],
            }
            vars = {
                "form_data": jsencode(json.dumps(form_data)),
                "wizard": self.uuid,
            }
            self.call("admin.response_template", "constructor/setup/form.html", vars)
        else:
            raise RuntimeError("Invalid ProjectSetupWizard state: %s" % state)

    def constructed(self, logo, arg):
        self.config.set("state", "logo")
        uri = self.call("admin-logo.store", logo, self.config.get("title_short"))
        self.config.set("logo", uri)
        self.config.store()

    def activate_project(self):
        self.call("cluster.static_preserve", self.config.get("logo"))
        # creating project
        project = self.app().project
        for key in ("logo", "title_full", "title_short", "title_code"):
            project.set(key, self.config.get(key))
        project.delkey("inactive")
        project.store()
        self.finish()
        config = self.app().config
        config.set("project.reg_ip", self.config.get("reg_ip"))
        config.set("project.reg_agent", self.config.get("reg_agent"))
        self.app().store_config_hooks()
        # administrator requisites
        name = self.config.get("admin_name")
        password = self.config.get("admin_password")
        email = self.config.get("admin_email")
        sex = self.config.get("admin_sex")
        # creating admin player
        now_ts = "%020d" % time.time()
        now = self.now()
        player = self.obj(DBPlayer)
        player.set("created", now)
        player_user = self.obj(User, player.uuid, {})
        player_user.set("created", now_ts)
        player_user.set("email", email)
        salt = ""
        letters = "abcdefghijklmnopqrstuvwxyz"
        for i in range(0, 10):
            salt += random.choice(letters)
        player_user.set("salt", salt)
        player_user.set("pass_reminder", re.sub(r'^(..).*$', r'\1...', password))
        m = hashlib.md5()
        m.update(salt + password.encode("utf-8"))
        player_user.set("pass_hash", m.hexdigest())
        # creating admin character
        character = self.obj(DBCharacter)
        character.set("created", now)
        character.set("player", player.uuid)
        character.set("admin", 1)
        character_user = self.obj(User, character.uuid, {})
        character_user.set("last_login", now_ts)
        character_user.set("name", name)
        character_user.set("name_lower", name.lower())
        character_user.set("sex", sex)
        character_user.set("created", now_ts)
        character_form = self.obj(DBCharacterForm, character.uuid, {})
        # storing
        player.store()
        player_user.store()
        character.store()
        character_user.store()
        character_form.store()
        # giving permissions
        perms = self.obj(UserPermissions, character_user.uuid, {"perms": {"project.admin": True}})
        perms.sync()
        perms.store()
        # entering new project
        self.call("admin.redirect_top", "//www.%s/constructor/game/%s" % (self.main_host, project.uuid))
