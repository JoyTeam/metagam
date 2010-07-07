#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

from mg.cass import CassandraConnection, CassandraRestructure, CassandraPool, CassandraObject, CassandraObjectList
import unittest
from concurrence import dispatch, Tasklet
import time
from cassandra.ttypes import *

class TestORM(unittest.TestCase):
    def setUp(self):
        self.db = CassandraPool().dbget("mgtest")
        restruct = CassandraRestructure(self.db)
        struct = {
            "Objects": CfDef(),
        }
        diff = restruct.diff(struct)
        restruct.apply(diff)

    def test01(self):
        obj = CassandraObject(self.db)
        obj.set("key1", 1)
        obj.set("key2", "value2")
        self.assertEqual(obj.get("key1"), 1)
        self.assertEqual(obj.get("key2"), "value2")
        self.assertEqual(obj.get("key3"), None)
        obj.store()

        obj2 = CassandraObject(self.db, obj.uuid)
        self.assertEqual(obj2.get("key1"), 1)
        self.assertEqual(obj2.get("key2"), "value2")
        self.assertEqual(obj2.get("key3"), None)
        obj2.set("key4", "test")
        obj2.store()

        obj3 = CassandraObject(self.db, obj.uuid)
        self.assertEqual(obj3.get("key1"), 1)
        self.assertEqual(obj3.get("key2"), "value2")
        self.assertEqual(obj3.get("key3"), None)
        self.assertEqual(obj3.get("key4"), "test")

    def test02(self):
        raised = 0
        try:
            obj = CassandraObject(self.db, "not-existent-object")
        except NotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)
        raised = 0
        try:
            obj = CassandraObjectList(self.db, ["not-existent-object", "not-existent-object-2"])
        except NotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)

    def test03(self):
        obj1 = CassandraObject(self.db)
        obj1.set("key1", 1)
        obj1.set("key2", "value2")
        obj1.store()

        obj2 = CassandraObject(self.db)
        obj2.set("key3", 3)
        obj2.set("key4", "value4")
        obj2.store()

        lst = CassandraObjectList(self.db, [obj1.uuid, obj2.uuid])
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
        except NotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)
        obj2.load()
        lst.remove()
        raised = 0
        try:
            obj2.load()
        except NotFoundException:
            raised = raised + 1
        self.assertEqual(raised, 1)

if __name__ == "__main__":
    dispatch(unittest.main)
