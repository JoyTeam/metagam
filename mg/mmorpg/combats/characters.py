import mg.constructor
from mg.mmorpg.combats.core import *

class Combats(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("combats-character.member", self.member)
        self.rhook("combats-character.free", self.free)
        self.rhook("combats-character.busy-lock", self.busy_lock)
        self.rhook("combats-character.set-busy", self.set_busy)
        self.rhook("combats-character.unset-busy", self.unset_busy)

    def member(self, combat, uuid):
        character = self.character(uuid)
        member = CombatCharacterMember(combat, character)
        control = CombatGUIController(member)
        member.add_controller(control)
        return member

    def free(self, combat_id, uuid):
        character = self.character(uuid)
        with self.lock([character.busy_lock]):
            busy = character.busy
            if busy and busy["tp"] == "combat" and busy.get("combat") == combat_id:
                character.unset_busy()

    def busy_lock(self, uuid):
        character = self.character(uuid)
        return character.busy_lock

    def set_busy(self, combat_id, uuid, dry_run=False):
        character = self.character(uuid)
        return not character.set_busy("combat", {
            "priority": 100,
            "show_uri": "/combat/interface/%s" % combat_id,
            "abort_event": "combats-character.abort-busy",
            "combat": combat_id
        }, dry_run)

    def unset_busy(self, combat_id, uuid):
        character = self.character(uuid)
        busy = character.busy
        if busy and busy["tp"] == "combat" and busy.get("combat") == combat_id:
            character.unset_busy()

class CombatCharacterMember(CombatMember):
    def __init__(self, combat, character, fqn="mg.mmorpg.combats.characters.CombatCharacterMember"):
        CombatMember.__init__(self, combat, fqn)
        self.character = character
        self.set_name(character.name)
        self.set_sex(character.sex)

class CombatGUIController(CombatMemberController):
    def __init__(self, member, fqn="mg.mmorpg.combats.characters.CombatGUIController"):
        CombatMemberController.__init__(self, member, fqn)
