import mg.constructor
from mg.core.tools import *
from mg.mmorpg.combats.core import Combat, CombatMember, CombatUnavailable
from mg.mmorpg.combats.characters import CombatCharacterMember, CombatGUIController
from mg.mmorpg.combats.daemon import CombatInterface, DBRunningCombat, DBRunningCombatList
import re

re_del = re.compile(r'^del/([a-z0-9_]+)$', re.IGNORECASE)
re_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile|actions|action/.+|script)$', re.IGNORECASE)
re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_action_cmd = re.compile(r'action/(.+)', re.IGNORECASE)
re_action_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile|script)$', re.IGNORECASE)

class Combats(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-combat.interface", self.combat_interface, priv="logged")

    def child_modules(self):
        return [
            "mg.mmorpg.combats.interfaces.CombatsAdmin",
            "mg.mmorpg.combats.wizards.AttackBlock",
            "mg.mmorpg.combats.scripts.CombatScripts",
            "mg.mmorpg.combats.daemon.CombatRunner",
            "mg.mmorpg.combats.characters.Combats",
        ]

    def objclasses_list(self, objclasses):
        objclasses["RunningCombat"] = (DBRunningCombat, DBRunningCombatList)

    def combat_interface(self):
        req = self.req()
        char = self.character(req.user())
        combat_id = req.args
        try:
            combat = CombatInterface(self.app(), combat_id)
            combat.ping()
        except CombatUnavailable as e:
            with self.lock([char.busy_lock]):
                busy = char.busy
                if busy and busy["tp"] == "combat" and busy.get("combat") == combat_id:
                    # character is a member of a missing combat. free him
                    self.call("debug-channel.character", char, self._("Character is a member of missing combat (%s). Freeing lock") % e)
                    char.unset_busy()
            self.call("web.redirect", "/location")
        else:
            self.call("main-frame.info", self._("Combat %s interface") % htmlescape(combat_id))

class CombatsAdmin(mg.constructor.ConstructorModule):
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
                        return [htmlescape(info["name"]), "combats/rules"]
                    elif action == "actions":
                        return [self._("Actions of '%s'") % htmlescape(info["name"]), "combats/rules"]
                    elif action == "script":
                        return [self._("Scripts of '%s'") % htmlescape(info["name"]), "combats/rules"]
                    else:
                        m = re_action_cmd.match(action)
                        if m:
                            cmd = m.group(1)
                            if cmd == "new":
                                return [self._("New action"), "combats/rules/edit/%s/actions" % code]
                            else:
                                m = re_action_edit.match(cmd)
                                if m:
                                    action_code, cmd = m.group(1, 2)
                                    for act in self.conf("combats-%s.actions" % code, []):
                                        if act["code"] == action_code:
                                            if cmd == "profile":
                                                return [htmlescape(act["name"]), "combats/rules/edit/%s/actions" % code]
                                            elif cmd == "script":
                                                return [self._("Scripts of '%s'") % htmlescape(act["name"]), "combats/rules/edit/%s/actions" % code]
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
                    u'<hook:admin.link href="combats/rules/edit/%s/profile" title="%s" />' % (code, self._("combat system profile")),
                    u'<hook:admin.link href="combats/rules/edit/%s/script" title="%s" />' % (code, self._("script handlers")),
                    u'<hook:admin.link href="combats/rules/edit/%s/actions" title="%s" />' % (code, self._("combat actions")),
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
        if action == "profile":
            return self.rules_edit_profile(rules, code)
        elif action == "actions":
            return self.rules_edit_actions(code)
        elif action == "script":
            return self.rules_edit_script(code)
        else:
            m = re_action_cmd.match(action)
            if m:
                cmd = m.group(1)
                return self.rules_action(code, cmd)

    def rules_edit_profile(self, rules, code):
        req = self.req()
        rules = rules.copy()
        info = rules[code].copy()
        # processing request
        if req.ok():
            errors = {}
            # name
            name = req.param("name")
            if not name:
                errors["name"] = self._("This field is mandatory")
            # order
            order = floatz(req.param("order"))
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
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

    def rules_edit_actions(self, code):
        actions = self.conf("combats-%s.actions" % code, [])
        rows = []
        for act in actions:
            rows.append([
                act["code"],
                htmlescape(act["name"]),
                act["order"],
                u'<br />'.join([
                    u'<hook:admin.link href="combats/rules/edit/%s/action/edit/%s/profile" title="%s" />' % (code, act["code"], self._("combat action profile")),
                    u'<hook:admin.link href="combats/rules/edit/%s/action/edit/%s/script" title="%s" />' % (code, act["code"], self._("script handlers")),
                ]),
                u'<hook:admin.link href="combats/rules/edit/%s/action/del/%s" title="%s" confirm="%s" />' % (code, act["code"], self._("delete"), self._("Are you sure want to delete this combat action?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "combats/rules/edit/%s/action/new" % code,
                            "text": self._("New combat action"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Code"),
                        self._("Action name"),
                        self._("Order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def rules_action(self, code, cmd):
        if cmd == "new":
            return self.rules_action_edit(code, None)
        else:
            m = re_del.match(cmd)
            if m:
                action_code = m.group(1)
                actions = [act for act in self.conf("combats-%s.actions" % code, []) if act["code"] != action_code]
                config = self.app().config_updater()
                config.set("combats-%s.actions" % code, actions)
                config.store()
                self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
            m = re_action_edit.match(cmd)
            if m:
                action_code, cmd = m.group(1, 2)
                if cmd == "profile":
                    return self.rules_action_edit(code, action_code)
                elif cmd == "script":
                    return self.rules_action_script(code, action_code)

    def rules_action_edit(self, code, action_code):
        req = self.req()
        actions = [act.copy() for act in self.conf("combats-%s.actions" % code, [])]
        if action_code is None:
            info = {}
            order = None
            for act in actions:
                if order is None or act["order"] > order:
                    order = act["order"]
            if order is None:
                info["order"] = 0.0
            else:
                info["order"] = order + 10.0
        else:
            info = None
            for act in actions:
                if act["code"] == action_code:
                    info = act
                    break
            if info is None:
                self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        existing_codes = set()
        for act in actions:
            existing_codes.add(act["code"])
        # processing request
        if req.ok():
            errors = {}
            # code
            act_code = req.param("code")
            if not act_code:
                errors["code"] = self._("This field is mandatory")
            elif not re_valid_identifier.match(act_code):
                errors["code"] = self._("Action code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
            elif act_code in existing_codes and act_code != action_code:
                errors["code"] = self._("Action with the same code already exists")
            # name
            name = req.param("name")
            if not name:
                errors["name"] = self._("This field is mandatory")
            # order
            order = floatz(req.param("order"))
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # saving changes
            info["code"] = act_code
            info["name"] = name
            info["order"] = order
            if action_code is None:
                actions.append(info)
            actions.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["code"], y["code"]))
            config = self.app().config_updater()
            config.set("combats-%s.actions" % code, actions)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        # rendering form
        fields = [
            {"name": "code", "label": self._("Action code"), "value": info.get("code")},
            {"name": "order", "label": self._("Sorting order"), "value": info.get("order"), "inline": True},
            {"name": "name", "label": self._("Action name"), "value": info.get("name")},
        ]
        self.call("admin.form", fields=fields)

    def rules_edit_script(self, code):
        req = self.req()
        if req.ok():
            # test objects
            combat = Combat(self.app(), None, code)
            # parsing form
            errors = {}
            config = self.app().config_updater()
            config.set("combats-%s.script-start" % code, self.call("combats-admin.script-field", combat, "start", errors, globs={"combat": combat}, mandatory=False))
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # storing
            config.store()
            self.call("admin.redirect", "combats/rules")
        fields = [
            {"name": "start", "label": self._("Combat script running when combat starts") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-start" % code)), "height": 150},
        ]
        self.call("admin.form", fields=fields)

    def rules_action_script(self, code, action_code):
        req = self.req()
        actions = [act.copy() for act in self.conf("combats-%s.actions" % code, [])]
        info = None
        for act in actions:
            if act["code"] == action_code:
                info = act
                break
        if info is None:
            self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        if req.ok():
            # test objects
            combat = Combat(self.app(), None, code)
            member1 = CombatMember(combat)
            member2 = CombatMember(combat)
            # parsing form
            errors = {}
            info["script-before-execute"] = self.call("combats-admin.script-field", combat, "before-execute", errors, globs={"combat": combat, "source": member1}, mandatory=False)
            info["script-execute"] = self.call("combats-admin.script-field", combat, "execute", errors, globs={"combat": combat, "source": member1, "target": member2}, mandatory=False)
            info["script-after-execute"] = self.call("combats-admin.script-field", combat, "after-execute", errors, globs={"combat": combat, "source": member1}, mandatory=False)
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # storing
            config = self.app().config_updater()
            config.set("combats-%s.actions" % code, actions)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        # rendering form
        fields = [
            {"name": "before-execute", "label": self._("Before execution") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-before-execute")), "height": 150},
            {"name": "execute", "label": self._("Execution itself (applying action effect to targets)") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-execute")), "height": 150},
            {"name": "after-execute", "label": self._("After execution") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-after-execute")), "height": 150},
        ]
        self.call("admin.form", fields=fields)

