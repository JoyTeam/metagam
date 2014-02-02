#!/usr/bin/python2.6

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

# -*- coding: utf-8 -*-

import unittest
from concurrence import dispatch, Tasklet
import mg.test.testorm
from mg.core.memcached import Memcached
from mg.core.cass import CassandraPool

class TestORM_Storage1(mg.test.testorm.TestORM):
    def setUp(self):
        mg.test.testorm.TestORM.setUp(self)
        self.db.storage = 1

def main():
    mg.test.testorm.cleanup()
    unittest.main()

if __name__ == "__main__":
    dispatch(main)
