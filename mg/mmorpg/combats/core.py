from mg.constructor import *
import weakref

class CombatError(Exception):
    def __init__(self, val):
        self.val = val

    def __unicode__(self):
        return str2unicode(self.val)

    def __str__(self):
        return utf2str(self.val)

class Combat(ConstructorModule):
    "Combat is the combat itself. It is created in the combat daemon process."
    def __init__(self, app, fqn="mg.mmorpg.combats.core.Combat"):
        ConstructorModule.__init__(self, app, fqn)
        self.members = []
        self.stage = "init"

    def join(self, member):
        self.members.append(member)

    def run(self):
        if self.running != None:
            raise CombatError(self._("Combat was started twice"))
        self.running = True

    def stages(self):
        val = self.config("combats.stages")
        if val is not None:
            return val
        return {
            "init": {
            },
            "combat": {
                "actions": True,
            },
            "finish": {
            },
        }

    def tick(self):
        if not self.running:
            return

class CombatCommand(object):
    pass

class CombatMember(object):
    def __init__(self, combat):
        self._combat = weakref.ref(combat)

    @property
    def combat(self):
        return self._combat()

    def command(self):
        self.commands.??
