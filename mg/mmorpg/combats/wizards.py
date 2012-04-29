from mg.constructor import *

class CombatRulesDialog(ConstructorModule):
    def register(self):
        self.rhook("admin-combats.types", self.types_list)

    def show(self):
        req = self.req()
        if req.ok() and req.param("form"):
            errors = {}
            # code
            code = req.param("code")
            if not code:
                errors["code"] = self._("This field is mandatory")
            elif not re_valid_identifier.match(code):
                errors["code"] = self._("Combat rules code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
            # name
            name = req.param("name")
            if not name:
                errors["name"] = self._("This field is mandatory")
            # processing errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # storing data
            self.call("web.response_json", {"success": False})
        fields = [
            {"name": "form", "value": 1, "type": "hidden"},
            {"name": "v_tp", "value": self.rules_type, "type": "hidden"},
            {"name": "code", "label": self._("Combat rules code")},
            {"name": "name", "label": self._("Combat rules name")},
        ]
        self.call("admin.form", fields=fields)

    def types_list(self, lst):
        lst.append({
            "id": self.rules_type,
            "name": self.rules_description,
            "dialog": self.__class__,
        })

class AttackBlock(CombatRulesDialog):
    def __init__(self, app, fqn="mg.mmorpg.combats.wizards.AttackBlock"):
        CombatRulesDialog.__init__(self, app, fqn)
        self.rules_type = "attack-block"
        self.rules_name = self._("Attack-block system")
        self.rules_description = self._("Attack-block system. Combat members choose arbitrary targets and zones being attacked or blocked")
