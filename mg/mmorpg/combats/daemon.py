from concurrence import Tasklet

class CombatDaemon(object):
    def __init__(self, combat):
        self.combat = combat

    def run(self):
        Tasklet.new(self._run)()

    def _run(self):
        self.tasklet = tasklet
        combat.run()
        while combat.running:
            combat.tick()
            Tasklet.yield_()
        del self.tasklet
