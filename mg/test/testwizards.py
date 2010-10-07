#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet
from mg.core import *
from mg.core.wizards import Wizard
from mg.core.cass import CassandraPool
from mg.core.memcached import MemcachedPool
from cassandra.ttypes import *

class Test1Wizard(Wizard):
    def test0(self, list):
        list.append(1)

    def test1(self, list):
        list.append(1)

class Test2Wizard(Wizard):
    def test0(self, list):
        list.append(2)

    def test2(self, list):
        list.append(2)

class TestWizards(unittest.TestCase):
    def setUp(self):
        self.app = Application(Instance(), CassandraPool(), MemcachedPool(), "mgtest")
        self.app.modules.load(["mg.core.cass_struct.CommonCassandraStruct", "mg.core.wizards.Wizards"])
        dbstruct = {}
        self.app.hooks.call("core.dbstruct", dbstruct)
        self.assertTrue(len(dbstruct) > 0)
        self.assertTrue("Core" in dbstruct)
        self.app.hooks.call("core.dbapply", dbstruct)

    def test01(self):
        for wiz in self.app.hooks.call("wizards.list"):
            wiz.abort()
        self.assertEqual(len(self.app.hooks.call("wizards.list")), 0)
        w1 = self.app.hooks.call("wizards.new", "mg.test.testwizards.Test1Wizard")
        self.assertTrue(w1)
        self.assertEqual(len(self.app.hooks.call("wizards.list")), 1)
        w2 = self.app.hooks.call("wizards.new", "mg.test.testwizards.Test2Wizard")
        self.assertTrue(w2)
        self.assertEqual(len(self.app.hooks.call("wizards.list")), 2)
        list = []
        self.app.hooks.call("wizards.call", "test0", list)
        self.assertEqual(len(list), 2)
        self.assertTrue(1 in list)
        self.assertTrue(2 in list)
        list = []
        self.app.hooks.call("wizards.call", "test1", list)
        self.assertEqual(len(list), 1)
        self.assertTrue(1 in list)
        self.assertTrue(2 not in list)
        list = []
        self.app.hooks.call("wizards.call", "test2", list)
        self.assertEqual(len(list), 1)
        self.assertTrue(1 not in list)
        self.assertTrue(2 in list)
        w2.abort()
        self.assertEqual(len(self.app.hooks.call("wizards.list")), 1)
        list = []
        self.app.hooks.call("wizards.call", "test0", list)
        self.assertEqual(len(list), 1)
        self.assertTrue(1 in list)
        self.assertTrue(2 not in list)
        w1.finish()
        self.assertEqual(len(self.app.hooks.call("wizards.list")), 0)

if __name__ == "__main__":
    dispatch(unittest.main)
