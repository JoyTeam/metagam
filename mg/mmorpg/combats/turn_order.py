from mg.mmorpg.combats.core import CombatObject
import time

class CombatTurnOrder(CombatObject):
    """
    Determines order of members to turns. It gives and takes back a right of making
    turns to the members.
    """
    def __init__(self, combat, fqn):
        CombatObject.__init__(self, combat, fqn)
        self.timeout = None

    def start(self):
        "This method notifies CombatTurnOrder about combat entered stage with actions enabled"

    def idle(self):
        "This method is called to allow CombatTurnOrder to make some background processing"

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

    def timeout_check(self):
        """
        For every member with right of turning check timeout. For timed out members call turn_timeout.
        """
        now = time.time()
        for member in self.combat.members:
            if member.may_turn and member.turn_till and now > member.turn_till:
                self.turn_timeout(member)

    def check(self):
        "This method asks CombatTurnOrder to check whether some actions may be executed"

class CombatRoundRobinTurnOrder(CombatTurnOrder):
    """
    This turn order assumes every member makes turn one after another"
    """
    def __init__(self, combat, fqn="mg.mmorpg.combats.turn_order.CombatRoundRobinTurnOrder"):
        CombatTurnOrder.__init__(self, combat, fqn)

    def start(self):
        member = self.next_turn()
        if member:
            self.turn_give(member)

    def idle(self):
        self.timeout_check()

    def turn_timeout(self, member):
        next_member = self.next_turn()
        CombatTurnOrder.turn_timeout(self, member)
        if next_member:
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

    def check(self):
        if self.combat.stage_flag("actions"):
            for member in self.combat.members:
                if member.active and member.may_turn and member.pending_actions:
                    next_member = self.next_turn()
                    self.turn_take(member)
                    act = member.pending_actions.pop(0)
                    self.combat.execute_action(act)
                    self.combat.process_actions()
                    if next_member and self.combat.stage_flag("actions"):
                        self.turn_give(next_member)
                    break
