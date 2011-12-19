#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet
import mg.test.testorm
from mg.core.memcached import Memcached
from mg.core.cass import CassandraPool

class TestORM_Storage2(mg.test.testorm.TestORM):
    def setUp(self):
        mg.test.testorm.TestORM.setUp(self)
        self.db.storage = 2
        self.db.app = "testapp"

def main():
    mg.test.testorm.cleanup()
    unittest.main()

if __name__ == "__main__":
    dispatch(main)
