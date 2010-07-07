#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

from mg.cass import CassandraConnection, CassandraRestructure, CassandraPool, CassandraObject
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

if __name__ == "__main__":
    dispatch(unittest.main)
