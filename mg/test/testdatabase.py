#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

from mg.core.cass import CassandraConnection, CassandraPool
from mg.core.cass_struct import CassandraRestructure
from mg.core.memcached import Memcached
import unittest
from concurrence import dispatch, Tasklet
import time
from cassandra.ttypes import *

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.mc = Memcached(prefix="mgtest-")
        self.db = CassandraPool().dbget("mgtest", self.mc)

        self.cleanup()
        restruct = CassandraRestructure(self.db)

        struct = {
            "Family1": CfDef(comparator_type="BytesType"),
            "Family2": CfDef(comparator_type="UTF8Type")
        }
        diff = restruct.diff(struct)
        self.assertEqual(len(diff.ops), 3)
        self.assertEqual(diff.ops[0][0], "cks")
        self.assertEqual(diff.ops[1][0], "cf")
        self.assertEqual(diff.ops[2][0], "cf")
        restruct.apply(diff)

        struct["Family3"] = CfDef(comparator_type="UTF8Type")
        diff = restruct.diff(struct)
        self.assertEqual(len(diff.ops), 1)
        self.assertEqual(diff.ops[0][0], "cf")
        restruct.apply(diff)

        del struct["Family2"]
        diff = restruct.diff(struct)
        self.assertEqual(len(diff.ops), 1)
        self.assertEqual(diff.ops[0][0], "df")
        restruct.apply(diff)

        struct["Family3"].comparator_type="BytesType"
        diff = restruct.diff(struct)
        self.assertEqual(len(diff.ops), 2)
        self.assertEqual(diff.ops[0][0], "df")
        self.assertEqual(diff.ops[1][0], "cf")
        restruct.apply(diff)

        diff = restruct.diff(struct)
        self.assertEqual(len(diff.ops), 0)
        restruct.apply(diff)

        ksinfo = dict([(cfdef.name, cfdef) for cfdef in self.db.describe_keyspace("mgtest").cf_defs])
        self.assertTrue("Family1" in ksinfo)
        self.assertTrue("Family2" not in ksinfo)
        self.assertTrue("Family3" in ksinfo)

    def tearDown(self):
        #self.cleanup()
        pass

    def cleanup(self):
        try:
            self.db.system_drop_keyspace("mgtest")
        except Exception as e:
            pass

    def testputget(self):
        timestamp = time.time() * 1000
        self.db.insert("1", ColumnParent(column_family="Family1"), Column(name="email", value="aml@rulezz.ru - проверка", clock=Clock(timestamp=timestamp)), ConsistencyLevel.QUORUM)
        self.db.get_slice("1", ColumnParent(column_family="Family1"), SlicePredicate(slice_range=SliceRange(start="", finish="")), ConsistencyLevel.QUORUM)

if __name__ == "__main__":
    dispatch(unittest.main)
