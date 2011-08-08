from mg import *
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageFilter
import cStringIO

class Icons(Module):
    def register(self):
        self.rhook("icon.get", self.get)

    def get(self, icon_code, default_icon=None):
        img = self.conf("icon.%s" % icon_code)
        if img:
            return img
        if default_icon:
            return default_icon
        return "/st-mg/icons/%s.gif" % icon_code

class IconsAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-gameinterface.index", self.menu_gameinterface_index)
        self.rhook("ext-admin-icons.editor", self.admin_icons_editor, priv="icons.editor")
        self.rhook("headmenu-admin-icons.editor", self.headmenu_icons_editor)

    def permissions_list(self, perms):
        perms.append({"id": "icons.editor", "name": self._("Icons editor")})

    def menu_gameinterface_index(self, menu):
        req = self.req()
        if req.has_access("icons.editor"):
            menu.append({"id": "icons/editor", "text": self._("Icons editor"), "leaf": True, "order": 50})

    def headmenu_icons_editor(self, args):
        if args:
            return [htmlescape(args), "icons/editor"]
        return self._("Icons editor")

    def admin_icons_editor(self):
        req = self.req()
        icons = []
        self.call("admin-icons.list", icons)
        if req.args:
            icon = None
            for i in icons:
                if i["code"] == req.args:
                    icon = i
                    break
            if not icons:
                self.call("admin.redirect", "icons/editor")
            if req.ok():
                self.call("web.upload_handler")
                errors = {}
                image_data = req.param_raw("image")
                if image_data:
                    try:
                        image_obj = Image.open(cStringIO.StringIO(image_data))
                        if image_obj.load() is None:
                            raise IOError
                    except IOError:
                        errors["image"] = self._("Image format not recognized")
                    except OverflowError:
                        errors["image"] = self._("Image format not recognized")
                    else:
                        width, height = image_obj.size
                        if image_obj.format == "GIF":
                            ext = "gif"
                            content_type = "image/gif"
                        elif image_obj.format == "PNG":
                            ext = "png"
                            content_type = "image/png"
                        elif image_obj.format == "JPEG":
                            ext = "jpg"
                            content_type = "image/jpeg"
                        else:
                            errors["image"] = self._("Image format must be GIF, JPEG or PNG")
                else:
                    errors["image"] = self._("Upload an image")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                uri = self.call("cluster.static_upload", "icons", ext, content_type, image_data)
                old_image = self.conf("icon.%s" % icon["code"])
                config = self.app().config_updater()
                config.set("icon.%s" % icon["code"], uri)
                config.store()
                self.call("admin-icons.changed")
                if old_image:
                    self.call("cluster.static_delete", old_image)
                self.call("admin.redirect", "icons/editor")
            fields = [
                {"name": "image", "type": "fileuploadfield", "label": self._("Icon image")},
            ]
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
        rows = []
        for ent in icons:
            rows.append([
                ent["code"],
                ent["title"],
                '<img src="%s" alt="" />' % self.conf("icon.%s" % ent["code"], ent.get("default", "/st-mg/icons/%s.gif" % ent["code"])),
                '<hook:admin.link href="icons/editor/%s" title="%s" />' % (ent["code"], self._("edit")),
            ])
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Code"),
                        self._("Title"),
                        self._("Image"),
                        self._("Editing"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
