from mg import *
from PIL import Image, ImageDraw, ImageEnhance
import cStringIO

class LogoWizard(Wizard):
    def new(self, target=None, redirect_fail=None, **kwargs):
        """
        target:
            [wizard, "283746287348234", "constructed", "123"] - after completion call method "constructed" of wizard "283746287348234". And pass it args: ("123", uri)
        redirect_fail - where to redirect user on failure
        """
        super(LogoWizard, self).new(**kwargs)
        if target is None:
            raise RuntimeError("LogoWizard target not specified")
        if redirect_fail is None:
            raise RuntimeError("LogoWizard redirect_fail not specified")
        self.config.set("tag", "logo")
        self.config.set("target", target)
        self.config.set("redirect_fail", redirect_fail)

    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Logo constructor"), "leaf": True, "order": 20})

    def request(self, cmd):
        req = self.req()
        if cmd == "abort":
            self.abort()
            self.call("admin.update_menu")
            self.call("admin.redirect", self.config.get("redirect_fail"))
        elif cmd == "background/solid":
            color = req.param("color")
            rgb = parse_color(color)
            if not rgb:
                self.call("web.response_json", {"success": False, "errormsg": self._("Invalid color")})
            print "rgb=%s" % [rgb]
            self.config.set("background_mode", "solid")
            self.config.set("background_color", color)
            img = Image.new("RGBA", (100, 75), rgb)
            # storing image
            png = cStringIO.StringIO()
            img.save(png, "PNG")
            png = png.getvalue()
            uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
            self.config.set("background", uri)
            self.config.store()
            self.call("web.response_json", {"success": True, "background": uri})
        elif cmd == "background/upload":
            image = req.param_raw("image")
            if image is None or not len(image):
                self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Upload background image")}})
            try:
                image_obj = Image.open(cStringIO.StringIO(image))
                if image_obj.load() is None:
                    raise IOError;
            except IOError:
                self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Image format not recognized")}})
            try:
                image_obj.seek(1)
                self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Animated backgrounds are not supported")}})
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
            # putting image on the white background
            background = Image.new("RGBA", (100, 75), (255, 255, 255))
            background.paste(image_obj, None, image_obj)
            # storing image
            png = cStringIO.StringIO()
            background.save(png, "PNG")
            png = png.getvalue()
            uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
            self.config.set("background_mode", "upload")
            self.config.set("background", uri)
            self.config.store()
            self.call("web.response_json_html", {"success": True, "background": uri})
        paddings = []
        paddings.append({"type": "circle", "title": self._("Circle"), "size": 70})
        vars = {
            "LogoConstructor": self._("Logo constructor"),
            "HereYouCan": self._("Here you can construct your own simple 100x75 logo using several basic elements."),
            "Apply": self._("Apply"),
            "Abort": self._("Abort"),
            "Upload": self._("Upload"),
            "BackgroundImage": self._("Background image"),
            "wizard": self.uuid,
            "logo": self.config.get("logo"),
            "Background": self._("Background"),
            "Padding": self._("Padding"),
            "Icon": self._("Icon"),
            "Effects": self._("Effects"),
            "UploadFile": self._("Load from file"),
            "SolidColor": self._("Solid color"),
            "SetButton": self._("Set"),
            "background_mode": self.config.get("background_mode"),
            "background_color": self.config.get("background_color", "FFFFFF"),
            "background": self.config.get("background"),
            "paddings": paddings,
            "Size": self._("Size"),
        }
        self.call("admin.response_template", "constructor/logo-wizard.html", vars)
