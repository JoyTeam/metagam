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
from mg.constructor import *
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageFilter
from uuid import uuid4
import re
import cStringIO

re_del = re.compile(r'^del/(\S+)$')
re_invalid_code = re.compile(r'([^\w0-9\-:\+#@\$%\^\&\*\(\)!;])', re.UNICODE)
re_escape_symbols = re.compile(r'([\+\$\^\&\*\(\)\?])')

class Smiles(Module):
    def register(self):
        self._re_find = None
        self._smiles = None
        self.rhook("chat.parse", self.chat_parse)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("smiles.form", self.smiles_form)
        self.rhook("smiles.dict", self.smiles_dict)
        self.rhook("smiles.split", self.smiles_split)

    @property
    def smiles(self):
        if self._smiles:
            return self._smiles
        smiles = self.app().config.get_group("smile").values()
        self._smiles = dict([(info["code"], info) for info in smiles])
        return self._smiles

    @property
    def re_find(self):
        if self._re_find:
            return self._re_find
        smiles = [self.escape(code) for code in self.smiles.keys()]
        # if no smiles present, generate any never matching pattern
        regexp = '(%s)' % ("|".join(smiles) if len(smiles) else uuid4().hex)
        self._re_find = re.compile(regexp)
        return self._re_find

    def escape(self, code):
        return re_escape_symbols.sub(r'\\\1', code)

    def chat_parse(self, tokens):
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.get("text"):
                lst = self.re_find.split(token["text"])
                if len(lst) > 1:
                    # inserting new tokens before the token being parsed
                    for ent in lst:
                        info = self.smiles.get(ent)
                        if info:
                            tokens.insert(i, {"html": '<img src="%s" alt="" class="chat-smile" onclick="Smiles.add(\'%s\')" />' % (info["image"], jsencode(info["code"]))})
                            i += 1
                        elif ent != u'':
                            tokens.insert(i, {"text": ent})
                            i += 1
                    # removing parsed token
                    del tokens[i]
                    i -= 1
            i += 1

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "roster-smiles",
            "onclick": "Smiles.show()",
            "icon": "roster-smiles.png",
            "title": self._("Show smiles"),
            "block": "roster-buttons-menu",
            "order": 5,
        })

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("chat-smiles")
        smiles = self.app().config.get_group("smile").values()
        smiles.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["code"], y["code"]))
        smiles = ", ".join(["{code: '%s', image: '%s'}" % (jsencode(smile["code"]), smile["image"]) for smile in smiles])
        vars["js_init"].append("Smiles.smiles = [%s];" % smiles)

    def smiles_form(self):
        smiles = self.app().config.get_group("smile").items()
        if not smiles:
            return None
        smiles.sort(cmp=lambda x, y: cmp(x[1]["order"], y[1]["order"]) or cmp(x[1]["code"], y[1]["code"]))
        smiles = [{"id": uuid, "code": jsencode(info["code"]), "image": info["image"]} for uuid, info in smiles]
        return [
            {
                "id": "all",
                "name": self._("Smiles"),
                "smiles": smiles
            }
        ]

    def smiles_dict(self):
        return self.smiles

    def smiles_split(self, text):
        return self.re_find.split(text)

class SmilesAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("ext-admin-socio.smiles", self.admin_socio_smiles, priv="socio.smiles")
        self.rhook("headmenu-admin-socio.smiles", self.headmenu_socio_smiles)

    def permissions_list(self, perms):
        perms.append({"id": "socio.smiles", "name": self._("Smiles settings")})

    def menu_socio_index(self, menu):
        req = self.req()
        if req.has_access("socio.smiles"):
            menu.append({"id": "socio/smiles", "text": self._("Smiles editor"), "leaf": True, "order": 5})

    def admin_socio_smiles(self):
        req = self.req()
        m = re_del.match(req.args)
        if m:
            uuid = m.group(1)
            info = self.conf("smile.%s" % uuid)
            if info:
                config = self.app().config_updater()
                config.delete("smile.%s" % uuid)
                config.store()
                self.call("cluster.static_delete", info["image"])
            self.call("admin.redirect", "socio/smiles")
        if req.args:
            if req.args != "new":
                uuid = req.args
                info = self.conf("smile.%s" % uuid)
                if not info:
                    self.call("web.not_found")
            else:
                uuid = uuid4().hex
            if req.ok():
                self.call("web.upload_handler")
                errors = {}
                code = req.param("code")
                image = req.param_raw("image")
                order = floatz(req.param("order"))
                if not code:
                    errors["code"] = self._("Specify smile code")
                else:
                    m = re_invalid_code.search(code)
                    if m:
                        symbol = m.group(1)
                        errors["code"] = self._("Smile code contains forbidden symbol '%s'") % htmlescape(symbol)
                if req.args == "new" and not image:
                    errors["image"] = self._("Provide an image for the smile")
                if image:
                    try:
                        image_obj = Image.open(cStringIO.StringIO(image))
                        if image_obj.load() is None:
                            raise IOError
                    except IOError:
                        errors["image"] = self._("Image format not recognized")
                    except OverflowError:
                        errors["image"] = self._("Image format not recognized")
                    else:
                        if image_obj.format == "GIF":
                            ext = "gif"
                            content_type = "image/gif"
                        elif image_obj.format == "JPEG":
                            ext = "jpg"
                            content_type = "image/jpeg"
                        elif image_obj.format == "PNG":
                            ext = "png"
                            content_type = "image/png"
                        else:
                            errors["image"] = self._("Invalid image format. Supported are: gif, jpg, png")
                if len(errors):
                    self.call("web.response_json_html", {"success": False, "errors": errors})
                if image:
                    uri = self.call("cluster.static_upload", "smiles", ext, content_type, image)
                else:
                    uri = info["image"]
                config = self.app().config_updater()
                config.set("smile.%s" % uuid, {
                    "code": code,
                    "image": uri,
                    "order": order,
                })
                config.store()
                if req.args != "new" and image:
                    self.call("cluster.static_delete", info["image"])
                self.call("web.response_json_html", {"success": True, "redirect": "socio/smiles"})
            else:
                if req.args == "new":
                    code = ""
                    order = 0
                    smiles = self.app().config.get_group("smile")
                    for uuid, info in smiles.iteritems():
                        if info["order"] >= order:
                            order = info["order"] + 10
                else:
                    code = info["code"]
                    order = info["order"]
            fields = [
                {"name": "image", "type": "fileuploadfield", "label": self._("Smile image")},
                {"name": "code", "value": code, "label": self._("Smile code (this text will be replaced with image below)")},
                {"name": "order", "label": self._("Sorting order"), "value": order, "inline": True},
            ]
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
        rows = []
        smiles = self.app().config.get_group("smile")
        for uuid, info in smiles.iteritems():
            rows.append([
                htmlescape(info["code"]),
                '<img src="%s" alt="" />' % info["image"],
                info["order"],
                '<hook:admin.link href="socio/smiles/%s" title="%s" />' % (uuid, self._("edit")),
                '<hook:admin.link href="socio/smiles/del/%s" title="%s" confirm="%s" />' % (uuid, self._("delete"), self._("Are you sure want to delete this smile?")),
            ])
        rows.sort(cmp=lambda x, y: cmp(x[2], y[2]) or cmp(x[0], y[0]))
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "socio/smiles/new",
                            "text": self._("New smile"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Code"),
                        self._("Image"),
                        self._("Order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_socio_smiles(self, args):
        if args == "new":
            return [self._("New smile"), "socio/smiles"]
        elif args:
            return [self._("Smile editor"), "socio/smiles"]
        return self._("Smiles")

