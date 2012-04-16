from mg.constructor import *
import weakref

class CombatError(Exception):
    def __init__(self, val):
        self.val = val

    def __unicode__(self):
        return str2unicode(self.val)

    def __str__(self):
        return utf2str(self.val)

class CombatAlreadyRunning(CombatError):
    pass

class CombatInvalidStage(CombatError):
    pass

class Combat(ConstructorModule):
    "Combat is the combat itself. It is created in the combat daemon process."
    def __init__(self, app, fqn="mg.mmorpg.combats.core.Combat"):
        ConstructorModule.__init__(self, app, fqn)
        self.members = []
        self.stage = "init"
        self.log = None

    def join(self, member):
        "Join member to the combat"
        self.members.append(member)

    def run(self, turn_order):
        """
        Run combat (switch to 'combat' stage).
        turn_order - CombatTurnOrder object
        """
        if self.stage != "init":
            raise CombatAlreadyRunning(self._("Combat was started twice"))
        self._turn_order = turn_order
        self.set_stage("combat")

    def set_stage(self, stage):
        "Switch combat stage"
        if self.stages.get(stage) is None:
            raise CombatInvalidStage(self._("Combat stage '%s' is not defined") % stage)
        self.stage = stage
        if self.stage_flag("actions"):
            self._turn_order.start()

    @property
    def stages(self):
        "Dictionary of stages and their flags"
        try:
            return self._stages
        except AttributeError:
            pass
        val = self.conf("combats.stages")
        if val is None:
            val = {
                "init": {
                },
                "combat": {
                    "actions": True,
                },
                "finish": {
                },
                "done": {
                   "done": True
                }
            }
        self._stages = val
        return val

    def stage_flag(self, flag):
        "Returns flag value of the current stage. If no flag with such code defined return None"
        return self.stages[self.stage].get(flag)

    def process(self):
        "Process combat logic"
        if self.stage_flag("actions"):
            self.process_actions()
        self._turn_order.idle()
        for member in self.members:
            member.idle()

    def process_actions(self):
        "Process actions logic"

    def set_log(self, log):
        self.log = log

class CombatObject(ConstructorModule):
    "Any object related to the combat. Link to combat is weakref"
    def __init__(self, combat, fqn):
        ConstructorModule.__init__(self, combat.app(), fqn)
        self._combat = weakref.ref(combat)

    @property
    def combat(self):
        return self._combat()

class CombatCommand(object):
    pass

class CombatMember(CombatObject):
    "Members take part in combats. Every fighting entity is a member"
    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatMember"):
        CombatObject.__init__(self, combat, fqn)
        self.commands = []
        self.may_turn = False
        self.active = True
        self.controllers = []

    def set_team(self, team):
        "Change team of the member"
        self.team = team

    def add_controller(self, controller):
        "Attach CombatMemberController to the member"
        self.controllers.append(controller)

    def command(self, cmd):
        "Enqueue command for the member"
        self.commands.append(cmd)

    def turn_give(self):
        "Grant right of making turn to the member"
        self.may_turn = True
        for controller in self.controllers:
            controller.turn_got()

    def turn_take(self):
        "Revoke right of making turn from the member"
        self.may_turn = False
        for controller in self.controllers:
           controller.turn_lost()

    def turn_timeout(self):
        "Revoke right of making turn from the member due to timeout"
        self.may_turn = False
        for controller in self.controllers:
            controller.turn_timeout()

    def idle(self):
        "Called when member can do any background processing"
        for controller in self.controllers:
            controller.idle()

class CombatMemberController(CombatObject):
    """
    Controller is an interface to CombatMember. Controller receives notifications about changes in the combat
    state that this member may know. Any number of controllers can be attached to a single member.
    """
    def __init__(self, member, fqn):
        CombatObject.__init__(self, member.combat, fqn)
        self.member = member

    def turn_got(self):
        "This command notifies controller that member got right to make a turn"

    def turn_lost(self):
        "This command notifies controller that member lost right to make a turn"

    def turn_timeout(self):
        "This command notifies controller that member hasn't made a turn"

    def idle(self):
        "Called when controller can do any background processing"

class CombatLog(CombatObject):
    "CombatLog logs combat actions"
