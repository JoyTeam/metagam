#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

from mg.core.memcached import Memcached, MemcachedPool, MemcachedEmptyKeyError
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
        tasks = []
        for i in xrange(0, 100):
            tasks.append(Tasklet.new(self.thread)(i))
        Tasklet.join_all(tasks)

    def thread(self, n):
        for i in xrange(0, 50):
            self.mc.set("key%d" % n, "value%d" % n)
            self.assertEqual(self.mc.get("key%d" % n), "value%d" % n)
            self.mc.delete("key%d" % n)
            self.assertEqual(self.mc.get("key%d" % n), None)

    def testerrors(self):
        mc = Memcached(pool=MemcachedPool(size=4))
        tasks = []
        for i in xrange(0, 100):
            tasks.append(Tasklet.new(self.error_thread)(mc))
        for i in xrange(0, 100):
            tasks.append(Tasklet.new(self.handled_thread)(mc))
        Tasklet.join_all(tasks)

    def handled_thread(self, mc):
        for i in xrange(0, 50):
            try:
                # must not happen
                self.assertEqual(mc.get(""), 1)
            except MemcachedEmptyKeyError:
                pass
            except Exception:
                self.assertFalse("must not happen")

    def error_thread(self, mc):
        for i in xrange(0, 50):
            self.assertEqual(mc.get(" "), None)

if __name__ == "__main__":
    dispatch(unittest.main)
