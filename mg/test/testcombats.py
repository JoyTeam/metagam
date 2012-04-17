#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet
from mg.core import *
from mg.core.cass import CassandraPool
from mg.core.memcached import MemcachedPool
from cassandra.ttypes import *
import logging
import os
from mg.mmorpg.combats.core import *
from mg.mmorpg.combats.turn_order import *
from mg.mmorpg.combats.simulation import *
from mg.mmorpg.combats.daemon import *

modlogger = logging.getLogger("")
modlogger.setLevel(logging.ERROR)
stderr_channel = logging.StreamHandler()
stderr_channel.setLevel(logging.ERROR)
modlogger.addHandler(stderr_channel)

class TurnTimeout(Exception):
    pass

class ManualDebugController(CombatMemberController):
    def __init__(self, member, fqn="ManualDebugController"):
        CombatMemberController.__init__(self, member, fqn)
        self.timeout_fired = False

    def turn_timeout(self):
        self.timeout_fired = True

    def idle(self):
        self.app().mc.get("test")
        if self.timeout_fired:
            self.timeout_fired = False
            raise TurnTimeout()

class TrivialAIController(CombatMemberController):
    def __init__(self, member, fqn="TrivialAIController"):
        CombatMemberController.__init__(self, member, fqn)

    def idle(self):
        self.app().mc.get("test")

    def turn_got(self):
        act = CombatAction(self.combat)
        for m in self.member.enemies:
            act.add_target(m)
        self.member.action(act)

class DebugCombatLog(CombatLog):
    def __init__(self, combat, fqn="DebugCombatLog"):
        CombatLog.__init__(self, combat, fqn)
        self.dump = []

class TestCombats(unittest.TestCase):
    def setUp(self):
        self.inst = Instance()
        self.inst.dbpool = CassandraPool((("director-db", 9160),))
        self.inst.mcpool = MemcachedPool(("director-mc", 11211))
        self.app = Application(self.inst, "mgtest")
        self.app.modules.load(["mg.core.l10n.L10n"])

    def test_00_stages(self):
        # creating combat
        combat = SimulationCombat(self.app)
        self.assertEqual(combat.stage, "init")
        # running combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        combat.run(turn_order)
        self.assertEqual(combat.stage, "combat")
        self.assertRaises(CombatAlreadyRunning, combat.run, turn_order)
        self.assertRaises(CombatInvalidStage, combat.set_stage, "invalid")
        self.assertFalse(combat.stage_flag("done"))
        # terminating combat
        combat.set_stage("done")
        self.assertTrue(combat.stage_flag("done"))

    def test_01_turn_order(self):
        combat = SimulationCombat(self.app)
        daemon = CombatDaemon(combat)
        # joining member 1
        member1 = CombatMember(combat)
        ai1 = ManualDebugController(member1)
        member1.add_controller(ai1)
        member1.set_team(1)
        combat.join(member1)
        # joining member 2
        member2 = CombatMember(combat)
        ai2 = ManualDebugController(member2)
        member2.add_controller(ai2)
        member2.set_team(2)
        combat.join(member2)
        # checking list of members and ensuring
        # that nobody has right to turn before
        # combat started
        self.assertEqual(combat.members, [member1, member2])
        self.assertFalse(member1.may_turn)
        self.assertFalse(member2.may_turn)
        # running combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        turn_order.timeout = 1
        combat.run(turn_order)
        # member1 must have right of turn
        self.assertTrue(member1.may_turn)
        self.assertFalse(member2.may_turn)
        # waiting for turn timeout
        with Timeout.push(3):
            self.assertRaises(TurnTimeout, daemon.loop)
        # member2 must have right of turn
        self.assertFalse(member1.may_turn)
        self.assertTrue(member2.may_turn)
        # waiting for turn timeout
        with Timeout.push(3):
            self.assertRaises(TurnTimeout, daemon.loop)
        # member1 must have right of turn
        self.assertTrue(member1.may_turn)
        self.assertFalse(member2.may_turn)

    def test_02_log(self):
        combat = SimulationCombat(self.app)
        daemon = CombatDaemon(combat)
        # joining member 1
        member1 = CombatMember(combat)
        ai1 = TrivialAIController(member1)
        member1.add_controller(ai1)
        member1.set_team(1)
        combat.join(member1)
        # joining member 2
        member2 = CombatMember(combat)
        ai2 = TrivialAIController(member2)
        member2.add_controller(ai2)
        member2.set_team(2)
        combat.join(member2)
        # attaching logger
        log = DebugCombatLog(combat)
        combat.set_log(log)
        # running combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        combat.run(turn_order)
        # running combat
        with Timeout.push(3):
            daemon.loop()
        # checking combat log
        self.assertEqual(log.dump, [[1, 2], [2, 1], [1, 2], [2, 1]])

def main():
    try:
        unittest.main()
    except RuntimeError as e:
        logging.error(e)
        os._exit(1)
    except Exception as e:
        logging.exception(e)
        os._exit(1)

if __name__ == "__main__":
    dispatch(unittest.main)
