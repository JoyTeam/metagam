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
from concurrence import dispatch, Tasklet
from mg import *
from mg.admin.wizards import Wizard
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
        self.inst = Instance("test", "test")
        self.inst._dbpool = CassandraPool((("localhost", 9160),))
        self.inst._mcpool = MemcachedPool()
        self.app = Application(self.inst, "mgtest")
        self.app.modules.load(["mg.admin.wizards.Wizards"])
        mc = Memcached(self.inst.mcpool, "mgtest-")
        mc.delete("Cassandra-CF-mgtest-ConfigGroup_Objects")
        mc.delete("Cassandra-CF-mgtest-ConfigGroup_Index_all")
        mc.delete("Cassandra-CF-mgtest-HookGroupModules_Objects")
        mc.delete("Cassandra-CF-mgtest-HookGroupModules_Index_all")
        mc.delete("Cassandra-CF-mgtest-WizardConfig_Objects")
        mc.delete("Cassandra-CF-mgtest-WizardConfig_Index_all")
        mc.delete("Cassandra-CF-mgtest-Data")

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
