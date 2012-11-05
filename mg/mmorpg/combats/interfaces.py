import mg.constructor
from mg.core.tools import *
from mg.mmorpg.combats.core import CombatUnavailable
from mg.mmorpg.combats.daemon import CombatInterface, DBRunningCombat, DBRunningCombatList
from mg.constructor.design import TemplateNotFound

class Combats(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-combat.interface", self.combat_interface, priv="logged")
        self.rhook("ext-combat.state", self.combat_state, priv="logged")
        self.rhook("gameinterface.render", self.gameinterface_render)

    def child_modules(self):
        return [
            "mg.mmorpg.combats.wizards.AttackBlock",
            "mg.mmorpg.combats.scripts.CombatScripts",
            "mg.mmorpg.combats.daemon.CombatRunner",
            "mg.mmorpg.combats.characters.Combats",
            "mg.mmorpg.combats.admin.CombatsAdmin",
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
            # Show combat interface to user
            rules = self.conf("combats.rules", {}).get(combat.rules, {})
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
            try:
                content = self.call("game.parse_internal", "combat-rules-%s.html" % combat.rules, vars)
            except TemplateNotFound:
                content = self.call("game.parse_internal", "combat-interface.html", vars)
            self.call("game.response_internal", "combat.html", vars, content)

    def combat_state(self):
        req = self.req()
        char = self.character(req.user())
        combat_id = req.args
        try:
            combat = CombatInterface(self.app(), combat_id)
            self.call("web.response_json", combat.state_for_interface(char, req.param("marker")))
        except CombatUnavailable:
            self.call("web.not_found")

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("combat-stream")
