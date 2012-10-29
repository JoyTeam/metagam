from mg.constructor import *
from mg.constructor.player_classes import *
from uuid import uuid4
import re
import cStringIO
from PIL import Image

max_dimensions = 5

re_dimensions = re.compile(r'\s*,\s*')
re_parse_dimensions = re.compile(r'^(\d+)x(\d+)$')
re_del = re.compile(r'^del\/([0-9a-f]+)$')
re_layer_edit = re.compile(r'([0-9a-f]+|new)$')
re_layer_images = re.compile(r'([0-9a-f]+)/images(?:/(.+)|)$')
re_image_key = re.compile(r'^image-')
re_newline = re.compile(r'\n')

class CharImages(ConstructorModule):
    def register(self):
        self.rhook("charimages.get", self.get)
        self.rhook("character-page.actions", self.charpage_actions)
        self.rhook("money-description.charimage", self.money_description_charimage)
        self.rhook("ext-charimage.select", self.charimage_select, priv="logged")
        if self.conf("charimages.layers"):
            self.rhook("ext-charimage.construct", self.charimage_construct, priv="logged")
        self.rhook("library-grp-index.pages", self.library_index_pages)
        self.rhook("library-page-charimages.content", self.library_page_charimages)

    def library_index_pages(self, pages):
        pages.append({"page": "charimages", "order": 30})

    def library_page_charimages(self, render_content):
        pageinfo = {
            "code": "charimages",
            "title": self._("Character images"),
            "keywords": self._("character images"),
            "description": self._("This page describes character images setting rules"),
            "parent": "index",
        }
        if render_content:
            vars = {
            }
            price = self.conf("charimages.price")
            currency = self.conf("charimages.currency")
            images = self.call("charimages.for-sex", 0)
            images.extend(self.call("charimages.for-sex", 1))
            images = [img for img in images if img["info"].get("available")]
            if images:
                vars["images"] = True
                for img in images:
                    p = img["info"].get("price")
                    c = img["info"].get("currency")
                    if p is None:
                        p = price
                        c = currency
                    if p:
                        vars["paid"] = True
                        if not img["info"].get("deny_free") and self.conf("charimages.first-free", True):
                            vars["first_free"] = True
                    elif not img["info"].get("deny_free"):
                        vars["free"] = True
            if self.conf("charimages.layers"):
                vars["layers"] = True
                if price:
                    vars["paid"] = True
                    vars["price"] = self.call("money.price-html", price, currency)
            pageinfo["content"] = self.call("socio.parse", "library-charimages.html", vars)
        return pageinfo

    def money_description_charimage(self):
        return {
            "args": ["name"],
            "text": self._("Character image: {name}"),
        }

    def get(self, character, dim):
        uri = None
        if dim == "charinfo":
            dim = self.conf("charimages.dim_charinfo", "240x440")
        elif dim == "charpage":
            dim = self.conf("charimages.dim_charpage", "120x220")
        try:
            image = character.db_charimage
        except ObjectNotFoundException:
            pass
        else:
            static = image.get("static")
            if static:
                info = self.conf("charimages.%s" % static)
                if info:
                    uri = info.get("image-%s" % dim)
            else:
                uri = image.get("image-%s" % dim)
        if uri is None:
            default = self.conf("charimages.default%s" % character.sex)
            if default:
                info = self.conf("charimages.%s" % default)
                if info:
                    uri = info.get("image-%s" % dim)
        return uri

    def charpage_actions(self, character, actions):
        images = self.call("charimages.for-sex", character.sex)
        def eval_desc():
            return self._("Character image availability")
        images = [img for img in images if self.call("script.evaluate-expression", img["info"].get("available"), globs={"char": character}, description=eval_desc)]
        if images:
            actions.append({"href": "/charimage/select", "text": self._("charimage///Select character image"), "order": 10})
        if self.conf("charimages.layers"):
            actions.append({"href": "/charimage/construct", "text": self._("charimage///Construct character image"), "order": 11})

    def charimage_select(self):
        req = self.req()
        character = self.character(req.user())
        dim = self.call("charimages.dim-charpage")
        m = re_parse_dimensions.match(dim)
        if m:
            width, height = m.group(1, 2)
        else:
            width = 100
            height = 100
        vars = {
            "width": width,
            "height": height,
            "Select": self._("charimage///Select"),
        }
        images = self.call("charimages.for-sex", character.sex)
        try:
            old_image = character.db_charimage
            first = False
        except ObjectNotFoundException:
            first = True
        for img in images:
            if first and self.conf("charimages.first-free", True) and not img["info"].get("deny_free"):
                price = None
                currency = None
            elif img["info"].get("price") is not None:
                price = img["info"]["price"]
                currency = img["info"].get("currency")
            else:
                price = self.conf("charimages.price")
                currency = self.conf("charimages.currency")
            img["price"] = price
            img["currency"] = currency
            if price:
                img["price_html"] = self.call("money.price-html", price, currency)
            else:
                img["price_html"] = self._("money///free")
        def eval_desc():
            return self._("Character image availability")
        images = [img for img in images if (img.get("price") or not img["info"].get("deny_free")) and self.call("script.evaluate-expression", img["info"].get("available"), globs={"char": character}, description=eval_desc)]
        if req.ok():
            image = req.param("image")
            for ent in images:
                if ent["id"] == image:
                    vars["image"] = image
                    obj = self.obj(DBCharImage, character.uuid, silent=True)
                    ok = False
                    if obj.get("static") != image:
                        if ent["price"]:
                            if not character.money.debit(ent["price"], ent["currency"], "charimage", name=ent["info"]["name"]):
                                vars["error"] = self.call("money.not-enough-funds", ent["currency"], character=character)
                            else:
                                ok = True
                        else:
                            ok = True
                        if ok:
                            delete_uri = []
                            for key, uri in obj.data.iteritems():
                                if re_image_key.match(key):
                                    delete_uri.append(uri)
                            obj.clear()
                            obj.set("static", image)
                            obj.store()
                            for uri in delete_uri:
                                self.call("cluster.static_delete", uri)
                    else:
                        ok = True
                    if ok:
                        self.call("web.redirect", "/interface/character")
        layout = self.call("game.parse_internal", "charimage-select-layout.html", vars)
        vars["images"] = []
        vars["layout"] = layout
        if not images:
            self.call("web.redirect", "/interface/character")
        for img in images:
            image = img["info"].get("image-%s" % dim)
            if not image:
                for key, val in img["info"].iteritems():
                    if re_image_key.match(key):
                        image = val
                        break
            vars["images"].append({
                "id": img["id"],
                "name": jsencode(htmlescape(img["info"]["name"])),
                "description": jsencode(re_newline.sub('<br />', htmlescape(img["info"].get("description")))),
                "image": image,
                "price": img.get("price_html"),
            })
        self.call("game.response_internal", "charimage-select.html", vars)

    def charimage_construct(self):
        req = self.req()
        character = self.character(req.user())
        dim = self.call("charimages.dim-charpage")
        m = re_parse_dimensions.match(dim)
        if m:
            width, height = m.group(1, 2)
            width = intz(width)
            height = intz(height)
        else:
            width = 100
            height = 100
        vars = {
            "width": width,
            "height": height,
            "Select": self._("charimage///Select"),
            "layers": [],
        }
        sex_key = "sex%d" % character.sex
        dimensions = self.call("charimages.dimensions")
        selected = {}
        for d in dimensions:
            selected["%dx%d" % (d["width"], d["height"])] = []
        all_selected = True
        for ent in self.call("charimages.layers"):
            layer = {
                "id": ent["id"],
                "name": htmlescape(ent["name"]),
            }
            images = []
            sel = req.param("image-%s" % ent["id"])
            for img in self.call("charimages.layer-images", ent["id"]):
                if img.get(sex_key):
                    ok = True
                    for d in dimensions:
                        if not img.get("image-%dx%d" % (d["width"], d["height"])):
                            ok = False
                            break
                    if ok:
                        images.append({
                            "id": img["id"],
                            "image": img.get("image-%s" % dim),
                        })
                        if sel == img["id"]:
                            layer["image"] = sel
                            for d in dimensions:
                                sz = "%dx%d" % (d["width"], d["height"])
                                selected[sz].append(img.get("image-%s" % sz))
            if images:
                images[-1]["lst"] = True
                layer["images"] = images
                layer["images_cnt"] = len(images)
                vars["layers"].append(layer)
                if not layer.get("image"):
                    all_selected = False
        if not vars["layers"]:
            self.call("main-frame.error", self._("Character image constructor is unavailable. No layers defined"))
        # calculating price
        price = self.conf("charimages.price")
        currency = self.conf("charimages.currency")
        try:
            old_image = character.db_charimage
            first = False
        except ObjectNotFoundException:
            first = True
        if first and self.conf("charimages.first-free", True):
            price = None
            currency = None
        if price:
            vars["price"] = self.call("money.price-html", price, currency)
        else:
            vars["price"] = self._("money///free")
        # constructing new character image
        if req.ok() and all_selected:
            image = {}
            for d in dimensions:
                size = "%dx%d" % (d["width"], d["height"])
                image[size] = Image.new("RGBA", (d["width"], d["height"]), (128, 128, 128, 0))
                for uri in reversed(selected[size]):
                    data = self.download(uri)
                    layer = Image.open(cStringIO.StringIO(data))
                    layer.load()
                    image[size].paste(layer.convert("RGB"), (0, 0), layer.convert("RGBA"))
            ok = False
            # money
            if price:
                if not character.money.debit(price, currency, "charimage", name=self._("charimage///user constructed")):
                    vars["error"] = self.call("money.not-enough-funds", currency, character=character)
                else:
                    ok = True
            else:
                ok = True
            # storing
            if ok:
                obj = self.obj(DBCharImage, character.uuid, silent=True)
                delete_uri = []
                for key, uri in obj.data.iteritems():
                    if re_image_key.match(key):
                        delete_uri.append(uri)
                obj.clear()
                for d in dimensions:
                    size = "%dx%d" % (d["width"], d["height"])
                    # resize
                    w = d["width"]
                    h = d["height"]
                    if h != d["height"]:
                        w = w * d["height"] / h
                        h = d["height"]
                    if w < d["width"]:
                        h = h * d["width"] / w
                        w = d["width"]
                    left = (w - d["width"]) / 2
                    top = (h - d["height"]) / 2
                    # store
                    stream = cStringIO.StringIO()
                    image[size].save(stream, "PNG")
                    uri = self.call("cluster.static_upload", "charimage-usergen", "png", "image/png", stream.getvalue())
                    obj.set("image-%s" % size, uri)
                obj.store()
                for uri in delete_uri:
                    self.call("cluster.static_delete", uri)
                self.call("web.redirect", "/interface/character")
        layout = self.call("game.parse_internal", "charimage-construct-layout.html", vars)
        vars["layout"] = layout
        self.call("game.response_internal", "charimage-construct.html", vars)

class CharImagesAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-characters.index", self.menu_characters_index)
        self.rhook("menu-admin-charimages.index", self.menu_charimages_index)
        self.rhook("ext-admin-charimages.config", self.ext_config, priv="charimages.config")
        self.rhook("headmenu-admin-charimages.config", self.headmenu_config)
        self.rhook("ext-admin-charimages.editor", self.ext_editor, priv="charimages.editor")
        self.rhook("headmenu-admin-charimages.editor", self.headmenu_editor)
        if self.conf("charimages.layers"):
            self.rhook("ext-admin-charimages.layers", self.ext_layers, priv="charimages.editor")
            self.rhook("headmenu-admin-charimages.layers", self.headmenu_layers)
        self.rhook("charimages.for-sex", self.images_for_sex)
        self.rhook("charimages.dim-charpage", self.dim_charpage)
        self.rhook("charimages.dim-charinfo", self.dim_charinfo)
        self.rhook("charimages.layers", self.layers)
        self.rhook("charimages.layer-images", self.layer_images)
        self.rhook("charimages.dimensions", self.dimensions)
        self.rhook("advice-admin-charimages.index", self.advice_charimages)
        self.rhook("admin-gameinterface.design-files", self.design_files)

    def design_files(self, files):
        files.append({"filename": "charimage-select.html", "description": self._("Character image selector"), "doc": "/doc/design/character-images"})
        files.append({"filename": "charimage-select-layout.html", "description": self._("Character image selector layout"), "doc": "/doc/design/character-images"})
        files.append({"filename": "charimage-construct.html", "description": self._("Character image constructor"), "doc": "/doc/design/character-images"})
        files.append({"filename": "charimage-construct-layout.html", "description": self._("Character image constructor layout"), "doc": "/doc/design/character-images"})

    def advice_charimages(self, hook, args, advice):
        advice.append({"title": self._("Characters images documentation"), "content": self._('You can find detailed information on the characters images system in the <a href="//www.%s/doc/character-images" target="_blank">characters images page</a> in the reference manual.') % self.main_host})

    def permissions_list(self, perms):
        perms.append({"id": "charimages.config", "name": self._("Character images configuration")})
        perms.append({"id": "charimages.editor", "name": self._("Character images editor")})

    def menu_characters_index(self, menu):
        menu.append({"id": "charimages.index", "text": self._("Character images"), "order": 30})

    def menu_charimages_index(self, menu):
        req = self.req()
        if req.has_access("charimages.config"):
            menu.append({"id": "charimages/config", "text": self._("charimages///Images configuration"), "leaf": True, "order": 10})
        if req.has_access("charimages.editor"):
            menu.append({"id": "charimages/editor", "text": self._("charimages///Images editor"), "leaf": True, "order": 20})
            if self.conf("charimages.layers"):
                menu.append({"id": "charimages/layers", "text": self._("Layers editor"), "leaf": True, "order": 30})

    def headmenu_config(self, args):
        return self._("Character images configuration")

    def dimensions(self):
        val = self.conf("charimages.dimensions")
        if val:
            return val
        return [
            {"width": 48, "height": 88},
            {"width": 120, "height": 220},
            {"width": 240, "height": 440}
        ]

    def dim_charpage(self):
        return self.conf("charimages.dim_charpage", "120x220")

    def dim_charinfo(self):
        return self.conf("charimages.dim_charinfo", "240x440")

    def images_for_sex(self, sex):
        lst = []
        for uuid in self.conf("charimages.list", []):
            info = self.conf("charimages.%s" % uuid)
            if info and info.get("sex%s" % sex):
                lst.append({
                    "id": uuid,
                    "info": info
                })
        return lst

    def ext_config(self):
        req = self.req()
        images0 = self.images_for_sex(0)
        images1 = self.images_for_sex(1)
        currencies = {}
        self.call("currencies.list", currencies)
        if req.param("ok"):
            dimensions = re_dimensions.split(req.param("dimensions"))
            config = self.app().config_updater()
            errors = {}
#            # require
#            config.set("charimages.require", True if req.param("require") else False)
            # layers
            config.set("charimages.layers", True if req.param("layers") else False)
            # default images
            if images0:
                default0 = req.param("v_default0")
                found = False
                for img in images0:
                    if img["id"] == default0:
                        found = True
                        config.set("charimages.default0", default0)
                        break
                if not found:
                    errors["v_default0"] = self._("charimage///Select a valid image")
            else:
                config.delete("charimages.default0")
            if images1:
                default1 = req.param("v_default1")
                found = False
                for img in images1:
                    if img["id"] == default1:
                        found = True
                        config.set("charimages.default1", default1)
                        break
                if not found:
                    errors["v_default1"] = self._("charimage///Select a valid image")
            else:
                config.delete("charimages.default0")
            # dimensions
            valid_dimensions = set()
            if not dimensions:
                errors["dimensions"] = self._("This field is mandatory")
            elif len(dimensions) > max_dimensions:
                errors["dimensions"] = self._("Maximal number of dimensions is %d") % max_dimensions
            else:
                result_dimensions = []
                for dim in dimensions:
                    if not dim:
                        errors["dimensions"] = self._("Empty dimension encountered")
                    else:
                        m = re_parse_dimensions.match(dim)
                        if not m:
                            errors["dimensions"] = self._("Invalid dimensions format: %s") % dim
                        else:
                            width, height = m.group(1, 2)
                            width = int(width)
                            height = int(height)
                            if width < 32 or height < 32:
                                errors["dimensions"] = self._("Minimal size is 32x32")
                            elif width > 460 or height > 880:
                                errors["dimensions"] = self._("Maximal size is 460x880")
                            else:
                                result_dimensions.append({
                                    "width": width,
                                    "height": height,
                                })
                                valid_dimensions.add(dim)
                result_dimensions.sort(cmp=lambda x, y: cmp(x["width"] + x["height"], y["width"] + y["height"]))
                config.set("charimages.dimensions", result_dimensions)
            # selected dimensions
            dim_charinfo = req.param("dim_charinfo")
            if not dim_charinfo:
                errors["dim_charinfo"] = self._("This field is mandatory")
            elif dim_charinfo not in valid_dimensions:
                errors["dim_charinfo"] = self._("This dimension must be listed in the list of available dimensions above")
            else:
                config.set("charimages.dim_charinfo", dim_charinfo)
            dim_charpage = req.param("dim_charpage")
            if not dim_charpage:
                errors["dim_charpage"] = self._("This field is mandatory")
            elif dim_charpage not in valid_dimensions:
                errors["dim_charpage"] = self._("This dimension must be listed in the list of available dimensions above")
            else:
                config.set("charimages.dim_charpage", dim_charpage)
            # prices
            price = req.param("price").strip()
            currency = req.param("v_currency")
            if price == "" or floatz(price) == 0:
                config.delete("charimages.price")
                config.delete("charimages.currency")
            elif self.call("money.valid_amount", price, currency, errors, "price", "v_currency"):
                price = float(price)
                config.set("charimages.price", price)
                config.set("charimages.currency", currency)
            config.set("charimages.first-free", True if req.param("first_free") else False)
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        dimensions = self.dimensions()
        fields = [
            {"name": "default0", "label": self._("charimage///Default male image"), "type": "combo", "values": [(ent["id"], ent["info"]["name"]) for ent in images0], "value": self.conf("charimages.default0")},
            {"name": "default1", "label": self._("charimage///Default female image"), "type": "combo", "values": [(ent["id"], ent["info"]["name"]) for ent in images1], "value": self.conf("charimages.default1"), "inline": True},
#            {"name": "require", "label": self._("Every character must select an image after registration (prohibit gameplay with default avatar)"), "checked": self.conf("charimages.require"), "type": "checkbox"},
            {"name": "dimensions", "label": self._("Store character images in these dimensions (comma separated)"), "value": ", ".join(["%dx%d" % (d["width"], d["height"]) for d in dimensions])},
            {"name": "dim_charinfo", "label": self._("Character image dimensions on the character info page"), "value": self.dim_charinfo()},
            {"name": "dim_charpage", "label": self._("Character image dimensions on the ingame character page"), "value": self.dim_charpage()},
            {"name": "layers", "label": self._("Enabled layered character images"), "type": "checkbox", "checked": self.conf("charimages.layers")},
            {"name": "price", "label": self._("charimage///Price for image change"), "value": self.conf("charimages.price") },
            {"name": "currency", "label": self._("Currency"), "type": "combo", "value": self.conf("charimages.currency"), "values": [(code, info["name_plural"]) for code, info in currencies.iteritems()], "inline": True},
            {"name": "first_free", "label": self._("First image selection after registration is free"), "checked": self.conf("charimages.first-free", True), "type": "checkbox"}
        ]
        self.call("admin.form", fields=fields)

    def headmenu_editor(self, args):
        if args == "new":
            return [self._("charimages///New image"), "charimages/editor"]
        elif args:
            info = self.conf("charimages.%s" % args)
            if info:
                return [htmlescape(info["name"]), "charimages/editor"]
        return self._("Character images list")

    def ext_editor(self):
        dimensions = self.dimensions()
        req = self.req()
        m = re_del.match(req.args)
        if m:
            del_uuid = m.group(1)
            config = self.app().config_updater()
            config.set("charimages.list", [uuid for uuid in self.conf("charimages.list", []) if uuid != del_uuid])
            obj = self.conf("charimages.%s" % del_uuid)
            if obj:
                obj["deleted"] = True
                config.set("charimages.%s" % del_uuid, obj)
            config.store()
            self.call("admin.redirect", "charimages/editor")
        elif req.args:
            if req.args == "new":
                uuid = uuid4().hex
                obj = {}
            else:
                uuid = req.args
                obj = self.conf("charimages.%s" % uuid)
                if obj is None or obj.get("deleted"):
                    self.call("admin.redirect", "charimages/editor")
            currencies = {}
            self.call("currencies.list", currencies)
            if req.ok():
                self.call("web.upload_handler")
                errors = {}
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                image_data = req.param_raw("image")
                replace = intz(req.param("v_replace"))
                dim_images = {}
                if req.args == "new" or replace == 1:
                    if not image_data:
                        errors["image"] = self._("Missing image")
                    else:
                        try:
                            image = Image.open(cStringIO.StringIO(image_data))
                            if image.load() is None:
                                raise IOError
                        except IOError:
                            errors["image"] = self._("Image format not recognized")
                        else:
                            ext, content_type = self.image_format(image)
                            form = image.format
                            trans = image.info.get("transparency")
                            if ext is None:
                                errors["image"] = self._("Valid formats are: PNG, GIF, JPEG")
                            else:
                                for dim in dimensions:
                                    size = "%dx%d" % (dim["width"], dim["height"])
                                    dim_images[size] = (image, ext, content_type, form, trans)
                elif replace == 2:
                    for dim in dimensions:
                        size = "%dx%d" % (dim["width"], dim["height"])
                        image_data = req.param_raw("image_%s" % size)
                        if image_data:
                            try:
                                dim_image = Image.open(cStringIO.StringIO(image_data))
                                if dim_image.load() is None:
                                    raise IOError
                            except IOError:
                                errors["image_%s" % size] = self._("Image format not recognized")
                            else:
                                ext, content_type = self.image_format(dim_image)
                                form = dim_image.format
                                trans = dim_image.info.get("transparency")
                                if ext is None:
                                    errors["image_%s" % size] = self._("Valid formats are: PNG, GIF, JPEG")
                                else:
                                    dim_images[size] = (dim_image, ext, content_type, form, trans)
                # sex
                sex0 = True if req.param("sex0") else False
                sex1 = True if req.param("sex1") else False
                # prices
                if req.param("override_price"):
                    price = req.param("price").strip()
                    currency = req.param("v_currency")
                    if floatz(price) != 0:
                        if self.call("money.valid_amount", price, currency, errors, "price", "v_currency"):
                            price = float(price)
                    else:
                        price = 0
                else:
                    price = None
                    currency = None
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                # storing images
                delete_images = []
                for dim in dimensions:
                    size = "%dx%d" % (dim["width"], dim["height"])
                    try:
                        image, ext, content_type, form, trans = dim_images[size]
                    except KeyError:
                        pass
                    else:
                        w, h = image.size
                        if h != dim["height"]:
                            w = w * dim["height"] / h
                            h = dim["height"]
                        if w < dim["width"]:
                            h = h * dim["width"] / w
                            w = dim["width"]
                        left = (w - dim["width"]) / 2
                        top = (h - dim["height"]) / 2
                        image = image.resize((w, h), Image.ANTIALIAS).crop((left, top, left + dim["width"], top + dim["height"]))
                        data = cStringIO.StringIO()
                        if form == "JPEG":
                            image.save(data, form, quality=95)
                        elif form == "GIF":
                            if trans:
                                image.save(data, form, transparency=trans)
                            else:
                                image.save(data, form)
                        else:
                            image.save(data, form)
                        uri = self.call("cluster.static_upload", "charimage", ext, content_type, data.getvalue())
                        key = "image-%s" % size
                        delete_images.append(obj.get(key))
                        obj[key] = uri
                # storing info
                obj["name"] = name
                obj["sex0"] = sex0
                obj["sex1"] = sex1
                obj["description"] = req.param("description").strip()
                char = self.character(req.user())
                obj["available"] = self.call("script.admin-expression", "available", errors, globs={"char": char})
                if obj["available"]:
                    obj["deny_free"] = True if req.param("deny_free") else False
                else:
                    obj["deny_free"] = False
                    price = None
                    currency = None
                # storing price
                if price == 0:
                    try:
                        del obj["currency"]
                    except KeyError:
                        pass
                    obj["price"] = price
                elif price is None:
                    try:
                        del obj["price"]
                        del obj["currency"]
                    except KeyError:
                        pass
                else:
                    obj["price"] = price
                    obj["currency"] = currency
                config = self.app().config_updater()
                lst = self.conf("charimages.list", [])
                if uuid not in lst:
                    lst.append(uuid)
                    config.set("charimages.list", lst)
                config.set("charimages.%s" % uuid, obj)
                config.store()
                # deleting old images
                for uri in delete_images:
                    if uri:
                        self.call("cluster.static_delete", uri)
                self.call("admin.redirect", "charimages/editor")
            fields = [
                {"name": "name", "label": self._("charimages///Image name"), "value": obj.get("name")},
                {"name": "description", "label": self._("Character image description"), "type": "textarea", "value": obj.get("description")},
                {"name": "sex0", "label": self._("Male"), "type": "checkbox", "checked": obj.get("sex0")},
                {"name": "sex1", "label": self._("Female"), "type": "checkbox", "checked": obj.get("sex1"), "inline": True},
                {"name": "available", "label": self._("Available to players") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", obj.get("available", 1))},
                {"name": "override_price", "label": self._("Specific price"), "checked": True if obj.get("price") is not None else False, "type": "checkbox", "condition": "[available]"},
                {"name": "deny_free", "label": self._("Deny selection for free"), "checked": obj.get("deny_free"), "type": "checkbox", "inline": True, "condition": "[available]"},
                {"name": "price", "label": self._("charimage///Price for this image"), "value": obj.get("price"), "condition": "[override_price] && [available]"},
                {"name": "currency", "label": self._("Currency"), "type": "combo", "value": obj.get("currency"), "values": [(code, info["name_plural"]) for code, info in currencies.iteritems()], "inline": True, "condition": "[override_price] && [available]"},
            ]
            if req.args == "new":
                fields.append({"name": "image", "type": "fileuploadfield", "label": self._("charimage///Image")})
            else:
                fields.append({"name": "replace", "type": "combo", "label": self._("Replace images"), "values": [(0, self._("Replace nothing")), (1, self._("Replace all images")), (2, self._("Replace specific images"))], "value": 0})
                fields.append({"name": "image", "type": "fileuploadfield", "label": self._("charimage///Image"), "condition": "[replace]==1"})
                for dim in dimensions:
                    fields.append({"name": "image_%dx%d" % (dim["width"], dim["height"]), "type": "fileuploadfield", "label": self._("charimage///Image {width}x{height}").format(width=dim["width"], height=dim["height"]), "condition": "[replace]==2"})
                for dim in dimensions:
                    size = "%dx%d" % (dim["width"], dim["height"])
                    key = "image-%s" % size
                    uri = obj.get(key)
                    if uri:
                        fields.append({"type": "html", "html": '<h1>%s</h1><img src="%s" alt="" />' % (size, uri)})
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
        rows = []
        for uuid in self.conf("charimages.list", []):
            info = self.conf("charimages.%s" % uuid)
            if info is None:
                continue
            sex = []
            if info.get("sex0"):
                sex.append(self._('male///M'))
            if info.get("sex1"):
                sex.append(self._('female///F'))
            name = htmlescape(info["name"])
            if not info.get("available"):
                name = '<strike>%s</strike>' % name
            row = [
                '<strong>%s</strong> (%s)' % (name, ', '.join(sex)),
            ]
            for dim in dimensions:
                row.append('<img src="/st-mg/img/%s.gif" alt="" />' % ("done" if info.get("image-%dx%d" % (dim["width"], dim["height"])) else "no"))
            if info.get("price") is not None:
                price = info["price"]
                currency = info.get("currency")
            else:
                price = self.conf("charimages.price")
                currency = self.conf("charimages.currency")
            tags = []
            if info.get("available"):
                if price:
                    tags.append(self.call("money.price-html", price, currency))
                if (not price or self.conf("charimages.first-free", True)) and not info.get("deny_free"):
                    tags.append(self._("money///free"))
            row.extend([
                '<br />'.join(tags),
                '<hook:admin.link href="charimages/editor/%s" title="%s" />' % (uuid, self._("edit")),
                '<hook:admin.link href="charimages/editor/del/%s" title="%s" confirm="%s" />' % (uuid, self._("delete"), self._("charimages///Are you sure want to delete this image?")),
            ])
            rows.append(row)
        header = [
            self._("charimages///Image name"),
        ]
        for dim in dimensions:
            header.append("%dx%d" % (dim["width"], dim["height"]))
        header.extend([
            self._("Price"),
            self._("Editing"),
            self._("Deletion"),
        ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "charimages/editor/new", "text": self._("charimages///New image"), "lst": True},
                    ],
                    "header": header,
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_layers(self, args):
        m = re_layer_edit.match(args)
        if m:
            layer_uuid = m.group(1)
            if layer_uuid == "new":
                return [self._("New layer"), "charimages/layers"]
            else:
                for ent in self.layers():
                    if ent["id"] == layer_uuid:
                        return [htmlescape(ent["name"]), "charimages/layers"]
        m = re_layer_images.match(args)
        if m:
            layer_uuid, cmd = m.group(1, 2)
            if cmd == "new":
                return [self._("New image"), "charimages/layers/%s/images" % layer_uuid]
            elif cmd:
                return [self._("Image editor"), "charimages/layers/%s/images" % layer_uuid]
            else:
                for ent in self.layers():
                    if ent["id"] == layer_uuid:
                        return [self._("Images: %s") % htmlescape(ent["name"]), "charimages/layers"]
        return self._("Character image layers")

    def layers(self):
        val = self.conf("charimages.layers-list")
        if val:
            return val
        return []

    def layer_images(self, layer_uuid):
        val = self.conf("charimages.layer-variants-%s" % layer_uuid)
        if val:
            return val
        return []

    def ext_layers(self):
        req = self.req()
        m = re_del.match(req.args)
        if m:
            del_uuid = m.group(1)
            config = self.app().config_updater()
            new_lst = []
            for ent in self.layers():
                if ent["id"] == del_uuid:
                    for img in self.layer_images(ent["id"]):
                        for key, val in img.iteritems():
                            if re_image_key.match(key):
                                self.call("cluster.static_delete", val)
                    config.delete("charimages.layer-variants-%s" % ent["id"])
                else:
                    new_lst.append(ent)
            config.set("charimages.layers-list", new_lst)
            config.store()
            self.call("admin.redirect", "charimages/layers")
        m = re_layer_edit.match(req.args)
        if m:
            layer_uuid = m.group(1)
            if layer_uuid == "new":
                layer_uuid = uuid4().hex
                layer_info = {"id": layer_uuid}
                layers = self.layers()
                if layers:
                    layer_info["order"] = layers[0]["order"] + 10.0
                else:
                    layer_info["order"] = 0.0
                new = True
            else:
                layer_info = None
                for ent in self.layers():
                    if ent["id"] == layer_uuid:
                        layer_info = ent.copy()
                        break
                if layer_info is None:
                    self.call("admin.redirect", "charimages/layers")
                new = False
            if req.ok():
                errors = {}
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    layer_info["name"] = name
                layer_info["order"] = floatz(req.param("order"))
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                config = self.app().config_updater()
                layers = [ent for ent in self.layers() if ent["id"] != layer_uuid]
                layers.append(layer_info)
                layers.sort(cmp=lambda x, y: cmp(y["order"], x["order"]))
                config.set("charimages.layers-list", layers)
                config.store()
                if new:
                    self.call("admin.redirect", "charimages/layers/%s/images/new" % layer_uuid)
                else:
                    self.call("admin.redirect", "charimages/layers")
            fields = [
                {"name": "name", "label": self._("Layer name"), "value": layer_info.get("name")},
                {"name": "order", "label": self._("Sorting order"), "value": layer_info.get("order")},
            ]
            self.call("admin.form", fields=fields)
        m = re_layer_images.match(req.args)
        if m:
            layer_uuid, cmd = m.group(1, 2)
            layer_info = None
            for layer in self.layers():
                if layer["id"] == layer_uuid:
                    layer_info = layer
                    break
            if layer_info is None:
                self.call("admin.redirect", "charimages/layers")
            m = re_del.match(cmd) if cmd else None
            if m:
                del_uuid = m.group(1)
                config = self.app().config_updater()
                lst = self.layer_images(layer_uuid)
                new_lst = []
                for ent in lst:
                    if ent["id"] == del_uuid:
                        for key, val in ent.iteritems():
                            if re_image_key.match(key):
                                self.call("cluster.static_delete", val)
                    else:
                        new_lst.append(ent)
                config.set("charimages.layer-variants-%s" % layer_uuid, new_lst)
                config.store()
                self.call("admin.redirect", "charimages/layers/%s/images" % layer_uuid)
            dimensions = self.dimensions()
            if cmd:
                if cmd == "new":
                    image_uuid = uuid4().hex
                    image_info = {"id": image_uuid}
                    images = self.layer_images(layer_uuid)
                    if images:
                        image_info["order"] = images[-1]["order"] + 10.0
                    else:
                        image_info["order"] = 0.0
                else:
                    image_uuid = cmd
                    image_info = None
                    for ent in self.layer_images(layer_uuid):
                        if ent["id"] == image_uuid:
                            image_info = ent.copy()
                            break
                    if image_info is None:
                        self.call("admin.redirect", "charimages/layers/%s/images" % layer_uuid)
                if req.ok():
                    self.call("web.upload_handler")
                    errors = {}
                    image_data = req.param_raw("image")
                    replace = intz(req.param("v_replace"))
                    dim_images = {}
                    if cmd == "new" or replace == 1:
                        if not image_data:
                            errors["image"] = self._("Missing image")
                        else:
                            try:
                                image = Image.open(cStringIO.StringIO(image_data))
                                if image.load() is None:
                                    raise IOError
                            except IOError:
                                errors["image"] = self._("Image format not recognized")
                            else:
                                ext, content_type = self.image_format(image)
                                form = image.format
                                trans = image.info.get("transparency")
                                if ext is None:
                                    errors["image"] = self._("Valid formats are: PNG, JPEG, GIF")
                                else:
                                    try:
                                        image.seek(1)
                                        errors["image"] = self._("Animated images are not supported")
                                    except EOFError:
                                        for dim in dimensions:
                                            size = "%dx%d" % (dim["width"], dim["height"])
                                            dim_images[size] = (image, ext, content_type, form, trans)
                    elif replace == 2:
                        for dim in dimensions:
                            size = "%dx%d" % (dim["width"], dim["height"])
                            image_data = req.param_raw("image_%s" % size)
                            if image_data:
                                try:
                                    dim_image = Image.open(cStringIO.StringIO(image_data))
                                    if dim_image.load() is None:
                                        raise IOError
                                except IOError:
                                    errors["image_%s" % size] = self._("Image format not recognized")
                                else:
                                    ext, content_type = self.image_format(dim_image)
                                    form = dim_image.format
                                    trans = dim_image.info.get("transparency")
                                    if ext is None:
                                        errors["image_%s" % size] = self._("Valid formats are: PNG, JPEG, GIF")
                                    else:
                                        try:
                                            dim_image.seek(1)
                                            errors["image_%s" % size] = self._("Animated images are not supported")
                                        except EOFError:
                                            dim_images[size] = (dim_image, ext, content_type, form, trans)
                    # 
                    # Copypaste is evil?
                    # 
                    #image_data = req.param_raw("image")
                    #if not image_data:
                    #    if cmd == "new":
                    #        errors["image"] = self._("Missing image")
                    #else:
                    #    try:
                    #        image = Image.open(cStringIO.StringIO(image_data))
                    #        if image.load() is None:
                    #            raise IOError
                    #    except IOError:
                    #        errors["image"] = self._("Image format not recognized")
                    #    else:
                    #        image = image.convert("RGBA")
                    image_info["order"] = floatz(req.param("order"))
                    image_info["sex0"] = True if req.param("sex0") else False
                    image_info["sex1"] = True if req.param("sex1") else False
                    if len(errors):
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # storing images
                    delete_images = []
                    for dim in dimensions:
                        size = "%dx%d" % (dim["width"], dim["height"])
                        try:
                            image, ext, content_type, form, trans = dim_images[size]
                        except KeyError:
                            pass
                        else:
                            w, h = image.size
                            if h != dim["height"]:
                                w = w * dim["height"] / h
                                h = dim["height"]
                            if w < dim["width"]:
                                h = h * dim["width"] / w
                                w = dim["width"]
                            left = (w - dim["width"]) / 2
                            top = (h - dim["height"]) / 2
                            image = image.resize((w, h), Image.ANTIALIAS).crop((left, top, left + dim["width"], top + dim["height"]))
                            data = cStringIO.StringIO()
                            if form == "JPEG":
                                image.save(data, form, quality=95)
                            elif form == "GIF":
                                if trans:
                                    image.save(data, form, transparency=trans)
                                else:
                                    image.save(data, form)
                            else:
                                image.save(data, form)
                            uri = self.call("cluster.static_upload", "charimage", ext, content_type, data.getvalue())
                            key = "image-%s" % size
                            delete_images.append(image_info.get(key))
                            image_info[key] = uri
                    config = self.app().config_updater()
                    images = [ent for ent in self.layer_images(layer_uuid) if ent["id"] != image_uuid]
                    images.append(image_info)
                    images.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
                    config.set("charimages.layer-variants-%s" % layer_uuid, images)
                    config.store()
                    # deleting old images
                    for uri in delete_images:
                        if uri:
                            self.call("cluster.static_delete", uri)
                    self.call("admin.redirect", "charimages/layers/%s/images" % layer_uuid)
                fields = []
                fields.append({"name": "order", "label": self._("Sorting order"), "value": image_info.get("order")})
                fields.append({"name": "sex0", "label": self._("Male"), "type": "checkbox", "checked": image_info.get("sex0")})
                fields.append({"name": "sex1", "label": self._("Female"), "type": "checkbox", "checked": image_info.get("sex1")})
                if cmd == "new":
                    fields.append({"name": "image", "type": "fileuploadfield", "label": self._("Image")})
                else:
                    fields.append({"name": "replace", "type": "combo", "label": self._("Replace images"), "values": [(0, self._("Replace nothing")), (1, self._("Replace all images")), (2, self._("Replace specific images"))], "value": 0})
                    fields.append({"name": "image", "type": "fileuploadfield", "label": self._("Image"), "condition": "[replace]==1"})
                    for dim in dimensions:
                        fields.append({"name": "image_%dx%d" % (dim["width"], dim["height"]), "type": "fileuploadfield", "label": self._("charimage///Image {width}x{height}").format(width=dim["width"], height=dim["height"]), "condition": "[replace]==2"})
                    for dim in dimensions:
                        size = "%dx%d" % (dim["width"], dim["height"])
                        key = "image-%s" % size
                        uri = image_info.get(key)
                        if uri:
                            fields.append({"type": "html", "html": '<h1>%s</h1><img src="%s" alt="" />' % (size, uri)})
                self.call("admin.form", fields=fields, modules=["FileUploadField"])
            rows = []
            for ent in self.layer_images(layer_uuid):
                img = None
                for dim in dimensions:
                    size = "%dx%d" % (dim["width"], dim["height"])
                    key = "image-%s" % size
                    img = ent.get(key)
                    if img:
                        img = '<img src="%s" alt="" />' % img
                        break
                sex = []
                if ent.get("sex0"):
                    sex.append(self._("male///M"))
                if ent.get("sex1"):
                    sex.append(self._("female///F"))
                row = [img, ', '.join(sex)]
                for dim in dimensions:
                    row.append('<img src="/st-mg/img/%s.gif" alt="" />' % ("done" if ent.get("image-%dx%d" % (dim["width"], dim["height"])) else "no"))
                row.extend([
                    ent["order"],
                    '<hook:admin.link href="charimages/layers/%s/images/%s" title="%s" />' % (layer_uuid, ent["id"], self._("edit")),
                    '<hook:admin.link href="charimages/layers/%s/images/del/%s" title="%s" confirm="%s" />' % (layer_uuid, ent["id"], self._("delete"), self._("Are you sure want to delete this image?")),
                ])
                rows.append(row)
            header = [
                self._("Image"),
                self._("Sex"),
            ]
            for dim in dimensions:
                header.append("%dx%d" % (dim["width"], dim["height"]))
            header.extend([
                self._("Sort order"),
                self._("Editing"),
                self._("Deletion"),
            ])
            vars = {
                "tables": [
                    {
                        "links": [
                            {"hook": "charimages/layers/%s/images/new" % layer_uuid, "text": self._("New image"), "lst": True},
                        ],
                        "header": header,
                        "rows": rows
                    }
                ]
            }
            self.call("admin.response_template", "admin/common/tables.html", vars)
        rows = []
        for layer in self.layers():
            rows.append([
                htmlescape(layer["name"]),
                layer["order"],
                '<hook:admin.link href="charimages/layers/%s/images" title="%s" />' % (layer["id"], self._("images")),
                '<hook:admin.link href="charimages/layers/%s" title="%s" />' % (layer["id"], self._("edit")),
                '<hook:admin.link href="charimages/layers/del/%s" title="%s" confirm="%s" />' % (layer["id"], self._("delete"), self._("charimages///Are you sure want to delete this layer?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "charimages/layers/new", "text": self._("New layer"), "lst": True},
                    ],
                    "header": [
                        self._("Layer name"),
                        self._("Sort order"),
                        self._("Images"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
