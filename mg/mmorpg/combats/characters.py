from mg.mmorpg.combats.core import *

class CombatCharacterMember(CombatMember):
    def __init__(self, combat, character, fqn="mg.mmorpg.combats.characters.CombatCharacterMember"):
        CombatMember.__init__(self, combat, fqn)
        self.character = character
        self.set_name(character.name)
        self.set_sex(character.sex)

    @property
    def busy_lock(self):
        return self.character.busy_lock

    def set_busy(self, dry_run=False):
        return self.character.set_busy("combat", {
            "priority": 100,
            "show_uri": "/combat/interface/%s" % self.combat.uuid,
            "abort_event": "combats.abort-busy",
            "combat": self.combat.uuid,
            "member": self.id,
        }, dry_run)

    def unset_busy(self):
        busy = self.character.busy
        if busy and busy["tp"] == "combat" and busy.get("combat") == self.combat.uuid:
            self.character.unset_busy()

class CombatGUIController(CombatMemberController):
    def __init__(self, member, fqn="mg.mmorpg.combats.characters.CombatGUIController"):
        CombatMemberController.__init__(self, member, fqn)
