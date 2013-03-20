import mg.constructor
from mg.mmorpg.combats.core import *
import mg

class DBCombatCharacterLog(mg.CassandraObject):
    clsname = "CombatCharacterLog"
    indexes = {
        "character-created": [["character"], "created"],
        "combat": [["combat"], "created"],
    }

class DBCombatCharacterLogList(mg.CassandraObjectList):
    objcls = DBCombatCharacterLog

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
        res = character.set_busy("combat", {
            "priority": 100,
            "show_uri": "/combat/interface/%s" % combat_id,
            "abort_event": "combats-character.abort-busy",
            "combat": combat_id
        }, dry_run)
        if not dry_run and res:
            character.message(self._("You have entered a combat"))
        return not res

    def unset_busy(self, combat_id, uuid):
        character = self.character(uuid)
        busy = character.busy
        if busy and busy["tp"] == "combat" and busy.get("combat") == combat_id:
            character.unset_busy()

class CombatCharacterMember(CombatMember):
    def __init__(self, combat, character, fqn="mg.mmorpg.combats.characters.CombatCharacterMember"):
        CombatMember.__init__(self, combat, fqn)
        self.set_param("char", character)
        self.set_name(character.name)
        self.set_sex(character.sex)
        self._victory = False
        # get avatar of desired size
        rules = self.combat.rulesinfo
        dim = rules.get("dim_avatar", [120, 220])
        dim = "%dx%d" % (dim[0], dim[1])
        charimage = self.call("charimages.get", character, dim)
        if charimage is None:
            charimage = "/st-mg/constructor/avatars/%s-120x220.jpg" % ("female" if character.sex else "male")
        self.set_param("image", charimage)
        # copy character parameters into member parameters
        for param in self.call("characters.params"):
            val = self.call("characters.param-value", character, param["code"])
            self.set_param("p_%s" % param["code"], val)

    def started(self):
        CombatMember.started(self)
        self.qevent("oncombat", char=self.param("char"), combat=self.combat, member=self, cevent="start")

    def victory(self):
        CombatMember.victory(self)
        self.qevent("oncombat", char=self.param("char"), combat=self.combat, member=self, cevent="victory")
        self._victory = True

    def defeat(self):
        CombatMember.defeat(self)
        self.qevent("oncombat", char=self.param("char"), combat=self.combat, member=self, cevent="defeat")

    def draw(self):
        CombatMember.draw(self)
        self.qevent("oncombat", char=self.param("char"), combat=self.combat, member=self, cevent="draw")

    def stopped(self):
        CombatMember.stopped(self)
        char = self.param("char")
        tokens = []
        quest_given_items = getattr(char, "quest_given_items", None)
        if quest_given_items:
            for key, val in quest_given_items.iteritems():
                name = u'<li class="combat-log-item"><span class="combat-log-itemname">%s</span> &mdash; <span class="combat-log-itemquantity">%d</span> %s</li>' % (htmlescape(key), val, self._("pcs"))
                tokens.append(name)
        quest_given_money = getattr(char, "quest_given_money", None)
        if quest_given_money:
            for currency, amount in quest_given_money.iteritems():
                tokens.append(u'<li class="combat-log-item">%s</li>' % self.call("money.price-html", amount, currency))
        if tokens:
            self.combat.textlog({
                "text": u'<span class="combat-log-member">%s</span> %s: <ul class="combat-log-itemlist">%s</ul>' % (
                    htmlescape(self.name),
                    self._("female///has got") if self.sex else self._("male///has got"),
                    u''.join(tokens)
                )
            })
        # save combat log in the character's profile
        log = self.obj(DBCombatCharacterLog)
        log.set("created", self.now())
        log.set("combat", self.combat.uuid)
        log.set("character", char.uuid)
        log.set("victory", self._victory)
        log.store()
