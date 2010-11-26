from mg import *
from mg.core.auth import User, UserPermissions, Session, UserList, SessionList, UserPermissionsList
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
from concurrence.dns import *
import re
import cgi
import cStringIO
import random

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
            self.call("admin.response_template", "constructor/intro-%s.html" % self.call("l10n.lang"), vars)
        elif state == "offer":
            if cmd == "agree":
                self.config.set("state", "name")
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            author = self.app().inst.appfactory.get_by_tag("main").obj(User, project.get("owner"))
            vars = {
                "author": cgi.escape(author.get("name")),
                "wizard": self.uuid,
            }
            self.call("admin.advice", {"title": self._("Law importance"), "content": self._("There are some very important points in the contract. At least read information in the red panel.")})
            self.call("admin.response_template", "constructor/offer-%s.html" % self.call("l10n.lang"), vars)
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
            self.call("admin.form", fields=fields, buttons=buttons)
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
                self.config.set("state", "domain")
                self.config.store()
                self.call("admin.redirect", "wizard/call/%s" % self.uuid)
            vars = {
                "GameLogo": self._("Game logo"),
                "HereYouCan": self._("Here you have to create unique logo for your project. You can either upload logo from your computer or create it using Constructor."),
                "FromFile": self._("Alternative 1. Upload pre-made logo file"),
                "FromConstructor": self._("Alternative 2. Launch logo constructor"),
                "wizard": self.uuid,
                "logo": self.config.get("logo"),
                "ImageFormat": self._("Upload image: 100x100, without animation"),
                "UploadNote": self._("Note your image will be postprocessed - corners will be rounded, 1px border added, black padding added, title written on the black padding."),
                "LaunchConstructor": self._("Launch the constructor"),
            }
            self.call("admin.response_template", "constructor/logo.html", vars)
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
                # Saving logo
                self.call("cluster.static_preserve", self.config.get("logo"))
                # Creating project
                self.call("domains.assign", domain)
                project = self.app().project
                for key in ("domain", "logo", "title_full", "title_short", "title_code"):
                    project.set(key, self.config.get(key))
                project.set("published", self.now())
                project.delkey("inactive")
                project.store()
                self.finish()
                self.call("cluster.appconfig_changed")
                owner = self.main_app().obj(User, self.app().project.get("owner"))
                self.call("admin.response", '<div class="text"><p>%s</p><p>%s: <a href="http://www.%s/admin">http://www.%s/admin</a><br />%s: admin<br />%s: &lt;%s&gt; (%s)</p></div>' % (self._("You have successfully completed registration of your game. And now get ready to enter your new admin panel:"), self._("Admin panel address"), domain, domain, self._("Login"), self._("Password"), self._("your_password"), owner.get("pass_reminder")), {})
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
            self.call("admin.response_template", "constructor/domain.html", vars)
        else:
            raise RuntimeError("Invalid ProjectSetupWizard state: %s" % state)

    def domain_registered(self, domain, arg):
        self.config.set("domain", domain)
        self.config.store()

    def constructed(self, logo, arg):
        self.config.set("state", "logo")
        self.store_logo(logo)

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