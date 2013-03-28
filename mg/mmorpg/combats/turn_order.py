from mg.mmorpg.combats.core import CombatObject
from mg.core.tools import *
import time
import random

class CombatTurnOrder(CombatObject):
    """
    Determines order of members to turns. It gives and takes back a right of making
    turns to the members.
    """
    def __init__(self, combat, fqn):
        CombatObject.__init__(self, combat, fqn)
        self.timeout = None
        self.active_members = set()
        self.started = False

    def start(self):
        "This method notifies CombatTurnOrder about combat entered stage with actions enabled"
        self.started = True
        for member in self.combat.members:
            if member.active:
                self.active_members.add(member)
        self.check()

    def check(self):
        "This method asks CombatTurnOrder to check whether some actions may be executed"
        self.update_active_members()

    def update_active_members(self):
        "Update local cache of active members and call member_died() and member_alive() respectively"
        if self.started and self.combat.stage_flag("actions"):
            for member in self.active_members.copy():
                if not member.active:
                    self.active_members.remove(member)
                    self.member_died(member)
            for member in self.combat.members:
                if member.active and member not in self.active_members:
                    self.active_members.add(member)
                    self.member_alive(member)

    def member_alive(self, member):
        "Do some actions on member start or resurrect"

    def member_died(self, member):
        "Do some actions on member death"
        if member.may_turn:
            self.turn_take(member)

    def idle(self):
        "This method is called to allow CombatTurnOrder to make some background processing"
        now = time.time()
        any_timeout = False
        for member in self.combat.members:
            if member.may_turn and member.turn_till and now > member.turn_till:
                self.turn_timeout(member)
                any_timeout = True
        if any_timeout:
            self.check()

    def turn_give(self, member):
        "Give member right of turn"
        member.turn_give()
        if self.timeout is None:
            member.turn_till = None
        else:
            member.turn_till = time.time() + self.timeout

    def turn_take(self, member):
        "Revoke right of turn from the member"
        member.turn_take()
        member.turn_till = None

    def turn_timeout(self, member):
        "Revoke right of turn from the member due to timeout"
        member.turn_timeout()
        member.turn_till = None

class CombatRoundRobinTurnOrder(CombatTurnOrder):
    """
    This turn order assumes every member makes turn each after another"
    """
    def __init__(self, combat, fqn="mg.mmorpg.combats.turn_order.CombatRoundRobinTurnOrder"):
        CombatTurnOrder.__init__(self, combat, fqn)

    def check(self):
        CombatTurnOrder.check(self)
        if self.combat.stage_flag("actions"):
            any_active = False
            for member in self.combat.members:
                if member.may_turn:
                    if member.active and member.pending_actions:
                        next_member = self.next_turn()
                        self.turn_take(member)
                        act = member.pending_actions.pop(0)
                        self.combat.execute_action(act)
                        self.combat.process_actions()
                        self.combat.add_time(1)
                        if next_member and self.combat.stage_flag("actions"):
                            self.turn_give(next_member)
                    return
                if member.active:
                    any_active = True
            if any_active:
                member = self.next_turn()
                if member:
                    self.turn_give(member)

    def turn_timeout(self, member):
        next_member = self.next_turn()
        CombatTurnOrder.turn_timeout(self, member)
        if next_member:
            self.turn_give(next_member)

    def member_died(self, member):
        may_turn = member.may_turn
        if may_turn:
            next_member = self.next_turn()
        CombatTurnOrder.member_died(self, member)
        if may_turn and next_member:
            self.turn_give(next_member)

    def next_turn(self):
        "Evaluate the next member who will take right of turn"
        first_active = None
        previous_turn = None
        for member in self.combat.members:
            if member.active:
                if previous_turn:
                    # found active member after previous member who had a right to turn
                    return member
                if not first_active:
                    # remember first active member in the list
                    first_active = member
            if not previous_turn and member.may_turn:
                previous_turn = member
        # if no active members after member who had a right to turn
        # select first active member
        return first_active

class CombatPairExchangesTurnOrder(CombatTurnOrder):
    """
    Each opponent chooses an attack to the randomly selected opponent. When their attacks match, the system performs strike exchange
    """
    def __init__(self, combat, fqn="mg.mmorpg.combats.turn_order.CombatPairExchangesTurnOrder"):
        CombatTurnOrder.__init__(self, combat, fqn)
        self._actions = {}

    def actions(self, member):
        try:
            return self._actions[member.id]
        except KeyError:
            self._actions[member.id] = {}
            return self._actions[member.id]

    def member_check(self, m1, active_members):
        # m1 is already dead
        if not m1.active:
            if m1.may_turn:
                self.turn_take(m1)
            return
        # m1 is alive
        if m1.may_turn:
            # check whether target member is alive
            if type(m1.targets) == list and len(m1.targets):
                target = self.combat.member(m1.targets[0])
                if target.active:
                    return
                # target is dead. Take turn order and find new target
                self.turn_take(m1)
        # find a target (m2) can be attacked by m1
        m1_actions = self.actions(m1)
        active_members = list(active_members)
        random.shuffle(active_members)
        for m2 in active_members:
            if m1.team != m2.team and not m1_actions.get(m2.id):
                m1.set_targets([m2.id])
                self.turn_give(m1)
                break

    def check(self):
        CombatTurnOrder.check(self)
        if self.combat.stage_flag("actions"):
            for m1 in self.combat.members:
                self.member_check(m1, self.active_members)
            for m1 in self.active_members.copy():
                if m1.may_turn and m1.pending_actions:
                    self.turn_take(m1)
                    anything_executed = False
                    while m1.pending_actions:
                        act1 = m1.pending_actions.pop(0)
                        if type(m1.targets) != list or len(m1.targets) != 1:
                            continue
                        if [m.id for m in act1.targets] != m1.targets:
                            continue
                        m2 = act1.targets[0]
                        self.actions(m1)[m2.id] = act1
                        act2 = self.actions(m2).get(m1.id)
                        if act2:
                            del self.actions(m1)[m2.id]
                            del self.actions(m2)[m1.id]
                            # actions match. execute then together
                            act1.set_attribute("a_pair", act2)
                            act2.set_attribute("a_pair", act1)
                            self.combat.execute_action(act2)
                            self.combat.execute_action(act1)
                            self.combat.process_actions()
                            self.combat.add_time(1)
                            self.update_active_members()
                            anything_executed = True
                    if not anything_executed:
                        self.member_check(m1, self.active_members)

    def member_died(self, member):
        CombatTurnOrder.member_died(self, member)
        for m1 in self.combat.members:
            if m1.active and m1.may_turn and member.id in m1.targets:
                self.turn_take(m1)

    def turn_timeout(self, member):
        # if somebody wants to attack this member, let them do it
        any_action = False
        for m1 in self.active_members.copy():
            if m1.active:
                actions = self.actions(m1)
                act = actions.get(member.id)
                if act:
                    del actions[member.id]
                    act.set_attribute("a_pair", None)
                    self.combat.execute_action(act)
                    any_action = True
        if any_action:
            self.combat.process_actions()
            self.combat.add_time(1)
            self.update_active_members()
        CombatTurnOrder.turn_timeout(self, member)

class CombatTimeLineTurnOrder(CombatTurnOrder):
    """
    Every member gets right of turn when his previous action finished. Every action takes specific number of time units to execute
    """
    def __init__(self, combat, fqn="mg.mmorpg.combats.turn_order.CombatPairExchangesTurnOrder"):
        CombatTurnOrder.__init__(self, combat, fqn)
        self._actions = {}

    def check(self):
        CombatTurnOrder.check(self)
        if self.combat.stage_flag("actions"):
            process_ready = False
            for member in self.active_members:
                if member.may_turn:
                    if member.pending_actions:
                        self.turn_take(member)
                        act = member.pending_actions.pop(0)
                        self._actions[member.id] = act
                        duration = self.combat.actions[act.code].get("duration")
                        globs = act.globs()
                        duration = intz(self.call("script.evaluate-expression", duration, globs=globs, description=lambda: self._("Evaluation of action duration")))
                        print "duration=%s" % duration
                        act.till_time = self.combat.time + duration
                        self.combat.execute_action(act)
                        process_ready = True
                else:
                    act = self._actions.get(member.id)
                    if act:
                        if not act.executing:
                            del self._actions[member.id]
                            self.turn_give(member)
                    else:
                        self.turn_give(member)
            if process_ready:
                self.combat.process_ready_actions()
        self.check_time()

    def idle(self):
        CombatTurnOrder.idle(self)
        self.check_time()

    def check_time(self):
        if self.combat.stage_flag("actions"):
            for member in self.active_members:
                act = self._actions.get(member.id)
                if not act or not act.executing:
                    return
            self.combat.add_time(1)
