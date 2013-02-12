import mg.constructor
import mg
from mg.core.tools import *
from mg.mmorpg.combats.core import CombatUnavailable
from mg.mmorpg.combats.daemon import CombatInterface, DBRunningCombat, DBRunningCombatList
from mg.constructor.design import TemplateNotFound
from mg.mmorpg.combats.logs import CombatLogViewer
import json
import re

re_valid_uuid = re.compile(r'^[0-9a-f]{32}$')

class Combats(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-combat.interface", self.combat_interface, priv="logged")
        self.rhook("ext-combat.state", self.combat_state, priv="logged")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("combat.default-aboveavatar", self.default_aboveavatar)
        self.rhook("combat.default-belowavatar", self.default_belowavatar)
        self.rhook("ext-combat.action", self.combat_action, priv="logged")
        self.rhook("combat.unavailable-exception-char", self.unavailable_exception_char)
        self.rhook("ext-combat.handler", self.combat_log, priv="public")

    def child_modules(self):
        return [
            "mg.mmorpg.combats.wizards.AttackBlock",
            "mg.mmorpg.combats.scripts.CombatScripts",
            "mg.mmorpg.combats.daemon.CombatRunner",
            "mg.mmorpg.combats.characters.Combats",
            "mg.mmorpg.combats.admin.CombatsAdmin",
            "mg.mmorpg.combats.design.CombatInterface",
            "mg.mmorpg.combats.design.CombatInterfaceAdmin",
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
            # Show combat interface to user
            rules = self.conf("combats-%s.rules" % combat.rules, {})
            vars = {
                "combat": combat_id,
                "load_extjs": {
                    "full": True
                },
                "generic": rules.get("generic", 1),
            }
            if vars["generic"]:
                vars["generic_myavatar"] = rules.get("generic_myavatar", 1)
                if vars["generic_myavatar"]:
                    vars["generic_myavatar_width"] = rules.get("generic_myavatar_width", 300)
                    vars["generic_myavatar_resize"] = "true" if rules.get("generic_myavatar_resize") else "false"
                vars["generic_enemyavatar"] = rules.get("generic_enemyavatar", 1)
                if vars["generic_enemyavatar"]:
                    vars["generic_enemyavatar_width"] = rules.get("generic_enemyavatar_width", 300)
                    vars["generic_enemyavatar_resize"] = "true" if rules.get("generic_enemyavatar_resize") else "false"
                vars["generic_log"] = rules.get("generic_log", 1)
                if vars["generic_log"]:
                    layout = vars["generic_log_layout"] = rules.get("generic_log_layout", 0)
                    if layout == 0:
                        vars["generic_combat_height"] = rules.get("generic_combat_height", 300)
                    elif layout == 1:
                        vars["generic_log_height"] = rules.get("generic_log_height", 300)
                    vars["generic_log_resize"] = "true" if rules.get("generic_log_resize", True) else "false"
                for pos in ["aboveavatar", "belowavatar"]:
                    params = rules.get(pos)
                    if params is None:
                        params = []
                        self.call("combats.default-%s" % pos, params)
                        params.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
                    vars["generic_%s" % pos] = json.dumps(params)
            dim_avatar = rules.get("dim_avatar", [120, 220])
            vars["combat_avatar_width"] = dim_avatar[0]
            vars["combat_avatar_height"] = dim_avatar[1]
            try:
                content = self.call("game.parse_internal", "combat-rules-%s.html" % combat.rules, vars)
            except TemplateNotFound:
                content = self.call("game.parse_internal", "combat-interface.html", vars)
            self.call("game.response_internal", "combat.html", vars, content)
        except CombatUnavailable as e:
            self.call("combat.unavailable-exception-char", combat_id, char, e)
            self.call("web.redirect", "/location")

    def combat_state(self):
        req = self.req()
        char = self.character(req.user())
        combat_id = req.args
        try:
            combat = CombatInterface(self.app(), combat_id)
            self.call("web.response_json", combat.state_for_interface(char, req.param("marker")))
        except CombatUnavailable:
            self.call("combat.unavailable-exception-char", combat_id, char, e)
            self.call("web.not_found")

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("combat-stream")

    def default_aboveavatar(self, lst):
        lst.extend([
            {
                "id": "1",
                "type": "tpl",
                "tpl": [
                    u'<div class="combat-param">\n  <span class="combat-param-name">%s</span>:\n  <span class="combat-param-value">' % self._("HP"),
                    [".", ["glob", "member"], "p_hp"],
                    ' / ',
                    [".", ["glob", "member"], "p_max_hp"],
                    '</span>\n</div>'
                ],
                "order": 10.0
            },
        ])

    def default_belowavatar(self, lst):
        pass

    def unavailable_exception_char(self, combat_id, char, e):
        with self.lock([char.busy_lock]):
            busy = char.busy
            if busy and busy["tp"] == "combat" and busy.get("combat") == combat_id:
                # character is a member of a missing combat. free him
                self.call("debug-channel.character", char, self._("Character is a member of missing combat (%s). Freeing lock") % e)
                char.unset_busy()

    def combat_action(self):
        req = self.req()
        data = req.param("data")
        try:
            data = json.loads(data)
        except ValueError:
            self.call("web.response_json", {"error": self._("Invalid JSON data submitted")})
        char = self.character(req.user())
        combat_id = req.args
        try:
            combat = CombatInterface(self.app(), combat_id)
            self.call("web.response_json", combat.action(char, data))
        except CombatUnavailable as e:
            self.call("combat.unavailable-exception-char", combat_id, char, e)
            self.call("web.not_found")

    def combat_log(self):
        req = self.req()
        uuid = req.args
        if not re_valid_uuid.match(uuid):
            self.call("web.not_found")
        log = CombatLogViewer(self.app(), "user", uuid)
        if not log.valid:
            self.call("web.not_found")
        result = ""
        for ent in log.entries(0, len(log)):
            result += utf2str(ent.get("text")) + "\n"
        self.call("web.response", result, "text/plain; charset=utf-8")
