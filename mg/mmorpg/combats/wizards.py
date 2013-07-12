from mg.constructor import *
import re
from uuid import uuid4

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_valid_parameter = re.compile(r'^p_([a-zA-Z0-9_]+)$')

class CombatRulesDialogs(ConstructorModule):
    def register(self):
        self.rhook("admin-combats.types", self.types_list)

    def types_list(self, lst):
        lst.append({
            "id": "round-robin",
            "name": self._("Round robin system. Combat members perform actions each after another in the same order."),
            "dialog": RoundRobin,
        })
        lst.append({
            "id": "attack-block",
            "name": self._("Attack-block system. Combat members choose arbitrary targets and zones being attacked or blocked. Attacks are performed in pair exchanges."),
            "dialog": AttackBlock,
        })
        lst.append({
            "id": "time-line",
            "name": self._("Time units system with continuous time line. Every action is performed in some number of time units. Combat members take right of turn when their previous action is finished."),
            "dialog": TimeLine,
        })
        lst.append({
            "id": "action-points",
            "name": self._("Round robin system with action points. Combat members perform actions each after another in the same order. Every turn may consist of several actions with limited total action points."),
            "dialog": ActionPoints,
        })

class CombatRulesDialog(ConstructorModule):
    def show(self):
        req = self.req()
        if req.ok() and req.param("form"):
            errors = {}
            self.rules = {}
            self.short_rules = {}
            self.params = {}
            self.actions = []
            self.ai_types = []
            self.rules["aboveavatar"] = []
            self.rules["belowavatar"] = []
            self.params["combat"] = self.combat_params = {}
            self.params["member"] = self.member_params = {}
            self.scripts = {}
            self.form_parse(errors)
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store everything
            self.generate()
            self.actions.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            self.ai_types.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            self.rules["aboveavatar"].sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            self.rules["belowavatar"].sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            config = self.app().config_updater()
            rules = self.conf("combats.rules", {}).copy()
            rules[self.code] = self.short_rules
            config.set("combats.rules", rules)
            config.set("combats-%s.rules" % self.code, self.rules)
            config.set("combats-%s.params" % self.code, self.params)
            config.set("combats-%s.actions" % self.code, self.actions)
            config.set("combats-%s.ai-types" % self.code, self.ai_types)
            for script_id, script_code in self.scripts.iteritems():
                config.set("combats-%s.script-%s" % (self.code, script_id), script_code)
            self.store(config)
            config.store()
            self.call("admin.redirect", "combats/rules")
        # show form
        fields = []
        fields.append({"name": "tp", "value": req.param("tp"), "type": "hidden"})
        fields.append({"name": "form", "value": 1, "type": "hidden"})
        self.form_render(fields)
        self.call("admin.form", fields=fields)

    def store(self, config):
        self.store_combat_quest(config)

    def store_combat_quest(self, config):
        quests = self.conf("quests.list", {})
        if "combat_triggers" not in quests:
            quests["combat_triggers"] = {
                "name": self._("Generic combat triggers"),
                "order": -10.0,
                "enabled": True,
                "available": 1,
            }
            config.set("quests.list", quests)
            config.set("quests.debug_combat_triggers", True)
            config.set("quest-combat_triggers.states", {
                "init": {
                    "order": 0.0,
                    "script": self.call("quests.parse-script", 'combat defeat draw { equipbreak random < 0.5 } combat victory { combat syslog \'Total inflicted damage: member=<b>{member.id}</b>, char=<b>{char.name}</b>, damage=<b>{member.p_inflicted_damage}</b>\' if member.p_inflicted_damage > 0 { set local.p_xp = member.p_inflicted_damage set char.%s = char.%s + local.p_xp combat log \'%s\' cls="combat-log-xp" } } clicked "attack" { if char.id != targetchar.id { if (char.location and targetchar.location and char.location.id == targetchar.location.id) { combat rules=\'%s\' ctitle=\'%s\' flags="pvp" { member char team=1 member targetchar team=2 } } else { error \'%s\' } } }' % (self.param_xp, self.param_xp, self._('<span class="combat-log-member">{member.name}</span> has got <span class="combat-log-xp-value">{local.p_xp}</span> [#local.p_xp:point,points] of experience'), self.code, self._('{char.name} has attacked {targetchar.name}'), self._("{targetchar.name} is in the different location"))),
                }
            })
            self.call("quest-admin.update-quest-handlers", config)

    def form_render(self, fields):
        rules = self.conf("combats.rules", {})
        order = None
        for code, info in rules.iteritems():
            if order is None or info["order"] > order:
                order = info["order"]
        if order is None:
            order = 0.0
        else:
            order += 10.0
        fields.extend([
            {"name": "code", "label": self._("Combat rules code")},
            {"name": "order", "label": self._("Sorting order"), "value": order, "inline": True},
            {"name": "name", "label": self._("Combat rules name")},
            {"type": "header", "html": self._("Character experience")},
            {"name": "param_xp", "label": self._("Character parameter holding its experience"), "value": "p_xp"},
        ])

    def form_parse(self, errors):
        req = self.req()
        # code
        rules = self.conf("combats.rules", {})
        code = req.param("code")
        if not code:
            errors["code"] = self._("This field is mandatory")
        elif not re_valid_identifier.match(code):
            errors["code"] = self._("Combat rules code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
        elif code in rules:
            errors["code"] = self._("Combat rules with the same code already exist")
        else:
            self.code = code
        # name
        name = req.param("name")
        if not name:
            errors["name"] = self._("This field is mandatory")
        else:
            self.short_rules["name"] = name
        # order
        self.short_rules["order"] = floatz(req.param("order"))
        # param_xp
        param_xp = req.param("param_xp")
        if not param_xp:
            errors["param_xp"] = self._("This field is mandatory")
        elif not re_valid_parameter.match(param_xp):
            errors["param_xp"] = self._("Parameter name must start with 'p_' and contain latin letters, digits and underscores only")
        else:
            self.param_xp = param_xp

    def generate(self):
        dimensions = self.call("charimages.dimensions")
        if dimensions:
            dimensions = [d for d in dimensions]
            # Find as close dimension to 110x220 as possible
            dimensions.sort(cmp=lambda x, y: cmp(abs(x["width"] - 110) + abs(x["width"] - 220), abs(y["width"] - 110) + abs(y["width"] - 220)))
            self.rules["dim_avatar"] = [dimensions[0]["width"], dimensions[0]["height"]]
            self.rules["generic_myavatar_width"] = dimensions[0]["width"] + 50
            self.rules["generic_enemyavatar_width"] = dimensions[0]["width"] + 50
        self.rules["generic"] = 1
        self.rules["generic_myavatar"] = 1
        self.rules["generic_enemyavatar"] = 1
        self.rules["generic_log"] = 1
        self.rules["generic_log_layout"] = 0
        self.rules["generic_combat_height"] = 300
        self.rules["generic_log_resize"] = True
        self.rules["time_mode"] = "none"
        self.rules["time_format"] = "num"
        self.rules["generic_gobutton"] = 1
        self.rules["generic_gobutton_text"] = self._("button///Go")
        self.rules["generic_target_template"] = self.call('script.parse-text', '{member.active ? "" : \'<span class="combat-member-dead">\'}{member.name}{member.active ? "" : "</span>"}')
        self.rules["generic_member_list_template"] = self.call('script.parse-text', '<span class="combat-bar"><span class="combat-bar-indicator" style="background-color: {(member.team == viewer.team) ? "green" : "red"}; width: {floor(member.%s * 100 / (member.%s or 1))}%%"></span></span> {member.active ? "" : \'<span class="combat-member-dead">\'}{member.name}{member.active ? "" : "</span>"}{member.may_turn ? " (%s)" : ""}' % (self.param_hp, self.param_max_hp, self._("waiting for turn")))
        self.rules["aboveavatar"].append({
            "id": uuid4().hex,
            "type": "tpl",
            "tpl": [
                '<div class="combat-member-name">',
                ['.', ['glob', 'member'], 'name'],
                '</div>'
            ],
            "visible": 1,
            "order": 10.0,
        })
        # scripts
        self.script_append("start", 'chat \'%s\' cls="combat-started"' % self._('Started <a href="/combat/{combat.id}" target="_blank">combat</a> {combat.team1_list} vs {combat.team2_list}'))
        self.script_append("joined", 'log \'%s\' cls="combat-log-joined"' % self._('<span class="combat-log-member">{member.name}</span> has joined the combat'))
        msg = self._('<a href="/combat/{combat.id}" target="_blank">Combat</a> {combat.team1_list} vs {combat.team2_list} was a draw')
        self.script_append("draw", 'set combat.stage = "done" chat \'%s\' cls="combat-stopped" log \'%s\' cls="combat-stopped"' % (msg, msg))
        msg = self._('{winners_list} <a href="/combat/{combat.id}" target="_blank">{winners_count >= 2 ? "have" : "has"} defeated</a> {loosers_list}')
        self.script_append("victory", 'set combat.stage = "done" chat \'%s\' cls="combat-stopped" log \'%s\' cls="combat-stopped"' % (msg, msg))
        self.script_append("turntimeout", 'syslog \'<b>[{combat.now}]</b> Timeout: member=<b>{member.id}</b> ({member.name})\' set member.p_timeouts = member.p_timeouts + 1 if member.active and member.p_timeouts >= 3 { set member.active = 0 log \'%s\' cls="dead" sound "//%s/st/sounds/death.mp3" mode="wait" }' % (self._('{class="combat-log-member"}{member.name}{/class} {class="combat-log-dead"}has become unconscious and died{/class}'), self.app().canonical_domain))

    def script_append(self, code, text):
        text = self.call("combats-admin.parse-script", text)
        try:
            self.scripts[code].extend(text)
        except KeyError:
            self.scripts[code] = text

    def form_render_hp(self, fields):
        fields.extend([
            {"type": "header", "html": self._("Member hitpoints")},
            {"name": "param_hp", "label": self._("Member parameter holding its hitpoints"), "value": "p_hp"},
            {"name": "param_max_hp", "label": self._("Member parameter holding its maximal hitpoints"), "value": "p_max_hp"},
        ])

    def form_parse_hp(self, errors):
        req = self.req()
        # param_hp
        param_hp = req.param("param_hp")
        if not param_hp:
            errors["param_hp"] = self._("This field is mandatory")
        elif not re_valid_parameter.match(param_hp):
            errors["param_hp"] = self._("Parameter name must start with 'p_' and contain latin letters, digits and underscores only")
        else:
            self.param_hp = param_hp
        # param_max_hp
        param_max_hp = req.param("param_max_hp")
        if not param_max_hp:
            errors["param_max_hp"] = self._("This field is mandatory")
        elif not re_valid_parameter.match(param_max_hp):
            errors["param_max_hp"] = self._("Parameter name must start with 'p_' and contain latin letters, digits and underscores only")
        else:
            self.param_max_hp = param_max_hp

    def generate_hp(self):
        self.rules["aboveavatar"].append({
            "id": uuid4().hex,
            "type": "tpl",
            "tpl": self.call('script.parse-text', '<div class="combat-bar">\n<div class="combat-bar-indicator" style="background-color: {{(member.team == viewer.team) ? "green" : "red"}}; width: {{floor(member.{hp} * 100 / (member.{max_hp} or 1))}}%">\n</div>\n</div>'.format(hp=self.param_hp, max_hp=self.param_max_hp)),
            "visible": 1,
            "order": 10.0,
        })
        self.rules["aboveavatar"].append({
            "id": uuid4().hex,
            "type": "tpl",
            "tpl": self.call('script.parse-text', '<div class="combat-param combat-member-hp"><span class="combat-param-name">{HP}</span>: <span class="combat-param-value">{{member.{hp}}} / {{member.{max_hp}}}</span></div>'.format(HP=self._("HP"), hp=self.param_hp, max_hp=self.param_max_hp)),
            "visible": 1,
            "order": 20.0,
        })
        self.member_params[self.param_hp] = {
            "visible": 1,
        }
        self.member_params[self.param_max_hp] = {
            "visible": 1,
        }
        self.script_append("joined", 'set member.%s = member.%s' % (self.param_max_hp, self.param_hp))
        self.script_append("actions-stopped-member", 'if member.active and member.%s <= 0 { set member.active = 0 log \'%s\' cls="dead" sound "//%s/st/sounds/death.mp3" mode="wait" }' % (self.param_hp, self._('{class="combat-log-member"}{member.name}{/class} {class="combat-log-dead"}has died{/class}'), self.app().canonical_domain))

    def store_xp(self, config):
        m = re_valid_parameter.match(self.param_xp)
        param = self.call("characters.param", m.group(1))
        if not param:
            # register new parameter
            params = config.get("characters.params", [])[:]
            order = 0.0
            for p in params:
                if p["order"] > order:
                    order = p["order"]
            order += 10.0
            params.append({
                "code": m.group(1),
                "order": order,
                "name": self._("Experience"),
                "name_g": self._("genitive///Experience"),
                "owner_visible": True,
                "zero_visible": True,
                "important": True,
                "public": True,
                "condition": 1,
                "description": self._("This parameter defines amount of experience gained in combats"),
                "grp": self._("characters///Combat parameters"),
                "type": 0,
                "visual_mode": 0,
                "library_visible": True,
            })
            config.set("characters.params", params)
            self.call("admin-characters.params-stored", params, config)

    def store_hp(self, config):
        m = re_valid_parameter.match(self.param_hp)
        param = self.call("characters.param", m.group(1))
        if not param:
            # register new parameter
            params = config.get("characters.params", [])[:]
            order = 0.0
            for p in params:
                if p["order"] > order:
                    order = p["order"]
            order += 10.0
            params.append({
                "code": m.group(1),
                "order": order,
                "name": self._("Hitpoints"),
                "name_g": self._("genitive///Hitpoints"),
                "owner_visible": True,
                "zero_visible": True,
                "important": True,
                "public": True,
                "condition": 1,
                "description": self._("This parameter defines amount of damage that the character can get in the combat before died"),
                "grp": self._("characters///Combat parameters"),
                "type": 1,
                "expression": 30,
                "visual_mode": 0,
                "library_visible": True,
            })
            config.set("characters.params", params)
            self.call("admin-characters.params-stored", params, config)

    def form_render_damage(self, fields):
        fields.extend([
            {"type": "header", "html": self._("Damage and defense modifiers")},
            {"name": "param_damage", "label": self._("Member parameter holding its damage"), "value": "p_damage"},
            {"name": "param_defense", "label": self._("Member parameter holding its defense"), "value": "p_defense"},
        ])

    def form_parse_damage(self, errors):
        req = self.req()
        # param_damage
        param_damage = req.param("param_damage")
        if not param_damage:
            errors["param_damage"] = self._("This field is mandatory")
        elif not re_valid_parameter.match(param_damage):
            errors["param_damage"] = self._("Parameter name must start with 'p_' and contain latin letters, digits and underscores only")
        else:
            self.param_damage = param_damage
        # param_defense
        param_defense = req.param("param_defense")
        if not param_defense:
            errors["param_defense"] = self._("This field is mandatory")
        elif not re_valid_parameter.match(param_defense):
            errors["param_defense"] = self._("Parameter name must start with 'p_' and contain latin letters, digits and underscores only")
        else:
            self.param_defense = param_defense

    def generate_damage(self):
        self.script_append("joined", 'set member.p_inflicted_damage = 0')

    def store_damage(self, config):
        # register new parameter
        params = config.get("characters.params", [])[:]
        order = 0.0
        for p in params:
            if p["order"] > order:
                order = p["order"]
        order += 10.0
        anything_changed = False
        m = re_valid_parameter.match(self.param_damage)
        param = self.call("characters.param", m.group(1))
        if not param:
            params.append({
                "code": m.group(1),
                "order": order,
                "name": self._("Damage"),
                "name_g": self._("genitive///Damage"),
                "owner_visible": True,
                "zero_visible": True,
                "important": True,
                "public": True,
                "condition": 1,
                "description": self._("Shows how much damage inflicted by the character is increased"),
                "grp": self._("characters///Combat parameters"),
                "type": 1,
                "expression": 0,
                "visual_mode": 0,
                "library_visible": True,
            })
            anything_changed = True
        m = re_valid_parameter.match(self.param_defense)
        param = self.call("characters.param", m.group(1))
        if not param:
            params.append({
                "code": m.group(1),
                "order": order,
                "name": self._("Defense"),
                "name_g": self._("genitive///Defense"),
                "owner_visible": True,
                "zero_visible": True,
                "important": True,
                "public": True,
                "condition": 1,
                "description": self._("Shows how much damage inflicted to the character is decreased"),
                "grp": self._("characters///Combat parameters"),
                "type": 1,
                "expression": 0,
                "visual_mode": 0,
                "library_visible": True,
            })
            anything_changed = True
        if anything_changed:
            config.set("characters.params", params)
            self.call("admin-characters.params-stored", params, config)

    def generate_selectable_targets(self):
        self.script_append("joined", 'set member.targets = "selectable"')

class AttackBlock(CombatRulesDialog):
    def __init__(self, app, fqn="mg.mmorpg.combats.wizards.AttackBlock"):
        CombatRulesDialog.__init__(self, app, fqn)

    def form_render(self, fields):
        CombatRulesDialog.form_render(self, fields)
        self.form_render_hp(fields)
        self.form_render_damage(fields)
        fields.extend([
            {"type": "header", "html": self._("Strike parameters")},
            {"name": "strike_name", "label": self._("Strike action name"), "value": self._("actionname///Strike")},
            {"name": "strike_action", "label": self._("Strike action text in the combat log"), "value": self._('{class="combat-log-attack"}has striked{/class} {class="combat-log-member"}{target.name}{/class} in {a_attack_zone == 1 ? "head" : a_attack_zone == 2 ? "chest" : a_attack_zone == 4 ? "waist" : a_attack_zone == 8 ? "legs" : a_attack_zone}')},
            {"name": "strike_failed_action", "label": self._("Strike action failed text in the combat log"), "value": self._('{class="combat-log-attack"}could not strike{/class} {class="combat-log-member"}{target.name}{/class} in blocked {a_attack_zone == 1 ? "head" : a_attack_zone == 2 ? "chest" : a_attack_zone == 4 ? "waist" : a_attack_zone == 8 ? "legs" : a_attack_zone}')},
            {"name": "default_damage", "label": self._("Strike default damage"), "value": 5},
            {"type": "header", "html": self._("Heal parameters")},
            {"name": "heal_name", "label": self._("Heal action name"), "value": self._("actionname///Heal")},
            {"name": "heal_action", "label": self._("Heal action text in the combat log"), "value": self._('{class="combat-log-heal"}has healed{/class} {class="combat-log-member"}{target.name}{/class}')},
            {"name": "heal_value", "label": self._("Heal amount"), "value": 3},
        ])

    def form_parse(self, errors):
        CombatRulesDialog.form_parse(self, errors)
        self.form_parse_hp(errors)
        self.form_parse_damage(errors)
        req = self.req()
        # strike_name
        strike_name = req.param("strike_name").strip()
        if not strike_name:
            errors["strike_name"] = self._("This field is mandatory")
        else:
            self.strike_name = strike_name
        # strike_action
        strike_action = req.param("strike_action").strip()
        if not strike_action:
            errors["strike_action"] = self._("This field is mandatory")
        else:
            self.strike_action = strike_action
        # strike_failed_action
        strike_failed_action = req.param("strike_failed_action").strip()
        if not strike_failed_action:
            errors["strike_failed_action"] = self._("This field is mandatory")
        else:
            self.strike_failed_action = strike_failed_action
        # default_damage
        default_damage = req.param("default_damage").strip()
        if not valid_nonnegative_int(default_damage):
            errors["default_damage"] = self._("This field must be a valid nonnegative integer")
        else:
            self.default_damage = intz(default_damage)
        # heal_name
        heal_name = req.param("heal_name").strip()
        if not heal_name:
            errors["heal_name"] = self._("This field is mandatory")
        else:
            self.heal_name = heal_name
        # heal_action
        heal_action = req.param("heal_action").strip()
        if not heal_action:
            errors["heal_action"] = self._("This field is mandatory")
        else:
            self.heal_action = heal_action
        # heal_value
        heal_value = req.param("heal_value").strip()
        if not valid_nonnegative_int(heal_value):
            errors["heal_value"] = self._("This field must be a valid nonnegative integer")
        else:
            self.heal_value = intz(heal_value)

    def generate(self):
        CombatRulesDialog.generate(self)
        self.rules["turn_order"] = "pair-exchanges"
        self.rules["time_mode"] = "begin"
        self.rules["time_format"] = "realhhmmss"
        self.generate_hp()
        self.generate_damage()
        self.ai_types.append({
            "code": "default",
            "order": 0.0,
            "name": self._("Basic AI algorithm"),
            "script-turn-got": self.call("combats-admin.parse-script", 'randomaction member "strike: 1" a_attack_zone=selrand(1, 2, 4, 8) a_defend_zone=selrand(3, 6, 12)'),
        })
        script_end_target = 'if a_pair and a_pair.a_defend_zone & a_attack_zone { log \'%s\' cls="attack" sound "//%s/st/sounds/strike-miss.mp3" mode="wait" } else { set local.damage = max(1, %d + source.%s - target.%s) syslog \'<b>[{combat.now}]</b> Strike: source=<b>{source.id}</b>, target=<b>{target.id}</b>, base_damage=<b>%d</b>, damage_mod=<b>{source.%s}</b>, defense_mod=<b>{target.%s}</b>, result_damage=<b>{local.damage}</b>\' damage target.%s value local.damage maxval=target.%s set source.p_inflicted_damage = source.p_inflicted_damage + last_damage log \'%s\' cls="attack" sound "//%s/st/sounds/strike-hit.mp3" mode="wait" }' % (('{class="combat-log-member"}{source.name}{/class} %s' % self.strike_failed_action), self.app().canonical_domain, self.default_damage, self.param_damage, self.param_defense, self.default_damage, self.param_damage, self.param_defense, self.param_hp, self.param_max_hp, ('{class="combat-log-member"}{source.name}{/class} %s <span class="combat-log-damage">-{local.damage}</span> <span class="combat-log-hp">[{target.%s}/{target.%s}]</span>' % (self.strike_action, self.param_hp, self.param_max_hp)), self.app().canonical_domain)
        script_enqueued = 'syslog \'<b>[{combat.now}]</b> Enqueued: source=<b>{source.id}</b> ({source.name}), targets=<b>{source.targets}</b>, attack=<b>{a_attack_zone}</b>, defend=<b>{a_defend_zone}</b>\''
        self.actions.append({
            "code": "strike",
            "name": self.strike_name,
            "description": self.call("script.parse-text", self._('Strike opponent<br />\nDamage: <b>{damage}</b>').format(damage=self.default_damage)),
            "order": 0.0,
            "available": 1,
            "targets": "enemies",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 1,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "script-enqueued": self.call("combats-admin.parse-script", script_enqueued),
            "attributes": [
                {
                    "code": "a_attack_zone",
                    "order": 0.0,
                    "name": self._("Zone to attack"),
                    "type": "static",
                    "values": [
                        {"code": "1", "title": self._("Head")},
                        {"code": "2", "title": self._("Chest")},
                        {"code": "4", "title": self._("Waist")},
                        {"code": "8", "title": self._("Legs")},
                    ]
                },
                {
                    "code": "a_defend_zone",
                    "order": 10.0,
                    "name": self._("Zones to defend"),
                    "type": "static",
                    "values": [
                        {"code": "3", "title": self._("Head and chest")},
                        {"code": "6", "title": self._("Chest and waist")},
                        {"code": "12", "title": self._("Waist and legs")},
                    ]
                },
            ],
        })
        script_end_target = 'set source.p_healed = source.p_healed + 1 set local.heal = %d syslog \'<b>[{combat.now}]</b> Heal: source=<b>{source.id}</b>, target=<b>{target.id}</b>, result_heal=<b>{local.heal}</b>\' heal target.%s value local.heal maxval=target.%s log \'%s\' cls="heal"' % (self.heal_value, self.param_hp, self.param_max_hp, ('{class="combat-log-member"}{source.name}{/class} %s <span class="combat-log-heal">+{local.heal}</span> <span class="combat-log-hp">[{target.%s}/{target.%s}]</span>' % (self.heal_action, self.param_hp, self.param_max_hp)))
        self.actions.append({
            "code": "heal",
            "name": self.heal_name,
            "description": self.call("script.parse-text", self._('Heal any allied member<br />\nValue: <b>{value}</b>').format(value=self.heal_value)),
            "order": 10.0,
            "available": self.call("script.parse-expression", "member.p_healed < 3"),
            "targets": "allies-myself",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 1,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "immediate": True,
            "ignore_preselected": True,
        })

    def store(self, config):
        CombatRulesDialog.store(self, config)
        self.store_hp(config)
        self.store_xp(config)
        self.store_damage(config)

class RoundRobin(CombatRulesDialog):
    def __init__(self, app, fqn="mg.mmorpg.combats.wizards.RoundRobin"):
        CombatRulesDialog.__init__(self, app, fqn)

    def form_render(self, fields):
        CombatRulesDialog.form_render(self, fields)
        self.form_render_hp(fields)
        self.form_render_damage(fields)
        fields.extend([
            {"type": "header", "html": self._("Strike parameters")},
            {"name": "strike_name", "label": self._("Strike action name"), "value": self._("actionname///Strike")},
            {"name": "strike_action", "label": self._("Strike action text in the combat log"), "value": self._('{class="combat-log-attack"}has striked{/class}')},
            {"name": "default_damage", "label": self._("Strike default damage"), "value": 5},
            {"type": "header", "html": self._("Heal parameters")},
            {"name": "heal_name", "label": self._("Heal action name"), "value": self._("actionname///Heal")},
            {"name": "heal_action", "label": self._("Heal action text in the combat log"), "value": self._('{class="combat-log-heal"}has healed{/class} {class="combat-log-member"}{target.name}{/class}')},
            {"name": "heal_value", "label": self._("Heal amount"), "value": 3},
        ])

    def form_parse(self, errors):
        CombatRulesDialog.form_parse(self, errors)
        self.form_parse_hp(errors)
        self.form_parse_damage(errors)
        req = self.req()
        # strike_name
        strike_name = req.param("strike_name").strip()
        if not strike_name:
            errors["strike_name"] = self._("This field is mandatory")
        else:
            self.strike_name = strike_name
        # strike_action
        strike_action = req.param("strike_action").strip()
        if not strike_action:
            errors["strike_action"] = self._("This field is mandatory")
        else:
            self.strike_action = strike_action
        # default_damage
        default_damage = req.param("default_damage").strip()
        if not valid_nonnegative_int(default_damage):
            errors["default_damage"] = self._("This field must be a valid nonnegative integer")
        else:
            self.default_damage = intz(default_damage)
        # heal_name
        heal_name = req.param("heal_name").strip()
        if not heal_name:
            errors["heal_name"] = self._("This field is mandatory")
        else:
            self.heal_name = heal_name
        # heal_action
        heal_action = req.param("heal_action").strip()
        if not heal_action:
            errors["heal_action"] = self._("This field is mandatory")
        else:
            self.heal_action = heal_action
        # heal_value
        heal_value = req.param("heal_value").strip()
        if not valid_nonnegative_int(heal_value):
            errors["heal_value"] = self._("This field must be a valid nonnegative integer")
        else:
            self.heal_value = intz(heal_value)

    def generate(self):
        CombatRulesDialog.generate(self)
        self.rules["turn_order"] = "round-robin"
        self.rules["time_mode"] = "begin"
        self.rules["time_format"] = "mmss"
        self.generate_hp()
        self.generate_damage()
        self.generate_selectable_targets()
        self.ai_types.append({
            "code": "default",
            "order": 0.0,
            "name": self._("Basic AI algorithm"),
            "script-turn-got": self.call("combats-admin.parse-script", 'randomaction member "strike: 2, heal: 1"'),
        })
        script_end_target = 'set local.damage = max(1, %d + source.%s - target.%s) syslog \'<b>[{combat.now}]</b> Strike: source=<b>{source.id}</b>, target=<b>{target.id}</b>, base_damage=<b>%d</b>, damage_mod=<b>{source.%s}</b>, defense_mod=<b>{target.%s}</b>, result_damage=<b>{local.damage}</b>\' damage target.%s value local.damage maxval=target.%s set source.p_inflicted_damage = source.p_inflicted_damage + last_damage sound "//%s/st/sounds/strike-hit.mp3" mode="wait"' % (self.default_damage, self.param_damage, self.param_defense, self.default_damage, self.param_damage, self.param_defense, self.param_hp, self.param_max_hp, self.app().canonical_domain)
        script_end = 'log \'%s\' cls="attack" turn "done"' % ('{class="combat-log-member"}{source.name}{/class} %s {action_log}' % self.strike_action)
        self.actions.append({
            "code": "strike",
            "name": self.strike_name,
            "description": self.call("script.parse-text", self._('Strike opponents<br />\nDamage: <b>{damage}</b><br />\nMaximal number of targets: <b>2</b>').format(damage=self.default_damage)),
            "order": 0.0,
            "available": 1,
            "targets": "enemies",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 2,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "script-end": self.call("combats-admin.parse-script", script_end),
        })
        script_end_target = 'set source.p_healed = source.p_healed + 1 set local.heal = %d syslog \'<b>[{combat.now}]</b> Heal: source=<b>{source.id}</b>, target=<b>{target.id}</b>, result_heal=<b>{local.heal}</b>\' heal target.%s value local.heal maxval=target.%s log \'%s\' cls="heal"' % (self.heal_value, self.param_hp, self.param_max_hp, ('{class="combat-log-member"}{source.name}{/class} %s <span class="combat-log-heal">+{local.heal}</span> <span class="combat-log-hp">[{target.%s}/{target.%s}]</span>' % (self.heal_action, self.param_hp, self.param_max_hp)))
        script_end = 'turn "done"'
        self.actions.append({
            "code": "heal",
            "name": self.heal_name,
            "description": self.call("script.parse-text", self._('Heal any allied member<br />\nValue: <b>{value}</b>').format(value=self.heal_value)),
            "order": 10.0,
            "available": self.call("script.parse-expression", "member.p_healed < 3"),
            "targets": "allies-myself",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 1,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "script-end": self.call("combats-admin.parse-script", script_end),
        })

    def store(self, config):
        CombatRulesDialog.store(self, config)
        self.store_hp(config)
        self.store_xp(config)
        self.store_damage(config)

class TimeLine(CombatRulesDialog):
    def __init__(self, app, fqn="mg.mmorpg.combats.wizards.TimeLine"):
        CombatRulesDialog.__init__(self, app, fqn)

    def form_render(self, fields):
        CombatRulesDialog.form_render(self, fields)
        self.form_render_hp(fields)
        self.form_render_damage(fields)
        fields.extend([
            {"type": "header", "html": self._("Parameters of the strikes")},
            {"name": "short_strike_name", "label": self._("Short strike action name"), "value": self._("actionname///Short strike")},
            {"name": "short_strike_action", "label": self._("Short strike action text in the combat log"), "value": self._('{class="combat-log-attack"}has striked {/class} {class="combat-log-member"}{target.name}{/class} short')},
            {"name": "short_default_damage", "label": self._("Short strike default damage"), "value": 5},
            {"name": "short_default_duration", "label": self._("Short strike duration"), "value": 3},
            {"name": "long_strike_name", "label": self._("Long strike action name"), "value": self._("actionname///Long strike")},
            {"name": "long_strike_action", "label": self._("Long strike action text in the combat log"), "value": self._('{class="combat-log-attack"}has striked {/class} {class="combat-log-member"}{target.name}{/class} long')},
            {"name": "long_default_damage", "label": self._("Long strike default damage"), "value": 9},
            {"name": "long_default_duration", "label": self._("Long strike duration"), "value": 5},
            {"type": "header", "html": self._("Heal parameters")},
            {"name": "heal_name", "label": self._("Heal action name"), "value": self._("actionname///Heal")},
            {"name": "heal_action", "label": self._("Heal action text in the combat log"), "value": self._('{class="combat-log-heal"}has healed{/class} {class="combat-log-member"}{target.name}{/class}')},
            {"name": "heal_value", "label": self._("Heal amount"), "value": 3},
            {"name": "heal_duration", "label": self._("Heal duration"), "value": 2},
        ])

    def form_parse(self, errors):
        CombatRulesDialog.form_parse(self, errors)
        self.form_parse_hp(errors)
        self.form_parse_damage(errors)
        req = self.req()
        # short_strike_name
        short_strike_name = req.param("short_strike_name").strip()
        if not short_strike_name:
            errors["short_strike_name"] = self._("This field is mandatory")
        else:
            self.short_strike_name = short_strike_name
        # short_strike_action
        short_strike_action = req.param("short_strike_action").strip()
        if not short_strike_action:
            errors["short_strike_action"] = self._("This field is mandatory")
        else:
            self.short_strike_action = short_strike_action
        # short_default_damage
        short_default_damage = req.param("short_default_damage").strip()
        if not valid_nonnegative_int(short_default_damage):
            errors["short_default_damage"] = self._("This field must be a valid nonnegative integer")
        else:
            self.short_default_damage = intz(short_default_damage)
        # short_default_duration
        short_default_duration = req.param("short_default_duration").strip()
        if not valid_nonnegative_int(short_default_duration):
            errors["short_default_duration"] = self._("This field must be a valid nonnegative integer")
        else:
            self.short_default_duration = intz(short_default_duration)
        # long_strike_name
        long_strike_name = req.param("long_strike_name").strip()
        if not long_strike_name:
            errors["long_strike_name"] = self._("This field is mandatory")
        else:
            self.long_strike_name = long_strike_name
        # long_strike_action
        long_strike_action = req.param("long_strike_action").strip()
        if not long_strike_action:
            errors["long_strike_action"] = self._("This field is mandatory")
        else:
            self.long_strike_action = long_strike_action
        # long_default_damage
        long_default_damage = req.param("long_default_damage").strip()
        if not valid_nonnegative_int(long_default_damage):
            errors["long_default_damage"] = self._("This field must be a valid nonnegative integer")
        else:
            self.long_default_damage = intz(long_default_damage)
        # long_default_duration
        long_default_duration = req.param("long_default_duration").strip()
        if not valid_nonnegative_int(long_default_duration):
            errors["long_default_duration"] = self._("This field must be a valid nonnegative integer")
        else:
            self.long_default_duration = intz(long_default_duration)
        # heal_name
        heal_name = req.param("heal_name").strip()
        if not heal_name:
            errors["heal_name"] = self._("This field is mandatory")
        else:
            self.heal_name = heal_name
        # heal_action
        heal_action = req.param("heal_action").strip()
        if not heal_action:
            errors["heal_action"] = self._("This field is mandatory")
        else:
            self.heal_action = heal_action
        # heal_value
        heal_value = req.param("heal_value").strip()
        if not valid_nonnegative_int(heal_value):
            errors["heal_value"] = self._("This field must be a valid nonnegative integer")
        else:
            self.heal_value = intz(heal_value)
        # heal_duration
        heal_duration = req.param("heal_duration").strip()
        if not valid_nonnegative_int(heal_duration):
            errors["heal_duration"] = self._("This field must be a valid nonnegative integer")
        else:
            self.heal_duration = intz(heal_duration)

    def generate(self):
        CombatRulesDialog.generate(self)
        self.rules["turn_order"] = "time-line"
        self.rules["time_mode"] = "begin"
        self.rules["time_format"] = "mmss"
        self.generate_hp()
        self.generate_damage()
        self.generate_selectable_targets()
        self.ai_types.append({
            "code": "default",
            "order": 0.0,
            "name": self._("Basic AI algorithm"),
            "script-turn-got": self.call("combats-admin.parse-script", 'randomaction member "short_strike: 2, long_strike: 2, heal: 1"'),
        })
        # short strike
        script_end_target = 'set local.damage = max(1, %d + source.%s - target.%s) syslog \'<b>[{combat.now}]</b> Short strike: source=<b>{source.id}</b>, target=<b>{target.id}</b>, base_damage=<b>%d</b>, damage_mod=<b>{source.%s}</b>, defense_mod=<b>{target.%s}</b>, result_damage=<b>{local.damage}</b>\' damage target.%s value local.damage maxval=target.%s set source.p_inflicted_damage = source.p_inflicted_damage + last_damage log \'%s\' cls="attack" sound "//%s/st/sounds/strike-hit.mp3" mode="wait"' % (self.short_default_damage, self.param_damage, self.param_defense, self.short_default_damage, self.param_damage, self.param_defense, self.param_hp, self.param_max_hp, ('{class="combat-log-member"}{source.name}{/class} %s <span class="combat-log-damage">-{local.damage}</span> <span class="combat-log-hp">[{target.%s}/{target.%s}]</span>' % (self.short_strike_action, self.param_hp, self.param_max_hp)), self.app().canonical_domain)
        self.actions.append({
            "code": "short_strike",
            "name": self.short_strike_name,
            "description": self.call("script.parse-text", self._('Strike opponents<br />\nDamage: <b>{damage}</b><br />\nMaximal number of targets: <b>2</b><br />\nDuration: <b>{duration}</b>').format(damage=self.short_default_damage, duration=self.short_default_duration)),
            "order": 0.0,
            "available": 1,
            "targets": "enemies",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 2,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "duration": self.short_default_duration,
        })
        # long strike
        script_end_target = 'set local.damage = max(1, %d + source.%s - target.%s) syslog \'<b>[{combat.now}]</b> Long strike: source=<b>{source.id}</b>, target=<b>{target.id}</b>, base_damage=<b>%d</b>, damage_mod=<b>{source.%s}</b>, defense_mod=<b>{target.%s}</b>, result_damage=<b>{local.damage}</b>\' damage target.%s value local.damage maxval=target.%s set source.p_inflicted_damage = source.p_inflicted_damage + last_damage log \'%s\' cls="attack" sound "//%s/st/sounds/strike-hit.mp3" mode="wait"' % (self.long_default_damage, self.param_damage, self.param_defense, self.long_default_damage, self.param_damage, self.param_defense, self.param_hp, self.param_max_hp, ('{class="combat-log-member"}{source.name}{/class} %s <span class="combat-log-damage">-{local.damage}</span> <span class="combat-log-hp">[{target.%s}/{target.%s}]</span>' % (self.long_strike_action, self.param_hp, self.param_max_hp)), self.app().canonical_domain)
        self.actions.append({
            "code": "long_strike",
            "name": self.long_strike_name,
            "description": self.call("script.parse-text", self._('Strike opponents<br />\nDamage: <b>{damage}</b><br />\nMaximal number of targets: <b>2</b><br />\nDuration: <b>{duration}</b>').format(damage=self.long_default_damage, duration=self.long_default_duration)),
            "order": 10.0,
            "available": 1,
            "targets": "enemies",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 2,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "duration": self.long_default_duration,
        })
        # heal
        script_end_target = 'set local.heal = %d syslog \'<b>[{combat.now}]</b> Heal: source=<b>{source.id}</b>, target=<b>{target.id}</b>, result_heal=<b>{local.heal}</b>\' heal target.%s value local.heal maxval=target.%s log \'%s\' cls="heal"' % (self.heal_value, self.param_hp, self.param_max_hp, ('{class="combat-log-member"}{source.name}{/class} %s <span class="combat-log-heal">+{local.heal}</span> <span class="combat-log-hp">[{target.%s}/{target.%s}]</span>' % (self.heal_action, self.param_hp, self.param_max_hp)))
        self.actions.append({
            "code": "heal",
            "name": self.heal_name,
            "description": self.call("script.parse-text", self._('Heal any allied member<br />\nValue: <b>{value}</b><br />\nDuration: <b>{duration}</b>').format(value=self.heal_value, duration=self.heal_duration)),
            "order": 20.0,
            "available": 1,
            "targets": "allies-myself",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 1,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "duration": self.heal_duration,
        })
        # timeout rule
        self.script_append("turntimeout", 'if member.active { giveturn member randomaction member "short_strike: 2, long_strike: 2, heal: 1" }')

    def store(self, config):
        CombatRulesDialog.store(self, config)
        self.store_hp(config)
        self.store_xp(config)
        self.store_damage(config)

class ActionPoints(CombatRulesDialog):
    def __init__(self, app, fqn="mg.mmorpg.combats.wizards.RoundRobin"):
        CombatRulesDialog.__init__(self, app, fqn)

    def form_render(self, fields):
        CombatRulesDialog.form_render(self, fields)
        self.form_render_hp(fields)
        self.form_render_damage(fields)
        fields.extend([
            {"type": "header", "html": self._("Action points")},
            {"name": "action_points", "label": self._("Number of actions points per turn"), "value": 6},
            {"type": "header", "html": self._("Parameters of the strikes")},
            {"name": "short_strike_name", "label": self._("Short strike action name"), "value": self._("actionname///Short strike")},
            {"name": "short_strike_action", "label": self._("Short strike action text in the combat log"), "value": self._('{class="combat-log-attack"}has striked short{/class}')},
            {"name": "short_default_damage", "label": self._("Short strike default damage"), "value": 5},
            {"name": "short_action_points", "label": self._("Short strike action points"), "value": 3},
            {"name": "long_strike_name", "label": self._("Long strike action name"), "value": self._("actionname///Long strike")},
            {"name": "long_strike_action", "label": self._("Long strike action text in the combat log"), "value": self._('{class="combat-log-attack"}has striked long{/class}')},
            {"name": "long_default_damage", "label": self._("Long strike default damage"), "value": 11},
            {"name": "long_action_points", "label": self._("Long strike action points"), "value": 5},
            {"type": "header", "html": self._("Heal parameters")},
            {"name": "heal_name", "label": self._("Heal action name"), "value": self._("actionname///Heal")},
            {"name": "heal_action", "label": self._("Heal action text in the combat log"), "value": self._('{class="combat-log-heal"}has healed{/class}')},
            {"name": "heal_value", "label": self._("Heal amount"), "value": 3},
            {"name": "heal_action_points", "label": self._("Heal action points"), "value": 2},
        ])

    def form_parse(self, errors):
        CombatRulesDialog.form_parse(self, errors)
        self.form_parse_hp(errors)
        self.form_parse_damage(errors)
        req = self.req()
        # action_points
        action_points = req.param("action_points").strip()
        if not valid_nonnegative_int(action_points):
            errors["action_points"] = self._("This field must be a valid nonnegative integer")
        else:
            self.action_points = intz(action_points)
        # short_strike_name
        short_strike_name = req.param("short_strike_name").strip()
        if not short_strike_name:
            errors["short_strike_name"] = self._("This field is mandatory")
        else:
            self.short_strike_name = short_strike_name
        # short_strike_action
        short_strike_action = req.param("short_strike_action").strip()
        if not short_strike_action:
            errors["short_strike_action"] = self._("This field is mandatory")
        else:
            self.short_strike_action = short_strike_action
        # short_default_damage
        short_default_damage = req.param("short_default_damage").strip()
        if not valid_nonnegative_int(short_default_damage):
            errors["short_default_damage"] = self._("This field must be a valid nonnegative integer")
        else:
            self.short_default_damage = intz(short_default_damage)
        # short_action_points
        short_action_points = req.param("short_action_points").strip()
        if not valid_nonnegative_int(short_action_points):
            errors["short_action_points"] = self._("This field must be a valid nonnegative integer")
        else:
            self.short_action_points = intz(short_action_points)
        # long_strike_name
        long_strike_name = req.param("long_strike_name").strip()
        if not long_strike_name:
            errors["long_strike_name"] = self._("This field is mandatory")
        else:
            self.long_strike_name = long_strike_name
        # long_strike_action
        long_strike_action = req.param("long_strike_action").strip()
        if not long_strike_action:
            errors["long_strike_action"] = self._("This field is mandatory")
        else:
            self.long_strike_action = long_strike_action
        # long_default_damage
        long_default_damage = req.param("long_default_damage").strip()
        if not valid_nonnegative_int(long_default_damage):
            errors["long_default_damage"] = self._("This field must be a valid nonnegative integer")
        else:
            self.long_default_damage = intz(long_default_damage)
        # long_action_points
        long_action_points = req.param("long_action_points").strip()
        if not valid_nonnegative_int(long_action_points):
            errors["long_action_points"] = self._("This field must be a valid nonnegative integer")
        else:
            self.long_action_points = intz(long_action_points)
        # heal_name
        heal_name = req.param("heal_name").strip()
        if not heal_name:
            errors["heal_name"] = self._("This field is mandatory")
        else:
            self.heal_name = heal_name
        # heal_action
        heal_action = req.param("heal_action").strip()
        if not heal_action:
            errors["heal_action"] = self._("This field is mandatory")
        else:
            self.heal_action = heal_action
        # heal_value
        heal_value = req.param("heal_value").strip()
        if not valid_nonnegative_int(heal_value):
            errors["heal_value"] = self._("This field must be a valid nonnegative integer")
        else:
            self.heal_value = intz(heal_value)
        # heal_action_points
        heal_action_points = req.param("heal_action_points").strip()
        if not valid_nonnegative_int(heal_action_points):
            errors["heal_action_points"] = self._("This field must be a valid nonnegative integer")
        else:
            self.heal_action_points = intz(heal_action_points)

    def generate(self):
        CombatRulesDialog.generate(self)
        self.rules["turn_order"] = "round-robin"
        self.rules["time_mode"] = "begin"
        self.rules["time_format"] = "mmss"
        self.generate_hp()
        self.generate_damage()
        self.generate_selectable_targets()
        self.ai_types.append({
            "code": "default",
            "order": 0.0,
            "name": self._("Basic AI algorithm"),
            "script-turn-got": self.call("combats-admin.parse-script", 'randomaction member "long_strike: 3, short_strike: 2, heal: 1"'),
        })
        # short strike
        script_end_target = 'set local.damage = max(1, %d + source.%s - target.%s) syslog \'<b>[{combat.now}]</b> Short strike: source=<b>{source.id}</b>, target=<b>{target.id}</b>, base_damage=<b>%d</b>, damage_mod=<b>{source.%s}</b>, defense_mod=<b>{target.%s}</b>, result_damage=<b>{local.damage}</b>\' damage target.%s value local.damage maxval=target.%s set source.p_inflicted_damage = source.p_inflicted_damage + last_damage sound "//%s/st/sounds/strike-hit.mp3" mode="wait"' % (self.short_default_damage, self.param_damage, self.param_defense, self.short_default_damage, self.param_damage, self.param_defense, self.param_hp, self.param_max_hp, self.app().canonical_domain)
        script_end = 'log \'%s\' cls="attack" set source.p_ap = source.p_ap - %d if source.p_ap < 2 { turn "done" }' % ('{class="combat-log-member"}{source.name}{/class} %s {action_log}' % self.short_strike_action, self.short_action_points)
        self.actions.append({
            "code": "short_strike",
            "name": self.short_strike_name,
            "description": self.call("script.parse-text", self._('Strike opponent<br />\nDamage: <b>{damage}</b><br />\nAction points: <b>{action_points}</b>').format(damage=self.short_default_damage, action_points=self.short_action_points)),
            "order": 0.0,
            "available": self.call("script.parse-expression", 'member.p_ap >= %d' % self.short_action_points),
            "targets": "enemies",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 1,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "script-end": self.call("combats-admin.parse-script", script_end),
        })
        # long strike
        script_end_target = 'set local.damage = max(1, %d + source.%s - target.%s) syslog \'<b>[{combat.now}]</b> Long strike: source=<b>{source.id}</b>, target=<b>{target.id}</b>, base_damage=<b>%d</b>, damage_mod=<b>{source.%s}</b>, defense_mod=<b>{target.%s}</b>, result_damage=<b>{local.damage}</b>\' damage target.%s value local.damage maxval=target.%s set source.p_inflicted_damage = source.p_inflicted_damage + last_damage sound "//%s/st/sounds/strike-hit.mp3" mode="wait"' % (self.long_default_damage, self.param_damage, self.param_defense, self.long_default_damage, self.param_damage, self.param_defense, self.param_hp, self.param_max_hp, self.app().canonical_domain)
        script_end = 'log \'%s\' cls="attack" set source.p_ap = source.p_ap - %d if source.p_ap < 2 { turn "done" }' % ('{class="combat-log-member"}{source.name}{/class} %s {action_log}' % self.long_strike_action, self.long_action_points)
        self.actions.append({
            "code": "long_strike",
            "name": self.long_strike_name,
            "description": self.call("script.parse-text", self._('Strike opponent<br />\nDamage: <b>{damage}</b><br />\nAction points: <b>{action_points}</b>').format(damage=self.long_default_damage, action_points=self.long_action_points)),
            "order": 10.0,
            "available": self.call("script.parse-expression", 'member.p_ap >= %d' % self.long_action_points),
            "targets": "enemies",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 1,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "script-end": self.call("combats-admin.parse-script", script_end),
        })
        # heal
        script_end_target = 'set source.p_healed = source.p_healed + 1 set local.heal = %d syslog \'<b>[{combat.now}]</b> Heal: source=<b>{source.id}</b>, target=<b>{target.id}</b>, result_heal=<b>{local.heal}</b>\' heal target.%s value local.heal maxval=target.%s' % (self.heal_value, self.param_hp, self.param_max_hp)
        script_end = 'log \'%s\' cls="heal" set source.p_ap = source.p_ap - %d if source.p_ap < 2 { turn "done" }' % (('{class="combat-log-member"}{source.name}{/class} %s {action_log}' % self.heal_action), self.heal_action_points)
        self.actions.append({
            "code": "heal",
            "name": self.heal_name,
            "description": self.call("script.parse-text", self._('Heal any allied member<br />\nValue: <b>{value}</b><br />\nAction points: <b>{action_points}</b>').format(value=self.heal_value, action_points=self.heal_action_points)),
            "order": 20.0,
            "available": self.call("script.parse-expression", 'member.p_ap >= %d' % self.heal_action_points),
            "targets": "allies-myself",
            "target_all": True,
            "targets_min": 1,
            "targets_max": 1,
            "script-end-target": self.call("combats-admin.parse-script", script_end_target),
            "script-end": self.call("combats-admin.parse-script", script_end),
        })
        self.script_append("turngot", 'if new_turn { set member.p_ap = %d }' % self.action_points)

    def store(self, config):
        CombatRulesDialog.store(self, config)
        self.store_hp(config)
        self.store_xp(config)
        self.store_damage(config)

