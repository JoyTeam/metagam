#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

from mg import *
import unittest
from concurrence import dispatch, Tasklet
import logging

modlogger = logging.getLogger("")
modlogger.setLevel(logging.DEBUG)
stderr_channel = logging.StreamHandler()
stderr_channel.setLevel(logging.DEBUG)
modlogger.addHandler(stderr_channel)

class TestMySQL(unittest.TestCase):
    def setUp(self):
        self.db = MySQLPool(user="mgtest", passwd="mgtest", db="mgtest").dbget()
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        try:
            self.db.do("drop table mgtest")
        except ClientError:
            pass

    def test01(self):
        self.assertEqual(self.db.do("select 1"), 1)
        data = self.db.selectall("select 2")
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]), 1)
        self.assertEqual(data[0][0], "2")

    def test02(self):
        self.db.do("create table mgtest(a integer, b integer, c varchar(30))")
        data = self.db.selectall("select a, b from mgtest")
        self.assertEqual(len(data), 0)
        self.db.do("insert into mgtest(a, b, c) values (1, 2, 'abc')")
        self.db.do("insert into mgtest(a, b, c) values (3, 4, 'def')")
        data = self.db.selectall("select a, b, 3, c from mgtest")
        self.assertEqual(len(data), 2)
        self.assertEqual(len(data[0]), 4)
        self.assertEqual(data[0][0], 1)
        self.assertEqual(data[0][1], 2)
        self.assertEqual(data[0][2], "3")
        self.assertEqual(data[0][3], "abc")
        self.assertEqual(len(data[1]), 4)
        self.assertEqual(data[1][0], 3)
        self.assertEqual(data[1][1], 4)
        self.assertEqual(data[1][2], "3")
        self.assertEqual(data[1][3], "def")
        data = self.db.selectall_dict("select * from mgtest")
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["a"], 1)
        self.assertEqual(data[0]["b"], 2)
        self.assertEqual(data[0]["c"], "abc")
        self.assertEqual(data[1]["a"], 3)
        self.assertEqual(data[1]["b"], 4)
        self.assertEqual(data[1]["c"], "def")
        self.assertEqual(self.db.do("update mgtest set a=3 where b=2"), 1)
        self.assertEqual(self.db.do("update mgtest set b=10"), 2)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["a"], 1)
        self.assertEqual(data[0]["b"], 2)
        self.assertEqual(data[0]["c"], "abc")

    def test03(self):
        self.db.do("create table mgtest(a integer, b integer, c varchar(30))")
        self.db.do("insert into mgtest(a, b, c) values (?, ?, ?)", 10, None, "test")
        data = self.db.selectall("select * from mgtest")
        self.assertEqual(data, [(10, None, "test")])
        self.db.do("delete from mgtest")
        self.db.do("insert into mgtest(c) values (?)", "\r\n\0'\"\\")
        data = self.db.selectall("select c from mgtest")
        self.assertEqual(data, [("\r\n\0'\"\\", )])

    def test04(self):
        self.db.do("create table mgtest(c varchar(30))")
        self.db.do("insert into mgtest(c) values (?)", "проверка")
        data = self.db.selectall("select c from mgtest")
        self.assertEqual(data, [("проверка", )])
        self.db.do("delete from mgtest")
        self.db.do("insert into mgtest(c) values (?)", u"проверка")
        data = self.db.selectall("select c from mgtest")
        self.assertEqual(data, [("проверка", )])

if __name__ == "__main__":
    dispatch(unittest.main)
