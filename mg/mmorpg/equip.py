from mg.constructor import *
import re

max_slot_id = 100
re_del = re.compile(r'^del/(\d+)$')
re_parse_dimensions = re.compile(r'^(\d+)x(\d+)$')

class Equip(ConstructorModule):
    def register(self):
        self.rhook("equip.slots", self.slots)
        self.rhook("equip.interfaces", self.interfaces)

    def child_modules(self):
        return ["mg.mmorpg.equip.EquipAdmin"]

    def slots(self):
        return self.conf("equip.slots", [])

    def interfaces(self):
        interfaces = [
            {
                "id": "char-owner",
                "title": self._("Internal game interface for character owner"),
            },
            {
                "id": "char-public",
                "title": self._("Public character info"),
            },
        ]
        return interfaces

class EquipAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-inventory.index", self.menu_inventory_index)
        self.rhook("headmenu-admin-equip.slots", self.headmenu_slots)
        self.rhook("ext-admin-equip.slots", self.admin_slots, priv="equip.config")
        self.rhook("admin-item-types.form-render", self.item_type_form_render)
        self.rhook("admin-item-types.form-validate", self.item_type_form_validate)
        self.rhook("admin-item-types.dimensions", self.item_type_dimensions)

    def permissions_list(self, perms):
        perms.append({"id": "equip.config", "name": self._("Characters equipment configuration")})

    def menu_inventory_index(self, menu):
        req = self.req()
        if req.has_access("equip.config"):
            menu.append({"id": "equip/slots", "text": self._("Equipment slots"), "order": 50, "leaf": True})

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

