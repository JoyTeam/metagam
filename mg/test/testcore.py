#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet
from mg.core import *
from mg.core.cass import CassandraPool
from mg.core.memcached import MemcachedPool
from cassandra.ttypes import *
import logging

modlogger = logging.getLogger("")
modlogger.setLevel(logging.ERROR)
stderr_channel = logging.StreamHandler()
stderr_channel.setLevel(logging.ERROR)
modlogger.addHandler(stderr_channel)

class Test1(Module):
    def register(self):
        self.rhook("core.dbstruct", self.cassandra_struct)
        self.rhook("grp1.test1", self.test1)
        self.rhook("grp1.test2", self.test2)
        self.rhook("grp2.test3", self.test3)

    def cassandra_struct(self, dbstruct):
        dbstruct["TestFamily"] = CfDef(comparator_type="BytesType")

    def test1(self):
        pass

    def test2(self):
        pass

    def test3(self):
        pass

class Test2(Module):
    def register(self):
        self.rhook("grp1.test1", self.test1)
        self.rhook("grp1.test2", self.test2)
        self.rhook("grp2.test3", self.test3)

    def test1(self):
        pass

    def test2(self):
        pass

    def test3(self):
        pass

class TestJoin(Module):
    def register(self):
        self.rhook("join.empty", self.empty)
        self.rhook("join.single", self.single)
        self.rhook("join.prio1", self.prio1)
        self.rhook("join.prio1", self.prio2)
        self.rhook("join.prio2", self.prio2)
        self.rhook("join.prio2", self.prio1)
        self.rhook("join.prio3", self.prio1)
        self.rhook("join.prio3", self.prio2, 10)
        self.rhook("join.filter1", self.res)
        self.rhook("join.filter2", self.filter1)
        self.rhook("join.filter2", self.res)
        self.rhook("join.filter3", self.filter1)
        self.rhook("join.filter3", self.filter2)
        self.rhook("join.filter3", self.res)
        self.rhook("join.immed", self.filter1)
        self.rhook("join.immed", self.immed)
        self.rhook("join.immed", self.filter2)
        self.rhook("join.immed", self.res)

    def empty(self):
        pass

    def single(self):
        return "single"

    def prio1(self):
        return "prio1"

    def prio2(self):
        return "prio2"

    def res(self, arg):
        return arg

    def filter1(self, arg):
        return (arg * 2,)

    def filter2(self, arg):
        return (arg + 10,)

    def immed(self, arg):
        raise Hooks.Return("immed")

class TestCore(unittest.TestCase):
    def setUp(self):
        self.inst = Instance()
        self.inst.dbpool = CassandraPool((("director-db", 9160),))
        self.inst.mcpool = MemcachedPool(("director-mc", 11211))

    def test00(self):
        conn = self.inst.dbpool.cget()
        try:
            conn.cass.set_keyspace("system")
            conn.cass.system_drop_keyspace("mgtest")
        except Exception as e:
            pass
        self.inst.dbpool.success(conn)
        mc = Memcached(self.inst.mcpool, "mgtest-")
        mc.delete("Cassandra-KS-mgtest")
        mc.delete("Cassandra-CF-mgtest-ConfigGroup_Objects")
        mc.delete("Cassandra-CF-mgtest-ConfigGroup_Index_all")
        mc.delete("Cassandra-CF-mgtest-HookGroupModules_Objects")
        mc.delete("Cassandra-CF-mgtest-HookGroupModules_Index_all")
        mc.delete("Cassandra-CF-mgtest-Data")

    def test01(self):
        app = Application(self.inst, "mgtest")
        list = []
        app.hooks.call("core.loaded_modules", list)
        self.assertEqual(len(list), 0)

        app.modules.load(["mg.test.testcore.Test1"])
        list = []
        app.hooks.call("core.loaded_modules", list)
        self.assertEqual(len(list), 1)
        self.assertEqual(list[0], "mg.test.testcore.Test1")

        app.config.load_groups(["a", "b", "c"])
        self.assertTrue("a" in app.config._config)
        self.assertTrue("b" in app.config._config)
        self.assertTrue("c" in app.config._config)
        self.assertFalse("d" in app.config._config)
        app.config.set("a.key1", "value1")
        self.assertEqual(app.config.get("a.key1"), "value1")
        app.config.store()

    def test02(self):
        app = Application(self.inst, "mgtest")
        self.assertEqual(app.config.get("a.key1"), "value1")
        app.config.set("a.key2", "value2")
        app.config.delete("a.key1")
        app.config.store()
        self.assertEqual(app.config.get("a.key1"), None)
        self.assertEqual(app.config.get("a.key2"), "value2")

    def test03(self):
        app = Application(self.inst, "mgtest")
        self.assertEqual(app.config.get("a.key1"), None)
        self.assertEqual(app.config.get("a.key2"), "value2")
        self.assertTrue("a" in app.config._config)
        self.assertFalse("b" in app.config._config)
        self.assertFalse("c" in app.config._config)
        self.assertFalse("d" in app.config._config)

    def test04(self):
        app = Application(self.inst, "mgtest")
        app.modules.load(["mg.test.testcore.Test1"])
        app.hooks.store()

    def test06(self):
        app = Application(self.inst, "mgtest")
        app.modules.load(["mg.test.testcore.Test2"])
        app.hooks.store()

    def test09(self):
        app = Application(self.inst, "mgtest")
        app.modules.load(["mg.test.testcore.TestJoin"])
        self.assertEqual(app.hooks.call("join.empty"), None)
        self.assertEqual(app.hooks.call("join.single"), "single")
        self.assertEqual(app.hooks.call("join.prio1"), "prio2")
        self.assertEqual(app.hooks.call("join.prio2"), "prio1")
        self.assertEqual(app.hooks.call("join.prio3"), "prio1")
        self.assertEqual(app.hooks.call("join.filter1", 2), 2)
        self.assertEqual(app.hooks.call("join.filter2", 2), 4)
        self.assertEqual(app.hooks.call("join.filter3", 2), 14)
        self.assertEqual(app.hooks.call("join.immed", 2), "immed")

if __name__ == "__main__":
    dispatch(unittest.main)
