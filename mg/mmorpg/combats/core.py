#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

import mg.constructor
from mg.core.tools import *
from concurrence import TimeoutError, Channel
import weakref
import re
from uuid import uuid4
import random
import os
import time
from mg.constructor.script_classes import ScriptRuntimeError, ScriptMemoryObject

re_param_attr = re.compile(r'^p_')
re_attr = re.compile(r'^a_')
re_team_list = re.compile(r'^team(\d+)_list')

textlog_ring_size = 10

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

    def set_busy_member(self, minfo):
        "Mark specified member busy. If impossible raise CombatMemberBusyError"
        with self.busy_lock():
            obj = minfo["object"]
            mtype = obj[0]
            if self.call("combats-%s.set-busy" % mtype, self.cobj, *obj[1:]):
                raise CombatMemberBusyError(format_gender(minfo.get("sex", 0), self._("%s is busy and can't join combat") % minfo.get("name", mtype)))

    def set_busy(self):
        "Mark all members busy. If impossible raise CombatMemberBusyError"
        with self.busy_lock():
            for minfo in self.cobj.get("members", []):
                obj = minfo["object"]
                mtype = obj[0]
                if self.call("combats-%s.set-busy" % mtype, self.cobj, *obj[1:], dry_run=True):
                    raise CombatMemberBusyError(format_gender(minfo.get("sex", 0), self._("%s is busy and can't join combat") % minfo.get("name", mtype)))
            for minfo in self.cobj.get("members", []):
                obj = minfo["object"]
                mtype = obj[0]
                self.call("combats-%s.set-busy" % mtype, self.cobj, *obj[1:])

    def unset_busy(self):
        "Mark all members not busy"
        with self.busy_lock():
            for minfo in self.cobj.get("members", []):
                obj = minfo["object"]
                mtype = obj[0]
                self.call("combats-%s.unset-busy" % mtype, self.cobj, *obj[1:])

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
            return False
        self._params[key] = val
        self._changed_params.add(key)
        self._all_params = None
        return True

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
    "Combat is the combat itself. It is created in the combat daemon process."

    system_params = set(["stage", "title", "time", "timetext"])
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
        self.wakeup_channel = Channel()
        self.running_actions = []
        self.ready_actions = []
        self._turn_order_check = False
        self._check_end_condition = True
        self.not_delivered_log = []
        self.start_time = time.time()
        self._flags = set()
        self._textlog_ring = []

    def script_code(self, tag):
        "Get combat script code (syntax tree)"
        return self.conf("combats-%s.script-%s" % (self.rules, tag), [])

    def join(self, member):
        "Join member to the combat"
        self.member_id += 1
        member.id = self.member_id
        self.members.append(member)
        # script event
        globs = self.globs()
        globs["member"] = member
        self.execute_script("joined", globs, lambda: self._("Member joined script"))
        # if combat is started already, notify all other members
        if self.running:
            for controller in self.controllers:
                if controller.connected:
                    controller.deliver_member_joined(member)
        # register member's controllers
        for controller in member.controllers:
            self.add_controller(controller)
        # log join
        self.syslog({
            "type": "join",
            "member": member.id,
            "text": self._("<b>[{time}]</b> Member {id} ({name}) has joined team {team}").format(
                time=self.now(),
                id=member.id,
                name=member.name,
                team=member.team,
            ),
            "cls": "combat-syslog-joined",
        })

    def member(self, memberId):
        for m in self.members:
            if m.id == memberId:
                return m
        return None

    def close(self):
        "Notify combat about it's terminated and about to be destroyed"
        if self.log:
            self.log.close()
        self.flush()

    @property
    def actions(self):
        "Dictionary of available combat actions"
        try:
            return self._actions
        except AttributeError:
            pass
        self._actions = {}
        for act in self.conf("combats-%s.actions" % self.rules, []):
            self._actions[act["code"]] = act
        return self._actions

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
        self.turn_order = turn_order
        self.set_stage("combat")
        self.log_combat_time()
        # execute start script
        globs = self.globs()
        self.execute_script("start", globs, lambda: self._("Combat start script"))
        # notify all members
        for member in self.members:
            member.started()
        # notify turn order manager
        if self.stage_flag("actions"):
            self.turn_order.start()

    @property
    def stage(self):
        return self._params.get("stage", "init")

    def set_stage(self, stage):
        "Switch combat stage"
        if self.stages.get(stage) is None:
            raise CombatInvalidStage(self._("Combat stage '%s' is not defined") % stage)
        self.set_param("stage", stage)
        self.syslog({
            "type": "stage",
            "stage": stage,
            "text": self._("Combat stage: %s") % stage,
            "cls": "combat-syslog-stage",
        })
        self.wakeup()

    @property
    def flags(self):
        return self._flags

    def set_flags(self, flags):
        self._flags = set(flags)

    @property
    def title(self):
        return self._params.get("title", self._("Combat"))

    def set_title(self, title):
        "Set combat title"
        self.set_param("title", title)
        if self.log:
            self.log.set_title(title)
        self.wakeup()

    @property
    def timetext(self):
        time_format = self.rulesinfo.get("time_format", "mmss")
        time = self.time
        if time_format == "mmss":
            return "%d:%02d" % (time / 60, time % 60)
        elif time_format == "num":
            return self.time
        elif time_format == "realhhmmss":
            return self.now_local().split(" ")[1]

    @property
    def time_mode(self):
        try:
            return self._time_mode
        except AttributeError:
            pass
        self._time_mode = self.rulesinfo.get("time_mode", "begin")
        return self._time_mode

    @property
    def time(self):
        return self._params.get("time", 0)

    def log_combat_time(self):
        self.syslog({
            "text": self._("Combat time: %s") % self.time,
            "time": self.time,
            "cls": "combat-syslog-time",
        })
        if self.time_mode == "change":
            self.textlog({
                "text": self.timetext,
                "cls": "combat-log-time-header",
            })

    def add_time(self, val):
        val = intz(val)
        if val < 1:
            return
        self.set_param("time", self.time + val)
        self.set_param("timetext", self.timetext)
        self.log_combat_time()

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

    def stopped(self):
        "Return True when the combat is stopped"
        return self.stage_flag("done")

    def add_command(self, command):
        "Put command to the combat queue to be executed immediately"
        self.commands.append(command)
        self.wakeup()

    def wakeup(self):
        "Wake up main combat loop if it's busy with processing now"
        if self.wakeup_channel.has_receiver():
            self.wakeup_channel.send(None)

    def process(self, timeout=1):
        "Process combat logic"
        if self._turn_order_check:
            self._turn_order_check = False
            self.turn_order.check()
        if self._check_end_condition:
            self._check_end_condition = False
            self.check_end_condition()
        self.process_commands()
        if self.stage_flag("actions"):
            self.process_actions()
        self.heartbeat()
        self.flush()
        try:
            self.wakeup_channel.receive(timeout)
        except TimeoutError:
            self.idle()

    def globs(self):
        return {
            "local": ScriptMemoryObject()
        }

    def execute_script(self, tag, globs, description=None):
        "Execute combat script with given code"
        self.call("combats.execute-script", self, self.script_code(tag), globs, description=description)

    def execute_member_script(self, member, tag, globs, description=None):
        "Execute combat script for given member"
        globs["member"] = member
        self.execute_script(tag, globs, description)
        self.enqueue_check_end_condition()

    def heartbeat(self):
        "Called on every iteration of the main loop"
        globs = self.globs()
        self.for_each_member(self.execute_member_script, "heartbeat-member", globs, lambda: self._("Member heartbeat script"))
        self.execute_script("heartbeat", globs, lambda: self._("Combat heartbeat script"))

    def process_commands(self):
        "Process enqueued commands"
        while self.commands:
            cmd = self.commands.pop(0)
            cmd.execute()

    def idle(self):
        "Do background processing"
        # execute scripts
        globs = self.globs()
        self.execute_script("idle", globs, lambda: self._("Combat idle script"))
        self.for_each_member(self.execute_member_script, "idle-member", globs, lambda: self._("Member idle script"))
        # call idle for all objects
        self.turn_order.idle()
        for member in self.members:
            member.idle()
        # process general timeouts
        elapsed = time.time() - self.start_time
        timeout = self.rulesinfo.get("timeout", 4 * 3600)
        if elapsed > timeout + 600:
            self.warning(self._("Combat %s terminated due to too long timeout"), self.uuid)
            os._exit(0)
        elif self.stage_flag("actions") and elapsed > timeout:
            self.info(self._("Combat %s timed out"), self.uuid)
            self.draw()

    def flush(self):
        "Flush pending messages"
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
        # commit logs
        if self.log:
            self.log.flush()
        # deliver new log entries
        if self.not_delivered_log:
            for controller in self.controllers:
                controller.deliver_log(self.not_delivered_log)
            self.not_delivered_log = []
        # flush everything to the clients
        for controller in self.controllers:
            controller.flush()
        self.call("stream.flush")

    def set_log(self, log):
        "Attach logging system to the combat"
        self.log = log

    def textlog(self, entry):
        "Add entry to combat log"
        if self.time_mode == "begin":
            entry["text"] = u'<span class="combat-log-time">%s</span> %s' % (self.timetext, entry.get("text", u""))
        self.not_delivered_log.append(entry)
        if self.log:
            self.log.textlog(entry)
        self._textlog_ring.append(entry)
        l = len(self._textlog_ring)
        if l > textlog_ring_size:
            del self._textlog_ring[0:l - textlog_ring_size]

    def syslog(self, entry):
        "Add entry to combat debug log"
        if self.log:
            self.log.syslog(entry)

    def stop(self):
        "Terminate combat"
        self.set_stage("done")

    # Scripting

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "id":
            return self.uuid
        elif attr == "stage":
            return self.stage
        elif attr == "stage_flags":
            return CombatStageFlags(self)
        elif attr == "time":
            return self.time
        elif attr == "timetext":
            return self.timetext
        elif attr == "now":
            return self.now_local()
        # team list
        m = re_team_list.match(attr)
        if m:
            team = intz(m.group(1))
            return self.call("l10n.literal_enumeration", [u'<span class="combat-log-member">%s</span>' % member.name for member in self.members if member.team == team])
        # parameters
        m = re_param_attr.match(attr)
        if m:
            return self.param(attr, handle_exceptions)
        if handle_exceptions:
            return None
        else:
            raise AttributeError(attr)

    def script_set_attr(self, attr, val, env):
        if attr == "stage":
            return self.set_stage(val)
        # parameters
        m = re_param_attr.match(attr)
        if m:
            return self.set_param(attr, val)
        raise ScriptRuntimeError(self._("Invalid attribute '%s'") % attr, env)

    def store(self):
        pass

    # Actions

    def execute_action(self, action):
        "Start executing action"
        self.ready_actions.append(action)
    
    def process_actions(self):
        "Process actions logic"
        self.process_ready_actions()
        self.process_stopped_actions()

    def process_ready_actions(self):
        """
        For every ready action call begin() method and move the action to the list
        of running actions
        """
        if self.ready_actions:
            actions = self.ready_actions
            self.ready_actions = []
            for act in actions:
                if act.source.active:
                    act.begin()
                    self.running_actions.append(act)
            self.enqueue_turn_order_check()
            self.actions_started()
            self.enqueue_check_end_condition()

    def process_stopped_actions(self):
        "For every stopped action call end() method and remove the action from the list"
        if self.running_actions:
            i = 0
            while i < len(self.running_actions):
                act = self.running_actions[i]
                if act.stopped():
                    act.end()
                    del self.running_actions[i]
                else:
                    i += 1
            self.enqueue_turn_order_check()
            self.actions_stopped()
            self.enqueue_check_end_condition()

    def enqueue_check_end_condition(self):
        "Enqueue check_end_condition() to be called on the next iteration of the main loop"
        self._check_end_condition = True
        self.wakeup()

    def check_end_condition(self):
        "Check combat end condition (0 or 1 teams active)"
        if self.stage_flag("actions"):
            teams = set()
            for member in self.members:
                if member.active:
                    teams.add(member.team)
            teams = list(teams)
            if len(teams) == 0:
                self.draw()
            elif len(teams) == 1:
                self.victory(teams[0])

    def draw(self):
        "Combat finished with draw"
        self.syslog({
            "type": "draw",
            "text": self._("Combat was a draw"),
            "cls": "combat-syslog-end",
        })
        for member in self.members:
            member.draw()
        globs = self.globs()
        self.for_each_member(self.execute_member_script, "draw-member", globs, lambda: self._("Combat draw script for a member"))
        self.execute_script("draw", globs, lambda: self._("Combat draw script"))

    def victory(self, team):
        "Combat finished with victory of specified team"
        self.syslog({
            "type": "victory",
            "team": team,
            "text": self._("Victory of team {team}").format(
                team=team,
            ),
            "cls": "combat-syslog-end",
        })
        winners_list = []
        loosers_list = []
        first_winner = None
        first_looser = None
        for member in self.members:
            if member.team != team:
                member.defeat()
                loosers_list.append(member)
                if first_looser is None:
                    first_looser = member
        for member in self.members:
            if member.team == team:
                member.victory()
                winners_list.append(member)
                if first_winner is None:
                    first_winner = member
        globs = self.globs()
        globs["winner_team"] = team
        globs["winners_list"] = self.call("l10n.literal_enumeration", [u'<span class="combat-log-member">%s</span>' % member.name for member in winners_list])
        globs["loosers_list"] = self.call("l10n.literal_enumeration", [u'<span class="combat-log-member">%s</span>' % member.name for member in loosers_list])
        globs["first_winner"] = first_winner
        globs["first_looser"] = first_looser
        globs["winners_count"] = len(winners_list)
        globs["loosers_count"] = len(loosers_list)
        for member in self.members:
            if member.team != team:
                self.execute_member_script(member, "defeat-member", globs, lambda: self._("Combat defeat script for a member"))
        for member in self.members:
            if member.team == team:
                self.execute_member_script(member, "victory-member", globs, lambda: self._("Combat victory script for a member"))
        self.execute_script("victory", globs, lambda: self._("Combat victory script"))

    def notify_stopped(self):
        "Call this method to signal combat that it's finally stopped"
        for member in self.members:
            if member.may_turn:
                member.turn_take()
        for member in self.members:
            member.stopped()

    def actions_started(self):
        "Called after ready actions started"
        globs = self.globs()
        self.for_each_member(self.execute_member_script, "actions-started-member", globs, lambda: self._("Combat actions started script for a member"))
        self.execute_script("actions-started", globs, lambda: self._("Combat actions started script"))

    def actions_stopped(self):
        "Called after ready actions stopped"
        globs = self.globs()
        self.for_each_member(self.execute_member_script, "actions-stopped-member", globs, lambda: self._("Combat actions stopped script for a member"))
        self.execute_script("actions-stopped", globs, lambda: self._("Combat actions stopped script"))

    def enqueue_turn_order_check(self):
        "Ask combat server to call turn_order check() on the next iteration"
        self._turn_order_check = True
        self.wakeup()

    def for_each_member(self, callback, *args, **kwargs):
        "Call callback for every combat member. Member is passed as a first argument"
        for member in self.members:
            callback(member, *args, **kwargs)

    def __unicode__(self):
        return self._("[Combat %s]") % self.uuid

    def __str__(self):
        return utf2str(unicode(self))

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

class CombatStageFlags(CombatObject):
    "CombatStageFlags is a script object (combat.stage_flags)"

    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatStageFlags"):
        CombatObject.__init__(self, combat, fqn)

    def script_attr(self, attr, handle_exceptions=True):
        return self.combat.stage_flag(attr)

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
        self.attrs = {}
        self.till_time = None
        self.executing = False

    def set_source(self, source):
        "Set combat action source"
        self.source = source

    def add_target(self, member):
        "This method adds another target to the action"
        self.targets.append(member)

    def set_attribute(self, key, value):
        "This method sets action attribute to the specific value"
        self.attrs[key] = value

    def for_each_target(self, callback, *args, **kwargs):
        "Call callback for every action target. Target is passed as a first argument"
        for target in self.targets:
            callback(target, *args, **kwargs)

    def script_code(self, tag):
        "Get combat script code (syntax tree)"
        if self.code not in self.combat.actions:
            return []
        return self.combat.actions[self.code].get("script-%s" % tag, [])

    def execute_script(self, tag, globs, description=None):
        self.call("combats.execute-script", self.combat, self.script_code(tag), globs, description=description)

    def enqueued(self):
        "Do any processing when the action is enqueued"
        globs = self.globs()
        self.execute_script("enqueued", globs, lambda: self._("Combat action '%s' script when enqueued") % self.code)

    def begin(self):
        "Do any processing in the beginning of the action"
        text = u"{text}: source={source}, targets={targets}".format(
            text=self._("Action {action} has started").format(action=self.code),
            source=self.source.id,
            targets=[t.id for t in self.targets] if type(self.targets) == list else self.targets,
        )
        if self.till_time is not None:
            text += u", till_time=%s" % self.till_time
        self.combat.syslog({
            "text": text,
            "cls": "combat-syslog-action-begin",
        })
        globs = self.globs()
        self.for_each_target(self.execute_targeted_script, "begin-target", globs, lambda: self._("Combat action '%s' begin target script") % self.code)
        self.execute_script("begin", globs, lambda: self._("Combat action '%s' begin script") % self.code)
        self.executing = True

    def end(self):
        "Do any processing in the end of the action"
        text = self._("Action {action} has stopped").format(action=self.code)
        self.combat.syslog({
            "text": u"{text}: source={source}, targets={targets}".format(
                text=text,
                source=self.source.id,
                targets=[t.id for t in self.targets] if type(self.targets) == list else self.targets,
            ),
            "cls": "combat-syslog-action-end",
        })
        globs = self.globs()
        self.for_each_target(self.execute_targeted_script, "end-target", globs, lambda: self._("Combat action '%s' end target script") % self.code)
        self.execute_script("end", globs, lambda: self._("Combat action '%s' end script") % self.code)
        self.executing = False

    def set_code(self, code):
        "Set action code"
        self.code = code

    def stopped(self):
        "Ask action whether it is stopped"
        if self.till_time is not None:
            return self.combat.time >= self.till_time
        else:
            return True

    def execute_targeted_script(self, target, tag, globs, description=None):
        globs["target"] = target
        self.execute_script(tag, globs, description)

    def globs(self):
        globs = self.combat.globs()
        globs["source"] = self.source
        globs["targets"] = lambda: self.call("l10n.literal_enumeration", [t.name for t in self.targets])
        for k, v in self.attrs.iteritems():
            globs[k] = v
        return globs

    def script_attr(self, attr, handle_exceptions=True):
        # parameters
        if re_attr.match(attr):
            return self.attrs.get(attr)
        if handle_exceptions:
            return None
        else:
            raise ScriptRuntimeError(self._("Invalid attribute name: '%s'") % attr, None)

class CombatMember(CombatObject, CombatParamsContainer):
    system_params = set(["name", "sex", "team", "may_turn", "active", "image", "targets"])

    "Members take part in combats. Every fighting entity is a member"
    def __init__(self, combat, fqn="mg.mmorpg.combats.core.CombatMember"):
        CombatObject.__init__(self, combat, fqn)
        CombatParamsContainer.__init__(self)
        self.pending_actions = []
        self.controllers = []
        self.clear_available_action_cache()
        self.log = combat.log

    def get_short_info(self):
        return {
            "id": getattr(self, "id", None),
            "name": self.param("name"),
            "sex": self.param("sex"),
            "team": self.param("team"),
            "may_turn": self.param("may_turn"),
            "active": self.param("active"),
            "image": self.param("image")
        }

    def set_param(self, key, val):
        if CombatParamsContainer.set_param(self, key, val):
            self.clear_available_action_cache()
            return True
        else:
            return False

    def is_a_combat_member(self):
        return True

    def add_controller(self, controller):
        "Attach CombatMemberController to the member"
        self.controllers.append(controller)

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
        act.set_source(self)
        # log action
        if self.log:
            self.log.syslog({
                "type": "enq",
                "source": self.id,
                "code": act.code,
                "targets": [t.id for t in act.targets],
            })
        act.enqueued()
        if act.code in self.combat.actions and self.combat.actions[act.code].get("immediate"):
            self.combat.execute_action(act)
            if self.may_turn:
                self.deliver_turn_got()
            self.combat.wakeup()
        else:
            self.pending_actions.append(act)
            # call appropriate script
            globs = self.combat.globs()
            self.combat.execute_member_script(self, "turnmade", globs, lambda: self._("'After turn made' script"))
        # if this member has turn right already, notify turn manager
        if self.may_turn:
            if self.combat.stage_flag("actions"):
                self.combat.enqueue_turn_order_check()

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
        elif attr == "may_turn":
            return self.may_turn
        elif attr == "active":
            return 1 if self.active else 0
        elif attr == "targets":
            return u"%s" % self.targets
        # parameters
        m = re_param_attr.match(attr)
        if m:
            return self.param(attr, handle_exceptions)
        if handle_exceptions:
            return None
        else:
            raise ScriptRuntimeError(self._("Invalid attribute name: '%s'") % attr, None)

    def script_set_attr(self, attr, val, env):
        # parameters
        if attr == "targets":
            return self.set_param(attr, val)
        elif attr == "active":
            return self.set_param(attr, 1 if val else 0)
        m = re_param_attr.match(attr)
        if m:
            return self.set_param(attr, val)
        raise ScriptRuntimeError(self._("Invalid attribute name: '%s'") % attr, env)

    def store(self):
        pass

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
        return self._params.get("active", 1)
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

    # combat start

    def started(self):
        "Called on combat start"

    # combat end

    def victory(self):
        "Called on victory of this member"

    def defeat(self):
        "Called on defeat of this member"

    def draw(self):
        "Called on draw of this member"

    def stopped(self):
        "Called on combat stop"

    # Turn order

    @property
    def may_turn(self):
        return self._params.get("may_turn", False)

    def deliver_turn_got(self):
        "Resend 'turn_got' event to the client"
        for controller in self.controllers:
            controller.deliver_turn_got()

    def turn_give(self, **kwargs):
        "Grant right of making turn to the member"
        self.set_param("may_turn", True)
        self.clear_available_action_cache()
        globs = self.combat.globs()
        for k, v in kwargs.iteritems():
            globs[k] = v
        self.combat.execute_member_script(self, "turngot", globs, lambda: self._("'After get turn' script"))
        for controller in self.controllers:
            controller.turn_got()

    def turn_take(self, **kwargs):
        "Revoke right of making turn from the member"
        self.set_param("may_turn", False)
        globs = self.combat.globs()
        for k, v in kwargs.iteritems():
            globs[k] = v
        self.combat.execute_member_script(self, "turnlost", globs, lambda: self._("'After lost turn' script"))
        for controller in self.controllers:
           controller.turn_lost()

    def turn_timeout(self):
        "Revoke right of making turn from the member due to timeout"
        self.set_param("may_turn", False)
        globs = self.combat.globs()
        self.combat.execute_member_script(self, "turntimeout", globs, lambda: self._("'After turn timeout' script"))
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
            available = target.active
        elif targets == "enemies":
            available = self.team != target.team and target.active
        elif targets == "allies":
            available = self.team == target.team and self.id != target.id and target.active
        elif targets == "allies-myself":
            available = self.team == target.team and target.active
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
            del globs["target"]
            if val:
                targets.append(target.id)
        if not targets:
            self.set_param("targets", None)
        else:
            self.set_param("targets", [random.choice(targets)])

    def targets_min(self, act):
        "Minimal number of targets of the given action"
        return self.call("script.evaluate-expression", act.get("targets_min", 1), globs={"combat": self.combat, "viewer": self}, description=self._("Minimal number of targets for combat action %s") % act["code"])

    def targets_max(self, act):
        "Maximal number of targets of the given action"
        return self.call("script.evaluate-expression", act.get("targets_max", 1), globs={"combat": self.combat, "viewer": self}, description=self._("Maximal number of targets for combat action %s") % act["code"])

    def __unicode__(self):
        return self._("[CombatMember {id}/{name}]").format(id=self.id, name=self.name)

    def __str__(self):
        return utf2str(unicode(self))

    def sound(self, *args, **kwargs):
        for controller in self.controllers:
            controller.deliver_sound(*args, **kwargs)

    def music(self, *args, **kwargs):
        for controller in self.controllers:
            controller.deliver_music(*args, **kwargs)

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
        if self.combat._textlog_ring:
            self.controller.deliver_log(self.combat._textlog_ring)
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
            if act.get("targets") == "none" or act.get("targets") == "myself":
                show = True
                targets_min = 0
                targets_max = 0
                targets = None
            else:
                targets = []
                for target in self.combat.members:
                    if self.member.target_available(act, target):
                        targets.append(target.id)
                if targets:
                    targets_min = self.member.targets_min(act)
                    targets_max = self.member.targets_max(act)
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

    def flush(self):
        "Called when needed to flush all pending messages"

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

    def deliver_log(self, entries):
        "Called when we have to deliver some combat log entries to the client"

    def deliver_sound(self, *args, **kwargs):
        "Send sound command to the member"

    def deliver_music(self, *args, **kwargs):
        "Send music command to the member"

class CombatSystemInfo(object):
    "CombatInfo is an object describing rules of the combat system"
    def params(self):
        "Returns list of member parameters"
