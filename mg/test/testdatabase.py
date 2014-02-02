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

from mg.core.cass import CassandraConnection, CassandraPool, DatabaseError
from mg.core.memcached import Memcached
import unittest
from concurrence import dispatch, Tasklet
import time
from cassandra.ttypes import *
import logging

modlogger = logging.getLogger("")
modlogger.setLevel(logging.ERROR)
stderr_channel = logging.StreamHandler()
stderr_channel.setLevel(logging.ERROR)
modlogger.addHandler(stderr_channel)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.mc = Memcached(prefix="mgtest-")
        self.db = CassandraPool().dbget("mgtest", self.mc)
        self.cleanup()

    def tearDown(self):
        self.cleanup()
        pass

    def cleanup(self):
        conn = self.db.pool.cget()
        try:
            conn.cass.system_drop_keyspace("mgtest")
        except Exception as e:
            pass
        self.db.pool.success(conn)
        self.mc.delete("Cassandra-KS-mgtest")
        self.mc.delete("Cassandra-CF-mgtest-Family1")
        self.mc.delete("Cassandra-CF-mgtest-Family2")
        self.mc.delete("Cassandra-CF-mgtest-Family3")

    def testputget(self):
        timestamp = time.time() * 1000
        self.db.insert("1", ColumnParent(column_family="Family1"), Column(name="email", value="aml@rulezz.ru - проверка", timestamp=timestamp), ConsistencyLevel.QUORUM)
        self.db.get_slice("1", ColumnParent(column_family="Family1"), SlicePredicate(slice_range=SliceRange(start="", finish="")), ConsistencyLevel.QUORUM)

    def testerror(self):
        try:
            self.db.insert("", ColumnParent(column_family="Family1"), Column(name="email", value="somevalue", timestamp=0), ConsistencyLevel.QUORUM)
            self.assertTrue(False)
        except DatabaseError as e:
            self.assertEqual(e.why, "Key may not be empty")
        else:
            self.assertTrue(False)

if __name__ == "__main__":
    dispatch(unittest.main)
