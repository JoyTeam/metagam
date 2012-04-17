from mg.constructor import *
import weakref
import re

re_param_attr = re.compile(r'^p_(.+)')

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
        self.member_id = 0

    def join(self, member):
        "Join member to the combat"
        self.member_id += 1
        member.id = self.member_id
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
        "Attach logging system to the combat"
        self.log = log

    def stop(self):
        "Terminate combat"
        self.set_stage("done")

class CombatObject(ConstructorModule):
    "Any object related to the combat. Link to combat is weakref"
    def __init__(self, combat, fqn):
        ConstructorModule.__init__(self, combat.app(), fqn)
        self._combat = weakref.ref(combat)

    @property
    def combat(self):
        return self._combat()

class CombatAction(CombatObject):
    "CombatMembers perform CombatActions according to the schedule"
    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatAction"):
        CombatObject.__init__(self, combat, fqn)
        self.targets = []

    def add_target(self, member):
        "This method adds another target to the action"
        self.targets.append(member)

class CombatMember(CombatObject):
    "Members take part in combats. Every fighting entity is a member"
    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatMember"):
        CombatObject.__init__(self, combat, fqn)
        self.pending_actions = []
        self.may_turn = False
        self.active = True
        self.controllers = []
        self._params = {}

    def is_a_combat_member(self):
        return True

    def set_team(self, team):
        "Change team of the member"
        self.team = team

    def add_controller(self, controller):
        "Attach CombatMemberController to the member"
        self.controllers.append(controller)

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

    @property
    def enemies(self):
        "List of combat members in other teams"
        return [m for m in self.combat.members if m.team != self.team]

    @property
    def allies(self):
        "List of combat members in the same team except myself"
        return [m for m in self.combat.members if m.team == self.team and m != self]

    def enqueue_action(self, act):
        "Enqueue action for the member"
        act.source = self
        self.pending_actions.append(act)

    def param(self, key, handle_exceptions=True):
        return self._params.get(key)

    def set_param(self, key, val):
        self._params[key] = val

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "id":
            return self.id
        # parameters
        m = re_param_attr.match(attr)
        if m:
            param = m.group(1)
            return self.param(param, handle_exceptions)
        raise AttributeError(attr)

    def script_set_attr(self, attr, val, env):
        # parameters
        m = re_param_attr.match(attr)
        if m:
            param = m.group(1)
            return self.set_param(param, val)
        raise AttributeError(attr)

class CombatMemberController(CombatObject):
    """
    Controller is an interface to CombatMember. Controller receives notifications about changes in the combat
    state that this member may know. Any number of controllers can be attached to a single member.
    """
    def __init__(self, member, fqn):
        CombatObject.__init__(self, member.combat, fqn)
        self.member = member

    def turn_got(self):
        "This command notifies controller that member has got a right to make a turn"

    def turn_lost(self):
        "This command notifies controller that member has lost a right to make a turn"

    def turn_timeout(self):
        "This command notifies controller that member hasn't made a turn"

    def idle(self):
        "Called when controller can do any background processing"

class CombatLog(CombatObject):
    "CombatLog logs combat actions"

class CombatSystemInfo(object):
    "CombatInfo is an object describing rules of the combat system"
    def params(self):
        "Returns list of member parameters"
