from mg.constructor import *
import re

max_slot_id = 100
re_del = re.compile(r'^del/(\d+)$')

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
        self.rhook("menu-admin-characters.index", self.menu_characters_index)
        self.rhook("headmenu-admin-equip.slots", self.headmenu_slots)
        self.rhook("ext-admin-equip.slots", self.admin_slots, priv="equip.config")

    def permissions_list(self, perms):
        perms.append({"id": "equip.config", "name": self._("Characters equipment configuration")})

    def menu_characters_index(self, menu):
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
            ]
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
