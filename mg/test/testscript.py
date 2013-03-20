#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet, Timeout, TimeoutError
from mg.core import *
from mg.core.cass import CassandraPool
from mg.core.memcached import MemcachedPool
from mg.constructor.script_classes import ScriptParserError
from mg.mmorpg.combats.core import *
from mg.mmorpg.combats.simulation import SimulationCombat
from cassandra.ttypes import *
import logging
import os
import mg
import re

modlogger = logging.getLogger("")
modlogger.setLevel(logging.ERROR)
stderr_channel = logging.StreamHandler()
stderr_channel.setLevel(logging.ERROR)
modlogger.addHandler(stderr_channel)

class TestObj(CombatParamsContainer):
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

class TestScript(unittest.TestCase):
    def setUp(self):
        self.inst = mg.Instance("script-test", "metagam")
        self.inst._dbpool = CassandraPool((("localhost", 9160),))
        self.inst._mcpool = MemcachedPool(("localhost", 11211))
        self.app = mg.Application(self.inst, "mgtest")
        self.app.modules.load([
            "mg.core.l10n.L10n",
            "mg.constructor.script.ScriptEngine",
            "mg.mmorpg.combats.scripts.CombatScripts",
            "mg.mmorpg.combats.scripts.CombatScriptsAdmin",
            "mg.constructor.script.ScriptEngine",
        ])

    def checkExpression(self, script_text, expected_code, expected_value):
        code = self.app.call("script.parse-expression", script_text)
        self.assertEqual(code, expected_code)
        script = self.app.call("script.unparse-expression", code)
        script = re.sub(r'\s+', ' ', script).strip()
        self.assertEqual(script, script_text)
        val = self.app.call("script.evaluate-expression", code)
        self.assertEqual(val, expected_value)

    def defaultCombat(self):
        combat = SimulationCombat(self.app)
        member1 = CombatMember(combat)
        member1.set_team(1)
        member1.set_param("p_val", 5)
        combat.join(member1)
        member2 = CombatMember(combat)
        member2.set_team(2)
        member2.set_param("p_val", 7)
        combat.join(member2)
        member3 = CombatMember(combat)
        member3.set_team(2)
        member3.set_param("p_val", 7)
        member3.set_param("p_alive", 1)
        combat.join(member3)
        return combat

    def checkCombatScript(self, script_text, expected_code, assertion=None, combat=None, globs=None):
        code = self.app.call("combats-admin.parse-script", script_text)
        self.assertEqual(code, expected_code)
        script = self.app.call("combats-admin.unparse-script", code)
        script = re.sub(r'\s+', ' ', script).strip()
        self.assertEqual(script, script_text)
        if combat is None:
            combat = self.defaultCombat()
        if globs is None:
            globs = {}
        testobj = TestObj()
        globs["test"] = testobj
        self.app.call("combats.execute-script", combat, code, globs, handle_exceptions=False)
        if assertion is not None:
            assertion(combat, testobj)

    def checkCombatScriptError(self, script_text, exception):
        self.assertRaises(exception, self.app.call, "combats-admin.parse-script", script_text)

    def test_expr_max(self):
        self.checkExpression('max(1, 2, 3)', ['call', 'max', 1, 2, 3], 3)

    def test_expr_min(self):
        self.checkExpression('min(1, 2, 3)', ['call', 'min', 1, 2, 3], 1)

    def test_combat_invalid_distinct(self):
        self.checkCombatScriptError('set obj.field = distinct(1, 2, 3)', ScriptParserError)

    def test_combat_invalid_uc(self):
        self.checkCombatScriptError('set obj.field = select uc(member.p_val) from members', ScriptParserError)

    def test_combat_distinct(self):
        self.checkCombatScript('set test.p_field = select distinct(member.p_val) from members', [
            ['select', ['glob', 'test'], 'p_field', 'distinct', ['.', ['glob', 'member'], 'p_val'], 'members', 1]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 2))
        self.checkCombatScript('set test.p_field = select distinct(member.p_val) from members where member.p_alive', [
            ['select', ['glob', 'test'], 'p_field', 'distinct', ['.', ['glob', 'member'], 'p_val'], 'members', ['.', ['glob', 'member'], 'p_alive']]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 1))

    def test_combat_max(self):
        self.checkCombatScript('set test.p_field = max(1, 2, 3)', [
            ['set', ['glob', 'test'], 'p_field', ['call', 'max', 1, 2, 3]]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 3))
        self.checkCombatScript('set test.p_field = select max(member.p_val) from members', [
            ['select', ['glob', 'test'], 'p_field', 'max', ['.', ['glob', 'member'], 'p_val'], 'members', 1]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 7))

    def test_combat_min(self):
        self.checkCombatScript('set test.p_field = min(1, 2, 3)', [
            ['set', ['glob', 'test'], 'p_field', ['call', 'min', 1, 2, 3]]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 1))
        self.checkCombatScript('set test.p_field = select min(member.p_val) from members', [
            ['select', ['glob', 'test'], 'p_field', 'min', ['.', ['glob', 'member'], 'p_val'], 'members', 1]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 5))

    def test_combat_sum(self):
        self.checkCombatScript('set test.p_field = select sum(member.p_val) from members', [
            ['select', ['glob', 'test'], 'p_field', 'sum', ['.', ['glob', 'member'], 'p_val'], 'members', 1]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 19))

    def test_combat_mult(self):
        self.checkCombatScript('set test.p_field = select mult(member.p_val) from members', [
            ['select', ['glob', 'test'], 'p_field', 'mult', ['.', ['glob', 'member'], 'p_val'], 'members', 1]
        ], lambda combat, testobj: self.assertEqual(testobj.param("p_field"), 245))

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
