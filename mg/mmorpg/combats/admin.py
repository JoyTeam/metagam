import mg.constructor
from mg.core.tools import *
from mg.core.cass import ObjectNotFoundException
from mg.mmorpg.combats.core import Combat, CombatMember
from mg.mmorpg.combats.logs import DBCombatLogList, DBCombatLogPage, DBCombatLogStat, DBCombatLogStatList
from mg.mmorpg.combats.characters import DBCombatCharacterLogList
from uuid import uuid4
import re
import datetime

re_del = re.compile(r'^del/([a-z0-9_]+)$', re.IGNORECASE)
re_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile|actions|action/.+|ai/.+|ai|script|params|aboveavatar/.+|belowavatar/.+)(?:|/(.+))$', re.IGNORECASE)
re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_action_cmd = re.compile(r'action/(.+)', re.IGNORECASE)
re_action_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile|script|attributes|attribute/.+)$', re.IGNORECASE)
re_ai_cmd = re.compile(r'ai/(.+)', re.IGNORECASE)
re_ai_edit = re.compile(r'^edit/([a-z0-9_]+)/(profile|script)$', re.IGNORECASE)
re_attributes_cmd = re.compile(r'^attribute/(.+)$')
re_combat_params = re.compile('^combat/(new|p_[a-z0-9_]+)$', re.IGNORECASE)
re_combat_param_del = re.compile('^combat/del/(p_[a-z0-9_]+)$', re.IGNORECASE)
re_member_params = re.compile('^member/(new|p_[a-z0-9_]+)$', re.IGNORECASE)
re_member_param_del = re.compile('^member/del/(p_[a-z0-9_]+)$', re.IGNORECASE)
re_valid_parameter = re.compile(r'^p_[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_shorten = re.compile(r'^(.{100}).{3,}$')
re_avatar_params_cmd = re.compile('^(aboveavatar|belowavatar)/(.+)$', re.IGNORECASE)
re_script_prefix = re.compile(r'^script-')
re_valid_attribute_code = re.compile(r'^a_[a-z0-9_]+$', re.IGNORECASE)
re_static_value = re.compile(r'(\S+)\s*:\s*(.+)')

class CombatsAdmin(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-combats.index", self.menu_combats_index)
        self.rhook("ext-admin-combats.rules", self.admin_rules, priv="combats.rules")
        self.rhook("headmenu-admin-combats.rules", self.headmenu_rules)
        #self.rhook("ext-admin-combats.config", self.admin_config, priv="combats.config")
        #self.rhook("headmenu-admin-combats.config", self.headmenu_config)
        self.rhook("admin-gameinterface.design-files", self.design_files)
        self.rhook("ext-admin-combats.history", self.admin_history, priv="combats.config")
        self.rhook("headmenu-admin-combats.history", self.headmenu_history)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("admin-combats.stats-cleanup", self.stats_cleanup)
        self.rhook("ext-admin-combats.stats", self.admin_stats, priv="combats.stats")
        self.rhook("headmenu-admin-combats.stats", self.headmenu_stats)
        self.rhook("admin-gameinterface.design-files", self.design_files)
        self.rhook("advice-admin-combats.index", self.advice_combats)

    def advice_combats(self, hook, args, advice):
        advice.append({"title": self._("Combats documentation"), "content": self._('You can find detailed information on the combats engine in the <a href="//www.%s/doc/combats" target="_blank">combats engine page</a> in the reference manual.') % self.main_host, "order": 10})
        advice.append({"title": self._("Scripts documentation"), "content": self._('You can find detailed information on the scripting engine in the <a href="//www.%s/doc/script" target="_blank">scripting engine page</a> in the reference manual.') % self.main_host, "order": 20})

    def design_files(self, files):
        files.append({"filename": "character-combats.html", "description": self._("List of character's combats"), "doc": "/doc/design/combats"})

    def schedule(self, sched):
        sched.add("admin-combats.stats-cleanup", "20 0 * * *", priority=5)

    def menu_root_index(self, menu):
        menu.append({"id": "combats.index", "text": self._("Combats"), "order": 24})

    def menu_combats_index(self, menu):
        req = self.req()
        if req.has_access("combats.config"):
            menu.append({"id": "combats/rules", "text": self._("Combats rules"), "order": 1, "leaf": True})
            #menu.append({"id": "combats/config", "text": self._("Combats configuration"), "order": 2, "leaf": True})
            menu.append({"id": "combats/history", "text": self._("Combats history configuration"), "order": 3, "leaf": True})
        if req.has_access("combats.stats"):
            menu.append({"id": "combats/stats", "text": self._("View combats statistics"), "order": 4, "leaf": True})

    def permissions_list(self, perms):
        perms.append({"id": "combats.rules", "name": self._("Combats rules editor")})
        perms.append({"id": "combats.config", "name": self._("Combats configuration")})
        perms.append({"id": "combats.stats", "name": self._("Combats statistics")})
        perms.append({"id": "combats.debug-logs", "name": self._("View combat debug logs")})

    def headmenu_config(self, args):
        return self._("Combats configuration")

    def admin_config(self):
        req = self.req()
        if req.param("ok"):
            config = self.app().config_updater()
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        fields = [
        ]
        self.call("admin.form", fields=fields)

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
                    elif action == "ai":
                        return [self._("AI types of '%s'") % htmlescape(info["name"]), "combats/rules"]
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
                                            elif cmd == "attributes":
                                                return [self._("Attributes of '%s'") % htmlescape(act["name"]), "combats/rules/edit/%s/actions" % code]
                                            else:
                                                m = re_attributes_cmd.match(cmd)
                                                if m:
                                                    attr_code = m.group(1)
                                                    if attr_code == "new":
                                                        return [self._("New attribute"), "combats/rules/edit/%s/action/edit/%s/attributes" % (code, action_code)]
                                                    else:
                                                        for attr in act.get("attributes", []):
                                                            if attr["code"] == attr_code:
                                                                return [htmlescape(attr.get("name")), "combats/rules/edit/%s/action/edit/%s/attributes" % (code, action_code)]
                        m = re_ai_cmd.match(action)
                        if m:
                            cmd = m.group(1)
                            if cmd == "new":
                                return [self._("New AI type"), "combats/rules/edit/%s/ai" % code]
                            else:
                                m = re_ai_edit.match(cmd)
                                if m:
                                    ai_code, cmd = m.group(1, 2)
                                    for ai_type in self.conf("combats-%s.ai-types" % code, []):
                                        if ai_type["code"] == ai_code:
                                            if cmd == "profile":
                                                return [htmlescape(ai_type["name"]), "combats/rules/edit/%s/ai" % code]
                                            elif cmd == "script":
                                                return [self._("Scripts of '%s'") % htmlescape(ai_type["name"]), "combats/rules/edit/%s/ai" % code]
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
                    config.store()
                self.call("admin.redirect", "combats/rules")
            # edit
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
                    u'<hook:admin.link href="combats/rules/edit/%s/ai" title="%s" />' % (code, self._("artifical intelligence algorithms")),
                    u'<hook:admin.link href="combatinterface-%s/design" title="%s" />' % (code, self._("combat design templates")),
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
        # load list of combat types
        combat_types = []
        self.call("admin-combats.types", combat_types)
        combat_types_dict = dict([(tp.get("id"), tp) for tp in combat_types])
        combat_types = [(tp.get("id"), tp.get("name")) for tp in combat_types]
        # process request
        if req.ok():
            errors = {}
            # tp
            tp = req.param("tp")
            if not tp:
                errors["tp"] = self._("This field is mandatory")
            else:
                type_info = combat_types_dict.get(tp)
                if not type_info:
                    errors["tp"] = self._("Make a valid selection")
            # process errors
            if errors:
                print errors
                self.call("web.response_json", {"success": False, "errors": errors})
            # run dialog
            dialog = type_info["dialog"](self.app())
            dialog.show()
        # render form
        fields = []
        for ct_id, ct_name in combat_types:
            fields.append({"id": "tp-%s" % ct_id, "name": "tp", "type": "radio", "value": ct_id, "boxLabel": ct_name})
        buttons = [
            {"text": self._("Select combat system type")},
        ]
        self.call("admin.form", fields=fields, buttons=buttons)

    def rules_edit(self, rules, code, action, cmd):
        if action == "profile":
            return self.rules_edit_profile(code)
        elif action == "actions":
            return self.rules_edit_actions(code)
        elif action == "ai":
            return self.rules_edit_ai(code)
        elif action == "script":
            return self.rules_edit_script(code)
        elif action == "params":
            return self.rules_edit_params(code, cmd)
        else:
            m = re_action_cmd.match(action)
            if m:
                cmd = m.group(1)
                return self.rules_action(code, cmd)
            m = re_ai_cmd.match(action)
            if m:
                cmd = m.group(1)
                return self.rules_ai(code, cmd)
            m = re_avatar_params_cmd.match(action)
            if m:
                pos, cmd = m.group(1, 2)
                return self.rules_avatar_param(code, pos, cmd)

    def rules_edit_profile(self, code):
        req = self.req()
        shortRules = self.conf("combats.rules", {})
        oldInfo = self.conf("combats-%s.rules" % code, {})
        # process request
        if req.ok():
            errors = {}
            shortInfo = {}
            info = {}
            # test objects
            combat = Combat(self.app(), None, code)
            member = CombatMember(combat)
            viewer = CombatMember(combat)
            combat.join(member)
            combat.join(viewer)
            globs = {"combat": combat, "member": member, "viewer": viewer}
            # name
            name = req.param("name").strip()
            if not name:
                errors["name"] = self._("This field is mandatory")
            else:
                shortInfo["name"] = name
            # order
            shortInfo["order"] = floatz(req.param("order"))
            # timeout
            timeout = intz(req.param("timeout"))
            if timeout < 60:
                errors["timeout"] = self._("Minimal timeout is %d seconds") % 60
            elif timeout > 86400:
                errors["timeout"] = self._("Maximal timeout is %d seconds") % 86400
            else:
                info["timeout"] = timeout
            # turn_order
            turn_order = req.param("turn_order")
            if not turn_order in ["round-robin", "pair-exchanges", "time-line"]:
                errors["turn_order"] = self._("This field is mandatory")
            else:
                info["turn_order"] = turn_order
            # turn_timeout
            turn_timeout = intz(req.param("turn_timeout"))
            if turn_timeout < 5:
                errors["turn_timeout"] = self._("Minimal turn timeout is %d seconds") % 5
            elif turn_timeout > 300:
                errors["turn_timeout"] = self._("Maximal turn timeout is %d seconds") % 300
            else:
                info["turn_timeout"] = turn_timeout
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
                # enemy avatar
                info["generic_enemyavatar"] = 1 if req.param("generic_enemyavatar") else 0
                if info["generic_enemyavatar"]:
                    width = info["generic_enemyavatar_width"] = intz(req.param("generic_enemyavatar_width"))
                    if width < 50:
                        errors["generic_enemyavatar_width"] = self._("Miminal value is %d") % 50
                    elif width > 1000:
                        errors["generic_enemyavatar_width"] = self._("Maximal value is %d") % 1000
                # template in the target list
                info["generic_target_template"] = self.call("script.admin-text", "generic_target_template", errors, globs=globs)
                info["generic_member_list_template"] = self.call("script.admin-text", "generic_member_list_template", errors, globs=globs)
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
                # go button
                info["generic_gobutton"] = 1 if req.param("generic_gobutton") else 0
                if info["generic_gobutton"]:
                    info["generic_gobutton_text"] = req.param("generic_gobutton_text")
                # keep some parameters of generic interface
                for key in ["aboveavatar", "belowavatar"]:
                    if key in oldInfo:
                        info[key] = oldInfo[key]
            # time mode
            time_mode = req.param("v_time_mode")
            if time_mode != "none" and time_mode != "begin" and time_mode != "change":
                errors["v_time_mode"] = self._("Invalid time mode")
            else:
                info["time_mode"] = time_mode
            # time format
            time_format = req.param("v_time_format")
            if time_format != "num" and time_format != "mmss" and time_format != "realhhmmss":
                errors["v_time_format"] = self._("Invalid time format")
            else:
                info["time_format"] = time_format
            # script debug
            info["debug_script_chat"] = True if req.param("debug_script_chat") else False
            info["debug_script_log"] = True if req.param("debug_script_log") else False
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
        turn_order = info.get("turn_order", "round-robin")
        fields = [
            {"name": "name", "label": self._("Combat rules name"), "value": shortInfo["name"]},
            {"name": "order", "label": self._("Sorting order"), "value": shortInfo["order"], "inline": True},
            {"name": "timeout", "label": self._("General combat timeout (in seconds)"), "value": info.get("timeout", 3600 * 4)},
            {"type": "header", "html": self._("Combat turns")},
            {"id": "turn_order-round-robin", "name": "turn_order", "type": "radio", "label": self._("Combat turn order"), "checked": turn_order == "round-robin", "value": "round-robin", "boxLabel": self._("Round robin. Combat members perform actions exactly each after another")},
            {"id": "turn_order-pair-exchanges", "name": "turn_order", "type": "radio", "checked": turn_order == "pair-exchanges", "value": "pair-exchanges", "boxLabel": self._("Pair exchanges. Each opponent chooses an action on the randomly selected opponent. When their actions match, the system performs strike exchange")},
            {"id": "turn_order-time-line", "name": "turn_order", "type": "radio", "checked": turn_order == "time-line", "value": "time-line", "boxLabel": self._("Time line. Every member gets right of turn when his previous action finished. Every action takes specific number of time units to execute")},
            {"name": "turn_timeout", "label": self._("Turn timeout (in seconds)"), "value": info.get("turn_timeout", 30)},
            {"type": "header", "html": self._("Combat debugging")},
            {"name": "debug_script_chat", "label": self._("Output script trace into debug chat"), "type": "checkbox", "checked": info.get("debug_script_chat")},
            {"name": "debug_script_log", "label": self._("Output script trace into debug log"), "type": "checkbox", "checked": info.get("debug_script_log")},
            {"type": "header", "html": self._("Combat time")},
            {"name": "time_mode", "label": self._("Time visualization mode"), "type": "combo", "value": info.get("time_mode", "begin"), "values": [("none", self._("Don't show time")), ("begin", self._("Show in the beginning of every log line")), ("change", self._("Output to log after every change"))]},
            {"name": "time_format", "label": self._("Time format"), "type": "combo", "value": info.get("time_format", "mmss"), "values": [("mmss", self._("MM:SS")), ("num", self._("Plain number")), ("realhhmmss", self._("Realtime HH:MM:SS"))]},
            {"type": "header", "html": self._("Combat avatars settings")},
            {"name": "dim_avatar", "label": self._("Combat avatar dimensions (example: 100x200)"), "value": dim_avatar},
            {"name": "generic", "type": "checkbox", "label": self._("Use generic GUI for this type of combats"), "checked": info.get("generic", 1)},
            {"type": "header", "html": self._("Generic interface settings"), "condition": "[generic]"},
            {"name": "generic_myavatar", "type": "checkbox", "label": self._("Show player's avatar on the left side"), "checked": info.get("generic_myavatar", 1), "condition": "[generic]"},
            {"name": "generic_myavatar_width", "label": self._("Player's avatar width"), "value": info.get("generic_myavatar_width", 300), "condition": "[generic] && [generic_myavatar]"},
            {"name": "generic_enemyavatar", "type": "checkbox", "label": self._("Show enemy's avatar on the right side"), "checked": info.get("generic_enemyavatar", 1), "condition": "[generic]"},
            {"name": "generic_enemyavatar_width", "label": self._("Enemy's avatar width"), "value": info.get("generic_enemyavatar_width", 300), "condition": "[generic] && [generic_enemyavatar]"},
            {"name": "generic_log", "type": "checkbox", "label": self._("Show combat log on the bottom side"), "checked": info.get("generic_log", 1), "condition": "[generic]"},
            {"name": "generic_log_layout", "type": "combo", "label": self._("Combat log layout"), "values": [(0, self._("Fixed combat height, variable log height")), (1, self._("Variable combat height, fixed log height"))], "value": info.get("generic_log_layout", 0), "condition": "[generic] && [generic_log]"},
            {"name": "generic_combat_height", "label": self._("Combat interface height"), "value": info.get("generic_combat_height", 300), "condition": "[generic] && [generic_log] && ([generic_log_layout] == 0)"},
            {"name": "generic_log_height", "label": self._("Combat log height"), "value": info.get("generic_log_height", 300), "condition": "[generic] && [generic_log] && ([generic_log_layout] == 1)"},
            {"name": "generic_log_resize", "label": self._("Allow player to resize combat log"), "type": "checkbox", "checked": info.get("generic_log_resize", True), "condition": "[generic] && [generic_log]", "inline": True},
            {"type": "header", "html": self._("Go button"), "condition": "[generic]"},
            {"name": "generic_gobutton", "label": self._("Use 'Go' button to perform an action"), "type": "checkbox", "checked": info.get("generic_gobutton", True), "condition": "[generic]"},
            {"name": "generic_gobutton_text", "label": self._("Text on the 'Go' button"), "value": info.get("generic_gobutton_text", "Go"), "condition": "[generic] && [generic_gobutton]"},
            {"type": "header", "html": self._("Member name templates"), "condition": "[generic]"},
            {"name": "generic_target_template", "label": self._("Template to show member name in the list of action targets") + self.call("script.help-icon-expressions", "combats"), "value": self.call("script.unparse-text", info.get("generic_target_template", [[".", ["glob", "member"], "name"]])), "condition": "[generic]"},
            {"name": "generic_member_list_template", "label": self._("Template to show member name in the list of members when waiting for turn right") + self.call("script.help-icon-expressions", "combats"), "value": self.call("script.unparse-text", info.get("generic_member_list_template", [[".", ["glob", "member"], "name"]])), "condition": "[generic]"},
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
                    u'<hook:admin.link href="combats/rules/edit/%s/%s/del/%s" title="%s" confirm="%s" />' % (code, pos, ent["id"], self._("delete"), self._("Are you sure want to delete this item?")),
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
                    u'<hook:admin.link href="combats/rules/edit/%s/action/edit/%s/attributes" title="%s" />' % (code, act["code"], self._("combat action attributes")),
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
                elif cmd == "attributes":
                    return self.rules_action_attributes(code, action_code)
                else:
                    m = re_attributes_cmd.match(cmd)
                    if m:
                        attr_code = m.group(1)
                        return self.rules_action_attribute_edit(code, action_code, attr_code)

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
        # process request
        if req.ok():
            combat = Combat(self.app(), None, code)
            member1 = CombatMember(combat)
            member2 = CombatMember(combat)
            combat.join(member1)
            combat.join(member2)
            # preserve scripts and attributes
            info = dict([(k, v) for k, v in info.iteritems() if re_script_prefix.match(k) or k == "attributes"])
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
            # description
            info["description"] = self.call("script.admin-text", "description", errors, globs={"combat": combat, "member": member1}, mandatory=False)
            # order
            info["order"] = floatz(req.param("order"))
            # available
            info["available"] = self.call("script.admin-expression", "available", errors, globs={"combat": combat, "member": member1})
            # immediate
            info["immediate"] = True if req.param("immediate") else False
            # ignore_preselected
            info["ignore_preselected"] = True if req.param("ignore_preselected") else False
            # available
            if not info["immediate"]:
                info["duration"] = self.call("script.admin-expression", "duration", errors, globs={"combat": combat, "member": member1}, mandatory=False)
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
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save changes
            if action_code:
                actions = [a for a in actions if a["code"] != action_code]
            actions.append(info)
            actions.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["code"], y["code"]))
            config = self.app().config_updater()
            config.set("combats-%s.actions" % code, actions)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        # render form
        fields = [
            {"name": "code", "label": self._("Action code"), "value": info.get("code")},
            {"name": "order", "label": self._("Sorting order"), "value": info.get("order"), "inline": True},
            {"name": "name", "label": self._("Action name"), "value": info.get("name")},
            {"name": "description", "type": "textarea", "label": self._("Action description") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", info.get("description", ""))},
            {"name": "available", "label": self._("Whether action is available to member 'member'") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("available", 1))},
            {"name": "immediate", "label": self._("Immediate execution (out of turn)"), "type": "checkbox", "checked": info.get("immediate")},
            {"name": "duration", "label": self._("Duration of the action (in time units). Applicable to turn orders supporting time units only") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("duration")) if info.get("duration") is not None else "", "condition": "![immediate]"},
            {"name": "ignore_preselected", "label": self._("Ignore preselected targets (allow player to select any)"), "type": "checkbox", "checked": info.get("ignore_preselected")},
            {"type": "header", "html": self._("Available targets filter")},
            {"name": "targets", "type": "combo", "label": self._("Available action targets"), "values": [
                ("none", self._("None (not applicable)")),
                ("all", self._("All combat members alive")),
                ("enemies", self._("All enemies alive")),
                ("allies", self._("All allies alive")),
                ("allies-myself", self._("All allies alive and myself")),
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
            # parse form
            errors = {}
            config = self.app().config_updater()
            for tag in ["start", "heartbeat", "idle", "actions-started",
                    "actions-stopped", "joined", "draw", "victory"]:
                config.set("combats-%s.script-%s" % (code, tag), self.call("combats-admin.script-field", combat, tag, errors, globs={"combat": combat}, mandatory=False))
            for tag in ["turngot", "turnlost", "turnmade", "turntimeout", "heartbeat-member", "idle-member", "actions-started-member",
                    "actions-stopped-member", "draw-member", "victory-member", "defeat-member"]:
                config.set("combats-%s.script-%s" % (code, tag), self.call("combats-admin.script-field", combat, tag, errors, globs={"combat": combat, "member": member}, mandatory=False))
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store
            config.store()
            self.call("admin.redirect", "combats/rules")
        fields = [
            {"name": "start", "label": self._("Combat script running when combat starts") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-start" % code)), "height": 300},
            {"name": "joined", "label": self._("Combat script running when member 'member' is joined") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-joined" % code)), "height": 300},
            {"name": "turngot", "label": self._("Combat script running for member 'member' immediately after he gets right of turn") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-turngot" % code)), "height": 300},
            {"name": "turnlost", "label": self._("Combat script running for member 'member' immediately after he loses right turn") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-turnlost" % code)), "height": 300},
            {"name": "turnmade", "label": self._("Combat script running for member 'member' immediately after he makes a turn") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-turnmade" % code)), "height": 300},
            {"name": "turntimeout", "label": self._("Combat script running for member 'member' when it is timed out making turn") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-turntimeout" % code)), "height": 300},
            {"name": "heartbeat", "label": self._("Combat script running for every main loop iteration ('heartbeat script')") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-heartbeat" % code)), "height": 300},
            {"name": "heartbeat-member", "label": self._("Member heartbeat script running for every member") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-heartbeat-member" % code)), "height": 300},
            {"name": "idle", "label": self._("Combat script running after combat was idle for every 1 full second ('idle script')") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-idle" % code)), "height": 300},
            {"name": "idle-member", "label": self._("Member idle script running for every member") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-idle-member" % code)), "height": 300},
            {"name": "actions-started", "label": self._("Combat script running after some actions are started") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-actions-started" % code)), "height": 300},
            {"name": "actions-started-member", "label": self._("Combat script running on every member after some actions are started") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-actions-started-member" % code)), "height": 300},
            {"name": "actions-stopped", "label": self._("Combat script running after some actions are stopped") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-actions-stopped" % code)), "height": 300},
            {"name": "actions-stopped-member", "label": self._("Combat script running on every member after some actions are stopped") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-actions-stopped-member" % code)), "height": 300},
            {"name": "draw", "label": self._("Combat script running when the combat was a draw") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-draw" % code)), "height": 300},
            {"name": "draw-member", "label": self._("Combat script running on every member when the combat was a draw") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-draw-member" % code)), "height": 300},
            {"name": "victory", "label": self._("Combat script running when the combat finished with victory of team 'winner_team'") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-victory" % code)), "height": 300},
            {"name": "defeat-member", "label": self._("Combat script running on every defeated member (member of defeated team, not called on a draw)") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-defeat-member" % code)), "height": 300},
            {"name": "victory-member", "label": self._("Combat script running on every winner member (member of winner team, not called on a draw, called even on inactive members)") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", self.conf("combats-%s.script-victory-member" % code)), "height": 300},
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

    def rules_action_attribute_edit(self, code, action_code, attr_code):
        req = self.req()
        actions = [act.copy() for act in self.conf("combats-%s.actions" % code, [])]
        info = None
        for act in actions:
            if act["code"] == action_code:
                info = act
                break
        if info is None:
            self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        attributes = act.get("attributes", [])
        if attr_code == "new":
            # new
            order = 0.0
            for attr in attributes:
                if attr["order"] > order:
                    order = attr["order"]
            attr = {
                "order": order + 10.0,
                "code": "a_",
            }
        else:
            m = re_del.match(attr_code)
            if m:
                # delete
                attr_code = m.group(1)
                config = self.app().config_updater()
                attributes = [a for a in attributes if a["code"] != attr_code]
                info["attributes"] = attributes
                config.set("combats-%s.actions" % code, actions)
                config.store()
                self.call("admin.redirect", "combats/rules/edit/%s/action/edit/%s/attributes" % (code, action_code))
            # edit
            attr = None
            for a in attributes:
                if a["code"] == attr_code:
                    attr = a.copy()
                    break
            if not attr:
                self.call("admin.redirect", "combats/rules/edit/%s/action/edit/%s/attributes" % (code, action_code))
        existing_codes = set()
        for a in attributes:
            existing_codes.add(a["code"])
        if req.ok():
            errors = {}
            # code
            new_code = req.param("code")
            if not new_code:
                errors["code"] = self._("This field is mandatory")
            elif not re_valid_attribute_code.match(new_code):
                errors["code"] = self._("Attribute code must start with 'a_' prefix and contain latin letters, digits, and underscores only")
            elif new_code in existing_codes and new_code != attr.get("code"):
                errors["code"] = self._("Attribute with this code already exists")
            else:
                attr["code"] = new_code
            # order
            attr["order"] = floatz(req.param("order"))
            # name
            name = req.param("name").strip()
            if not name:
                errors["name"] = self._("This field is mandatory")
            else:
                attr["name"] = name
            # values
            tp = req.param("v_type")
            if tp == "static":
                attr["type"] = "static"
                values = req.param("values").strip()
                attr["values"] = []
                for v in values.split("\n"):
                    v = v.strip()
                    if not v:
                        continue
                    m = re_static_value.match(v)
                    if not m:
                        errors["values"] = self._("Invalid field format")
                    else:
                        v_code, v_title = m.group(1, 2)
                        attr["values"].append({
                            "code": v_code,
                            "title": v_title,
                        })
                if not attr["values"]:
                    errors["values"] = self._("This list cannot be empty")
            elif tp == "int":
                attr["type"] = "int"
            else:
                errors["v_type"] = self._("Invalid attribute values type")
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store
            config = self.app().config_updater()
            attributes = [a for a in attributes if a["code"] != attr_code]
            attributes.append(attr)
            attributes.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            info["attributes"] = attributes
            config.set("combats-%s.actions" % code, actions)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/action/edit/%s/attributes" % (code, action_code))
        fields = [
            {"name": "code", "label": self._("Attribute code"), "value": attr.get("code")},
            {"name": "order", "label": self._("Sorting order"), "value": attr.get("order"), "inline": True},
            {"name": "name", "label": self._("Attribute name"), "value": attr.get("name")},
            {"name": "type", "type": "combo", "label": self._("Attribute values type"), "value": attr.get("type", "static"), "values": [("static", self._("Static list")), ("int", self._("Integer value"))]},
            {"name": "values", "label": self._("List of values (every value must start from new line and be in form code:title)"), "type": "textarea", "value": u"\n".join([u"%s: %s" % (val["code"], val["title"]) for val in attr.get("values", [])]), "condition": "[type]=='static'"},
        ]
        self.call("admin.form", fields=fields)

    def rules_action_attributes(self, code, action_code):
        req = self.req()
        actions = [act.copy() for act in self.conf("combats-%s.actions" % code, [])]
        info = None
        for act in actions:
            if act["code"] == action_code:
                info = act
                break
        if info is None:
            self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        rows = []
        for attr in act.get("attributes", []):
            rows.append([
                htmlescape(attr.get("name")),
                attr.get("order", 0.0),
                u'<hook:admin.link href="combats/rules/edit/%s/action/edit/%s/attribute/%s" title="%s" />' % (code, action_code, attr["code"], self._("edit")),
                u'<hook:admin.link href="combats/rules/edit/%s/action/edit/%s/attribute/del/%s" title="%s" confirm="%s" />' % (code, action_code, attr["code"], self._("delete"), self._("Are you sure want to delete this attribute?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "combats/rules/edit/%s/action/edit/%s/attribute/new" % (code, action_code),
                            "text": self._("New action attribute"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Name"),
                        self._("Order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
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
            # parse form
            errors = {}
            globs = {"combat": combat, "source": member1}
            for attr in act.get("attributes", []):
                globs[attr["code"]] = 0
            globs_target = globs.copy()
            globs_target["target"] = member2
            info["script-enqueued"] = self.call("combats-admin.script-field", combat, "enqueued", errors, globs=globs, mandatory=False)
            info["script-begin"] = self.call("combats-admin.script-field", combat, "begin", errors, globs=globs, mandatory=False)
            info["script-begin-target"] = self.call("combats-admin.script-field", combat, "begin-target", errors, globs=globs_target, mandatory=False)
            info["script-end"] = self.call("combats-admin.script-field", combat, "end", errors, globs=globs, mandatory=False)
            info["script-end-target"] = self.call("combats-admin.script-field", combat, "end-target", errors, globs=globs_target, mandatory=False)
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store
            config = self.app().config_updater()
            config.set("combats-%s.actions" % code, actions)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/actions" % code)
        # render form
        fields = [
            {"name": "enqueued", "label": self._("Action enqueued") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-enqueued")), "height": 300},
            {"name": "begin", "label": self._("Begin execution") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-begin")), "height": 300},
            {"name": "begin-target", "label": self._("Begin execution on target 'target'") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-begin-target")), "height": 300},
            {"name": "end", "label": self._("End execution") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-end")), "height": 300},
            {"name": "end-target", "label": self._("End execution on target 'target'") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-end-target")), "height": 300},
        ]
        self.call("admin.form", fields=fields)

    def design_files(self, files):
        files.append({"filename": "combat-interface.html", "description": self._("Combat interface template (used when no specific combat-rules-*.html exist)"), "doc": "/doc/combats"})
        rules = self.conf("combats.rules", {})
        rules = rules.items()
        rules.sort(cmp=lambda x, y: cmp(x[1]["order"], y[1]["order"]) or cmp(x[0], y[0]))
        for code, info in rules:
            files.append({"filename": "combat-rules-%s.html" % code, "description": self._("Combat interface for combat rules '{code}' ({name})").format(code=code, name=htmlescape(info["name"])), "doc": "/doc/combats"})

    def rules_edit_ai(self, code):
        ai_types = self.conf("combats-%s.ai-types" % code, [])
        rows = []
        for ai_type in ai_types:
            rows.append([
                ai_type["code"],
                htmlescape(ai_type["name"]),
                ai_type["order"],
                u'<br />'.join([
                    u'<hook:admin.link href="combats/rules/edit/%s/ai/edit/%s/profile" title="%s" />' % (code, ai_type["code"], self._("AI type profile")),
                    u'<hook:admin.link href="combats/rules/edit/%s/ai/edit/%s/script" title="%s" />' % (code, ai_type["code"], self._("script handlers")),
                ]),
                u'<hook:admin.link href="combats/rules/edit/%s/ai/del/%s" title="%s" confirm="%s" />' % (code, ai_type["code"], self._("delete"), self._("Are you sure want to delete this AI type?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "combats/rules/edit/%s/ai/new" % code,
                            "text": self._("New AI type"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Code"),
                        self._("AI type name"),
                        self._("Order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def rules_ai(self, code, cmd):
        if cmd == "new":
            return self.rules_ai_type_edit(code, None)
        else:
            m = re_del.match(cmd)
            if m:
                ai_code = m.group(1)
                ai_types = [ai_type for ai_type in self.conf("combats-%s.ai-types" % code, []) if ai_type["code"] != ai_code]
                config = self.app().config_updater()
                config.set("combats-%s.ai-types" % code, ai_types)
                config.store()
                self.call("admin.redirect", "combats/rules/edit/%s/ai" % code)
            m = re_ai_edit.match(cmd)
            if m:
                ai_code, cmd = m.group(1, 2)
                if cmd == "profile":
                    return self.rules_ai_type_edit(code, ai_code)
                elif cmd == "script":
                    return self.rules_ai_type_script(code, ai_code)

    def rules_ai_type_edit(self, combat_code, ai_code):
        req = self.req()
        ai_types = [ai_type.copy() for ai_type in self.conf("combats-%s.ai-types" % combat_code, [])]
        if ai_code is None:
            info = {}
            order = None
            for ai_type in ai_types:
                if order is None or ai_type["order"] > order:
                    order = ai_type["order"]
            if order is None:
                info["order"] = 0.0
            else:
                info["order"] = order + 10.0
        else:
            info = None
            for ai_type in ai_types:
                if ai_type["code"] == ai_code:
                    info = ai_type
                    break
            if info is None:
                self.call("admin.redirect", "combats/rules/edit/%s/ai" % combat_code)
        existing_codes = set()
        for ai_type in ai_types:
            existing_codes.add(ai_type["code"])
        # process request
        if req.ok():
            combat = Combat(self.app(), None, combat_code)
            member1 = CombatMember(combat)
            member2 = CombatMember(combat)
            combat.join(member1)
            combat.join(member2)
            # preserve scripts and attributes
            info = dict([(k, v) for k, v in info.iteritems() if re_script_prefix.match(k)])
            errors = {}
            # code
            code = req.param("code")
            if not code:
                errors["code"] = self._("This field is mandatory")
            elif not re_valid_identifier.match(code):
                errors["code"] = self._("AI type code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
            elif code in existing_codes and code != ai_code:
                errors["code"] = self._("AI type with the same code already exists")
            else:
                info["code"] = code
            # name
            name = req.param("name")
            if not name:
                errors["name"] = self._("This field is mandatory")
            else:
                info["name"] = name
            # order
            info["order"] = floatz(req.param("order"))
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save changes
            if ai_code:
                ai_types = [a for a in ai_types if a["code"] != ai_code]
            ai_types.append(info)
            ai_types.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["code"], y["code"]))
            config = self.app().config_updater()
            config.set("combats-%s.ai-types" % combat_code, ai_types)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/ai" % combat_code)
        # render form
        fields = [
            {"name": "code", "label": self._("AI type code"), "value": info.get("code")},
            {"name": "order", "label": self._("Sorting order"), "value": info.get("order"), "inline": True},
            {"name": "name", "label": self._("AI type name"), "value": info.get("name")},
        ]
        self.call("admin.form", fields=fields)

    def rules_ai_type_script(self, code, ai_code):
        req = self.req()
        ai_types = [ai_type.copy() for ai_type in self.conf("combats-%s.ai-types" % code, [])]
        info = None
        for ai_type in ai_types:
            if ai_type["code"] == ai_code:
                info = ai_type
                break
        if info is None:
            self.call("admin.redirect", "combats/rules/edit/%s/ai" % code)
        if req.ok():
            # test objects
            combat = Combat(self.app(), None, code)
            member = CombatMember(combat)
            combat.join(member)
            # parse form
            errors = {}
            info["script-turn-got"] = self.call("combats-admin.script-field", combat, "turn-got", errors, globs={"combat": combat, "member": member}, mandatory=False)
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store
            config = self.app().config_updater()
            config.set("combats-%s.ai-types" % code, ai_types)
            config.store()
            self.call("admin.redirect", "combats/rules/edit/%s/ai" % code)
        # render form
        fields = [
            {"name": "turn-got", "label": self._("Executed when AI member gets right of turn") + self.call("script.help-icon-expressions", "combats"), "type": "textarea", "value": self.call("combats-admin.unparse-script", info.get("script-turn-got")), "height": 100},
        ]
        self.call("admin.form", fields=fields)

    def headmenu_history(self, args):
        return self._("Combats history configuration")

    def admin_history(self):
        req = self.req()
        if req.param("ok"):
            errors = {}
            config = self.app().config_updater()
            val = req.param("syslog_retention")
            if not valid_nonnegative_int(val):
                errors["syslog_retention"] = self._("This value must be a valid integer number")
            else:
                val = intz(val)
                if val < 1:
                    errors["syslog_retention"] = self._("Minimal value is %d") % 1
                elif val > 365:
                    errors["syslog_retention"] = self._("Maximal value is %d") % 365
                else:
                    config.set("combats-history.syslog_retention", val)
            val = req.param("log_retention")
            if not valid_nonnegative_int(val):
                errors["log_retention"] = self._("This value must be a valid integer number")
            else:
                val = intz(val)
                if val < 1:
                    errors["log_retention"] = self._("Minimal value is %d") % 1
                elif val > 365:
                    errors["log_retention"] = self._("Maximal value is %d") % 365
                else:
                    config.set("combats-history.log_retention", val)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        fields = [
            {"name": "syslog_retention", "label": self._("System logs retention (for how many days to keep system logs)"), "value": self.conf("combats-history.syslog_retention", 7)},
            {"name": "log_retention", "label": self._("User logs retention (for how many days to keep user combat logs)"), "value": self.conf("combats-history.log_retention", 30)},
        ]
        self.call("admin.form", fields=fields)

    def headmenu_stats(self, args):
        return self._("Combats statistics")

    def admin_stats(self):
        rows = []
        lst = self.objlist(DBCombatLogStatList, query_index="created", query_reversed=True, query_limit=365)
        lst.load(silent=True)
        log_size = 0
        syslog_size = 0
        for ent in lst:
            rows.append([
                { "text": self.call("l10n.date_local", ent.get("created")) },
                { "text": ent.get("log_keep0_cnt"), "striked": ent.get("log_purged") },
                { "text": ent.get("log_keep0_size"), "striked": ent.get("log_purged") },
                { "text": ent.get("syslog_keep0_cnt"), "striked": ent.get("syslog_purged") },
                { "text": ent.get("syslog_keep0_size"), "striked": ent.get("syslog_purged") },
                { "text": ent.get("log_keep1_cnt") },
                { "text": ent.get("log_keep1_size") },
                { "text": ent.get("syslog_keep1_cnt") },
                { "text": ent.get("syslog_keep1_size") },
            ])
            if not ent.get("log_purged"):
                log_size += ent.get("log_keep0_size")
            if not ent.get("syslog_purged"):
                syslog_size += ent.get("syslog_keep0_size")
        vars = {
            "Date": self._("Date"),
            "NotImportant": self._("Not important combat logs (keep=0)"),
            "Important": self._("Important combat logs (keep=1)"),
            "UserLogs": self._("User logs"),
            "SystemLogs": self._("System logs"),
            "Count": self._("Count"),
            "Size": self._("Size"),
            "StoredSize": self._("Stored size"),
            "rows": rows,
            "LogType": self._("Logs type"),
            "Log": self._("User logs"),
            "Syslog": self._("System logs"),
            "Limit": self._("Limit for the game"),
            "log_size": log_size,
            "syslog_size": syslog_size,
            "log_limit": self.conf("combats-history.max-log", 10000000),
            "syslog_limit": self.conf("combats-history.max-syslog", 10000000),
        }
        self.call("admin.response_template", "admin/combats/stats.html", vars)

    def stats_cleanup(self):
        self.debug("Updating combats stats")
        # To update combat statistics query the date of the last statistics entry first
        lst = self.objlist(DBCombatLogStatList, query_index="created", query_reversed=True, query_limit=1)
        lst.load(silent=True)
        if len(lst):
            laststat = lst[0].get("created")
            self.debug("Last statistics date is %s", laststat)
            since = datetime.datetime.strptime(laststat, "%Y-%m-%d") + datetime.timedelta(days=1)
        else:
            self.debug("No statistics exist. Query first combat date")
            lst = self.objlist(DBCombatLogList, query_index="keep-started", query_equal="0", query_limit=10)
            lst.load(silent=True)
            if len(lst):
                self.debug("First combat date is %s", lst[0].get("started"))
                since = datetime.datetime.strptime(lst[0].get("started").split(" ")[0], "%Y-%m-%d")
            else:
                self.debug("No combats in the database. Giving up")
                return
        # Enumerate all dates from since to yesterday and calculate its statistics
        till = datetime.datetime.strptime(self.now(-86400).split(" ")[0], "%Y-%m-%d")
        self.debug("Enumerating combat logs from %s to %s", since.strftime("%Y-%m-%d"), till.strftime("%Y-%m-%d"))
        cur = since
        while cur <= till:
            self.debug("Processing %s", cur.strftime("%Y-%m-%d"))
            cur_str = cur.strftime("%Y-%m-%d")
            stat = self.obj(DBCombatLogStat)
            stat.set("created", cur_str)
            stat.set("log_keep0_cnt", 0)
            stat.set("log_keep0_size", 0)
            stat.set("syslog_keep0_cnt", 0)
            stat.set("syslog_keep0_size", 0)
            stat.set("log_keep1_cnt", 0)
            stat.set("log_keep1_size", 0)
            stat.set("syslog_keep1_cnt", 0)
            stat.set("syslog_keep1_size", 0)
            stat.set("stored", 1)
            for keep in ["0", "1"]:
                lst = self.objlist(DBCombatLogList, query_index="keep-started", query_equal=keep, query_start="%s 00:00:00" % cur_str, query_finish="%s 24:00:00" % cur_str)
                lst.load(silent=True)
                for ent in lst:
                    if ent.get("debug"):
                        stat.set("syslog_keep%s_cnt" % keep, stat.get("syslog_keep%s_cnt" % keep) + 1)
                        stat.set("syslog_keep%s_size" % keep, stat.get("syslog_keep%s_size" % keep) + ent.get("size", 0))
                    else:
                        stat.set("log_keep%s_cnt" % keep, stat.get("log_keep%s_cnt" % keep) + 1)
                        stat.set("log_keep%s_size" % keep, stat.get("log_keep%s_size" % keep) + ent.get("size", 0))
            stat.store()
            cur += datetime.timedelta(days=1)
        # Load statistics of all logs still stored in the database
        lst = self.objlist(DBCombatLogStatList, query_index="stored-created", query_equal="1")
        lst.load(silent=True)
        total_log = 0
        total_syslog = 0
        max_log = self.conf("combats-history.max-log", 10000000)
        max_syslog = self.conf("combats-history.max-syslog", 10000000)
        purge_log = None
        purge_syslog = None
        for ent in reversed(lst):
            if not ent.get("log_purged"):
                total_log += ent.get("log_keep0_size")
            if not ent.get("syslog_purged"):
                total_syslog += ent.get("syslog_keep0_size")
            if total_log > max_log and purge_log is None:
                purge_log = ent.get("created")
                self.debug("Purge combat logs created before %s because of storage overflow (%d > %d)", purge_log, total_log, max_log)
            if total_syslog > max_syslog and purge_syslog is None:
                purge_syslog = ent.get("created")
                self.debug("Purge combat system logs created before %s because of storage overflow (%d > %d)", purge_syslog, total_syslog, max_syslog)
        log_retention = self.conf("combats-history.log_retention", 30)
        syslog_retention = self.conf("combats-history.syslog_retention", 7)
        retention_log_since = (datetime.datetime.utcnow() - datetime.timedelta(days=log_retention + 1)).strftime("%Y-%m-%d")
        retention_syslog_since = (datetime.datetime.utcnow() - datetime.timedelta(days=syslog_retention + 1)).strftime("%Y-%m-%d")
        self.debug("Retention logs since: %s", retention_log_since)
        self.debug("Retention system logs since: %s", retention_syslog_since)
        purge_log_before = retention_log_since
        if purge_log and purge_log > purge_log_before:
            purge_log_before = purge_log
        self.debug("Purging logs before: %s", purge_log_before)
        purge_syslog_before = retention_syslog_since
        if purge_syslog and purge_syslog > purge_syslog_before:
            purge_syslog_before = purge_syslog
        self.debug("Purging system logs before: %s", purge_syslog_before)
        for ent in lst:
            if not ent.get("log_purged") and ent.get("created") <= purge_log_before:
                self.debug("Purging logs at %s", ent.get("created"))
                clst = self.objlist(DBCombatLogList, query_index="keep-started", query_equal="0",
                        query_start="%s 00:00:00" % ent.get("created"), query_finish="%s 24:00:00" % ent.get("created"))
                clst.load(silent=True)
                for cent in clst:
                    if cent.get("debug") == 0:
                        self.purge_log(cent)
                ent.set("log_purged", 1)
            if not ent.get("syslog_purged") and ent.get("created") <= purge_syslog_before:
                self.debug("Purging system logs at %s", ent.get("created"))
                clst = self.objlist(DBCombatLogList, query_index="keep-started", query_equal="0",
                        query_start="%s 00:00:00" % ent.get("created"), query_finish="%s 24:00:00" % ent.get("created"))
                clst.load(silent=True)
                for cent in clst:
                    if cent.get("debug") == 1:
                        self.purge_log(cent)
                ent.set("syslog_purged", 1)
            if ent.get("log_purged") and ent.get("syslog_purged"):
                ent.delkey("stored")
            ent.store()

    def purge_log(self, cent):
        # Purge log pages
        for page in xrange(0, cent.get("pages", 0)):
            try:
                obj = self.obj(DBCombatLogPage, "%s-%s" % (cent.uuid, page))
            except ObjectNotFoundException:
                self.warning("Could not delete page %d of log %s", page, cent.uuid)
                pass
            else:
                obj.remove()
        # Purge character log
        lst = self.objlist(DBCombatCharacterLogList, query_index="combat", query_equal=cent.uuid)
        lst.load(silent=True)
        lst.remove()
        # Purge log itself
        cent.remove()
