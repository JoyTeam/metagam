from mg.constructor import ConstructorModule
from mg.mmorpg.combats.core import CombatObject
from concurrence import Tasklet

class CombatDaemon(CombatObject):
    def __init__(self, combat, fqn="mg.mmorpg.combats.daemon.CombatDaemon"):
        CombatObject.__init__(self, combat, fqn)

    def run(self):
        "Runs daemon loop in separate tasklet"
        self.tasklet = Tasklet.new(self._run)
        self.tasklet()

    def _run(self):
        try:
            self.loop()
        finally:
            del self.tasklet

    def loop(self):
        while not self.combat.stage_flag("done"):
            self.combat.process()
            Tasklet.yield_()

class CombatRequest(ConstructorModule):
    def __init__(self, app, fqn="mg.mmorpg.combats.requests.CombatRequest"):
        ConstructorModule.__init__(self, app, fqn)
        self.members = []

    def add_member(self, member):
        self.members.append(member)

    def run(self):
        +++
