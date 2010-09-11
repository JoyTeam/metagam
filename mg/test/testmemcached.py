#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

from mg.core.memcached import Memcached, MemcachedPool
import unittest
from concurrence import dispatch, Tasklet

class TestMemcached(unittest.TestCase):
    def setUp(self):
        self.mc = Memcached(prefix="mgtest-")

    def testsetget(self):
        self.mc.set("key1", "value1")
        self.assertEqual(self.mc.get("key1"), "value1")
        self.mc.delete("key1")
        self.assertEqual(self.mc.get("key1"), None)

    def testgetmulti(self):
        self.mc.set("key1", "value1")
        self.mc.set("key2", "value2")
        self.assertEqual(self.mc.get("key1"), "value1")
        self.assertEqual(self.mc.get("key2"), "value2")
        res = self.mc.get_multi([ "key1", "key2" ])
        self.assertEqual(res["key1"], "value1")
        self.assertEqual(res["key2"], "value2")

    def testunicode(self):
        self.mc.set("key1", u"проверка")
        self.assertEqual(type(self.mc.get("key1")), unicode)
        self.mc.set("key1", u"проверка1")
        self.mc.set("key2", u"проверка2")
        self.assertEqual(self.mc.get("key1"), u"проверка1")
        self.assertEqual(self.mc.get("key2"), u"проверка2")
        res = self.mc.get_multi([ "key1", "key2" ])
        self.assertEqual(res["key1"], u"проверка1")
        self.assertEqual(res["key2"], u"проверка2")

    def testthreading(self):
        task = {}
        for i in range(1, 100):
            task[i] = Tasklet.new(self.thread)(i)
        for i in range(1, 100):
            Tasklet.join(task[i])

    def thread(self, n):
        for i in range(1, 50):
            self.mc.set("key%d" % n, "value%d" % n)
            self.assertEqual(self.mc.get("key%d" % n), "value%d" % n)
            self.mc.delete("key%d" % n)
            self.assertEqual(self.mc.get("key%d" % n), None)

if __name__ == "__main__":
    dispatch(unittest.main)
