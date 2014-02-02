#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

from mg import *
from PIL import Image
import cStringIO
from struct import pack

class SiteAdmin(Module):
    def register(self):
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-site.robots", self.robots, priv="site.robots")
        self.rhook("menu-admin-site.index", self.menu_site)

    def menu_root_index(self, menu):
        menu.append({"id": "site.index", "text": self._("Site"), "order": 30})

    def permissions_list(self, perms):
        perms.append({"id": "site.robots", "name": self._("Robots.txt administration")})

    def menu_site(self, menu):
        req = self.req()
        if req.has_access("site.robots"):
            menu.append({"id": "site/robots", "text": "robots.txt", "leaf": True, "order": 10})

    def robots(self):
        req = self.req()
        indexing = True if req.param("indexing") else False
        if req.ok():
            config = self.app().config_updater()
            config.set("indexing.enabled", indexing)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            indexing = self.conf("indexing.enabled", True)
        fields = [
            {"name": "indexing", "type": "checkbox", "label": self._("Allow web search engines index this site"), "checked": indexing},
        ]
        self.call("admin.form", fields=fields)

class Counters(Module):
    def register(self):
        self.rhook("web.setup_design", self.web_setup_design)

    def web_setup_design(self, vars):
        if not vars.get("counters_processed"):
            vars["counters_processed"] = True
            vars["counters"] = utf2str(vars.get("counters", "")) + utf2str(self.conf("counters.html", ""))
            vars["head"] = utf2str(vars.get("head", "")) + utf2str(self.conf("counters.head", ""))

class CountersAdmin(Module):
    def register(self):
        self.rhook("menu-admin-site.index", self.menu_site)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-site.counters", self.counters, priv="site.counters")

    def permissions_list(self, perms):
        perms.append({"id": "site.counters", "name": self._("Counters administration")})

    def menu_site(self, menu):
        req = self.req()
        if req.has_access("site.counters"):
            menu.append({"id": "site/counters", "text": self._("Counters"), "leaf": True})

    def counters(self):
        req = self.req()
        self.call("admin.advice", {"title": self._("Installing trackers"), "content": self._("You can setup any number of counters on your pages. To do it register in the counting or tracking services and paste the tracking code into this form. The first input field will be put in the [%counters%] template variable and displayed in the counters panel. The second input field will be placed in the &lt;head&gt; section of the HTML document. Google analytics code is placed in the second field.")})
        html = req.param("html")
        head = req.param("head")
        if req.ok():
            config = self.app().config_updater()
            config.set("counters.html", html)
            config.set("counters.head", head)
            config.store()
            self.call("admin.response", self._("Counters stored"), {})
        else:
            html = self.conf("counters.html")
            head = self.conf("counters.head")
        fields = [
            {"name": "html", "type": "textarea", "label": self._("Counters HTML code"), "value": html},
            {"name": "head", "type": "textarea", "label": self._("Tracking code (before the end of 'head')"), "value": head},
        ]
        self.call("admin.form", fields=fields)

class Favicon(Module):
    def register(self):
        self.rhook("ext-favicon.ico.index", self.favicon, priv="public")

    def child_modules(self):
        return ["mg.core.sites.FaviconAdmin"]

    def favicon(self):
        uri = self.conf("favicon.main")
        if not uri:
            self.call("web.not_found")
        try:
            data = self.download(uri)
        except DownloadError:
            self.call("web.internal_server_error")
        req = self.req()
        req.content_type = str(self.conf("favicon.main_mime_type"))
        self.call("web.response", data)

class FaviconAdmin(Module):
    def register(self):
        self.rhook("menu-admin-site.index", self.menu_site)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-site.favicon", self.headmenu_favicon)
        self.rhook("ext-admin-site.favicon", self.admin_favicon, priv="site.favicon")
        self.rhook("advice-admin-site.favicon", self.advice_favicon)

    def permissions_list(self, perms):
        perms.append({"id": "site.favicon", "name": self._("Favicon settings")})

    def menu_site(self, menu):
        req = self.req()
        if req.has_access("site.favicon"):
            menu.append({"id": "site/favicon", "text": self._("Favicon"), "leaf": True})

    def headmenu_favicon(self, args):
        if args == "set":
            return [self._("Replacing"), "site/favicon"]
        return self._("Favicon")

    def advice_favicon(self, args, advice):
        advice.append({"title": self._("Favicon documentation"), "content": self._('You can find detailed information on the favicon icons in the <a href="//www.%s/doc/favicon" target="_blank">favicons page</a> in the reference manual.') % self.main_host})

    def admin_favicon(self):
        req = self.req()
        if req.args == "del":
            uri = self.conf("favicon.main")
            if uri:
                config = self.app().config_updater()
                config.delete("favicon.main")
                config.delete("favicon.main_mime_type")
                config.store()
                self.call("cluster.static_delete", uri)
            self.call("admin.redirect", "site/favicon")
        elif req.args == "set":
            if req.ok():
                self.call("web.upload_handler")
                errors = {}
                # image
                image = req.param_raw("image")
                if image is None or not len(image):
                    errors["image"] = self._("Upload an icon")
                else:
                    try:
                        image_obj = Image.open(cStringIO.StringIO(image))
                        if image_obj.load() is None:
                            raise IOError
                    except IOError:
                        errors["image"] = self._("Image format not recognized")
                    else:
                        try:
                            image_obj.seek(1)
                        except EOFError:
                            animated = False
                        else:
                            animated = True
                        image_obj = image_obj.convert("RGBA")
                        w, h = image_obj.size
                        if w == 16 and h == 16:
                            pass
                        elif w < 16 or h < 16:
                            errors["image"] = self._("Icon size must be at least 16x16")
                        elif animated:
                            errors["image"] = self._("Animated GIF must be exactly 16x16")
                        else:
                            if w < h:
                                h = int(h * 16 / w)
                                w = 16
                            else:
                                w = int(w * 16 / h)
                                h = 16
                            image_obj.thumbnail((w, h), Image.ANTIALIAS)
                            if w > 16:
                                left = (w - 16) / 2
                                top = 0
                                image_obj = image_obj.crop((left, top, left + 16, top + 16))
                            if h > 16:
                                left = 0
                                top = (h - 16) / 2
                                image_obj = image_obj.crop((left, top, left + 16, top + 16))
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # converting
                if animated:
                    ext = "gif"
                    mime_type = "image/gif"
                else:
                    # generating ICO format
                    # semi-transparent images should be rendered over white background
                    plate = Image.new("RGB", (16, 16), (255, 255, 255))
                    plate.paste(image_obj, (0, 0), image_obj)
                    image = cStringIO.StringIO()
                    image.write("\x00\x00")             # reserved
                    image.write("\x01\x00")             # format: ICO
                    image.write("\x01\x00")             # 1 image
                    image.write("\x10\x10")             # dimensions (16x16)
                    image.write("\x00")                 # no palette
                    image.write("\x00")                 # reserved
                    image.write("\x01\x00")             # 1 color plane
                    image.write("\x18\x00")             # 24 bits per pixel
                    image.write("\x68\x03\x00\x00")     # payload size (768 + 40)
                    image.write("\x16\x00\x00\x00")     # payload offset (22)
                    # DIB header
                    image.write("\x28\x00\x00\x00")     # DIB header size (40)
                    image.write("\x10\x00\x00\x00")     # image width (16)
                    image.write("\x20\x00\x00\x00")     # image height (16) * 2?
                    image.write("\x01\x00")             # 1 color plane
                    image.write("\x18\x00")             # 24 bits per pixel
                    image.write("\x00\x00\x00\x00")     # no compression
                    image.write("\x00\x00\x00\x00")     # size of raw data
                    image.write("\x00\x00\x00\x00")     # horizontal resolution
                    image.write("\x00\x00\x00\x00")     # vertical resolution
                    image.write("\x00\x00\x00\x00")     # no palette
                    image.write("\x00\x00\x00\x00")     # all colors are important
                    # writing image data
                    rows = []
                    row = ""
                    col = 0
                    for pixel in plate.getdata():
                        row += pack("BBB", pixel[2], pixel[1], pixel[0])
                        col += 1
                        if col >= 16:
                            rows.append(row)
                            col = 0
                            row = ""
                    for row in reversed(rows):
                        image.write(row)
                    # writing transparency mask
                    rows = []
                    row = ""
                    col = 0
                    data = 0
                    for pixel in image_obj.getdata():
                        data = (data * 2) | (0 if pixel[3] >= 128 else 1)
                        col += 1
                        if (col % 8) == 0:
                            row += pack("B", data)
                            data = 0
                        if col == 16:
                            col = 0
                            row += "\x00\x00"           # row padding
                            rows.append(row)
                            row = ""
                    for row in reversed(rows):
                        image.write(row)
                    image = image.getvalue()
                    ext = "ico"
                    mime_type = "image/x-icon"
                # storing
                delete = set()
                uri = self.call("cluster.static_upload", "favicon", ext, mime_type, image)
                config = self.app().config_updater()
                old = config.get("favicon.main")
                if old:
                    delete.add(old)
                config.set("favicon.main", uri)
                config.set("favicon.main_mime_type", mime_type)
                config.store()
                for uri in delete:
                    self.call("cluster.static_delete", uri)
                self.call("admin.redirect", "site/favicon")
            fields = [
                {"name": "image", "type": "fileuploadfield", "label": self._("Upload an icon (16x16)")}
            ]
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
        icon = self.conf("favicon.main")
        rows = []
        rows.append([
            ('<img src="%s" alt="" />' % icon) if icon else self._("none"),
            u'<hook:admin.link href="site/favicon/set" title="%s" />' % (self._("replace") if icon else self._("upload")),
            (u'<hook:admin.link href="site/favicon/del" title="%s" confirm="%s" />' % (self._("delete"), self._("Are you sure want to delete this icon?"))) if icon else None,
        ])
        vars = {
            "tables": [
                {
                    "header": [self._("Current icon"), self._("Editing"), self._("Deletion")],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
