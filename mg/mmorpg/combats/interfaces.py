from mg.constructor import *
import re

re_del = re.compile(r'^del/([a-z0-9_]+)$', re.IGNORECASE)
re_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile)$', re.IGNORECASE)
re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)

class Combats(ConstructorModule):
    def child_modules(self):
        return [
            "mg.mmorpg.combats.interfaces.CombatsAdmin",
            "mg.mmorpg.combats.wizards.AttackBlock",
        ]

class CombatsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-combats.index", self.menu_combats_index)
        self.rhook("ext-admin-combats.rules", self.admin_rules, priv="combats.rules")
        self.rhook("headmenu-admin-combats.rules", self.headmenu_rules)
        self.rhook("ext-admin-combats.config", self.admin_config, priv="combats.config")
        self.rhook("headmenu-admin-combats.config", self.headmenu_config)

    def menu_root_index(self, menu):
        menu.append({"id": "combats.index", "text": self._("Combats"), "order": 24})

    def menu_combats_index(self, menu):
        req = self.req()
        if req.has_access("combats.config"):
            menu.append({"id": "combats/rules", "text": self._("Combats rules"), "order": 1, "leaf": True})
            menu.append({"id": "combats/config", "text": self._("Combats configuration"), "order": 2, "leaf": True})

    def permissions_list(self, perms):
        perms.append({"id": "combats.rules", "name": self._("Combats rules editor")})
        perms.append({"id": "combats.config", "name": self._("Combats configuration")})

    def headmenu_config(self, args):
        return self._("Combats configuration")

    def admin_config(self):
        self.call("admin.response", "TODO", {})

    def headmenu_rules(self, args):
        if args == "new":
            return [self._("New rules"), "combats/rules"]
        elif args:
            m = re_edit.match(args)
            if m:
                code, action = m.group(1, 2)
                rules = self.conf("combats.rules", {})
                info = rules.get(code)
                if info:
                    if action == "profile":
                        return [self._("Profile of '%s'") % htmlescape(info["name"]), "combats/rules"]
        return self._("Combats rules")

    def admin_rules(self):
        req = self.req()
        rules = self.conf("combats.rules", {})
        if req.args == "new":
            return self.rules_new()
        elif req.args:
            # deletion
            m = re_del.match(req.args)
            if m:
                code = m.group(1)
                if code in rules:
                    del rules[code]
                    self.app().config.delete_group("combats-%s" % code)
                    config = self.app().config_updater()
                    config.set("combats.rules", rules)
                    config.store()
                self.call("admin.redirect", "combats/rules")
            # editing
            m = re_edit.match(req.args)
            if m:
                code, action = m.group(1, 2)
                if code in rules:
                    return self.rules_edit(rules, code, action)
                self.call("admin.redirect", "combats/rules")
            # not found
            self.call("web.not_found")
        rules = rules.items()
        rows = []
        rules.sort(cmp=lambda x, y: cmp(x[1]["order"], y[1]["order"]) or cmp(x[0], y[0]))
        for code, info in rules:
            rows.append([
                code,
                htmlescape(info["name"]),
                info["order"],
                u'<br />'.join([
                    u'<hook:admin.link href="combats/rules/edit/%s/profile" title="%s" />' % (code, self._("profile")),
                ]),
                u'<hook:admin.link href="combats/rules/del/%s" title="%s" confirm="%s" />' % (code, self._("delete"), self._("Are you sure want to delete these rules?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "combats/rules/new",
                            "text": self._("New combats rules"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Code"),
                        self._("Rules name"),
                        self._("Order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def rules_new(self):
        req = self.req()
        # loading list of combat types
        combat_types = []
        self.call("admin-combats.types", combat_types)
        combat_types.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x.get("name"), y.get("name")))
        combat_types_dict = dict([(tp.get("id"), tp) for tp in combat_types])
        combat_types = [(tp.get("id"), tp.get("name")) for tp in combat_types]
        combat_types.insert(0, (None, None))
        # processing request
        if req.ok():
            errors = {}
            # tp
            tp = req.param("v_tp")
            if not tp:
                errors["v_tp"] = self._("This field is mandatory")
            else:
                type_info = combat_types_dict.get(tp)
                if not type_info:
                    errors["v_tp"] = self._("Make a valid selection")
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # running dialog
            dialog = type_info["dialog"](self.app())
            dialog.show()
        # rendering form
        fields = [
            {"name": "tp", "type": "combo", "label": self._("Type of combat system"), "values": combat_types},
        ]
        buttons = [
            {"text": self._("Generate combat system")},
        ]
        self.call("admin.form", fields=fields, buttons=buttons)

    def rules_edit(self, rules, code, action):
        req = self.req()
        rules = rules.copy()
        info = rules[code].copy()
        if action == "profile":
            # processing request
            if req.ok():
                errors = {}
                # name
                name = req.param("name")
                if not name:
                    errors["name"] = self._("This field is mandatory")
                # order
                order = floatz(req.param("order"))
                # saving changes
                info["order"] = order
                info["name"] = name
                rules[code] = info
                config = self.app().config_updater()
                config.set("combats.rules", rules)
                config.store()
                self.call("admin.redirect", "combats/rules")
            # rendering form
            fields = [
                {"name": "name", "label": self._("Combat rules name"), "value": info["name"]},
                {"name": "order", "label": self._("Sorting order"), "value": info["order"], "inline": True},
            ]
            self.call("admin.form", fields=fields)
