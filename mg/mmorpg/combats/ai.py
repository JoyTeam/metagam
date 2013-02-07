from mg.mmorpg.combats.core import CombatMemberController

class AIController(CombatMemberController):
    def __init__(self, member, fqn="mg.mmorpg.combats.ai.AIController"):
        CombatMemberController.__init__(self, member, fqn)
