#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

from mg.core.cass import CassandraConnection, CassandraPool, CassandraObject, CassandraObjectList, ObjectNotFoundException
from mg.core.memcached import Memcached
import unittest
from concurrence import dispatch, Tasklet
import time
from cassandra.ttypes import *
from math import floor
import logging

modlogger = logging.getLogger("")
modlogger.setLevel(logging.ERROR)
stderr_channel = logging.StreamHandler()
stderr_channel.setLevel(logging.ERROR)
modlogger.addHandler(stderr_channel)

class SimpleObject(CassandraObject):
    clsname = "SimpleObject"

class SimpleObjectList(CassandraObjectList):
    objcls = SimpleObject

class TestObject(CassandraObject):
    clsname = "TestObject"
    indexes = {
        "topic": [["topic"]],
        "created": [["topic"], "created"],
        "index": [[], "index"],
        "val": [[], "val"]
    }

class TestObjectList(CassandraObjectList):
    objcls = TestObject

def cleanup():
    mc = Memcached(prefix="mgtest-")
    db = CassandraPool().dbget("mgtest", mc)
    conn = db.pool.cget()
    try:
        conn.cass.system_drop_keyspace("mgtest")
    except Exception as e:
        pass
    db.pool.success(conn)
    mc.delete("Cassandra-KS-mgtest")
    mc.delete("Cassandra-CF-mgtest-Data")
    mc.delete("Cassandra-CF-mgtest-SimpleObject_Objects")
    mc.delete("Cassandra-CF-mgtest-TestObject_Objects")
    mc.delete("Cassandra-CF-mgtest-TestObject_Index_topic")
    mc.delete("Cassandra-CF-mgtest-TestObject_Index_created")
    mc.delete("Cassandra-CF-mgtest-TestObject_Index_index")
    mc.delete("Cassandra-CF-mgtest-TestObject_Index_val")
    mc.delete("Cassandra-CF-mgtest-TestObject_Indexes")

class TestORM(unittest.TestCase):
    def setUp(self):
        self.db = CassandraPool().dbget("mgtest", mc=None)

    def test01(self):
        obj = SimpleObject(self.db)
        obj.set("key1", 1)
        obj.set("key2", "value2")
        self.assertEqual(obj.get("key1"), 1)
        self.assertEqual(obj.get("key2"), "value2")
        self.assertEqual(obj.get("key3"), None)
        obj.store()

        obj_a = TestObject(self.db, obj.uuid, {})
        obj_a.set("K1", 1)
        obj_a.store()

        obj2 = SimpleObject(self.db, obj.uuid)
        self.assertEqual(obj2.get("key1"), 1)
        self.assertEqual(obj2.get("key2"), "value2")
        self.assertEqual(obj2.get("key3"), None)
        obj2.set("key4", "test")
        obj2.store()

        obj3 = SimpleObject(self.db, obj.uuid)
        self.assertEqual(obj3.get("key1"), 1)
        self.assertEqual(obj3.get("key2"), "value2")
        self.assertEqual(obj3.get("key3"), None)
        self.assertEqual(obj3.get("key4"), "test")

        obj_a = TestObject(self.db, obj.uuid)
        self.assertEqual(obj_a.get("K1"), 1)
        obj_a.store()

    def test02(self):
        raised = 0
        try:
            obj = SimpleObject(self.db, "not-existent-object")
            obj.load()
        except ObjectNotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)
        raised = 0
        try:
            obj = SimpleObjectList(self.db, ["not-existent-object", "not-existent-object-2"])
            obj.load()
        except ObjectNotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)

    def test03(self):
        obj1 = SimpleObject(self.db)
        obj1.set("key1", 1)
        obj1.set("key2", "value2")
        obj1.store()

        obj2 = SimpleObject(self.db)
        obj2.set("key3", 3)
        obj2.set("key4", "value4")
        obj2.store()

        lst = SimpleObjectList(self.db, [obj1.uuid, obj2.uuid])
        lst.load()
        self.assertEqual(len(lst), 2)
        self.assertEqual(lst[0].uuid, obj1.uuid)
        self.assertEqual(lst[1].uuid, obj2.uuid)
        self.assertEqual(lst[0].get("key1"), 1)
        self.assertEqual(lst[0].get("key2"), "value2")
        self.assertEqual(lst[1].get("key3"), 3)
        self.assertEqual(lst[1].get("key4"), "value4")
        lst[0].set("key1", "test")
        obj1.load()
        self.assertEqual(obj1.get("key1"), 1)
        lst.store()
        self.assertEqual(obj1.get("key1"), 1)
        obj1.load()
        self.assertEqual(obj1.get("key1"), "test")
        obj1.set("key1", "aaa")
        self.assertEqual(lst[0].get("key1"), "test")
        obj1.store()
        self.assertEqual(lst[0].get("key1"), "test")
        lst.load()
        self.assertEqual(lst[0].get("key1"), "aaa")

        obj1.remove()
        raised = 0
        try:
            obj1.load()
        except ObjectNotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)
        obj2.load()
        lst.remove()
        raised = 0
        try:
            obj2.load()
        except ObjectNotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)

        obj1 = SimpleObject(self.db)
        obj1.set("key1", 1)
        obj1.set("key2", "value2")
        obj1.store()

        obj2 = SimpleObject(self.db)
        obj2.set("key3", 3)
        obj2.set("key4", "value4")
        obj2.store()

    def test04(self):
        obj1 = TestObject(self.db)
        obj1.set("created", "2010-01-01")
        obj1.set("topic", "Топик")
        obj1.store()
        obj1.set("created", "2010-01-02")
        obj1.set("topic", "Другой-топик")
        obj1.store()
        obj1.delkey("created")
        obj1.store()
        obj1.set("created", "Не-дата")
        obj1.store()
        obj1.remove()

    def test05(self):
        lst = TestObjectList(self.db, query_index="created", query_equal="Топик")
        lst.remove()
        lst = TestObjectList(self.db, query_index="created", query_equal="Другой-топик")
        lst.remove()

        lst = TestObjectList(self.db, query_index="created", query_equal="Топик")
        self.assertEqual(len(lst), 0)

        obj1 = TestObject(self.db, data={
            "topic": u"Топик",
            "created": "2011-01-01"
        })
        obj1.store()
        obj2 = TestObject(self.db)
        obj2.set("created", "2011-01-01")
        obj2.set("topic", "Другой-топик")
        obj2.store()
        obj3 = TestObject(self.db)
        obj3.set("created", "2012-01-01")
        obj3.set("topic", "Другой-топик")
        obj3.store()
        lst = TestObjectList(self.db, [obj1.uuid, obj2.uuid])
        lst.load()
        lst[0].set("created", "Не-дата");
        lst[1].set("topic", "Топик")
        lst.store()

        lst = TestObjectList(self.db, query_index="created", query_equal="Топик")
        self.assertEqual(len(lst), 2)
        uuids = [obj.uuid for obj in lst]
        self.assertTrue(obj1.uuid in uuids)
        self.assertTrue(obj2.uuid in uuids)

        lst = TestObjectList(self.db, query_index="created", query_equal=["Топик", "Другой-топик"])
        self.assertEqual(len(lst), 3)
        uuids = [obj.uuid for obj in lst]
        self.assertTrue(obj1.uuid in uuids)
        self.assertTrue(obj2.uuid in uuids)
        self.assertTrue(obj3.uuid in uuids)

        for ent in lst:
            if ent.uuid == obj2.uuid:
                ent.delkey("topic")
                ent.store()

        obj2 = TestObject(self.db, obj2.uuid)
        obj2.set("topic", "Жопик")
        obj2.store()

        lst = TestObjectList(self.db, query_index="created", query_equal="Топик")
        self.assertEqual(len(lst), 1)
        uuids = [obj.uuid for obj in lst]
        self.assertTrue(obj1.uuid in uuids)

    def test06(self):
        lst = TestObjectList(self.db, query_index="index")
        lst.remove()

        uuids = []
        for i in range(0, 10):
            obj = TestObject(self.db)
            obj.set("index", i)
            obj.set("val", floor(i / 2))
            obj.set("topic", "index-values")
            obj.store()
            uuids.append(obj.uuid)
        # ---
        lst = TestObjectList(self.db, query_index="index")
        self.assertEqual(len(lst), 10)
        for uuid in uuids:
            self.assertTrue(uuid in uuids)
        # ---
        lst = TestObjectList(self.db, query_index="index", query_start="3")
        self.assertEqual(len(lst), 7)
        lst_uuids = [obj.uuid for obj in lst]
        for i in range(3, 10):
            self.assertTrue(uuids[i] in lst_uuids)
        # ---
        lst = TestObjectList(self.db, query_index="index", query_finish="3")
        self.assertEqual(len(lst), 3)
        lst_uuids = [obj.uuid for obj in lst]
        for i in range(0, 3):
            self.assertTrue(uuids[i] in lst_uuids)
        # ---
        lst = TestObjectList(self.db, query_index="index", query_start="3", query_finish="7")
        self.assertEqual(len(lst), 4)
        lst_uuids = [obj.uuid for obj in lst]
        for i in range(3, 7):
            self.assertTrue(uuids[i] in lst_uuids)
        # ---
        lst = TestObjectList(self.db, query_index="index", query_start="3", query_finish="7", query_limit=3)
        self.assertEqual(len(lst), 3)
        lst_uuids = [obj.uuid for obj in lst]
        for i in range(3, 6):
            self.assertTrue(uuids[i] in lst_uuids)
        # ---
        lst = TestObjectList(self.db, query_index="index", query_start="7", query_finish="3", query_limit=3, query_reversed=True)
        self.assertEqual(len(lst), 3)
        lst_uuids = [obj.uuid for obj in lst]
        for i in range(4, 7):
            self.assertTrue(uuids[i] in lst_uuids)

    def test07(self):
        # read recovery
        lst = TestObjectList(self.db, query_index="index")
        lst.remove()
        obj = TestObject(self.db)
        obj.set("index", 11)
        obj.store()
        obj = TestObject(self.db)
        obj.set("index", 12)
        obj.store()
        lst = TestObjectList(self.db, query_index="index")
        self.assertEqual(len(lst), 2)
        tmp = TestObject(self.db, obj.uuid)
        # breaking indexes
        tmp._indexes = {}
        tmp.remove()
        lst = TestObjectList(self.db, query_index="index")
        self.assertEqual(len(lst), 2)
        lst.load(True)
        self.assertEqual(len(lst), 1)

def main():
    cleanup()
    unittest.main()

if __name__ == "__main__":
    dispatch(main)
