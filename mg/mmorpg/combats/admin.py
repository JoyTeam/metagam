import mg.constructor
from mg.core.tools import *
from mg.mmorpg.combats.core import Combat, CombatMember
from uuid import uuid4
import re

re_del = re.compile(r'^del/([a-z0-9_]+)$', re.IGNORECASE)
re_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile|actions|action/.+|script|params|aboveavatar/.+|belowavatar/.+)(?:|/(.+))$', re.IGNORECASE)
re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_action_cmd = re.compile(r'action/(.+)', re.IGNORECASE)
re_action_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile|script)$', re.IGNORECASE)
re_combat_params = re.compile('^combat/(new|p_[a-z0-9]+)$', re.IGNORECASE)
re_combat_param_del = re.compile('^combat/del/(p_[a-z0-9]+)$', re.IGNORECASE)
re_member_params = re.compile('^member/(new|p_[a-z0-9]+)$', re.IGNORECASE)
re_member_param_del = re.compile('^member/del/(p_[a-z0-9]+)$', re.IGNORECASE)
re_valid_parameter = re.compile(r'^p_[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_shorten = re.compile(r'^(.{100}).{3,}$')
re_avatar_params_cmd = re.compile('^(aboveavatar|belowavatar)/(.+)$', re.IGNORECASE)

class CombatsAdmin(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-combats.index", self.menu_combats_index)
        self.rhook("ext-admin-combats.rules", self.admin_rules, priv="combats.rules")
        self.rhook("headmenu-admin-combats.rules", self.headmenu_rules)
        self.rhook("ext-admin-combats.config", self.admin_config, priv="combats.config")
        self.rhook("headmenu-admin-combats.config", self.headmenu_config)
        self.rhook("admin-gameinterface.design-files", self.design_files)

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
                code, action, cmd = m.group(1, 2, 3)
                rules = self.conf("combats.rules", {})
                info = rules.get(code)
                if info:
                    if action == "profile":
                        return [htmlescape(info["name"]), "combats/rules"]
                    elif action == "actions":
                        return [self._("Actions of '%s'") % htmlescape(info["name"]), "combats/rules"]
                    elif action == "script":
                        return [self._("Scripts of '%s'") % htmlescape(info["name"]), "combats/rules"]
                    elif action == "params":
                        if cmd:
                            m = re_combat_params.match(cmd)
                            if m:
                                paramid = m.group(1)
                                return [self._("Combat parameter '%s'") % paramid, "combats/rules/edit/%s/params" % code]
                            m = re_member_params.match(cmd)
                            if m:
                                paramid = m.group(1)
                                return [self._("Member parameter '%s'") % paramid, "combats/rules/edit/%s/params" % code]
                        return [self._("Parameters of '%s' delivered to client") % htmlescape(info["name"]), "combats/rules"]
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
                        m = re_avatar_params_cmd.match(action)
                        if m:
                            pos, paramid = m.group(1, 2)
                            if pos == "aboveavatar":
                                if paramid == "new":
                                    return [self._("New item above avatar"), "combats/rules/edit/%s/profile" % code]
                                else:
                                    return [self._("Item above avatar"), "combats/rules/edit/%s/profile" % code]
                            elif pos == "belowavatar":
                                if paramid == "new":
                                    return [self._("New item below avatar"), "combats/rules/edit/%s/profile" % code]
                                else:
                                    return [self._("Item below avatar"), "combats/rules/edit/%s/profile" % code]
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
                    config.delete("combats-%s.rules" % code)
                    config.store()
                self.call("admin.redirect", "combats/rules")
            # editing
            m = re_edit.match(req.args)
            if m:
                code, action, cmd = m.group(1, 2, 3)
                if code in rules:
                    return self.rules_edit(rules, code, action, cmd)
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
                    u'<hook:admin.link href="combats/rules/edit/%s/params" title="%s" />' % (code, self._("parameters delivery to client")),
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

    def rules_edit(self, rules, code, action, cmd):
        if action == "profile":
            return self.rules_edit_profile(code)
        elif action == "actions":
            return self.rules_edit_actions(code)
        elif action == "script":
            return self.rules_edit_script(code)
        elif action == "params":
            return self.rules_edit_params(code, cmd)
        else:
            m = re_action_cmd.match(action)
            if m:
                cmd = m.group(1)
                return self.rules_action(code, cmd)
            m = re_avatar_params_cmd.match(action)
            if m:
                pos, cmd = m.group(1, 2)
                return self.rules_avatar_param(code, pos, cmd)

    def rules_edit_profile(self, code):
        req = self.req()
        shortRules = self.conf("combats.rules", {})
        oldInfo = self.conf("combats-%s.rules" % code, {})
        # processing request
        if req.ok():
            errors = {}
            shortInfo = {}
            info = {}
            # name
            name = req.param("name").strip()
            if not name:
                errors["name"] = self._("This field is mandatory")
            else:
                shortInfo["name"] = name
            # order
            shortInfo["order"] = floatz(req.param("order"))
            # avatar dimensions
            dim_avatar = req.param("dim_avatar").strip()
            if not dim_avatar:
                errors["dim_avatar"] = self._("This field is mandatory")
            else:
                val = None
                dimensions = self.call("charimages.dimensions")
                for dim in self.call("charimages.dimensions"):
                    if dim_avatar == "%dx%d" % (dim["width"], dim["height"]):
                        val = [dim["width"], dim["height"]]
                        break
                if val is None:
                    errors["dim_avatar"] = self._("This dimension must be listed in the list of available dimensions on characters images configuration page. Current settings: %s") % ", ".join(["%dx%d" % (dim["width"], dim["height"]) for dim in dimensions])
                else:
                    info["dim_avatar"] = val
            # generic interface
            info["generic"] = 1 if req.param("generic") else 0
            if info["generic"]:
                # my avatar
                info["generic_myavatar"] = 1 if req.param("generic_myavatar") else 0
                if info["generic_myavatar"]:
                    width = info["generic_myavatar_width"] = intz(req.param("generic_myavatar_width"))
                    if width < 50:
                        errors["generic_myavatar_width"] = self._("Miminal value is %d") % 50
                    elif width > 1000:
                        errors["generic_myavatar_width"] = self._("Maximal value is %d") % 1000
                    info["generic_myavatar_resize"] = True if req.param("generic_myavatar_resize") else False
                # enemy avatar
                info["generic_enemyavatar"] = 1 if req.param("generic_enemyavatar") else 0
                if info["generic_enemyavatar"]:
                    width = info["generic_enemyavatar_width"] = intz(req.param("generic_enemyavatar_width"))
                    if width < 50:
                        errors["generic_enemyavatar_width"] = self._("Miminal value is %d") % 50
                    elif width > 1000:
                        errors["generic_enemyavatar_width"] = self._("Maximal value is %d") % 1000
                    info["generic_enemyavatar_resize"] = True if req.param("generic_enemyavatar_resize") else False
                # combat log
                info["generic_log"] = 1 if req.param("generic_log") else 0
                if info["generic_log"]:
                    layout = info["generic_log_layout"] = intz(req.param("v_generic_log_layout"))
                    if layout < 0 or layout > 1:
                        errors["v_generic_log_layout"] = self._("Invalid selection")
                    elif layout == 0:
                        height = info["generic_combat_height"] = intz(req.param("generic_combat_height"))
                        if height < 50:
                            errors["generic_combat_height"] = self._("Miminal value is %d") % 50
                        elif height > 500:
                            errors["generic_combat_height"] = self._("Maximal value is %d") % 500
                    elif layout == 1:
                        height = info["generic_log_height"] = intz(req.param("generic_log_height"))
                        if height < 50:
                            errors["generic_log_height"] = self._("Miminal value is %d") % 50
                        elif height > 500:
                            errors["generic_log_height"] = self._("Maximal value is %d") % 500
                    info["generic_log_resize"] = True if req.param("generic_log_resize") else False
                # keep some parameters of generic interface
                for key in ["aboveavatar", "belowavatar"]:
                    if key in oldInfo:
                        info[key] = oldInfo[key]
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save changes
            shortRules[code] = shortInfo
            config = self.app().config_updater()
            config.set("combats.rules", shortRules)
            config.set("combats-%s.rules" % code, info)
            config.store()
            self.call("admin.redirect", "combats/rules")
        # render form
        shortInfo = shortRules[code]
        info = oldInfo
        dim_avatar = info.get("dim_avatar", [120, 220])
        dim_avatar = [str(i) for i in dim_avatar]
        dim_avatar = "x".join(dim_avatar)
        fields = [
            {"name": "name", "label": self._("Combat rules name"), "value": shortInfo["name"]},
            {"name": "order", "label": self._("Sorting order"), "value": shortInfo["order"], "inline": True},
            {"type": "header", "html": self._("Combat avatars settings")},
            {"name": "dim_avatar", "label": self._("Combat avatar dimensions (example: 100x200)"), "value": dim_avatar},
            {"name": "generic", "type": "checkbox", "label": self._("Use generic GUI for this type of combats"), "checked": info.get("generic", 1)},
            {"type": "header", "html": self._("Generic interface settings"), "condition": "[generic]"},
            {"name": "generic_myavatar", "type": "checkbox", "label": self._("Show player's avatar on the left side"), "checked": info.get("generic_myavatar", 1), "condition": "[generic]"},
            {"name": "generic_myavatar_width", "label": self._("Player's avatar width"), "value": info.get("generic_myavatar_width", 300), "condition": "[generic] && [generic_myavatar]"},
            {"name": "generic_myavatar_resize", "label": self._("Allow player to resize player's avatar block"), "type": "checkbox", "checked": info.get("generic_myavatar_resize", False), "condition": "[generic] && [generic_myavatar]", "inline": True},
            {"name": "generic_enemyavatar", "type": "checkbox", "label": self._("Show enemy's avatar on the right side"), "checked": info.get("generic_enemyavatar", 1), "condition": "[generic]"},
            {"name": "generic_enemyavatar_width", "label": self._("Enemy's avatar width"), "value": info.get("generic_enemyavatar_width", 300), "condition": "[generic] && [generic_enemyavatar]"},
            {"name": "generic_enemyavatar_resize", "label": self._("Allow player to resize enemy's avatar block"), "type": "checkbox", "checked": info.get("generic_enemyavatar_resize", False), "condition": "[generic] && [generic_enemyavatar]", "inline": True},
            {"name": "generic_log", "type": "checkbox", "label": self._("Show combat log on the bottom side"), "checked": info.get("generic_log", 1), "condition": "[generic]"},
            {"name": "generic_log_layout", "type": "combo", "label": self._("Combat log layout"), "values": [(0, self._("Fixed combat height, variable log height")), (1, self._("Variable combat height, fixed log height"))], "value": info.get("generic_log_layout", 0), "condition": "[generic] && [generic_log]"},
            {"name": "generic_combat_height", "label": self._("Combat interface height"), "value": info.get("generic_combat_height", 300), "condition": "[generic] && [generic_log] && ([generic_log_layout] == 0)"},
            {"name": "generic_log_height", "label": self._("Combat log height"), "value": info.get("generic_log_height", 300), "condition": "[generic] && [generic_log] && ([generic_log_layout] == 1)"},
            {"name": "generic_log_resize", "label": self._("Allow player to resize combat log"), "type": "checkbox", "checked": info.get("generic_log_resize", True), "condition": "[generic] && [generic_log]", "inline": True},
        ]

        def render_params(pos, header, newtitle):
            rows = []
            params = info.get(pos)
            if params is None:
                params = []
                self.call("combats.default-%s" % pos, params)
                params.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
            for ent in params:
                tp = ent["type"]
                if tp == "tpl":
                    text = self.call("script.unparse-text", ent["tpl"])
                    text = htmlescape(re_shorten.sub(r'\1...', text))
                    rows.append([
                        self._("Template"),
                        text
                    ])
                else:
                    rows.append([
                        htmlescape(tp),
                        None
                    ])
                rows[-1].extend([
                    ent["order"],
                    u'<hook:admin.link href="combats/rules/edit/%s/%s/%s" title="%s" />' % (code, pos, ent["id"], self._("edit")),
                    u'<hook:admin.link href="combats/rules/edit/%s/%s/del/%s" title="%s" confirm="%s" />' % (code, pos, ent["id"], self._("delete"),
                        self._("Are you sure want to delete this item?")),
                ])
            vars = {
                "tables": [
                    {
                        "links": [
                            {"hook": "combats/rules/edit/%s/%s/new" % (code, pos), "text": newtitle, "lst": True}
                        ],
                        "header": [
                            self._("Type"),
                            self._("Parameters"),
                            self._("Sort order"),
                            self._("Editing"),
                            self._("Deletion"),
                        ],
                        "rows": rows,
                    }
                ]
            }
            fields.extend([
                {"type": "header", "html": header, "condition": "[generic]"},
                {"type": "html", "html": self.call("web.parse_layout", "admin/common/tables.html", vars), "condition": "[generic]"}
            ])
        render_params(
            pos = "aboveavatar",
            header = self._("Items above avatar in the generic interface"),
            newtitle = self._("Create new item above avatar"),
        )
        render_params(
            pos = "belowavatar",
            header = self._("Items below avatar in the generic interface"),
            newtitle = self._("Create new item below avatar"),
        )
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

    def rules_avatar_param(self, code, pos, cmd):
        req = self.req()
        # load list of parameters
        rules = self.conf("combats-%s.rules" % code, {})
        params = rules.get(pos)
        if params is None:
            params = []
            self.call("combats.default-%s" % pos, params)
            params.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
        # handle delete
        m = re_del.match(cmd)
        if m:
            paramid = m.group(1)
            params = [p for p in params if p["id"] != paramid]
            rules[pos] = params
            config = self.app().config_updater()
            config.set("combats-%s.rules" % code, rules)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/profile" % code)
        # find requested item
        if cmd == "new":
            order = 10.0
            for p in params:
                if p["order"] + 10 > order:
                    order = p["order"] + 10
            ent = {
                "type": "tpl",
                "order": order,
                "tpl": '<div class="combat-param">\n  <span class="combat-param-name"></span>:\n  <span class="combat-param-value">{member.}</span>\n</div>'
            }
        else:
            ent = None
            for p in params:
                if p["id"] == cmd:
                    ent = p
                    break
            if ent is None:
                self.call("admin.redirect", "combats/rules/edit/%s/profile" % code)
        # parse form parameters
        if req.ok():
            errors = {}
            ent = {
                "id": uuid4().hex if cmd == "new" else cmd,
            }
            # test objects
            combat = Combat(self.app(), None, code)
            member = CombatMember(combat)
            viewer = CombatMember(combat)
            combat.join(member)
            combat.join(viewer)
            globs = {"combat": combat, "member": member, "viewer": viewer}
            # order
            ent["order"] = floatz(req.param("order"))
            # type
            tp = req.param("v_type")
            ent["type"] = tp
            if tp == "tpl":
                ent["tpl"] = self.call("script.admin-text", "tpl", errors, globs=globs)
            else:
                errors["v_type"] = self._("Make a valid selection")
            ent["visible"] = self.call("script.admin-expression", "visible", errors, globs=globs)
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save changes
            params = [p for p in params if p["id"] != cmd]
            params.append(ent)
            params.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
            rules[pos] = params
            config = self.app().config_updater()
            config.set("combats-%s.rules" % code, rules)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/profile" % code)
        # render form
        fields = [
            {"name": "order", "label": self._("Sorting order"), "value": ent.get("order")},
            {"name": "visible", "label": self._("Visibility condition") + self.call("script.help-icon-expressions", "combats"), "value": self.call("script.unparse-expression", ent.get("visible", 1))},
            {"name": "type", "label": self._("Type of item"), "type": "combo", "value": ent.get("type"), "values": [("tpl", self._("MMOScript HTML template"))]},
            {"name": "tpl", "label": self._("Item HTML template") + self.call("script.help-icon-expressions", "combats"), "value": self.call("script.unparse-text", ent.get("tpl")), "type": "textarea", "height": 300, "condition": "[type] == 'tpl'"},
        ]
        self.call("admin.form", fields=fields)

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
            combat = Combat(self.app(), None, code)
            member1 = CombatMember(combat)
            member2 = CombatMember(combat)
            combat.join(member1)
            combat.join(member2)
            info = {}
            errors = {}
            # code
            act_code = req.param("code")
            if not act_code:
                errors["code"] = self._("This field is mandatory")
            elif not re_valid_identifier.match(act_code):
                errors["code"] = self._("Action code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
            elif act_code in existing_codes and act_code != action_code:
                errors["code"] = self._("Action with the same code already exists")
            else:
                info["code"] = act_code
            # name
            name = req.param("name")
            if not name:
                errors["name"] = self._("This field is mandatory")
            else:
                info["name"] = name
            # order
            info["order"] = floatz(req.param("order"))
            # available
            info["available"] = self.call("script.admin-expression", "available", errors, globs={"combat": combat, "member": member1})
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # targets
            valid_targets = set(["none", "all", "enemies", "allies", "allies-myself", "myself", "script"])
            targets = req.param("v_targets")
            if not targets in valid_targets:
                errors["v_targets"] = self._("Make a valid selection")
            else:
                info["targets"] = targets
                if targets == "script":
                    info["target_available"] = self.call("script.admin-expression", "target_available", errors, globs={"combat": combat, "member": member1, "target": member2})
            if targets != "none" and targets != "myself":
                info["target_all"] = True if req.param("target_all") else False
                if not info["target_all"]:
                    info["targets_limit"] = self.call("script.admin-expression", "targets_limit", errors, globs={"combat": combat, "member": member1})
                    if req.param("targets_sort"):
                        targets_sort = []
                        for i in xrange(0, 5):
                            if req.param("targets_sort_%d" % i).strip() != "":
                                order = "desc" if req.param("v_targets_sort_order_%d" % i) == "desc" else "asc"
                                targets_sort.append({
                                    "expression": self.call("script.admin-expression", "targets_sort_%d" % i, errors, globs={"combat": combat, "member": member1}),
                                    "order": order
                                })
                        if targets_sort:
                            info["targets_sort"] = targets_sort
                info["targets_min"] = self.call("script.admin-expression", "targets_min", errors, globs={"combat": combat, "member": member1})
                info["targets_max"] = self.call("script.admin-expression", "targets_max", errors, globs={"combat": combat, "member": member1})
            # saving changes
            if action_code:
                actions = [a for a in actions if a["code"] != action_code]
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
            {"name": "available", "label": self._("Whether action is available to member 'member'") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("available", 1))},
            {"type": "header", "html": self._("Available targets filter")},
            {"name": "targets", "type": "combo", "label": self._("Available action targets"), "values": [
                ("none", self._("None (not applicable)")),
                ("all", self._("All combat members")),
                ("enemies", self._("All enemies")),
                ("allies", self._("All allies")),
                ("allies-myself", self._("All allies and myself")),
                ("myself", self._("Myself only")),
                ("script", self._("Script expression")),
            ], "value": info.get("targets", "enemies")},
            {"name": "target_available", "label": self._("Member 'target' can be targeted by member 'member'") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("target_available")) if "target_available" in info else "", "condition": "[targets]=='script'"},
            {"type": "header", "html": self._("Available targets randomization"), "condition": "[targets] != 'none' && [targets] != 'myself'"},
            {"name": "target_all", "label": self._("All matching targets are available for selection"), "type": "checkbox", "checked": info.get("target_all", True), "condition": "[targets] != 'none' && [targets] != 'myself'"},
            {"name": "targets_limit", "label": self._("Targets number limit") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("targets_limit", 1)), "condition": "[targets] != 'none' && [targets] != 'myself' && ![target_all]"},
            {"name": "targets_sort", "label": self._("Sort members before applying limit"), "type": "checkbox", "checked": True if info.get("targets_sort") else False, "condition": "![target_all] && [targets] != 'none' && [targets] != 'myself'"},
        ]
        targets_sort = info.get("targets_sort", [])
        for i in xrange(0, 5):
            val = targets_sort[i] if i < len(targets_sort) else None
            fields.append({"name": "targets_sort_%d" % i, "label": self._("Expression") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", val["expression"]) if val else "", "condition": "![target_all] && [targets_sort] && [targets] != 'none' && [targets] != 'myself'"})
            fields.append({"name": "targets_sort_order_%d" % i, "label": self._("Sorting order"), "type": "combo", "values": [
                ("asc", self._("Ascending")),
                ("desc", self._("Descending")),
            ], "value": val["order"] if val else "asc", "condition": "![target_all] && [targets_sort] && [targets] != 'none' && [targets] != 'myself'", "inline": True})
        fields.extend([
            {"type": "header", "html": self._("Number of possible targets"), "condition": "[targets] != 'none' && [targets] != 'myself'"},
            {"name": "targets_min", "label": self._("Minimal number of targets allowed to select") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("targets_min", 1)), "condition": "[targets] != 'none' && [targets] != 'myself'"},
            {"name": "targets_max", "label": self._("Maximal number of targets allowed to select") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("targets_max", 1)), "condition": "[targets] != 'none' && [targets] != 'myself'", "inline": True},
        ])
        self.call("admin.form", fields=fields)

    def rules_edit_script(self, code):
        req = self.req()
        if req.ok():
            # test objects
            combat = Combat(self.app(), None, code)
            member = CombatMember(combat)
            combat.join(member)
            # parsing form
            errors = {}
            config = self.app().config_updater()
            config.set("combats-%s.script-start" % code, self.call("combats-admin.script-field", combat, "start", errors, globs={"combat": combat}, mandatory=False))
            config.set("combats-%s.script-turngot" % code, self.call("combats-admin.script-field", combat, "turngot", errors, globs={"combat": combat, "member": member}, mandatory=False))
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # storing
            config.store()
            self.call("admin.redirect", "combats/rules")
        fields = [
            {"name": "start", "label": self._("Combat script running when combat starts") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-start" % code)), "height": 300},
            {"name": "turngot", "label": self._("Combat script running for member 'member' immediately after he gets turn") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-turngot" % code)), "height": 300},
        ]
        self.call("admin.form", fields=fields)

    def rules_edit_params(self, code, cmd):
        req = self.req()
        params = self.conf("combats-%s.params" % code, {})
        params["combat"] = combat_params = params.get("combat", {})
        params["member"] = member_params = params.get("member", {})
        if cmd:
            m = re_combat_param_del.match(cmd)
            if m:
                paramid = m.group(1)
                if paramid in combat_params:
                    del combat_params[paramid]
                    config = self.app().config_updater()
                    config.set("combats-%s.params" % code, params)
                    config.store()
                    self.call("admin.redirect", "combats/rules/edit/%s/params" % code)
            m = re_combat_params.match(cmd)
            if m:
                paramid = m.group(1)
                if req.ok():
                    errors = {}
                    # test objects
                    combat = Combat(self.app(), None, code)
                    member1 = CombatMember(combat)
                    member2 = CombatMember(combat)
                    combat.join(member1)
                    combat.join(member2)
                    # code
                    pcode = req.param("code")
                    if not re_valid_parameter.match(pcode):
                        errors["code"] = self._("Parameter code must start with p_ and contain only latin letters, digits and underscode characters")
                    elif pcode in combat_params and pcode != paramid:
                        errors["code"] = self._("Parameter with this code is already delivered to client")
                    # visible
                    visible = self.call("script.admin-expression", "visible", errors, globs={"combat": combat, "viewer": member1})
                    # process errors
                    if errors:
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # store configuration
                    if paramid != "new":
                        del combat_params[paramid]
                    combat_params[pcode] = {
                        "visible": visible
                    }
                    config = self.app().config_updater()
                    config.set("combats-%s.params" % code, params)
                    config.store()
                    self.call("admin.redirect", "combats/rules/edit/%s/params" % code)
                if paramid == "new":
                    code = "p_"
                    visible = 1
                else:
                    code = paramid
                    paraminfo = combat_params.get(code)
                    if not paraminfo:
                        self.call("admin.redirect", "combats/rules/edit/%s/params" % code)
                    visible = paraminfo.get("visible")
                fields = [
                    {"name": "code", "label": self._("Parameter code (prefixed with 'p_')"), "value": code},
                    {"name": "visible", "label": self._("Whether parameter is visible to member 'viewer'") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", visible)},
                ]
                self.call("admin.form", fields=fields)
            m = re_member_param_del.match(cmd)
            if m:
                paramid = m.group(1)
                if paramid in member_params:
                    del member_params[paramid]
                    config = self.app().config_updater()
                    config.set("combats-%s.params" % code, params)
                    config.store()
                    self.call("admin.redirect", "combats/rules/edit/%s/params" % code)
            m = re_member_params.match(cmd)
            if m:
                paramid = m.group(1)
                if req.ok():
                    errors = {}
                    # test objects
                    combat = Combat(self.app(), None, code)
                    member1 = CombatMember(combat)
                    member2 = CombatMember(combat)
                    combat.join(member1)
                    combat.join(member2)
                    # code
                    pcode = req.param("code")
                    if not re_valid_parameter.match(pcode):
                        errors["code"] = self._("Parameter code must start with p_ and contain only latin letters, digits and underscode characters")
                    elif pcode in member_params and pcode != paramid:
                        errors["code"] = self._("Parameter with this code is already delivered to client")
                    # visible
                    visible = self.call("script.admin-expression", "visible", errors, globs={"combat": combat, "member": member1, "viewer": member2})
                    # process errors
                    if errors:
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # store configuration
                    if paramid != "new":
                        del member_params[paramid]
                    member_params[pcode] = {
                        "visible": visible
                    }
                    config = self.app().config_updater()
                    config.set("combats-%s.params" % code, params)
                    config.store()
                    self.call("admin.redirect", "combats/rules/edit/%s/params" % code)
                if paramid == "new":
                    code = "p_"
                    visible = 1
                else:
                    code = paramid
                    paraminfo = member_params.get(code)
                    if not paraminfo:
                        self.call("admin.redirect", "combats/rules/edit/%s/params" % code)
                    visible = paraminfo.get("visible")
                fields = [
                    {"name": "code", "label": self._("Parameter code (prefixed with 'p_')"), "value": code},
                    {"name": "visible", "label": self._("Whether parameter of member 'member' is visible to member 'viewer'") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", visible)},
                ]
                self.call("admin.form", fields=fields)
        combat_rows = []
        combat_params = combat_params.items()
        combat_params.sort(cmp=lambda x, y: cmp(x[0], y[0]))
        for paramid, info in combat_params:
            visible = htmlescape(re_shorten.sub(r'\1...', self.call("script.unparse-expression", info["visible"])))
            combat_rows.append([
                paramid,
                visible,
                u'<hook:admin.link href="combats/rules/edit/%s/params/combat/%s" title="%s" />' % (code, paramid, self._("edit")),
                u'<hook:admin.link href="combats/rules/edit/%s/params/combat/del/%s" title="%s" confirm="%s" />' % (code, paramid, self._("delete"), self._("Are you sure want to delete this parameter?")),
            ])
        member_rows = []
        member_params = member_params.items()
        member_params.sort(cmp=lambda x, y: cmp(x[0], y[0]))
        for paramid, info in member_params:
            visible = htmlescape(re_shorten.sub(r'\1...', self.call("script.unparse-expression", info["visible"])))
            member_rows.append([
                paramid,
                visible,
                u'<hook:admin.link href="combats/rules/edit/%s/params/member/%s" title="%s" />' % (code, paramid, self._("edit")),
                u'<hook:admin.link href="combats/rules/edit/%s/params/member/del/%s" title="%s" confirm="%s" />' % (code, paramid, self._("delete"), self._("Are you sure want to delete this parameter?")),
            ])
        vars = {
            "tables": [
                {
                    "title": self._("Combat parameters"),
                    "header": [
                        self._("Code"),
                        self._("Visibility"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": combat_rows,
                    "links": [
                        {
                            "hook": "combats/rules/edit/%s/params/combat/new" % code,
                            "text": self._("Deliver new combat parameter"),
                            "lst": True,
                        },
                    ]
                },
                {
                    "title": self._("Combat member parameters"),
                    "header": [
                        self._("Code"),
                        self._("Visibility"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": member_rows,
                    "links": [
                        {
                            "hook": "combats/rules/edit/%s/params/member/new" % code,
                            "text": self._("Deliver new combat member parameter"),
                            "lst": True,
                        },
                    ]
                },
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

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
            combat.join(member1)
            combat.join(member2)
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

    def design_files(self, files):
        files.append({"filename": "combat-interface.html", "description": self._("Combat interface template (used when no specific combat-rules-*.html exist)"), "doc": "/doc/combats"})
        rules = self.conf("combats.rules", {})
        rules = rules.items()
        rules.sort(cmp=lambda x, y: cmp(x[1]["order"], y[1]["order"]) or cmp(x[0], y[0]))
        for code, info in rules:
            files.append({"filename": "combat-rules-%s.html" % code, "description": self._("Combat interface for combat rules '{code}' ({name})").format(code=code, name=htmlescape(info["name"])), "doc": "/doc/combats"})
