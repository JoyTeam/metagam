import mg.constructor
from mg.core.tools import *
from mg.mmorpg.combats.core import CombatUnavailable
from mg.mmorpg.combats.daemon import CombatInterface, DBRunningCombat, DBRunningCombatList
from mg.constructor.design import TemplateNotFound
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
        self.rhook("ext-combat.state", self.combat_state, priv="logged")

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
            vars = {
                "combat": combat_id,
                "load_extjs": {
                    "full": True
                },
            }
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
            self.call("web.response_json", combat.state)
        except CombatUnavailable:
            self.call("web.not_found")
