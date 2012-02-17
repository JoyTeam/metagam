from mg.constructor import *
import re

max_slot_id = 100
re_del = re.compile(r'^del/(\d+)$')
re_parse_dimensions = re.compile(r'^(\d+)x(\d+)$')
re_slot_token = re.compile(r'^slot-(\d+):(-?\d+),(-?\d+),(\d+),(\d+)$')
re_charimage_token = re.compile(r'^charimage:(-?\d+),(-?\d+),(\d+),(\d+)$')
re_staticimage_token = re.compile(r'^staticimage-([a-f0-9]{32})\((//.+)\):(-?\d+),(-?\d+),(\d+),(\d+)$')

class EquipAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-inventory.index", self.menu_inventory_index)
        self.rhook("menu-admin-equip.index", self.menu_equip_index)
        self.rhook("headmenu-admin-equip.slots", self.headmenu_slots)
        self.rhook("ext-admin-equip.slots", self.admin_slots, priv="equip.config")
        self.rhook("admin-item-types.form-render", self.item_type_form_render)
        self.rhook("admin-item-types.form-validate", self.item_type_form_validate)
        self.rhook("admin-item-types.dimensions", self.item_type_dimensions)
        self.rhook("headmenu-admin-equip.layout", self.headmenu_layout)
        self.rhook("ext-admin-equip.layout", self.admin_layout, priv="equip.config")
        self.rhook("admin-storage.group-names", self.group_names)
        self.rhook("admin-storage.nondeletable", self.nondeletable)

    def nondeletable(self, uuids):
        interfaces = self.call("equip.interfaces")
        for iface in interfaces:
            layout = self.conf("equip.layout-%s" % iface["id"])
            if layout:
                images = layout.get("images")
                if images:
                    for img in images:
                        uuids.add(img["uuid"])

    def group_names(self, group_names):
        group_names["equip-layout"] = self._("Equipment layout")

    def permissions_list(self, perms):
        perms.append({"id": "equip.config", "name": self._("Characters equipment configuration")})

    def menu_inventory_index(self, menu):
        menu.append({"id": "equip.index", "text": self._("Equipment"), "order": 50})

    def menu_equip_index(self, menu):
        req = self.req()
        if req.has_access("equip.config"):
            menu.append({"id": "equip/slots", "text": self._("Equipment slots"), "order": 0, "leaf": True})
            menu.append({"id": "equip/layout", "text": self._("Equipment layouts"), "order": 10, "leaf": True})

    def headmenu_slots(self, args):
        if args == "new":
            return [self._("New slot"), "equip/slots"]
        elif valid_nonnegative_int(args):
            return [self._("Slot %s") % args, "equip/slots"]
        return self._("Equipment slots")

    def admin_slots(self):
        req = self.req()
        slots = self.call("equip.slots")
        interfaces = self.call("equip.interfaces")
        # deletion
        m = re_del.match(req.args)
        if m:
            sid = intz(m.group(1))
            slots = [slot for slot in slots if slot["id"] != sid]
            config = self.app().config_updater()
            config.set("equip.slots", slots)
            config.store()
            self.call("admin.redirect", "equip/slots")
        # editing
        if req.args:
            if req.args == "new":
                sid = self.conf("equip.max-slot", 0) + 1
                if sid > max_slot_id:
                    sid = None
                order = None
                for s in slots:
                    if order is None or s["order"] > order:
                        order = s["order"]
                order = 0.0 if order is None else order + 10.0
                slot = {
                    "id": sid,
                    "order": order,
                }
            else:
                sid = intz(req.args)
                slot = None
                for s in slots:
                    if s["id"] == sid:
                        slot = s
                        break
                if not slot:
                    self.call("admin.redirect", "equip/slots")
            if req.ok():
                slot = slot.copy()
                errors = {}
                # id
                sid = req.param("id").strip()
                if not sid:
                    errors["id"] = self._("This field is mandatory")
                elif not valid_nonnegative_int(sid):
                    errors["id"] = self._("Slot ID must be a nonnegative integer in range 1-%d") % max_slot_id
                else:
                    sid = intz(sid)
                    if sid < 1:
                        errors["id"] = self._("Minimal value is %d") % 1
                    elif sid > max_slot_id:
                        errors["id"] = self._("Maximal value is %d") % max_slot_id
                    elif sid != slot["id"]:
                        for s in slots:
                            if s["id"] == sid:
                                errors["id"] = self._("Slot with this ID already exists")
                # order
                slot["order"] = floatz(req.param("order"))
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    slot["name"] = name
                # description
                description = req.param("description").strip()
                if not description:
                    errors["description"] = self._("This field is mandatory")
                else:
                    slot["description"] = description
                # interfaces
                for iface in interfaces:
                    key = "iface-%s" % iface["id"]
                    if req.param(key):
                        slot[key] = True
                        key_size = "ifsize-%s" % iface["id"]
                        dim = req.param(key_size).strip()
                        m = re_parse_dimensions.match(dim)
                        if not m:
                            errors[key_size] = self._("Invalid dimensions format")
                        else:
                            width, height = m.group(1, 2)
                            width = int(width)
                            height = int(height)
                            if width < 16 or height < 16:
                                errors[key_size] = self._("Minimal size is 16x16")
                            elif width > 128 or height > 128:
                                errors[key_size] = self._("Maximal size is 128x128")
                            else:
                                slot[key_size] = [width, height]
                    else:
                        slot[key] = False
                # handling errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # storing
                slots = [s for s in slots if s["id"] != slot["id"]]
                slot["id"] = sid
                slots.append(slot)
                slots.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
                config = self.app().config_updater()
                if sid > self.conf("equip.max-slot", 0):
                    config.set("equip.max-slot", sid)
                config.set("equip.slots", slots)
                config.store()
                self.call("admin.redirect", "equip/slots")
            fields = [
                {"label": self._("Slot ID (integer number)"), "name": "id", "value": slot.get("id")},
                {"label": self._("Sorting order"), "name": "order", "value": slot.get("order"), "inline": True},
                {"label": self._("Slot name"), "name": "name", "value": slot.get("name")},
                {"label": self._("Description (ex: Slot for summoning scrolls)"), "name": "description", "value": slot.get("description")},
                {"type": "header", "html": self._("slot///Visibility in the interfaces")},
            ]
            for iface in interfaces:
                key = "iface-%s" % iface["id"]
                fields.append({"name": key, "label": iface["title"], "type": "checkbox", "checked": slot.get(key)})
                key_size = "ifsize-%s" % iface["id"]
                size = slot.get(key_size, [60, 60])
                fields.append({"name": key_size, "label": self._("Slot dimensions (ex: 60x60)"), "value": "%dx%d" % (size[0], size[1]), "condition": "[%s]" % key, "inline": True})
            self.call("admin.form", fields=fields)
        rows = []
        for slot in slots:
            rows.append([
                htmlescape(slot["id"]),
                htmlescape(slot["name"]),
                u'<hook:admin.link href="equip/slots/%s" title="%s" />' % (slot["id"], self._("edit")),
                u'<hook:admin.link href="equip/slots/del/%s" title="%s" confirm="%s" />' % (slot["id"], self._("delete"), self._("Are you sure want to delete this slot?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "equip/slots/new", "text": self._("New slot"), "lst": True},
                    ],
                    "header": [
                        self._("Slot ID"),
                        self._("Slot name"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def item_type_form_render(self, obj, fields):
        pos = len(fields)
        for i in xrange(0, len(fields)):
            if fields[i].get("mark") == "categories":
                pos = i
                break
        fields.insert(pos, {"type": "header", "html": self._("Equipment")})
        pos += 1
        fields.insert(pos, {"type": "checkbox", "label": self._("This item is wearable"), "name": "equip", "checked": obj.get("equip")})
        pos += 1
        # checkboxes
        slots = self.call("equip.slots")
        col = 0
        cols = 3
        while col < len(slots):
            slot = slots[col]
            key = "equip-%s" % slot["id"]
            fields.insert(pos, {"name": key, "type": "checkbox", "label": slot["name"], "checked": obj.get(key), "inline": col % cols, "condition": "[equip]"})
            pos += 1
            col += 1
        while col % cols:
            fields.insert(pos, {"type": "empty", "inline": True})
            pos += 1
            col += 1

    def item_type_form_validate(self, obj, errors):
        req = self.req()
        if req.param("equip"):
            obj.set("equip", True)
            for slot in self.call("equip.slots"):
                key = "equip-%s" % slot["id"]
                if req.param(key):
                    obj.set(key, True)
                else:
                    obj.delkey(key)
        else:
            obj.delkey("equip")

    def item_type_dimensions(self, obj, dimensions):
        if obj.get("equip"):
            existing = set(["%dx%d" % (d["width"], d["height"]) for d in dimensions])
            for slot in self.call("equip.slots"):
                key = "equip-%s" % slot["id"]
                if obj.get(key):
                    for iface in self.call("equip.interfaces"):
                        key_size = "ifsize-%s" % iface["id"]
                        dim = slot.get(key_size) or [60, 60]
                        key_size = "%dx%d" % (dim[0], dim[1])
                        if not key_size in existing:
                            existing.add(key_size)
                            dimensions.append({"width": dim[0], "height": dim[1]})

    def headmenu_layout(self, args):
        if args:
            for iface in self.call("equip.interfaces"):
                if iface["id"] == args:
                    return [iface["title"], "equip/layout"]
        return self._("Equipment layouts")

    def admin_layout(self):
        req = self.req()
        if req.args:
            iface = None
            for i in self.call("equip.interfaces"):
                if i["id"] == req.args:
                    iface = i
                    break
            if not iface:
                self.call("admin.redirect", "equip/layout")
            slots = self.call("equip.slots")
            if req.ok():
                layout = {}
                min_x = None
                min_y = None
                max_x = None
                max_y = None
                errors = {}
                error = None
                # grid
                if req.param("grid"):
                    grid_size = req.param("grid_size")
                    if valid_nonnegative_int(grid_size):
                        grid_size = int(grid_size)
                        if grid_size <= 1:
                            layout["grid"] = 1
                        elif grid_size > 50:
                            layout["grid"] = 50
                        else:
                            layout["grid"] = grid_size
                else:
                    layout["grid"] = 0
                # slot_border
                slot_border = intz(req.param("slot_border"))
                if slot_border < 0:
                    slot_border = 0
                elif slot_border > 50:
                    slot_border = 50
                layout["slot-border"] = slot_border
                # charimage_border
                charimage_border = intz(req.param("charimage_border"))
                if charimage_border < 0:
                    charimage_border = 0
                elif charimage_border > 50:
                    charimage_border = 50
                layout["charimage-border"] = charimage_border
                # coords
                images = []
                for token in req.param("coords").split(";"):
                    m = re_slot_token.match(token)
                    if m:
                        slot_id, x, y, width, height = m.group(1, 2, 3, 4, 5)
                        x = int(x)
                        y = int(y)
                        width = int(width)
                        height = int(height)
                        layout["slot-%s-x" % slot_id] = x
                        layout["slot-%s-y" % slot_id] = y
                        min_x = min2(x, min_x)
                        min_y = min2(y, min_y)
                        max_x = max2(x + width, max_x)
                        max_y = max2(y + height, max_y)
                        continue
                    m = re_charimage_token.match(token)
                    if m:
                        x, y, width, height = m.group(1, 2, 3, 4)
                        x = int(x)
                        y = int(y)
                        width = int(width)
                        height = int(height)
                        layout["char-x"] = x
                        layout["char-y"] = y
                        min_x = min2(x, min_x)
                        min_y = min2(y, min_y)
                        max_x = max2(x + width, max_x)
                        max_y = max2(y + height, max_y)
                        continue
                    m = re_staticimage_token.match(token)
                    if m:
                        uuid, uri, x, y, width, height = m.group(1, 2, 3, 4, 5, 6)
                        x = int(x)
                        y = int(y)
                        width = int(width)
                        height = int(height)
                        images.append({
                            "uuid": uuid,
                            "uri": uri,
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                        })
                        min_x = min2(x, min_x)
                        min_y = min2(y, min_y)
                        max_x = max2(x + width, max_x)
                        max_y = max2(y + height, max_y)
                        continue
                    error = self._("Unknown token: %s" % htmlescape(token))
                if error:
                    self.call("web.response_json", {"success": False, "error": error})
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # storing
                if images:
                    layout["images"] = images
                if min_x is not None:
                    layout["min_x"] = min_x
                    layout["min_y"] = min_y
                    layout["width"] = max_x - min_x
                    layout["height"] = max_y - min_y
                config = self.app().config_updater()
                config.set("equip.layout-%s" % iface["id"], layout)
                config.store()
                self.call("admin.redirect", "equip/layout")
            layout = self.conf("equip.layout-%s" % iface["id"], {})
            vars = {
                "ie_warning": self._("Warning! Internet Explorer browser is not supported. Equipment layout editor may work slowly and unstable. Mozilla Firefox, Google Chrome and Opera are fully supported"),
                "submit_url": "/admin-equip/layout/%s" % iface["id"],
                "grid_size": layout.get("grid", iface["grid"]),
                "slot_border": layout.get("slot-border", 1),
                "charimage_border": layout.get("charimage-border", 0),
            }
            if not self.conf("module.storage"):
                vars["storage_unavailable"] = jsencode(self._("To access this function you need to enable 'Static Storage' system module"))
            elif not req.has_access("storage.static"):
                vars["storage_unavailable"] = jsencode(self._("You don't have permission to upload objects to the static storage"))
            # slots
            rslots = []
            for slot in slots:
                if slot.get("iface-%s" % iface["id"]):
                    dim = slot.get("ifsize-%s" % iface["id"]) or [60, 60]
                    rslots.append({
                        "id": slot["id"],
                        "name": jsencode(slot["name"]),
                        "x": layout.get("slot-%d-x" % slot["id"], 0),
                        "y": layout.get("slot-%d-y" % slot["id"], 0),
                        "width": dim[0],
                        "height": dim[1],
                    })
            vars["slots"] = rslots;
            # character image
            dim = self.call(iface["dim_hook"])
            if dim:
                m = re_parse_dimensions.match(dim)
                if m:
                    width, height = m.group(1, 2)
                    width = int(width)
                    height = int(height)
                    vars["charimage"] = {
                        "x": layout.get("char-x", 0),
                        "y": layout.get("char-y", 0),
                        "width": width,
                        "height": height,
                    }
            # static images
            images = layout.get("images")
            if images:
                rimages = []
                for img in images:
                    rimages.append({
                        "uuid": img["uuid"],
                        "uri": jsencode(img["uri"]),
                        "x": img["x"],
                        "y": img["y"],
                        "width": img["width"],
                        "height": img["height"],
                    })
                vars["staticimages"] = rimages
            # rendering
            self.call("admin.response_template", "admin/equip/layout.html", vars)
        rows = []
        interfaces = self.call("equip.interfaces")
        for iface in interfaces:
            rows.append([u'<hook:admin.link href="equip/layout/%s" title="%s" />' % (iface["id"], iface["title"])])
        vars = {
            "tables": [
                {
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

def min2(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a < b:
        return a
    else:
        return b

def max2(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a > b:
        return a
    else:
        return b

class Equip(ConstructorModule):
    def register(self):
        self.rhook("equip.slots", self.slots)
        self.rhook("equip.interfaces", self.interfaces)
        self.rhook("character-page.render", self.character_page_render)

    def child_modules(self):
        return ["mg.mmorpg.equip.EquipAdmin"]

    def slots(self):
        return self.conf("equip.slots", [])

    def interfaces(self):
        interfaces = [
            {
                "id": "char-owner",
                "title": self._("Internal game interface for character owner"),
                "dim_hook": "charimages.dim-charpage",
                "grid": 5,
            },
            {
                "id": "char-public",
                "title": self._("Public character info"),
                "dim_hook": "charimages.dim-charinfo",
                "grid": 10,
            },
        ]
        return interfaces

    def character_page_render(self, character, vars):
        self.render_layout("char-owner", character, vars)

    def render_layout(self, iface_id, character, vars):
        for iface in self.interfaces():
            if iface["id"] == iface_id:
                layout = self.conf("equip.layout-%s" % iface_id)
                if layout:
                    slot_border = layout.get("slot-border", 1)
                    charimage_border = layout.get("charimage-border", 0)
                    border = max(slot_border, charimage_border)
                    offset_x = border
                    offset_y = border
                    items = []
                    # static images
                    images = layout.get("images")
                    if images:
                        for image in images:
                            items.append({
                                "x": image["x"] + offset_x,
                                "y": image["y"] + offset_y,
                                "width": image["width"],
                                "height": image["height"],
                                "cls": "equip-static-image",
                                "border": 0,
                                "image": {
                                    "src": image["uri"],
                                },
                            })
                    # characer image
                    dim = self.call(iface["dim_hook"])
                    if dim:
                        m = re_parse_dimensions.match(dim)
                        if m:
                            width, height = m.group(1, 2)
                            width = int(width)
                            height = int(height)
                            items.append({
                                "x": layout.get("char-x", 0) + offset_x,
                                "y": layout.get("char-y", 0) + offset_y,
                                "width": width,
                                "height": height,
                                "cls": "equip-char-image",
                                "border": charimage_border,
                                "image": {
                                    "src": vars["avatar_image"],
                                },
                            })
                    # slots
                    for slot in self.slots():
                        if slot.get("iface-%s" % iface_id):
                            size = slot.get("ifsize-%s" % iface_id)
                            items.append({
                                "x": layout.get("slot-%s-x" % slot["id"], 0) + offset_x,
                                "y": layout.get("slot-%s-y" % slot["id"], 0) + offset_y,
                                "width": size[0],
                                "height": size[1],
                                "cls": "equip-slot",
                                "border": slot_border,
                            })
                    cur_y = 0
                    for item in items:
                        item["x"] = item["x"] - layout["min_x"] - item["border"]
                        item["y"] = item["y"] - layout["min_y"] - cur_y - item["border"]
                        cur_y += item["height"] + item["border"] * 2
                    rlayout = {
                        "width": layout["width"] + border * 2,
                        "height": layout["height"] + border * 2,
                        "items": items,
                    }
                    vars["equip_layout"] = rlayout

