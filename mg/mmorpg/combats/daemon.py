from mg.constructor import ConstructorModule, Daemon
from mg.mmorpg.combats.core import CombatObject, Combat, CombatMember, CombatRunError
from mg.mmorpg.combats.turn_order import *
from concurrence import Tasklet

class CombatRequest(ConstructorModule):
    def __init__(self, app, fqn="mg.mmorpg.combats.requests.CombatRequest"):
        ConstructorModule.__init__(self, app, fqn)
        self.members = []
        self.rules = None

    def add_member(self, member):
        self.members.append(member)

    def run(self):
        self.debug("Running combat")
        combat = Combat(self.app(), self.rules)
        daemon = CombatDaemon(combat)
        for minfo in self.members:
            # member
            mtype = minfo["type"]
            if mtype == "virtual":
                member = CombatMember(combat)
            else:
                makemember = getattr(mtype, "combat_member", None)
                if makemember is None:
                    raise CombatRunError(self._("This object cannot be a combat member: %s") % mtype)
                member = makemember(combat)
            member.set_team(minfo["team"])
            # control
            if "control" in minfo:
                control = minfo["control"]
                if control == "ai":
                    ai = AIController(member)
                    member.add_controller(ai)
                else:
                    raise CombatRunError(self._("Invalid controller type: %s") % control)
            # properties
            if "name" in minfo:
                member.set_name(minfo["name"])
            if "sex" in minfo:
                member.set_sex(minfo["sex"])
            # joining
            combat.join(member)
        # running combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        combat.run(turn_order)
        daemon.run()

class CombatDaemon(CombatObject, Daemon):
    def __init__(self, combat, fqn="mg.mmorpg.combats.daemon.CombatDaemon"):
        CombatObject.__init__(self, combat, fqn)
        Daemon.__init__(self, combat.app(), fqn, combat.uuid)

    def main(self):
        while not self.combat.stage_flag("done"):
            self.combat.process()
            Tasklet.yield_()

