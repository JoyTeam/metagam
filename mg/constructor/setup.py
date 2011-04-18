from mg import *
from mg.core.auth import UserPermissions, UserPermissionsList
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
from concurrence.dns import *
from mg.constructor.players import CharacterList, Character, Player, CharacterForm
import re
import cgi
import cStringIO
import random
import time
import hashlib

re_domain = re.compile(r'^[a-z0-9][a-z0-9\-]*(\.[a-z0-9][a-z0-9\-]*)+$')
re_bad_symbols = re.compile(r'.*[\'"<>&\\]')

class ProjectSetupWizard(Wizard):
    def new(self, **kwargs):
        super(ProjectSetupWizard, self).new(**kwargs)
        self.config.set("state", "intro")
        
    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Setup wizard"), "leaf": True, "admin_index": True, "ord": 10})

    def request(self, cmd):
        req = self.req()
        state = self.config.get("state")
        project = self.app().project
        if state == "intro":
            if cmd == "next":
                self.config.set("state", "offer")
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            vars = {
                "wizard": self.uuid,
                "next_text": jsencode(self._("Next")),
            }
            self.call("admin.advice", {"title": self._("Demo advice"), "content": self._("Look to the right to read some recommendations")})
            self.call("admin.response_template", "constructor/setup/intro-%s.html" % self.call("l10n.lang"), vars)
        elif state == "offer":
            if cmd == "agree":
                self.config.set("state", "name")
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            author = self.main_app().obj(User, project.get("owner"))
            vars = {
                "author": cgi.escape(author.get("name")),
                "wizard": self.uuid,
                "main_host": self.app().inst.config["main_host"],
            }
            self.call("admin.advice", {"title": self._("Law importance"), "content": self._("There are some very important points in the contract. At least read information in the red panel.")})
            self.call("admin.response_template", "constructor/setup/offer-%s.html" % self.call("l10n.lang"), vars)
        elif state == "name":
            if cmd == "name-submit":
                errors = {}
                title_full = req.param("title_full")
                title_short = req.param("title_short")
                title_code = req.param("title_code")

                if not title_full or title_full == "":
                    errors["title_full"] = self._("Enter full title")
                elif len(title_full) > 50:
                    errors["title_full"] = self._("Maximal length - 50 characters")
                elif re_bad_symbols.match(title_full):
                    errors["title_full"] = self._("Bad symbols in the title")

                if not title_short or title_short == "":
                    errors["title_short"] = self._("Enter short title")
                elif len(title_short) > 17:
                    errors["title_short"] = self._("Maximal length - 17 characters")
                elif re_bad_symbols.match(title_short):
                    errors["title_short"] = self._("Bad symbols in the title")

                if not title_code or title_code == "":
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
            buttons = [
                {"text": self._("Next"), "url": "admin-wizard/call/%s/name-submit" % self.uuid}
            ]
            self.call("admin.advice", {"title": self._("Choosing titles"), "content": self._("Titles should be short and descriptive. Try to avoid long words, especially in short title. Otherwize you can introduce lines wrapping problems")})
            self.call("admin.form", fields=fields, buttons=buttons, title=self._("Title of the game"))
        elif state == "logo":
            wizs = self.call("wizards.find", "logo")
            if cmd == "upload":
                image = req.param_raw("image")
                if image is None or not len(image):
                    self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Upload logo image")}})
                try:
                    image_obj = Image.open(cStringIO.StringIO(image))
                    if image_obj.load() is None:
                        raise IOError;
                except IOError:
                    self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Image format not recognized")}})
                try:
                    image_obj.seek(1)
                    self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Animated logos are not supported")}})
                except EOFError:
                    pass
                image_obj = image_obj.convert("RGBA")
                width, height = image_obj.size
                if width == 100 and height == 100:
                    image_obj = image_obj.crop((0, 0, 100, 75))
                elif width * 75 >= height * 100:
                    width = width * 75 / height
                    height = 75
                    image_obj = image_obj.resize((width, height), Image.ANTIALIAS)
                    if width != 100:
                        image_obj = image_obj.crop(((width - 100) / 2, 0, (width - 100) / 2 + 100, 75))
                else:
                    height = height * 100 / width
                    width = 100
                    image_obj = image_obj.resize((width, height), Image.ANTIALIAS)
                    if height != 75:
                        image_obj = image_obj.crop((0, (height - 75) / 2, 100, (height - 75) / 2 + 75))
                uri = self.store_logo(image_obj)
                self.call("web.response_json_html", {"success": True, "logo_preview": uri})
            elif cmd == "prev":
                self.config.set("state", "name")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            elif cmd == "constructor":
                if len(wizs):
                    self.call("admin.redirect", "wizard/call/%s" % wizs[0].uuid)
                wiz = self.call("wizards.new", "mg.constructor.logo.LogoWizard", target=["wizard", self.uuid, "constructed", ""], redirect_fail="wizard/call/%s" % self.uuid, title_code=self.config.get("title_code"))
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
        elif state == "domain":
            if cmd == "prev":
                self.config.set("state", "logo")
                self.config.store()
                self.call("web.response_json", {"success": True, "redirect": "wizard/call/%s" % self.uuid})
            elif cmd == "check":
                domain = req.param("domain").strip().lower()
                self.config.set("domain", domain)
                self.config.store()
                errors = {}
                if domain == "":
                    errors["domain"] = self._("Specify your domain name")
                elif not re_domain.match(domain):
                    errors["domain"] = self._("Invalid domain name")
                elif len(domain) > 63:
                    errors["domain"] = self._("Domain name is too long")
                if not len(errors):
                    self.call("domains.validate_new", domain, errors)
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                wizs = self.call("wizards.find", "domain-reg")
                for wiz in wizs:
                    wiz.abort()
                # saving wizard data
                self.call("domains.assign", domain)
            elif cmd == "register":
                wizs = self.call("wizards.find", "domain-reg")
                if len(wizs):
                    self.call("admin.redirect", "wizard/call/%s" % wizs[0].uuid)
                wiz = self.call("wizards.new", "mg.constructor.domains.DomainRegWizard", target=["wizard", self.uuid, "domain_registered", ""], redirect_fail="wizard/call/%s" % self.uuid)
                self.call("admin.redirect", "wizard/call/%s" % wiz.uuid)
            ns1 = self.main_app().config.get("dns.ns1")
            ns2 = self.main_app().config.get("dns.ns2")
            vars = {
                "GameDomain": self._("Domain for your game"),
                "HereYouCan": self._("<p>We don't offer free domain names &mdash; you have to register it manually.</p>"),
                "AlreadyRegistered": self._("Step 1. Alternative 1. Register domain yourself"),
                "DomainSettings": "<ul><li>%s</li><li>%s</li><li>%s</li></ul>" % (self._("Register a new domain (or take any previously registered)"), self._("Specify the following DNS servers for your domain: <strong>{0}</strong> and <strong>{1}</strong>").format(ns1, ns2), self._("You may use any level domains")),
                "RegisterWizard": self._("Step 1. Alternative 2. Let us register a domain for you"),
                "wizard": self.uuid,
                "LaunchWizard": self._("Launch domain registration wizard"),
                "DomainName": self._("Domain name (without www)"),
                "CheckDomain": self._("Check domain and assign it to the game"),
                "CheckingDomain": self._("Checking domain..."),
                "DomainCheck": self._("Step 2. Check your configured domain and link it with your game"),
                "domain_name": jsencode(self.config.get("domain")),
            }
            self.call("admin.response_template", "constructor/setup/domain.html", vars)
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

    def domain_registered(self, domain, arg):
        self.config.set("domain", domain)
        self.config.store()

    def constructed(self, logo, arg):
        self.config.set("state", "logo")
        self.store_logo(logo)

    def activate_project(self):
        self.call("cluster.static_preserve", self.config.get("logo"))
        # creating project
        project = self.app().project
        for key in ("domain", "logo", "title_full", "title_short", "title_code"):
            project.set(key, self.config.get(key))
        project.delkey("inactive")
        project.store()
#        email = self.main_app().config.get("constructor.moderator-email")
#        if email:
#            content = self._("New project has been registered: {0}\nPlease perform required moderation actions: http://www.{1}/admin#constructor/project-dashboard/{2}").format(project.get("title_full"), self.app().inst.config["main_host"], project.uuid)
#            self.main_app().hooks.call("email.send", email, self._("Constructor moderator"), self._("Project moderation: %s" % project.get("title_short")), content)
        self.finish()
        self.app().store_config_hooks()
        # administrator requisites
        name = self.config.get("admin_name")
        password = self.config.get("admin_password")
        email = self.config.get("admin_email")
        sex = self.config.get("admin_sex")
        # creating admin player
        now_ts = "%020d" % time.time()
        now = self.now()
        player = self.obj(Player)
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
        character = self.obj(Character)
        character.set("created", now)
        character.set("player", player.uuid)
        character.set("admin", 1)
        character_user = self.obj(User, character.uuid, {})
        character_user.set("last_login", now_ts)
        character_user.set("name", name)
        character_user.set("name_lower", name.lower())
        character_user.set("sex", sex)
        character_form = self.obj(CharacterForm, character.uuid, {})
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
        self.call("admin.redirect_top", "http://www.%s/constructor/game/%s" % (self.app().inst.config["main_host"], project.uuid))

    def store_logo(self, image_obj):
        background = Image.new("RGBA", (100, 100), (255, 255, 255))
        background.paste(image_obj, (0, 0, 100, 75), image_obj)
        # drawing image border
        bord = Image.open(mg.__path__[0] + "/data/logo/logo-pad.png")
        background.paste(bord, None, bord)
        # rounding corners
        mask = Image.open(mg.__path__[0] + "/data/logo/logo-mask.png")
        mask = mask.convert("RGBA")
        mask.paste(background, None, mask)
        # writing text
        textpad = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
        title = self.config.get("title_short")
        font_size = 20
        watchdog = 0
        while font_size > 5:
            font = ImageFont.truetype(mg.__path__[0] + "/data/fonts/arialn.ttf", font_size, encoding="unic")
            w, h = font.getsize(title)
            if w <= 92 and h <= 20:
                break
            font_size -= 1
        draw = ImageDraw.Draw(textpad)
        draw.text((50 - w / 2, 88 - h / 2), title, font=font)
        enhancer = ImageEnhance.Sharpness(textpad)
        textpad_blur = enhancer.enhance(0.5)
        mask.paste(textpad_blur, None, textpad_blur)
        mask.paste(textpad, None, textpad)
        # generating png
        png = cStringIO.StringIO()
        mask.save(png, "PNG")
        png = png.getvalue()
        uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
        self.config.set("logo", uri)
        self.config.store()
        return uri
