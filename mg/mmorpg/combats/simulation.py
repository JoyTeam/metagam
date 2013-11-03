from mg.mmorpg.combats.core import Combat

class SimulationCombat(Combat):
    def __init__(self, app, fqn="mg.mmorpg.combats.simulation.SimulationCombat"):
        Combat.__init__(self, app, None, ":simulation", fqn)
