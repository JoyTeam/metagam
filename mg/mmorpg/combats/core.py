import mg.constructor
from mg.core.tools import *
from concurrence import TimeoutError, Channel
import weakref
import re
from uuid import uuid4
import random
from mg.constructor.script_classes import ScriptRuntimeError

re_param_attr = re.compile(r'^p_')

class CombatError(Exception):
    def __init__(self, val):
        self.val = val

    def __unicode__(self):
        return str2unicode(self.val)

    def __str__(self):
        return utf2str(self.val)

class CombatUnavailable(CombatError):
    pass

class CombatAlreadyRunning(CombatError):
    pass

class CombatInvalidStage(CombatError):
    pass

class CombatRunError(CombatError):
    pass

class CombatMemberBusyError(CombatRunError):
    pass

class CombatLocker(mg.constructor.ConstructorModule):
    "CombatLocker is an interface for locking and unlocking combat members."
    def __init__(self, app, cobj, fqn="mg.mmorpg.combats.core.CombatLocker"):
        mg.constructor.ConstructorModule.__init__(self, app, fqn)
        self.cobj = cobj

    def busy_lock(self):
        lock_keys = []
        for minfo in self.cobj.get("members", []):
            obj = minfo["object"]
            mtype = obj[0]
            key = self.call("combats-%s.busy-lock" % mtype, *obj[1:])
            if key:
                lock_keys.append(key)
        return self.lock(lock_keys)

    def set_busy(self):
        "Mark all members busy. If impossible raise CombatMemberBusyError"
        with self.busy_lock():
            for minfo in self.cobj.get("members", []):
                obj = minfo["object"]
                mtype = obj[0]
                if self.call("combats-%s.set-busy" % mtype, self.cobj.uuid, *obj[1:], dry_run=True):
                    raise CombatMemberBusyError(format_gender(minfo.get("sex", 0), self._("%s can't join combat. [gender?She:He] is busy") % minfo.get("name", mtype)))
            for minfo in self.cobj.get("members", []):
                obj = minfo["object"]
                mtype = obj[0]
                self.call("combats-%s.set-busy" % mtype, self.cobj.uuid, *obj[1:])

    def unset_busy(self):
        "Mark all members not busy"
        with self.busy_lock():
            for minfo in self.cobj.get("members", []):
                obj = minfo["object"]
                mtype = obj[0]
                self.call("combats-%s.unset-busy" % mtype, self.cobj.uuid, *obj[1:])

class CombatParamsContainer(object):
    def __init__(self):
        self._params = {}
        self._changed_params = set()
        self._last_sent_params = None
        self._all_params = None

    def param(self, key, handle_exceptions=True):
        "Get parameter value"
        return self._params.get(key)

    def set_param(self, key, val):
        "Set parameter value"
        if self._params.get(key) == val:
            return
        self._params[key] = val
        self._changed_params.add(key)
        self._all_params = None

    def all_params(self):
        "Return map(param => value) of all parameters"
        if self._all_params is not None:
            return self._all_params
        params = {}
        for key in self.__class__.system_params:
            params[key] = getattr(self, key)
        for key, val in self._params.iteritems():
            if re_param_attr.match(key):
                params[key] = val
        self._all_params = params
        return params

    def changed_params(self):
        "Returns map(param => value) of all changed parameters since last call to changed_params"
        if self._last_sent_params is None:
            # send all parameters
            params = self._last_sent_params = self.all_params()
            self._changed_params.clear()
            return params
        else:
            # send changed parameters only
            params = {}
            for key in self._changed_params:
                if not re_param_attr.match(key) and key not in self.__class__.system_params:
                    continue
                val = self.param(key)
                if val != self._last_sent_params.get(key):
                    params[key] = self._last_sent_params[key] = val
            self._changed_params.clear()
            return params

class Combat(mg.constructor.ConstructorModule, CombatParamsContainer):
    system_params = set(["stage"])

    "Combat is the combat itself. It is created in the combat daemon process."
    def __init__(self, app, uuid, rules, fqn="mg.mmorpg.combats.core.Combat"):
        mg.constructor.ConstructorModule.__init__(self, app, fqn)
        CombatParamsContainer.__init__(self)
        self.members = []
        self.log = None
        self.member_id = 0
        self.rules = rules
        self.uuid = uuid
        self.controllers = []
        self.rulesinfo = self.conf("combats-%s.rules" % rules, {})
        self.paramsinfo = self.conf("combats-%s.params" % rules, {})
        self.actionsinfo = self.conf("combats-%s.actions" % rules, [])
        self.commands = []
        self.commands_channel = Channel()

    def join(self, member):
        "Join member to the combat"
        self.member_id += 1
        member.id = self.member_id
        self.members.append(member)
        # if combat is started already, notify all other members
        if self.running:
            for controller in self.controllers:
                if controller.connected:
                    controller.deliver_member_joined(member)
        # registering member's controllers
        for controller in member.controllers:
            self.add_controller(controller)
        # log join
        if self.log:
            self.log.syslog({
                "type": "join",
                "member": member.id,
            })

    def member(self, memberId):
        for m in self.members:
            if m.id == memberId:
                return m
        return None

    @property
    def running(self):
        "True when combat is running"
        return self.stage != "init"

    def run(self, turn_order):
        """
        Run combat (switch to 'combat' stage).
        turn_order - CombatTurnOrder object
        """
        if self.running:
            raise CombatAlreadyRunning(self._("Combat was started twice"))
        self._turn_order = turn_order
        self.set_stage("combat")

    @property
    def stage(self):
        return self._params.get("stage", "init")

    def set_stage(self, stage):
        "Switch combat stage"
        if self.stages.get(stage) is None:
            raise CombatInvalidStage(self._("Combat stage '%s' is not defined") % stage)
        self.set_param("stage", stage)
        # logging stage
        if self.log:
            self.log.syslog({
                "type": "stage",
                "stage": stage,
            })
        # notifying turn order manager
        if self.stage_flag("actions"):
            self._turn_order.start()

    def add_controller(self, controller):
        "Register member controller"
        self.controllers.append(controller)

    @property
    def stages(self):
        "Dictionary of stages and their flags"
        try:
            return self._stages
        except AttributeError:
            pass
        val = self.conf("combats-%s.stages" % self.rules)
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

    def add_command(self, command):
        "Put command to the combat queue to be executed immediately"
        self.commands.append(command)
        if self.commands_channel.has_receiver():
            self.commands_channel.send(None)

    def process(self):
        "Process combat logic"
        self.process_commands()
        if self.stage_flag("actions"):
            self.process_actions()
        self.idle()
        try:
            self.commands_channel.receive(1)
        except TimeoutError:
            pass

    def process_commands(self):
        "Process enqueued commands"
        while self.commands:
            cmd = self.commands.pop(0)
            cmd.execute()

    def idle(self):
        "Do background processing"
        # deliver changed parameters
        params = self.changed_params()
        if params:
            for controller in self.controllers:
                controller.combat_params_changed(params)
        for member in self.members:
            params = member.changed_params()
            if params:
                for controller in self.controllers:
                    controller.member_params_changed(member, params)
        # call idle for all objects
        self._turn_order.idle()
        for member in self.members:
            member.idle()
        self.call("stream.flush")

    def process_actions(self):
        "Process actions logic"

    def set_log(self, log):
        "Attach logging system to the combat"
        self.log = log

    def stop(self):
        "Terminate combat"
        self.set_stage("done")

    # Scripting

    def script_attr(self, attr, handle_exceptions=True):
        # parameters
        m = re_param_attr.match(attr)
        if m:
            return self.param(attr, handle_exceptions)
        if handle_exceptions:
            return None
        else:
            raise AttributeError(attr)

    def script_set_attr(self, attr, val, env):
        # parameters
        m = re_param_attr.match(attr)
        if m:
            return self.set_param(attr, val)
        raise ScriptRuntimeError(self._("Invalid attribute '%s'") % attr, env)

class CombatObject(mg.constructor.ConstructorModule):
    "Any object related to the combat. Link to combat is weakref"
    def __init__(self, combat, fqn, weak=True):
        mg.constructor.ConstructorModule.__init__(self, combat.app(), fqn)
        self._combat_weak = weak
        if weak:
            self._combat = weakref.ref(combat)
        else:
            self._combat = combat

    @property
    def combat(self):
        if self._combat_weak:
            return self._combat()
        else:
            return self._combat

class CombatCommand(CombatObject):
    "CombatActions are executed immediately in the main combat loop"
    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatCommand"):
        CombatObject.__init__(self, combat, fqn)

    def execute(self):
        "Called when it's allowed to run"

class CombatAction(CombatObject):
    "CombatMembers perform CombatActions according to the schedule"
    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatAction"):
        CombatObject.__init__(self, combat, fqn)
        self.targets = []
        self.source = None
        self.code = None

    def set_source(self, source):
        "Set combat action source"
        self.source = source

    def add_target(self, member):
        "This method adds another target to the action"
        self.targets.append(member)

    def for_every_target(self, callback, *args, **kwargs):
        "Call callback for every action target. Target is passed as a first argument"
        for target in self.targets:
            callback(target, *args, **kwargs)

    def begin(self):
        "Do any processing in the beginning of the action"

    def end(self):
        "Do any processing in the end of the action"

    def set_code(self, code):
        "Set action code"
        self.code = code

class CombatMember(CombatObject, CombatParamsContainer):
    system_params = set(["name", "sex", "team", "may_turn", "active", "image", "targets"])

    "Members take part in combats. Every fighting entity is a member"
    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatMember"):
        CombatObject.__init__(self, combat, fqn)
        CombatParamsContainer.__init__(self)
        self.pending_actions = []
        self.controllers = []
        self.clear_available_action_cache()

    def is_a_combat_member(self):
        return True

    def add_controller(self, controller):
        "Attach CombatMemberController to the member"
        self.controllers.append(controller)

    def idle(self):
        "Called when member can do any background processing"
        # DEBUG: Make some parameter change randomly
        #self.set_param("p_test", random.random())
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
        act.set_source(self)
        self.pending_actions.append(act)
        print "Action %s enqueued for member %s" % (act, self.name)

    # Scripting

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "id":
            return self.id
        elif attr == "name":
            return self.name
        elif attr == "sex":
            return self.sex
        elif attr == "team":
            return self.team
        # parameters
        m = re_param_attr.match(attr)
        if m:
            return self.param(attr, handle_exceptions)
        raise ScriptRuntimeError(self._("Invalid attribute name: '%s'") % attr)

    def script_set_attr(self, attr, val, env):
        # parameters
        if attr == "targets":
            return self.set_param(attr, val)
        m = re_param_attr.match(attr)
        if m:
            return self.set_param(attr, val)
        raise ScriptRuntimeError(self._("Invalid attribute name: '%s'") % attr, env)

    # System parameters

    @property
    def name(self):
        return self._params.get("name", "Anonymous")
    def set_name(self, name):
        self.set_param("name", name)

    @property
    def sex(self):
        return self._params.get("sex", 0)
    def set_sex(self, sex):
        self.set_param("sex", sex)

    @property
    def active(self):
        return self._params.get("active", True)
    def set_active(self, active):
        self.set_param("active", active)

    @property
    def team(self):
        return self._params.get("team")
    def set_team(self, team):
        "Change team of the member"
        self.set_param("team", team)

    @property
    def image(self):
        return self._params.get("image")
    def set_image(self, image):
        "Change image of the member"
        self.set_param("image", image)

    @property
    def targets(self):
        return self._params.get("targets")
    def set_targets(self, targets):
        self.set_param("targets", targets)

    # Turn order

    @property
    def may_turn(self):
        return self._params.get("may_turn", False)

    def turn_give(self):
        "Grant right of making turn to the member"
        self.set_param("may_turn", True)
        self.clear_available_action_cache()
        desc = lambda: self._("'After get turn' script")
        self.call("combats.execute-script", self.combat, self.conf("combats-%s.script-turngot" % self.combat.rules), globs={"combat": self.combat, "member": self}, description=desc)
        for controller in self.controllers:
            controller.turn_got()

    def turn_take(self):
        "Revoke right of making turn from the member"
        self.set_param("may_turn", False)
        for controller in self.controllers:
           controller.turn_lost()

    def turn_timeout(self):
        "Revoke right of making turn from the member due to timeout"
        self.set_param("may_turn", False)
        for controller in self.controllers:
            controller.turn_timeout()

    # actions

    def available_actions(self):
        "Return list of actions available for the member"
        if not self.may_turn:
            return []
        res = []
        for act in self.combat.actionsinfo:
            if self.action_available(act):
                res.append(act)
        return res

    def clear_available_action_cache(self):
        "Invalidate available actions cache"
        self._available_action_cache = {}

    def action_available(self, act):
        "Return True if action is available for the member (cacheable)"
        if not self.may_turn:
            return False
        try:
            return False if self._available_action_cache[act["code"]] is None else True
        except KeyError:
            pass
        available = self.call("script.evaluate-expression", act.get("available", 1), globs={"combat": self.combat, "member": self}, description=self._("Availability of combat action %s") % act["code"])
        self._available_action_cache[act["code"]] = {} if available else None
        return available

    def target_available(self, act, target):
        "Return True if given action can be targeted to given target (cacheable)"
        if not self.may_turn:
            return False
        if not self.action_available(act):
            return False
        act_cache = self._available_action_cache[act["code"]]
        try:
            return act_cache[target.id]
        except KeyError:
            pass
        targets = act.get("targets", "enemies")
        if targets == "none":
            available = False
        elif targets == "all":
            available = True
        elif targets == "enemies":
            available = self.team != target.team
        elif targets == "allies":
            available = self.team == target.team and self.id != target.id
        elif targets == "allies-myself":
            available = self.team == target.team
        elif targets == "myself":
            available = self.id == target.id
        elif targets == "script":
            available = self.call("script.evaluate-expression", act.get("target_available"), globs={"combat": self.combat, "member": self, "target": target}, description=self._("Availability of combat action %s targeted to specific target") % act["code"])
        else:
            available = False
        act_cache[target.id] = available
        return available

    def select_target(self, condition, env):
        targets = []
        globs = {"combat": self.combat, "member": self}
        for target in self.combat.members:
            globs["target"] = target
            val = self.call("script.evaluate-expression", condition, globs=globs, description=lambda: self._("Evaluation of target availability"))
            if val:
                targets.append(target.id)
        if not targets:
            self.set_param("targets", None)
        else:
            self.set_param("targets", [random.choice(targets)])

class RequestStateCommand(CombatCommand):
    "Request combat state and deliver it to the controller"
    def __init__(self, controller, marker, fqn="mg.mmorpg.combats.core.RequestStateCommand"):
        CombatCommand.__init__(self, controller.combat, fqn)
        self.controller = controller
        self.marker = marker

    def execute(self):
        self.controller.connected = True
        self.controller.clear_last_params()
        self.controller.clear_sent_actions()
        self.controller.deliver_marker(self.marker)
        self.controller.combat_params_changed(self.combat.all_params())
        for member in self.combat.members:
            self.controller.deliver_member_joined(member)
            self.controller.member_params_changed(member, member.all_params())
        self.controller.deliver_myself()
        if self.controller.member.may_turn:
            self.controller.turn_got()

class CombatMemberController(CombatObject):
    """
    Controller is an interface to CombatMember. Controller receives notifications about changes in the combat
    state that this member may know. Any number of controllers can be attached to a single member.
    """
    def __init__(self, member, fqn):
        CombatObject.__init__(self, member.combat, fqn)
        self.member = member
        self.connected = False
        self.clear_last_params()
        self.clear_sent_actions()
        self.tags = set()

    def clear_last_params(self):
        "Mark all parameters as never sent"
        self._last_combat_sent_params = {}
        self._last_member_sent_params = {}

    def clear_sent_actions(self):
        "Mark all actions as never sent"
        self._sent_actions = set()

    def turn_got(self):
        "This command notifies controller that member has got a right to make a turn"
        actions = []
        for act in self.member.available_actions():
            show = False
            if act.get("targets") == "none":
                show = True
                targets_min = 0
                targets_max = 0
            else:
                targets = []
                for target in self.combat.members:
                    if self.member.target_available(act, target):
                        targets.append(target.id)
                if targets:
                    targets_min = self.call("script.evaluate-expression", act.get("targets_min", 1), globs={"combat": self.combat, "viewer": self.member}, description=self._("Minimal number of targets for combat action %s") % act["code"])
                    targets_max = self.call("script.evaluate-expression", act.get("targets_max", 1), globs={"combat": self.combat, "viewer": self.member}, description=self._("Maximal number of targets for combat action %s") % act["code"])
                    show = True
            if show:
                actions.append({
                    "action": act["code"],
                    "targets": targets,
                    "targets_min": targets_min,
                    "targets_max": targets_max,
                })
                # deliver action description
                if act["code"] not in self._sent_actions:
                    self._sent_actions.add(act["code"])
                    self.deliver_action(act)
        self.deliver_available_actions(actions)
        self.deliver_turn_got()

    def turn_lost(self):
        "This command notifies controller that member has lost a right to make a turn"
        self.deliver_turn_lost()

    def turn_timeout(self):
        "This command notifies controller that member hasn't made a turn"
        self.deliver_turn_timeout()

    def idle(self):
        "Called when controller can do any background processing"

    def combat_params_changed(self, params):
        "Called when combat parameters changed"
        if not self.connected:
            return
        paramsinfo = self.combat.paramsinfo.get("combat", {})
        deliver = {}
        for key, val in params.iteritems():
            if re_param_attr.match(key):
                paraminfo = paramsinfo.get(key)
                if paraminfo:
                    # visibility check
                    visible_script = paraminfo.get("visible")
                    visible = self.call("script.evaluate-expression", visible_script, globs={"combat": self.combat, "viewer": self.member}, description=self._("Visibility of combat parameter %s") % key)
                    if not visible:
                        val = None
                else:
                    val = None
            # deliver parameter
            if val != self._last_combat_sent_params.get(key):
                deliver[key] = self._last_combat_sent_params[key] = val
        if deliver:
            self.deliver_combat_params(deliver)

    def member_params_changed(self, member, params):
        "Called when member parameters changed"
        if not self.connected:
            return
        paramsinfo = self.combat.paramsinfo.get("member", {})
        deliver = {}
        try:
            last_sent_params = self._last_member_sent_params[member.id]
        except KeyError:
            last_sent_params = self._last_member_sent_params[member.id] = {}
        for key, val in params.iteritems():
            if key == "targets":
                # available only for member
                if self.member.id != member.id:
                    val = None
            elif re_param_attr.match(key):
                paraminfo = paramsinfo.get(key)
                if paraminfo:
                    # visibility check
                    visible_script = paraminfo.get("visible")
                    visible = self.call("script.evaluate-expression", visible_script, globs={"combat": self.combat, "member": member, "viewer": self.member}, description=self._("Visibility of combat parameter %s") % key)
                    if not visible:
                        val = None
                else:
                    val = None
            # deliver parameter
            if val != last_sent_params.get(key):
                deliver[key] = last_sent_params[key] = val
        if deliver:
            self.deliver_member_params(member, deliver)

    def deliver_combat_params(self, params):
        "Called when we have to deliver combat 'params' to client"

    def deliver_member_params(self, member, params):
        "Called when we have to deliver member 'params' to client"

    def deliver_member_joined(self, member):
        "Called when we have to notify client about joined member"

    def request_state(self, marker):
        "Query current combat state and deliver it to client"
        self.combat.add_command(RequestStateCommand(self, marker))

    def deliver_marker(self, marker):
        "Called when we have to deliver marker to the client"

    def deliver_myself(self):
        "Called when we have to deliver myself identifier to client"

    def deliver_action(self, action):
        "Called when we have to deliver action description to the client"

    def deliver_available_actions(self, actions):
        "Called when we have to deliver list of available actions to the client"

    def deliver_turn_got(self):
        "Called when we have to notify client about its controlled member got a turn"

    def deliver_turn_lost(self):
        "Called when we have to notify client about its controlled member lost a turn"

    def deliver_turn_timeout(self):
        "Called when we have to notify client about its controlled member timed out"

class CombatSystemInfo(object):
    "CombatInfo is an object describing rules of the combat system"
    def params(self):
        "Returns list of member parameters"
