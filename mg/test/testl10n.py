#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet
from mg import *

class FakeRequest(object):
    pass

class TestCore(unittest.TestCase):
    def setUp(self):
        self.inst = Instance("test", "test")
        self.app = Application(self.inst, "mgtest")
        self.app.modules.load(["mg.core.l10n.L10n"])

    def test_local(self):
        req = Tasklet.current().req = FakeRequest()
        req.lang = "en"
        values = "apple/apples"
        self.assertEqual(self.app.call("l10n.literal_value", 0, values), "apples")
        self.assertEqual(self.app.call("l10n.literal_value", 1, values), "apple")
        self.assertEqual(self.app.call("l10n.literal_value", 1.5, values), "apples")
        self.assertEqual(self.app.call("l10n.literal_value", 101, values), "apples")
        req.lang = "ru"
        values = "яблоко/яблока/яблок"
        self.assertEqual(self.app.call("l10n.literal_value", 0, values), "яблок")
        self.assertEqual(self.app.call("l10n.literal_value", 1, values), "яблоко")
        self.assertEqual(self.app.call("l10n.literal_value", 1.5, values), "яблока")
        self.assertEqual(self.app.call("l10n.literal_value", 2, values), "яблока")
        self.assertEqual(self.app.call("l10n.literal_value", 3, values), "яблока")
        self.assertEqual(self.app.call("l10n.literal_value", 5, values), "яблок")
        self.assertEqual(self.app.call("l10n.literal_value", 11, values), "яблок")
        self.assertEqual(self.app.call("l10n.literal_value", 21, values), "яблоко")
        values = "зелёное яблоко/зелёных яблока/зелёных яблок/зелёного яблока"
        self.assertEqual(self.app.call("l10n.literal_value", 0, values), "зелёных яблок")
        self.assertEqual(self.app.call("l10n.literal_value", 1, values), "зелёное яблоко")
        self.assertEqual(self.app.call("l10n.literal_value", 1.5, values), "зелёного яблока")
        self.assertEqual(self.app.call("l10n.literal_value", 2, values), "зелёных яблока")
        self.assertEqual(self.app.call("l10n.literal_value", 3, values), "зелёных яблока")
        self.assertEqual(self.app.call("l10n.literal_value", 5, values), "зелёных яблок")
        self.assertEqual(self.app.call("l10n.literal_value", 11, values), "зелёных яблок")
        self.assertEqual(self.app.call("l10n.literal_value", 21, values), "зелёное яблоко")

if __name__ == "__main__":
    dispatch(unittest.main)

