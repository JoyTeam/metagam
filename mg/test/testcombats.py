#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

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

import unittest
from concurrence import dispatch, Tasklet, Timeout, TimeoutError
from mg.core import *
from mg.core.cass import CassandraPool
from mg.core.memcached import MemcachedPool
from cassandra.ttypes import *
import logging
import os
import mg
from mg.mmorpg.combats.core import *
from mg.mmorpg.combats.turn_order import *
from mg.mmorpg.combats.simulation import *
from mg.mmorpg.combats.daemon import *
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

class DebugCombat(SimulationCombat):
    def __init__(self, app, fqn="DebugCombat", flags={}):
        SimulationCombat.__init__(self, app, fqn)
        self._debug_flags = flags

    def script_code(self, tag):
        res = []
        if tag == "heartbeat" or tag == "idle" or tag == "start" or tag == "actions-started" or tag == "actions-stopped":
            if tag in self._debug_flags:
                res.append(['syslog', [
                        '%s called' % tag
                ]])
            if tag == "actions-stopped":
                res.append([
                    'if', ['.', ['.', ['glob', 'combat'], 'stage_flags'], 'actions'],
                    [
                        [
                            'select',
                            ['glob', 'local'], 'alive',
                            'distinct',
                            ['.', ['glob', 'member'], 'team'],
                            'members',
                            ['>', ['.', ['glob', 'member'], 'p_hp'], 0]
                        ],
                        [
                            'if', ['<', ['.', ['glob', 'local'], 'alive'], 2],
                            [
                                [
                                    'set',
                                    ['glob', 'combat'], 'stage',
                                    'done'
                                ]
                            ]
                        ]
                    ]
                ])
        elif tag == "heartbeat-member" or tag == "idle-member":
            if tag in self._debug_flags:
                res.append(['syslog', [
                    '%s called for ' % tag,
                    ['.', ['glob', 'member'], 'name']
                ]])
        return res

class DebugCombatAction(CombatAction):
    def __init__(self, combat, fqn="DebugCombatAction"):
        CombatAction.__init__(self, combat, fqn)
        self.set_code("foo")

    def script_code(self, tag):
        if tag == "end-target":
            return [
                ['damage', ['glob', 'target'], 'p_hp', 5],
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
        act = DebugCombatAction(self.combat)
        for m in self.member.enemies:
            act.add_target(m)
        self.member.enqueue_action(act)

class DebugCombatLog(CombatLog):
    def __init__(self, combat, fqn="DebugCombatLog"):
        CombatLog.__init__(self, combat, fqn)
        self._textlog = []
        self._syslog = []

    def textlog(self, entry):
        self._textlog.append(entry)

    def syslog(self, entry):
        self._syslog.append(entry)

class FakeObj(object):
    def set(self, key, val):
        pass

    def get(self, key, default=None):
        return default

    def remove(self):
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
        self.inst = mg.Instance("combat-test", "metagam")
        self.inst._dbpool = CassandraPool((("localhost", 9160),))
        self.inst._mcpool = MemcachedPool()
        self.app = mg.Application(self.inst, "mgtest")
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
        script_text = 'damage target.p_hp 5 set source.p_damage = source.p_damage + last_damage'
        code = self.app.hooks.call("combats-admin.parse-script", script_text)
        self.assertEqual(code, [
            ['damage', ['glob', 'target'], 'p_hp', 5, {}],
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
        self.assertEqual(member1.param("p_damage"), 0)
        self.assertEqual(member2.param("p_hp"), 0)
        self.assertEqual(globs["last_damage"], 0)
        # executing script again
        member2.set_param("p_hp", 7)
        self.app.hooks.call("combats.execute-script", combat, code, globs=globs, handle_exceptions=False)
        self.assertEqual(member1.param("p_damage"), 5)
        self.assertEqual(member2.param("p_hp"), 2)
        self.assertEqual(globs["last_damage"], 5)
        # executing script one more time
        self.app.hooks.call("combats.execute-script", combat, code, globs=globs, handle_exceptions=False)
        self.assertEqual(member1.param("p_damage"), 7)
        self.assertEqual(member2.param("p_hp"), 0)
        self.assertEqual(globs["last_damage"], 2)
        # unparsing
        script = self.app.hooks.call("combats-admin.unparse-script", code)
        script = re.sub(r'\s+', ' ', script).strip()
        self.assertEqual(script, script_text)

    def test_03_log(self):
        combat = SimulationCombat(self.app)
        combat._time_mode = "none"
        # attach logger
        log = DebugCombatLog(combat)
        combat.set_log(log)
        # join member 1
        member1 = CombatMember(combat)
        ai1 = TrivialAIController(member1)
        member1.add_controller(ai1)
        member1.set_team(1)
        member1.set_param("p_hp", 8)
        member1.set_name("M1")
        combat.join(member1)
        # join member 2
        member2 = CombatMember(combat)
        ai2 = TrivialAIController(member2)
        member2.add_controller(ai2)
        member2.set_team(2)
        member2.set_param("p_hp", 15)
        member2.set_name("M2")
        combat.join(member2)
        # run combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        combat.run(turn_order)
        # check combat log
        self.assertEqual(len(log._syslog), 5)
        self.assertEqual(log._syslog[0]["type"], "join")
        self.assertEqual(log._syslog[0]["member"], 1)
        self.assertEqual(log._syslog[1]["type"], "join")
        self.assertEqual(log._syslog[1]["member"], 2)
        self.assertEqual(log._syslog[2]["type"], "stage")
        self.assertEqual(log._syslog[2]["stage"], "combat")
        self.assertEqual(log._syslog[3]["time"], 0)
        self.assertEqual(log._syslog[4]["type"], "enq")
        self.assertEqual(log._syslog[4]["code"], "foo")
        self.assertEqual(log._syslog[4]["source"], 1)
        self.assertEqual(log._syslog[4]["targets"][0], 2)
        self.assertEqual(len(log._textlog), 0)
        # clear log
        log._syslog = []
        log._textlog = []
        # perform iteration of combat loop
        combat.process(0)
        self.assertEqual(len(log._syslog), 4)
        self.assertEqual(log._syslog[2]["type"], "damage")
        self.assertEqual(log._syslog[2]["source"], 1)
        self.assertEqual(log._syslog[2]["target"], 2)
        self.assertEqual(log._syslog[2]["damage"], 5)
        self.assertEqual(log._syslog[2]["param"], "p_hp")
        self.assertEqual(log._syslog[2]["oldval"], 15)
        self.assertEqual(log._syslog[2]["newval"], 10)
        self.assertEqual(log._syslog[3]["type"], "enq")
        self.assertEqual(log._syslog[3]["code"], "foo")
        self.assertEqual(log._syslog[3]["source"], 2)
        self.assertEqual(log._syslog[3]["targets"][0], 1)
        self.assertEqual(len(log._textlog), 1)
        self.assertEqual(log._textlog[0]["text"], "M1 damaged M2")
        # clear log
        log._syslog = []
        log._textlog = []
        # perform iteration of combat loop
        combat.process(0)
        self.assertEqual(len(log._syslog), 4)
        self.assertEqual(log._syslog[2]["type"], "damage")
        self.assertEqual(log._syslog[2]["source"], 2)
        self.assertEqual(log._syslog[2]["target"], 1)
        self.assertEqual(log._syslog[2]["damage"], 5)
        self.assertEqual(log._syslog[2]["param"], "p_hp")
        self.assertEqual(log._syslog[2]["oldval"], 8)
        self.assertEqual(log._syslog[2]["newval"], 3)
        self.assertEqual(log._syslog[3]["type"], "enq")
        self.assertEqual(log._syslog[3]["code"], "foo")
        self.assertEqual(log._syslog[3]["source"], 1)
        self.assertEqual(log._syslog[3]["targets"][0], 2)
        self.assertEqual(len(log._textlog), 1)
        self.assertEqual(log._textlog[0]["text"], "M2 damaged M1")
        # clear log
        log._syslog = []
        log._textlog = []
        # perform iteration of combat loop
        combat.process(0)
        self.assertEqual(len(log._syslog), 4)
        self.assertEqual(log._syslog[2]["type"], "damage")
        self.assertEqual(log._syslog[2]["source"], 1)
        self.assertEqual(log._syslog[2]["target"], 2)
        self.assertEqual(log._syslog[2]["damage"], 5)
        self.assertEqual(log._syslog[2]["param"], "p_hp")
        self.assertEqual(log._syslog[2]["oldval"], 10)
        self.assertEqual(log._syslog[2]["newval"], 5)
        self.assertEqual(log._syslog[3]["type"], "enq")
        self.assertEqual(log._syslog[3]["code"], "foo")
        self.assertEqual(log._syslog[3]["source"], 2)
        self.assertEqual(log._syslog[3]["targets"][0], 1)
        self.assertEqual(len(log._textlog), 1)
        self.assertEqual(log._textlog[0]["text"], "M1 damaged M2")
        # clear log
        log._syslog = []
        log._textlog = []
        # perform iteration of combat loop
        combat.process(0)
        self.assertEqual(len(log._syslog), 4)
        self.assertEqual(log._syslog[2]["type"], "damage")
        self.assertEqual(log._syslog[2]["source"], 2)
        self.assertEqual(log._syslog[2]["target"], 1)
        self.assertEqual(log._syslog[2]["damage"], 5)
        self.assertEqual(log._syslog[2]["param"], "p_hp")
        self.assertEqual(log._syslog[2]["oldval"], 3)
        self.assertEqual(log._syslog[2]["newval"], 0)
        self.assertEqual(log._syslog[3]["type"], "enq")
        self.assertEqual(log._syslog[3]["code"], "foo")
        self.assertEqual(log._syslog[3]["source"], 1)
        self.assertEqual(log._syslog[3]["targets"][0], 2)
        self.assertEqual(len(log._textlog), 1)
        self.assertEqual(log._textlog[0]["text"], "M2 damaged M1")

    def test_04_scripts(self):
        combat = DebugCombat(self.app)
        # attach logger
        log = DebugCombatLog(combat)
        combat.set_log(log)
        # join member 1
        member1 = CombatMember(combat)
        ai1 = TrivialAIController(member1)
        member1.add_controller(ai1)
        member1.set_team(1)
        member1.set_param("p_hp", 8)
        member1.set_name("M1")
        combat.join(member1)
        # join member 2
        member2 = CombatMember(combat)
        ai2 = TrivialAIController(member2)
        member2.add_controller(ai2)
        member2.set_team(2)
        member2.set_param("p_hp", 15)
        member2.set_name("M2")
        combat.join(member2)
        # run combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        combat.run(turn_order)
        while not combat.stopped():
            combat.process(0)
            log._syslog = []

def main():
    try:
        unittest.main()
    except RuntimeError as e:
        logging.error(e)
        os._exit(1)
    except Exception as e:
        logging.exception(e)
        os._exit(1)

# FIXME: this test is not up to date
#if __name__ == "__main__":
#    dispatch(unittest.main)
