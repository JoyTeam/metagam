from mg.constructor import *
import re

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)

class CombatRulesDialogs(ConstructorModule):
    def register(self):
        self.rhook("admin-combats.types", self.types_list)

    def types_list(self, lst):
        lst.append({
            "id": "attack-block",
            "name": self.combat._textlog_ring
            "dialog": AttackBlock,
        })

class CombatRulesDialog(ConstructorModule):
    def show(self):
        req = self.req()
        rules = self.conf("combats.rules", {}).copy()
        if req.ok() and req.param("form"):
            errors = {}
            # code
            code = req.param("code")
            if not code:
                errors["code"] = self._("This field is mandatory")
            elif not re_valid_identifier.match(code):
                errors["code"] = self._("Combat rules code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
            elif code in rules:
                errors["code"] = self._("Combat rules with the same code already exist")
            # name
            name = req.param("name")
            if not name:
                errors["name"] = self._("This field is mandatory")
            # order
            order = floatz(req.param("order"))
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # storing data
            self.shortRules = rules[code] = {
                "name": name,
                "order": order,
            }
            self.rules = {}
            # custom fields
            self.form_parse(errors)
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store everything
            config = self.app().config_updater()
            config.set("combats.rules", self.shortRules)
            config.set("combats-%s.rules" % code, self.rules)
            config.store()
            self.call("admin.redirect", "combats/rules")
        order = None
        for code, info in rules.iteritems():
            if order is None or info["order"] > order:
                order = info["order"]
        if order is None:
            order = 0.0
        else:
            order += 10.0
        fields = [
            {"name": "form", "value": 1, "type": "hidden"},
            {"name": "v_tp", "value": self.rules_type, "type": "hidden"},
            {"name": "code", "label": self._("Combat rules code")},
            {"name": "order", "label": self._("Sorting order"), "value": order, "inline": True},
            {"name": "name", "label": self._("Combat rules name")},
        ]
        self.form_render(fields)
        self.call("admin.form", fields=fields)

    def form_parse(self, errors):
        dimensions = self.call("charimages.dimensions")
        if dimensions:
            self.rules["dim_avatar"] = [dimensions[0]["width"], dimensions[1]["height"]]
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
        self.rules["generic_gobutton_text"] = self._("button///Strike")

    def form_render(self, fields):
        pass

class AttackBlock(CombatRulesDialog):
    pass
