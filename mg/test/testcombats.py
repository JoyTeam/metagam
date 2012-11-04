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
from mg.mmorpg.combats.scripts import ScriptedCombatAction
from mg.mmorpg.combats.logs import *
import re

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

class DebugCombatAction(ScriptedCombatAction):
    def __init__(self, combat, fqn="DebugCombatAction"):
        ScriptedCombatAction.__init__(self, combat, fqn)

    def script_code(self, tag):
        if tag == "end-target":
            return [
                ['damage', ['glob', 'target'], 'hp', 5],
            ]
        elif tag == "end":
            return [
                ['log', [
                    ['.', ['glob', 'source'], 'name'],
                    ' damaged ',
                    ['glob', 'targets'],
                ]]
            ]
        else:
            return []

class TrivialAIController(CombatMemberController):
    def __init__(self, member, fqn="TrivialAIController"):
        CombatMemberController.__init__(self, member, fqn)

    def idle(self):
        self.app().mc.get("test")

    def turn_got(self):
        act = ScriptedCombatAction(self.combat)
        for m in self.member.enemies:
            act.add_target(m)
        self.member.enqueue_action(act)

class DebugCombatLog(CombatLog):
    def __init__(self, combat, fqn="DebugCombatLog"):
        CombatLog.__init__(self, combat, fqn)
        self._syslog = []

    def syslog(self, entry):
        self._syslog.append(entry)

class FakeObj(object):
    def set(self, key, val):
        pass

    def store(self):
        pass

class DebugCombatService(CombatService):
    def __init__(self, combat, fqn="mg.test.combats.DebugCombatService"):
        mg.SingleApplicationWebService.__init__(self, combat.app(), "combat", "combat", "cmb", fqn)
        self.combat_id = None
        self.cobj = FakeObj()
        CombatObject.__init__(self, combat, fqn, weak=False)
        self.running = False

    def add_members(self):
        pass

    def serve_any_port(self):
        self.addr = (None, None)

    def run_combat(self):
        if self.running:
            return
        self.running = True
        turn_order = CombatRoundRobinTurnOrder(self.combat)
        turn_order.timeout = 1
        self.combat.run(turn_order)

class TestCombats(unittest.TestCase):
    def setUp(self):
        self.inst = Instance("combat-test", "metagam")
        self.inst._dbpool = CassandraPool((("localhost", 9160),))
        self.inst._mcpool = MemcachedPool(("localhost", 11211))
        self.app = Application(self.inst, "mgtest")
        self.app.modules.load(["mg.core.l10n.L10n", "mg.constructor.script.ScriptEngine", "mg.mmorpg.combats.scripts.CombatScripts", "mg.mmorpg.combats.scripts.CombatScriptsAdmin"])

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
        service = DebugCombatService(combat)
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
        service.run_combat()
        # member1 must have right of turn
        self.assertTrue(member1.may_turn)
        self.assertFalse(member2.may_turn)
        # waiting for turn timeout
        with Timeout.push(3):
            self.assertRaises(TurnTimeout, service.run)
        # member2 must have right of turn
        self.assertFalse(member1.may_turn)
        self.assertTrue(member2.may_turn)
        # waiting for turn timeout
        with Timeout.push(3):
            self.assertRaises(TurnTimeout, service.run)
        # member1 must have right of turn
        self.assertTrue(member1.may_turn)
        self.assertFalse(member2.may_turn)

    def test_02_scripts(self):
        combat = SimulationCombat(self.app)
        # compiling script
        script_text = 'damage target.hp 5 set source.p_damage = source.p_damage + last_damage'
        code = self.app.hooks.call("combats-admin.parse-script", script_text)
        self.assertEqual(code, [
            ['damage', ['glob', 'target'], 'hp', 5],
            ['set', ['glob', 'source'], 'p_damage', ['+', ['.', ['glob', 'source'], 'p_damage'], ['glob', 'last_damage']]],
        ])
        # joining members
        member1 = CombatMember(combat)
        member1.set_team(1)
        combat.join(member1)
        member2 = CombatMember(combat)
        member2.set_team(2)
        combat.join(member2)
        globs = {"source": member1, "target": member2}
        # executing script
        self.app.hooks.call("combats.execute-script", combat, code, globs=globs, handle_exceptions=False)
        self.assertEqual(member1.param("damage"), 0)
        self.assertEqual(member2.param("hp"), 0)
        self.assertEqual(globs["last_damage"], 0)
        # executing script again
        member2.set_param("hp", 7)
        self.app.hooks.call("combats.execute-script", combat, code, globs=globs, handle_exceptions=False)
        self.assertEqual(member1.param("damage"), 5)
        self.assertEqual(member2.param("hp"), 2)
        self.assertEqual(globs["last_damage"], 5)
        # executing script one more time
        self.app.hooks.call("combats.execute-script", combat, code, globs=globs, handle_exceptions=False)
        self.assertEqual(member1.param("damage"), 7)
        self.assertEqual(member2.param("hp"), 0)
        self.assertEqual(globs["last_damage"], 2)
        # unparsing
        script = self.app.hooks.call("combats-admin.unparse-script", code)
        script = re.sub(r'\s+', ' ', script).strip()
        self.assertEqual(script, script_text)

    def test_03_log(self):
        combat = SimulationCombat(self.app)
        service = DebugCombatService(combat)
        # attaching logger
        log = DebugCombatLog(combat)
        combat.set_log(log)
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
        # running combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        combat.run(turn_order)
        # checking combat log
        self.assertEqual(len(log._syslog), 3)
        self.assertEqual(log._syslog[0]["type"], "join")
        self.assertEqual(log._syslog[0]["member"], 1)
        self.assertEqual(log._syslog[1]["type"], "join")
        self.assertEqual(log._syslog[1]["member"], 2)
        self.assertEqual(log._syslog[2]["type"], "stage")
        self.assertEqual(log._syslog[2]["stage"], "combat")

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
