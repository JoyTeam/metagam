#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet, Timeout, TimeoutError
from mg.core import *
from mg.core.cass import CassandraPool
from mg.core.memcached import MemcachedPool
from mg.constructor.script_classes import ScriptParserError, Vec3
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
        self.inst._mcpool = MemcachedPool()
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

    def test_evaluation(self):
        # Documentation: conversions from numbers to strings
        self.assertEqual(self.evaluate(['+', '1', '2']), '12')
        self.assertEqual(self.evaluate(['+', '1', 2]), 3)
        self.assertEqual(self.evaluate(['-', '1', '2']), -1)
        self.assertEqual(self.evaluate(['*', '1', '2']), 2)
        self.assertEqual(self.evaluate(['/', '1', '2']), 0.5)
        self.assertEqual(self.evaluate(['/', None, '2']), 0)
        self.assertEqual(self.evaluate(['-', '15', 'test']), 15)

        # Documentation: comparsions
        self.assertEqual(self.evaluate(['==', 1, 2]), 0)
        self.assertEqual(self.evaluate(['==', 1, 1]), 1)
        self.assertEqual(self.evaluate(['!=', 1, 2]), 1)
        self.assertEqual(self.evaluate(['!=', 1, 1]), 0)
        self.assertEqual(self.evaluate(['==', 'a', 'b']), 0)
        self.assertEqual(self.evaluate(['!=', 'a', 'b']), 1)
        self.assertEqual(self.evaluate(['>', 'a', 'b']), 0)
        self.assertEqual(self.evaluate(['<', 'a', 'b']), 0)

        # Addition
        self.assertEqual(self.evaluate(['+', None, None]), None)
        self.assertEqual(self.evaluate(['+', None, 1]), 1)
        self.assertEqual(str(self.evaluate(['+', None, Vec3(4, 5, 6)])), str(Vec3(4, 5, 6)))
        self.assertEqual(self.evaluate(['+', None, 'hello']), 'hello')
        self.assertEqual(self.evaluate(['+', 1, None]), 1)
        self.assertEqual(self.evaluate(['+', 1, 3]), 4)
        self.assertEqual(self.evaluate(['+', 1, Vec3(4, 5, 6)]), None)
        self.assertEqual(self.evaluate(['+', 1, 'hello']), 1)
        self.assertEqual(str(self.evaluate(['+', Vec3(10, 11, 12), None])), str(Vec3(10, 11, 12)))
        self.assertEqual(self.evaluate(['+', Vec3(10, 11, 12), 3]), None)
        self.assertEqual(str(self.evaluate(['+', Vec3(10, 11, 12), Vec3(4, 5, 6)])), str(Vec3(14, 16, 18)))
        self.assertEqual(self.evaluate(['+', Vec3(10, 11, 12), 'hello']), None)
        self.assertEqual(self.evaluate(['+', '1.5', None]), '1.5')
        self.assertEqual(self.evaluate(['+', '1.5', 1]), 2.5)
        self.assertEqual(self.evaluate(['+', '1.5', Vec3(1, 2, 3)]), None)
        self.assertEqual(self.evaluate(['+', 'foo', 'bar']), 'foobar')

        # Substraction
        self.assertEqual(self.evaluate(['-', None, None]), None)
        self.assertEqual(self.evaluate(['-', None, 1]), -1)
        self.assertEqual(str(self.evaluate(['-', None, Vec3(4, 5, 6)])), str(Vec3(-4, -5, -6)))
        self.assertEqual(self.evaluate(['-', None, 'hello']), 0)
        self.assertEqual(self.evaluate(['-', 1, None]), 1)
        self.assertEqual(self.evaluate(['-', 1, 3]), -2)
        self.assertEqual(self.evaluate(['-', 1, Vec3(4, 5, 6)]), None)
        self.assertEqual(self.evaluate(['-', 1, '8']), -7)
        self.assertEqual(str(self.evaluate(['-', Vec3(10, 11, 12), None])), str(Vec3(10, 11, 12)))
        self.assertEqual(self.evaluate(['-', Vec3(10, 11, 12), 3]), None)
        self.assertEqual(str(self.evaluate(['-', Vec3(10, 11, 12), Vec3(4, 5, 6)])), str(Vec3(6, 6, 6)))
        self.assertEqual(self.evaluate(['-', Vec3(10, 11, 12), 'hello']), None)
        self.assertEqual(self.evaluate(['-', '5', None]), '5')
        self.assertEqual(self.evaluate(['-', '5.5', 1]), 4.5)
        self.assertEqual(self.evaluate(['-', 'foo', Vec3(1, 2, 3)]), None)
        self.assertEqual(self.evaluate(['-', '8.5', '1.5']), 7)

        # Multiplication
        self.assertEqual(self.evaluate(['*', None, None]), 0)
        self.assertEqual(self.evaluate(['*', None, 1]), 0)
        self.assertEqual(str(self.evaluate(['*', None, Vec3(4, 5, 6)])), str(Vec3(0, 0, 0)))
        self.assertEqual(self.evaluate(['*', None, 'hello']), 0)
        self.assertEqual(self.evaluate(['*', 1, None]), 0)
        self.assertEqual(self.evaluate(['*', 2, 3]), 6)
        self.assertEqual(str(self.evaluate(['*', 2, Vec3(4, 5, 6)])), str(Vec3(8, 10, 12)))
        self.assertEqual(self.evaluate(['*', 2, '8']), 16)
        self.assertEqual(str(self.evaluate(['*', Vec3(10, 11, 12), None])), str(Vec3(0, 0, 0)))
        self.assertEqual(str(self.evaluate(['*', Vec3(10, 11, 12), 3])), str(Vec3(30, 33, 36)))
        self.assertEqual(str(self.evaluate(['*', Vec3(10, 11, 12), Vec3(4, 5, 6)])), str(Vec3(0, 0, 0)))
        self.assertEqual(str(self.evaluate(['*', Vec3(10, 11, 12), '2'])), str(Vec3(20, 22, 24)))
        self.assertEqual(self.evaluate(['*', '5', None]), 0)
        self.assertEqual(self.evaluate(['*', '5.5', 2]), 11)
        self.assertEqual(str(self.evaluate(['*', '2.0', Vec3(1, 2, 3)])), str(Vec3(2, 4, 6)))
        self.assertEqual(self.evaluate(['*', '8.5', '1.5']), 12.75)

        # Division
        self.assertEqual(self.evaluate(['/', None, None]), None)
        self.assertEqual(self.evaluate(['/', None, 1]), 0)
        self.assertEqual(self.evaluate(['/', None, Vec3(4, 5, 6)]), None)
        self.assertEqual(self.evaluate(['/', None, '1.5']), 0)
        self.assertEqual(self.evaluate(['/', 1, None]), None)
        self.assertEqual(self.evaluate(['/', 3, 2]), 1.5)
        self.assertEqual(self.evaluate(['/', 2, Vec3(4, 5, 6)]), None)
        self.assertEqual(self.evaluate(['/', 2, '4']), 0.5)
        self.assertEqual(self.evaluate(['/', Vec3(10, 11, 12), None]), None)
        self.assertEqual(str(self.evaluate(['/', Vec3(10, 11, 12), 2])), str(Vec3(5, 5.5, 6)))
        self.assertEqual(self.evaluate(['/', Vec3(10, 11, 12), Vec3(4, 5, 6)]), None)
        self.assertEqual(str(self.evaluate(['/', Vec3(10, 11, 12), '2'])), str(Vec3(5, 5.5, 6)))
        self.assertEqual(self.evaluate(['/', '5', None]), None)
        self.assertEqual(self.evaluate(['/', '4.5', 1.5]), 3)
        self.assertEqual(self.evaluate(['/', '2.0', Vec3(1, 2, 3)]), None)
        self.assertEqual(self.evaluate(['/', '7.5', '1.5']), 5)

        # Division by zero
        self.assertEqual(self.evaluate(['/', None, None]), None)
        self.assertEqual(self.evaluate(['/', None, 0]), None)
        self.assertEqual(self.evaluate(['/', None, '0']), None)
        self.assertEqual(self.evaluate(['/', 0, None]), None)
        self.assertEqual(self.evaluate(['/', 0, 0]), None)
        self.assertEqual(self.evaluate(['/', 0, '0']), None)
        self.assertEqual(self.evaluate(['/', Vec3(1, 2, 3), None]), None)
        self.assertEqual(self.evaluate(['/', Vec3(1, 2, 3), 0]), None)
        self.assertEqual(self.evaluate(['/', Vec3(1, 2, 3), '0']), None)
        self.assertEqual(self.evaluate(['/', '5', None]), None)
        self.assertEqual(self.evaluate(['/', '5', 0]), None)
        self.assertEqual(self.evaluate(['/', '5', '0']), None)

        # Negation
        self.assertEqual(self.evaluate(['-', None]), None)
        self.assertEqual(self.evaluate(['-', 1]), -1)
        self.assertEqual(str(self.evaluate(['-', Vec3(1, 2, 3)])), str(Vec3(-1, -2, -3)))
        self.assertEqual(self.evaluate(['-', '1.5']), -1.5)

        # Comparsion
        self.assertEqual(self.evaluate(['==', None, None]), 1)
        self.assertEqual(self.evaluate(['<', None, None]), 0)
        self.assertEqual(self.evaluate(['>', None, None]), 0)
        self.assertEqual(self.evaluate(['!=', None, None]), 0)
        self.assertEqual(self.evaluate(['==', None, 0]), 0)
        self.assertEqual(self.evaluate(['!=', None, 0]), 1)
        self.assertEqual(self.evaluate(['>=', None, 0]), 1)
        self.assertEqual(self.evaluate(['<=', None, 0]), 1)
        self.assertEqual(self.evaluate(['<', None, 0]), 0)
        self.assertEqual(self.evaluate(['>', None, 0]), 0)
        self.assertEqual(self.evaluate(['<', 0, None]), 0)
        self.assertEqual(self.evaluate(['>', 0, None]), 0)
        self.assertEqual(self.evaluate(['<', None, 1]), 1)
        self.assertEqual(self.evaluate(['!=', None, 1]), 1)
        self.assertEqual(self.evaluate(['>', None, -1]), 1)
        self.assertEqual(self.evaluate(['!=', None, -1]), 1)
        self.assertEqual(self.evaluate(['<', None, '1']), 1)
        self.assertEqual(self.evaluate(['!=', None, '1']), 1)
        self.assertEqual(self.evaluate(['>', None, '-1']), 1)
        self.assertEqual(self.evaluate(['!=', None, '-1']), 1)
        self.assertEqual(self.evaluate(['!=', None, Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['==', 1, 1]), 1)
        self.assertEqual(self.evaluate(['<', 1, 2]), 1)
        self.assertEqual(self.evaluate(['>', 2, 1]), 1)
        self.assertEqual(self.evaluate(['>', 1, None]), 1)
        self.assertEqual(self.evaluate(['<', -1, None]), 1)
        self.assertEqual(self.evaluate(['==', 1, '1']), 1)
        self.assertEqual(self.evaluate(['!=', 1, '1']), 0)
        self.assertEqual(self.evaluate(['>=', 1, '1']), 1)
        self.assertEqual(self.evaluate(['<=', 1, '1']), 1)
        self.assertEqual(self.evaluate(['<', 1, '2']), 1)
        self.assertEqual(self.evaluate(['>', 1, '-2']), 1)
        self.assertEqual(self.evaluate(['!=', 0, Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['>=', 0, Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['<=', 0, Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['>', 1, Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['<', -1, Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['==', '1', 1]), 1)
        self.assertEqual(self.evaluate(['<', '1', 2]), 1)
        self.assertEqual(self.evaluate(['>', '1', None]), 1)
        self.assertEqual(self.evaluate(['<', '-1', None]), 1)
        self.assertEqual(self.evaluate(['==', '1.0', '1.0']), 1)
        self.assertEqual(self.evaluate(['==', '1.0', '1.00']), 0)
        self.assertEqual(self.evaluate(['<', '1.0', '2.0']), 1)
        self.assertEqual(self.evaluate(['>', '1.0', '2.0']), 0)
        self.assertEqual(self.evaluate(['>', 'foo', 'bar']), 0)
        self.assertEqual(self.evaluate(['<', 'foo', 'bar']), 0)
        self.assertEqual(self.evaluate(['!=', '0', Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['>=', '0', Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['<=', '0', Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['>', '1', Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['<', '-1', Vec3(0, 0, 0)]), 1)
        self.assertEqual(self.evaluate(['!=', Vec3(1.2, 1.3, 1.4), None]), 1)
        self.assertEqual(self.evaluate(['<=', Vec3(1.2, 1.3, 1.4), None]), 1)
        self.assertEqual(self.evaluate(['>=', Vec3(1.2, 1.3, 1.4), None]), 1)
        self.assertEqual(self.evaluate(['!=', Vec3(1.2, 1.3, 1.4), 0]), 1)
        self.assertEqual(self.evaluate(['<=', Vec3(1.2, 1.3, 1.4), 0]), 1)
        self.assertEqual(self.evaluate(['>=', Vec3(1.2, 1.3, 1.4), 0]), 1)
        self.assertEqual(self.evaluate(['<', Vec3(1.2, 1.3, 1.4), 1]), 1)
        self.assertEqual(self.evaluate(['>', Vec3(1.2, 1.3, 1.4), -1]), 1)
        self.assertEqual(self.evaluate(['!=', Vec3(1.2, 1.3, 1.4), '0']), 1)
        self.assertEqual(self.evaluate(['<=', Vec3(1.2, 1.3, 1.4), '0']), 1)
        self.assertEqual(self.evaluate(['>=', Vec3(1.2, 1.3, 1.4), '0']), 1)
        self.assertEqual(self.evaluate(['<', Vec3(1.2, 1.3, 1.4), '1']), 1)
        self.assertEqual(self.evaluate(['>', Vec3(1.2, 1.3, 1.4), '-1']), 1)
        self.assertEqual(self.evaluate(['==', Vec3(1.2, 1.3, 1.4), Vec3(1.2, 1.3, 1.4)]), 1)
        self.assertEqual(self.evaluate(['>', Vec3(1.2, 1.3, 1.5), Vec3(1.2, 1.3, 1.4)]), 1)
        self.assertEqual(self.evaluate(['<', Vec3(1.2, 1.3, 1.3), Vec3(1.2, 1.3, 1.4)]), 1)
        self.assertEqual(self.evaluate(['>', Vec3(1.2, 1.4, 1.4), Vec3(1.2, 1.3, 1.5)]), 1)

        # Modules
        self.assertEqual(self.evaluate(['%', 7, 4]), 3)
        self.assertEqual(self.evaluate(['%', 7, 0]), None)

        # Vectors
        self.assertEqual(str(self.evaluate(['call', 'vec3', 1, 2, 3])), str(Vec3(1, 2, 3)))
        
        # Strings
        self.assertEqual(self.evaluate(['call', 'lc', 'Lorem Ipsum Dolor Sit Amet']), 'lorem ipsum dolor sit amet')
        self.assertEqual(self.evaluate(['call', 'uc', 'Lorem Ipsum Dolor Sit Amet']), 'LOREM IPSUM DOLOR SIT AMET')
        self.assertEqual(self.evaluate(['call', 'length', 'Lorem Ipsum Dolor Sit Amet']), 26)
        
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

    def evaluate(self, expr):
        return self.app.call("script.evaluate-expression", expr)

    def test_unparse(self):
        self.checkExpression('2 * 3 * 4', ['*', ['*', 2, 3], 4], 24)
        self.assertEqual('2 * 3 * 4', self.app.call("script.unparse-expression", ['*', 2, ['*', 3, 4]]))
        self.checkExpression('2 / 4 / 8', ['/', ['/', 2, 4], 8], 1.0/16)
        self.checkExpression('2 / (4 / 8)', ['/', 2, ['/', 4, 8]], 4)
        self.checkExpression('(2 * 4) % 8', ['%', ['*', 2, 4], 8], 0)
        self.checkExpression('2 * (4 % 8)', ['*', 2, ['%', 4, 8]], 8)

    def partialEval(self, inval, outval):
        expr = self.app.call("script.parse-expression", inval)
        evalres = self.app.call("script.evaluate-expression", expr, globs={"g1": 1, "g2": 2}, keep_globs={"t": True})
        unparsed = self.app.call("script.unparse-expression", evalres)
        self.assertEqual(unparsed, outval)

    def partialTextEval(self, inval, outval):
        expr = self.app.call("script.parse-text", inval)
        evalres = self.app.call("script.evaluate-text", expr, globs={"g1": 1, "g2": 2}, keep_globs={"t": True})
        unparsed = self.app.call("script.unparse-text", evalres)
        self.assertEqual(unparsed, outval)

    def test_partial_eval(self):
        self.partialEval("1", "1")
        self.partialEval("1 + 5", "6")
        self.partialEval("g1", "1")
        self.partialEval("g1 + g2", "3")
        self.partialEval("t", "t")
        # +
        self.partialEval("1 + t", "1 + t")
        self.partialEval("t + 1", "t + 1")
        self.partialEval("1 + 2 + t", "3 + t")
        self.partialEval("g1 + g2 + t", "3 + t")
        # -
        self.partialEval("1 - 2", "-1")
        self.partialEval("t - 1", "t - 1")
        self.partialEval("1 - t", "1 - t")
        # *
        self.partialEval("3 * 2", "6")
        self.partialEval("t * 1", "t * 1")
        self.partialEval("1 * t", "1 * t")
        # /
        self.partialEval("1 / 2", "0.5")
        self.partialEval("t / 1", "t / 1")
        self.partialEval("1 / t", "1 / t")
        self.partialEval("t / 0", "none")
        # Unary -
        self.partialEval("-1", "-1")
        self.partialEval("-(1)", "-1")
        self.partialEval("-vec3(1, 2, 3)", "vec3(-1, -2, -3)")
        self.partialEval("-g2", "-2")
        self.partialEval("-t", "-t")
        self.partialEval("-(t + 1)", "-(t + 1)")
        # %
        self.partialEval("3 % 2", "1")
        self.partialEval("t % 2", "t % 2")
        self.partialEval("2 % t", "2 % t")
        self.partialEval("t % 0", "none")
        # ==
        self.partialEval("2 == 2", "1")
        self.partialEval("2 == 3", "0")
        self.partialEval("t == 2", "t == 2")
        self.partialEval("2 == t", "2 == t")
        # !=
        self.partialEval("2 != 2", "0")
        self.partialEval("2 != 3", "1")
        self.partialEval("t != 2", "t != 2")
        self.partialEval("2 != t", "2 != t")
        # in
        self.partialEval("'abc' in 'abcd'", "1")
        self.partialEval("'abc' in 'abed'", "0")
        self.partialEval('"abc" in t', '"abc" in t')
        self.partialEval('t in "abc"', 't in "abc"')
        # <
        self.partialEval("1 < 2", "1")
        self.partialEval("2 < 1", "0")
        self.partialEval("t < 1", "t < 1")
        self.partialEval("1 < t", "1 < t")
        # >
        self.partialEval("1 > 2", "0")
        self.partialEval("2 > 1", "1")
        self.partialEval("t > 1", "t > 1")
        self.partialEval("1 > t", "1 > t")
        # <=
        self.partialEval("1 <= 2", "1")
        self.partialEval("2 <= 1", "0")
        self.partialEval("t <= 1", "t <= 1")
        self.partialEval("1 <= t", "1 <= t")
        # >=
        self.partialEval("1 >= 2", "0")
        self.partialEval("2 >= 1", "1")
        self.partialEval("t >= 1", "t >= 1")
        self.partialEval("1 >= t", "1 >= t")
        # ~
        self.partialEval("~~3", "3")
        self.partialEval("~t", "~t")
        self.partialEval("~(t + 1)", "~(t + 1)")
        # &
        self.partialEval("6 & 12", "4")
        self.partialEval("t & 3", "t & 3")
        self.partialEval("3 & t", "3 & t")
        # |
        self.partialEval("6 | 12", "14")
        self.partialEval("t | 3", "t | 3")
        self.partialEval("3 | t", "3 | t")
        # not
        self.partialEval("not 0", "1")
        self.partialEval("not 5", "0")
        self.partialEval("not t", "not t")
        # and
        self.partialEval("0 and 1", "0")
        self.partialEval("1 and 0", "0")
        self.partialEval("2 and 3", "3")
        self.partialEval("0 and t", "0")
        self.partialEval("t and 0", "t and 0")
        self.partialEval("1 and t", "1 and t")
        # or
        self.partialEval("0 or 2", "2")
        self.partialEval("3 or 0", "3")
        self.partialEval("2 or 3", "2")
        self.partialEval("1 or t", "1")
        self.partialEval("0 or t", "0 or t")
        self.partialEval("t or 1", "t or 1")
        # ?
        self.partialEval("1 ? 2 : 3", "2")
        self.partialEval("0 ? 2 : 3", "3")
        self.partialEval("t ? 2 : 3", "t ? 2 : 3")
        # min
        self.partialEval("min(1, 2, 3)", "1")
        self.partialEval("min(7, 5, t)", "min(t, 5)")
        self.partialEval("min(4, t, t)", "min(t, t, 4)")
        # max
        self.partialEval("max(1, 2, 3)", "3")
        self.partialEval("max(7, 5, t)", "max(t, 7)")
        self.partialEval("max(4, t, t)", "max(t, t, 4)")
        # lc
        self.partialEval('lc("Abc")', '"abc"')
        self.partialEval("lc(t)", "lc(t)")
        # uc
        self.partialEval('uc("Abc")', '"ABC"')
        self.partialEval("uc(t)", "uc(t)")
        # selrand
        self.partialEval("selrand(1, 2, 3 + 5)", "selrand(1, 2, 8)")
        self.partialEval("selrand(t, 2, 3 + 5)", "selrand(t, 2, 8)")
        # 1-dimensional math functions
        self.partialEval("floor(5.4)", "5.0")
        self.partialEval("floor(t)", "floor(t)")
        # pow
        self.partialEval("pow(2, 4)", "16.0")
        self.partialEval("pow(2, t)", "pow(2, t)")
        self.partialEval("pow(t, 2)", "pow(t, 2)")
        # vec3
        self.partialEval("vec3(1, 2, 3)", "vec3(1, 2, 3)")
        self.partialEval("vec3(1, t, 3)", "vec3(1, t, 3)")
        self.partialEval("vec3(1, 2, 3) + vec3(4, 5, 6)", "vec3(5, 7, 9)")
        self.partialEval("vec3(1, 2, 3) + vec3(4, 5, t)", "vec3(1, 2, 3) + vec3(4, 5, t)")
        # glob
        self.partialEval("e", "none")
        self.partialEval("t", "t")
        # dot
        self.partialEval("t.attr + 5", "t.attr + 5")
        # true/false
        self.partialEval("not 0", "1")
        self.partialEval("not 1", "0")
        self.partialEval("not ''", "1")
        self.partialEval("not '0'", "0")
        self.partialEval("not 1/0", "1")
        # strings
        self.partialEval("'abc'", '"abc"')
        self.partialEval('"abc"', '"abc"')
        self.partialEval('"a\'bc"', '"a\'bc"')
        self.partialEval("'a\"bc'", "'a\"bc'")
        self.partialEval("'a\"\\'bc'", '"a\\"\'bc"')

    def test_partial_text_eval(self):
        self.partialTextEval('string', 'string')
        self.partialTextEval('string {3 + 3}', 'string 6')
        self.partialTextEval('string {t + 3}', 'string {t + 3}')
        # index
        self.partialTextEval('string [0:abc,def]', 'string abc')
        self.partialTextEval('string [1:abc,def]', 'string def')
        self.partialTextEval('string [t:abc,def]', 'string [t:abc,def]')
        # numdecl
        self.assertEqual(self.app.call("l10n.literal_value", 1, ["object", "objects"]), "object")
        self.assertEqual(self.app.call("l10n.literal_value", 2, ["object", "objects"]), "objects")
        self.partialTextEval('string [#1:abc,abces]', 'string abc')
        self.partialTextEval('string [#2:abc,abces]', 'string abces')
        self.partialTextEval('string [#t:abc,abces]', 'string [#t:abc,abces]')

    def test_dates(self):
        self.assertEqual(type(self.evaluate(['.', ['now'], 'year'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'month'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'day'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'hour'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'minute'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'second'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'utc_year'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'utc_month'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'utc_day'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'utc_hour'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'utc_minute'])), int)
        self.assertEqual(type(self.evaluate(['.', ['now'], 'utc_second'])), int)

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
