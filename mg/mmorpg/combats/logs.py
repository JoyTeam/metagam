from mg.mmorpg.combats.core import CombatObject

class CombatLog(CombatObject):
    "CombatLog logs combat actions"
    def __init__(self, combat, fqn="mg.mmorpg.combats.logs.CombatLog"):
        CombatObject.__init__(self, combat, fqn)

    def syslog(self, entry):
        "Record entry to the machine readable log"

    def textlog(self, entry):
        "Record entry to the user readable log"
