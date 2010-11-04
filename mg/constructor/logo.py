import mg
from mg import *
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
import cStringIO
import urlparse
import cgi

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
        if kwargs.get("title_code"):
            fonts = ["agaaler.ttf", "albion1.ttf", "anirb.ttf", "ardvrk.ttf", "assuan8.ttf", "batik.ttf", "billb.ttf", "blazed.ttf", "bleeding.ttf", "bodon11.ttf", "broken74.ttf", "bumbazo.ttf", "drake.ttf", "impact.ttf", "thehard.ttf", "cosmdd.ttf", "creamandsugar.ttf", "bentt13.ttf"]
            for font_name in fonts:
                textpad = Image.new("RGBA", (100, 75), (255, 255, 255, 0))
                title = kwargs["title_code"]
                font_size = 65
                watchdog = 0
                while font_size > 5:
                    try:
                        font = ImageFont.truetype(mg.__path__[0] + "/data/fonts/%s" % font_name, font_size, encoding="unic")
                    except IOError:
                        raise RuntimeError("Couldn't open font file %s" % font_name)
                    w, h = font.getsize(title)
                    if w * w + h * h < 64 * 64:
                        break
                    font_size -= 1
                draw = ImageDraw.Draw(textpad)
                draw.text((50 - w / 2, 36 - h / 2), title, font=font, fill=(0, 0, 0, 255))
                del draw
                # storing image
                png = cStringIO.StringIO()
                textpad.save(png, "PNG")
                png = png.getvalue()
                uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
                shape_id = self.config.get_int("shapes") + 1
                self.config.set("shapes", shape_id)
                self.config.set("shape%d_uri" % shape_id, uri)
                title = self._("Project code: Font %s") % shape_id
                self.config.set("shape%d_title" % shape_id, title)

    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Logo constructor"), "leaf": True, "order": 20})

    def download_image(self, uri):
        if type(uri) == unicode:
            uri = uri.encode("utf-8")
        uri_obj = urlparse.urlparse(uri, "http", False)
        cnn = HTTPConnection()
        cnn.connect((uri_obj.hostname, 80))
        resp = None
        try:
            req = cnn.get(uri_obj.path)
            resp = cnn.perform(req)
            if resp.status_code != 200:
                raise RuntimeError("Couldn't download %s: %s" % (uri, cgi.escape(resp.status)))
        finally:
            cnn.close()
        im = Image.open(cStringIO.StringIO(resp.body))
        im.load()
        return im

    def open_image(self, subdir, key, suffix=""):
        im = Image.open("%s/../static/constructor/logo/%s/%s%s.png" % (mg.__path__[0], subdir, key, suffix))
        im.load()
        return im

    def render(self, shapes, fillers):
        background = None
        layers = self.config.get("layers")
        result_image = Image.new("RGBA", (100, 75), (255, 255, 255))
        if layers:
            for layer in layers:
                print "rendering %s - %s" % (layer["shape"], layer["filler"])
                shape_info = shapes[layer["shape"]]
                if shape_info.get("uri"):
                    shape_mask = self.download_image(shape_info["uri"])
                else:
                    shape_mask = self.open_image("shapes", shape_info["key"])
                if layer.get("smooth"):
                    print "smoothing mask"
                    shape_mask = ImageEnhance.Sharpness(shape_mask).enhance(0)
                    shape_mask = ImageEnhance.Sharpness(shape_mask).enhance(0)
                    shape_mask = ImageEnhance.Sharpness(shape_mask).enhance(0)
                    shape_mask = ImageEnhance.Sharpness(shape_mask).enhance(0)
                filler_info = fillers[layer["filler"]]
                if filler_info.get("uri"):
                    filler = self.download_image(filler_info["uri"])
                else:
                    filler = self.open_image("fillers", filler_info["key"])
                if shape_info.get("bg_mask") and background:
                    bg_mask = self.open_image("shapes", shape_info["key"], "-bg")
                    result_image.paste(background, None, bg_mask)
                result_image.paste(filler, None, shape_mask)
                if background is None:
                    background = result_image.copy()
        # storing image
        png = cStringIO.StringIO()
        result_image.save(png, "PNG")
        png = png.getvalue()
        uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
        self.config.set("preview", uri)
        return uri

    def finish(self):
        image = self.download_image(self.config.get("preview"))
        self.result(image)
        super(LogoWizard, self).finish()

    def request(self, cmd):
        req = self.req()
        # loading layer options
        shapes = []
        shapes.append({"key": None, "title": "", "html": self._("Remove")})
        shapes.append({"key": "solid", "title": self._("Solid"), "html": '<img src="/st/constructor/logo/shapes/solid.png" class="logo-image" alt="" />'})
        shapes.append({"key": "circle", "title": self._("Circle"), "html": '<img src="/st/constructor/logo/shapes/circle.png" class="logo-image" alt="" />'})
        shapes.append({"key": "ring", "title": self._("Ring border"), "html": '<img src="/st/constructor/logo/shapes/ring.png" class="logo-image" alt="" />', "bg_mask": True})
        shapes.append({"key": "square", "title": self._("Square"), "html": '<img src="/st/constructor/logo/shapes/square.png" class="logo-image" alt="" />'})
        shapes.append({"key": "rect", "title": self._("Rectangle"), "html": '<img src="/st/constructor/logo/shapes/rect.png" class="logo-image" alt="" />', "bg_mask": True})
        shapes.append({"key": "triangle1", "title": self._("Triangle 1"), "html": '<img src="/st/constructor/logo/shapes/triangle1.png" class="logo-image" alt="" />'})
        shapes.append({"key": "triangle2", "title": self._("Triangle 2"), "html": '<img src="/st/constructor/logo/shapes/triangle2.png" class="logo-image" alt="" />'})
        for shape_id in range(1, self.config.get_int("shapes") + 1):
            uri = self.config.get("shape%d_uri" % shape_id)
            title = self.config.get("shape%d_title" % shape_id)
            shapes.append({"key": "custom.%d" % shape_id, "title": title, "html": '<img src="%s" class="logo-image" alt="" />' % uri, "uri": uri})
        shapes[-1]["lst"] = True
        valid_shapes = dict([(shape["key"], shape) for shape in shapes])
        fillers = []
        fillers.append({"key": None, "title": "", "html": self._("Remove")})
        fillers.append({"key": "bamboo01", "title": self._("Bamboo #1"), "html": '<img src="/st/constructor/logo/fillers/bamboo01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "brick01", "title": self._("Brick #1"), "html": '<img src="/st/constructor/logo/fillers/brick01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "brick02", "title": self._("Brick #2"), "html": '<img src="/st/constructor/logo/fillers/brick02.png" class="logo-image" alt="" />'})
        fillers.append({"key": "dirt01", "title": self._("Dirt #1"), "html": '<img src="/st/constructor/logo/fillers/dirt01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "fur01", "title": self._("Fur #1"), "html": '<img src="/st/constructor/logo/fillers/fur01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "grass01", "title": self._("Grass #1"), "html": '<img src="/st/constructor/logo/fillers/grass01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "grass02", "title": self._("Grass #2"), "html": '<img src="/st/constructor/logo/fillers/grass02.png" class="logo-image" alt="" />'})
        fillers.append({"key": "grass03", "title": self._("Grass #3"), "html": '<img src="/st/constructor/logo/fillers/grass03.png" class="logo-image" alt="" />'})
        fillers.append({"key": "grass04", "title": self._("Grass #4"), "html": '<img src="/st/constructor/logo/fillers/grass04.png" class="logo-image" alt="" />'})
        fillers.append({"key": "leather01", "title": self._("Leather #1"), "html": '<img src="/st/constructor/logo/fillers/leather01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "metal01", "title": self._("Metal #1"), "html": '<img src="/st/constructor/logo/fillers/metal01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "metal02", "title": self._("Metal #2"), "html": '<img src="/st/constructor/logo/fillers/metal02.png" class="logo-image" alt="" />'})
        fillers.append({"key": "metal03", "title": self._("Metal #3"), "html": '<img src="/st/constructor/logo/fillers/metal03.png" class="logo-image" alt="" />'})
        fillers.append({"key": "sack01", "title": self._("Sack #1"), "html": '<img src="/st/constructor/logo/fillers/sack01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "sack02", "title": self._("Sack #2"), "html": '<img src="/st/constructor/logo/fillers/sack02.png" class="logo-image" alt="" />'})
        fillers.append({"key": "sky01", "title": self._("Sky #1"), "html": '<img src="/st/constructor/logo/fillers/sky01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "stones01", "title": self._("Stones #1"), "html": '<img src="/st/constructor/logo/fillers/stones01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "wicker01", "title": self._("Wicker #1"), "html": '<img src="/st/constructor/logo/fillers/wicker01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "wood01", "title": self._("Wood #1"), "html": '<img src="/st/constructor/logo/fillers/wood01.png" class="logo-image" alt="" />'})
        fillers.append({"key": "wood02", "title": self._("Wood #2"), "html": '<img src="/st/constructor/logo/fillers/wood02.png" class="logo-image" alt="" />'})
        fillers.append({"key": "wood03", "title": self._("Wood #3"), "html": '<img src="/st/constructor/logo/fillers/wood03.png" class="logo-image" alt="" />'})
        fillers.append({"key": "wood04", "title": self._("Wood #4"), "html": '<img src="/st/constructor/logo/fillers/wood04.png" class="logo-image" alt="" />'})
        fillers.append({"key": "wood05", "title": self._("Wood #5"), "html": '<img src="/st/constructor/logo/fillers/wood05.png" class="logo-image" alt="" />'})
        for filler_id in range(1, self.config.get_int("fillers") + 1):
            uri = self.config.get("filler%d_uri" % filler_id)
            title = self.config.get("filler%d_title" % filler_id)
            fillers.append({"key": "custom.%d" % filler_id, "title": title, "html": '<img src="%s" class="logo-image" alt="" />' % uri, "uri": uri})
        fillers.append({"key": "upload", "title": "", "html": self._("Upload new custom 100x75 image...")})
        fillers.append({"key": "solid", "title": "", "html": self._("Select solid color...")})
        fillers[-1]["lst"] = True
        valid_fillers = dict([(filler["key"], filler) for filler in fillers])
        # parsing command
        if cmd == "abort":
            self.abort()
            self.call("admin.update_menu")
            self.call("admin.redirect", self.config.get("redirect_fail"))
        elif cmd == "filler/solid":
            color = req.param("color")
            rgb = parse_color(color)
            if not rgb:
                self.call("web.response_json", {"success": False, "errormsg": self._("Invalid color")})
            img = Image.new("RGBA", (100, 75), rgb)
            # storing image
            png = cStringIO.StringIO()
            img.save(png, "PNG")
            png = png.getvalue()
            uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
            filler_id = self.config.get_int("fillers") + 1
            self.config.set("fillers", filler_id)
            solid_id = self.config.get_int("solids") + 1
            self.config.set("solids", solid_id)
            self.config.set("filler%d_uri" % filler_id, uri)
            title = self._("Solid color #%d - %s") % (solid_id, color)
            self.config.set("filler%d_title" % filler_id, title)
            self.config.store()
            self.call("web.response_json_html", {"success": True, "filler": True, "key": "custom.%d" % filler_id, "title": title, "html": '<img src="%s" width="100" height="75" alt="" />' % uri})
        elif cmd == "filler/upload":
            image = req.param_raw("image")
            if image is None or not len(image):
                self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Upload your image")}})
            try:
                image_obj = Image.open(cStringIO.StringIO(image))
                if image_obj.load() is None:
                    raise IOError;
            except IOError:
                self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Image format not recognized")}})
            try:
                image_obj.seek(1)
                self.call("web.response_json_html", {"success": False, "errors": {"image": self._("Animated images are not supported")}})
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
            # putting image on the white result_image
            result_image = Image.new("RGBA", (100, 75), (255, 255, 255, 0))
            result_image.paste(image_obj, None, image_obj)
            # storing image
            png = cStringIO.StringIO()
            result_image.save(png, "PNG")
            png = png.getvalue()
            uri = self.call("cluster.static_upload_temp", "logo", "png", "image/png", png, wizard=self.uuid)
            filler_id = self.config.get_int("fillers") + 1
            self.config.set("fillers", filler_id)
            custom_id = self.config.get_int("customs") + 1
            self.config.set("customs", custom_id)
            self.config.set("filler%d_uri" % filler_id, uri)
            title = self._("Custom image #%d") % custom_id
            self.config.set("filler%d_title" % filler_id, title)
            self.config.store()
            self.call("web.response_json_html", {"success": True, "filler": True, "key": "custom.%d" % filler_id, "title": title, "html": '<img src="%s" width="100" height="75" alt="" />' % uri})
        elif cmd == "shapes":
            i = 1
            errors = {}
            layers = []
            add_layer = True
            while req.param_raw("shape%d" % i) != None:
                shape = req.param("shape%d" % i)
                filler = req.param("filler%d" % i)
                smooth = True if req.param("smooth%d" % i) else False
                add_layer = True
                if filler in valid_fillers and shape in valid_shapes:
                    layers.append({"shape": shape, "filler": filler, "smooth": smooth})
                else:
                    add_layer = False
                print "layer %d - shape %s - filler %s - smooth %s" % (i, shape, filler, smooth)
                i += 1
            if len(errors):
                self.call("web.response_json_html", {"success": False, "errors": errors})
            self.config.set("layers", layers)
            uri = self.render(valid_shapes, valid_fillers)
            self.config.store()
            self.call("web.response_json_html", {"success": True, "add_layer": add_layer, "preview": uri})
        elif cmd == "apply":
            if self.config.get("preview"):
                target = self.config.get("target")
                self.finish()
                if target[0] == "wizard":
                    self.call("admin.redirect", "wizard/call/%s" % target[1])
                else:
                    self.call("admin.redirect", "")
        vars = {
            "LogoConstructor": self._("Logo constructor"),
            "HereYouCan": self._("Here you can construct your own simple 100x75 logo using several basic elements."),
            "wizard": self.uuid,
            "shapes": shapes,
            "fillers": fillers,
            "layers": self.config.get("layers"),
            "preview": self.config.get("preview"),
        }
        self.call("admin.response_template", "constructor/logo-wizard.html", vars)
