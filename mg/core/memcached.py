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

from concurrence.memcache.client import Memcache, MemcacheResult
from concurrence import Tasklet
from mg.core.tools import utf2str
import stackless
import re
import time
import logging
import traceback
import concurrence
import random

DEBUG = 0

class MemcachedEmptyKeyError(Exception):
    pass

class MemcachedPool(object):
    """
    Handles pool of Memcache objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, hosts=[("127.0.0.1", 11211)], size=8):
        """
        size - max amount of active memcached connections (None if no limit)
        """
        self.hosts = [(a, 100) for a in hosts]
        self.hosts_version = 0
        self.connections = []
        self.size = size
        self.allocated = 0
        self.channel = None
        self.last_debug = 0

    def set_hosts(self, hosts):
        self.hosts = hosts
        self.hosts_version += 1
        del self.connections[:]
        self.allocated = 0

    def new_connection(self):
        "Create a new Memcached and connect it"
        conn = Memcache(self.hosts)
        conn._hosts_version = self.hosts_version
        return conn

    def get(self):
        "Get a connection from the pool. If the pool is empty, current tasklet will be locked"
#        now = time.time()
#        if now > self.last_debug + 300:
#            logging.getLogger("memcached").debug("idle %s, allocated %s/%s", len(self.connections), self.allocated, self.size)
#            self.last_debug = now
        # The Pool contains at least one connection
        if len(self.connections) > 0:
            conn = self.connections.pop(0)
            return conn

        # There are no connections in the pool, but we may allocate more
        if self.size is None or self.allocated < self.size:
            self.allocated += 1
            conn = self.new_connection()
            return conn

        # We may not allocate more connections. Locking on the channel
        if self.channel is None:
            self.channel = concurrence.Channel()
        conn = self.channel.receive()
        return conn

    def put(self, connection):
        "Return a connection to the pool"
        # If memcached host changed
        if connection._hosts_version != self.hosts_version:
            self.put(self.new_connection())
        else:
            # If somebody waits on the channel
            if self.channel is not None and self.channel.balance < 0:
                self.channel.send(connection)
            else:
                self.connections.append(connection)

    def new(self):
        "Put a new connection to the pool"
        self.put(self.new_connection())

class Memcached(object):
    """
    Memcached - interface to the memcached system
    pool - MemcachedPool object
    prefix will be used in every key
    """
    def __init__(self, pool=None, prefix=""):
        """
        pool - MemcachedPool object
        prefix - prefix for all keys
        """
        object.__init__(self)
        if pool is None:
            self.pool = MemcachedPool()
        else:
            self.pool = pool
        self.prefix = prefix
        self.prefix_re = re.compile("^" + prefix)
    
    def get(self, key, default=None):
        if key == "":
            raise MemcachedEmptyKeyError()
        values = self.get_multi([key])
        return values.get(key, default)

    def get_multi(self, keys):
        connection = self.pool.get()
        if not connection:
            return {}
        try:
            query_keys = []
            for key in keys:
                qk = str(self.prefix + key)
                if qk == "":
                    raise MemcachedEmptyKeyError()
                query_keys.append(qk)
            got = connection.get_multi(query_keys)
            res = {}
            for item in got[1].iteritems():
                (key, data) = item
                res[self.prefix_re.sub("", key)] = data
        except IOError:
            self.pool.new()
            return {}
        except EOFError:
            self.pool.new()
            return {}
        except Exception as e:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def set(self, key, data, expiration=0, flags=0):
        if key == "":
            raise MemcachedEmptyKeyError()
        connection = self.pool.get()
        if not connection:
            return MemcacheResult.ERROR
        try:
            res = connection.set(str(self.prefix + key), data, expiration, flags)
            if res == MemcacheResult.ERROR or res == MemcacheResult.TIMEOUT:
                self.pool.new()
                return res
        except IOError:
            self.pool.new()
            return MemcacheResult.ERROR
        except EOFError:
            self.pool.new()
            return MemcacheResult.ERROR
        except Exception:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def add(self, key, data, expiration=0, flags=0):
        if key == "":
            raise MemcachedEmptyKeyError()
        connection = self.pool.get()
        if not connection:
            return MemcacheResult.ERROR
        try:
            res = connection.add(str(self.prefix + key), data, expiration, flags)
            if res == MemcacheResult.ERROR or res == MemcacheResult.TIMEOUT:
                self.pool.new()
                return res
        except IOError:
            self.pool.new()
            return MemcacheResult.ERROR
        except EOFError:
            self.pool.new()
            return MemcacheResult.ERROR
        except Exception:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def replace(self, key, data, expiration=0, flags=0):
        if key == "":
            raise MemcachedEmptyKeyError()
        connection = self.pool.get()
        if not connection:
            return MemcacheResult.ERROR
        try:
            res = connection.replace(str(self.prefix + key), data, expiration, flags)
            if res == MemcacheResult.ERROR or res == MemcacheResult.TIMEOUT:
                self.pool.new()
                return res
        except IOError:
            self.pool.new()
            return MemcacheResult.ERROR
        except EOFError:
            self.pool.new()
            return MemcacheResult.ERROR
        except Exception:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def incr(self, key, increment=1):
        if key == "":
            raise MemcachedEmptyKeyError()
        connection = self.pool.get()
        if not connection:
            return MemcacheResult.ERROR
        try:
            res = connection.incr(str(self.prefix + key), increment)
            if res == MemcacheResult.ERROR or res == MemcacheResult.TIMEOUT:
                self.pool.new()
                return res
        except IOError:
            self.pool.new()
            return MemcacheResult.ERROR
        except EOFError:
            self.pool.new()
            return MemcacheResult.ERROR
        except Exception:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def decr(self, key, decrement=1):
        if key == "":
            raise MemcachedEmptyKeyError()
        connection = self.pool.get()
        if not connection:
            return MemcacheResult.ERROR
        try:
            res = connection.decr(str(self.prefix + key), decrement)
            if res == MemcacheResult.ERROR or res == MemcacheResult.TIMEOUT:
                self.pool.new()
                return res
        except IOError:
            self.pool.new()
            return MemcacheResult.ERROR
        except EOFError:
            self.pool.new()
            return MemcacheResult.ERROR
        except Exception:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def delete(self, key, expiration=0):
        if key == "":
            raise MemcachedEmptyKeyError()
        connection = self.pool.get()
        if not connection:
            return MemcacheResult.ERROR
        try:
            res = connection.delete(str(self.prefix + key), expiration)
            if res == MemcacheResult.ERROR or res == MemcacheResult.TIMEOUT:
                self.pool.new()
                return res
        except IOError:
            self.pool.new()
            return MemcacheResult.ERROR
        except EOFError:
            self.pool.new()
            return MemcacheResult.ERROR
        except Exception:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def get_ver(self, group):
        if group == "":
            raise MemcachedEmptyKeyError()
        ver = self.get("GRP-%s" % group)
        if ver is None:
            ver = random.randrange(0, 1000000000)
            self.set("GRP-%s" % group, ver)
        return ver

    def incr_ver(self, group):
        if group == "":
            raise MemcachedEmptyKeyError()
        res = self.incr("GRP-%s" % group)
        if res[0] != MemcacheResult.OK:
            ver = random.randrange(0, 1000000000)
            self.set("GRP-%s" % group, ver)

    def ver(self, groups):
        key = '/ver'
        for g in groups:
            key += '/%s' % self.get_ver(g)
        return key

lock_serial = [0]

class MemcachedLock(object):
    """
    MemcachedLocker performs basic services on locking object using memcached INCR-DECR service
    """
    def __init__(self, mc, keys, patience=20, delay=0.1, ttl=30, value_prefix="", reason=None):
        """
        mc - Memcached instance
        keys - list of keys to lock
        """
        # Filter out keys that are already locked by the current tasklet
        tasklet_locks = self.tasklet_locks()
        self.keys = []
        for key in sorted(keys):
            mkey = "LOCK-" + str(key)
            if mkey not in tasklet_locks:
                self.keys.append(mkey)

        self.mc = mc
        self.patience = patience
        self.delay = delay
        self.locked = None
        self.ttl = ttl
        self.reason = reason
        self.value = str(value_prefix) + str(id(Tasklet.current()))
        if self.reason != None:
            self.value += "-" + str(self.reason)
        lock_serial[0] += 1
        self.value += "-" + str(lock_serial[0])

    def tasklet_locks(self):
        tasklet = Tasklet.current()
        try:
            return tasklet.memcached_locks
        except AttributeError:
            locks = set()
            tasklet.memcached_locks = locks
            return locks

    def __del__(self):
        self.__exit__(None, None, None)

    def __enter__(self):
        if self.mc is None:
            return
        start = None
        while True:
            locked = []
            try:
                success = True
                badlock = None
                for key in self.keys:
                    if self.mc.add(key, self.value, self.ttl) != MemcacheResult.NOT_STORED:
                        locked.append(key)
                    else:
                        for k in locked:
                            self.mc.delete(k)
                        success = False
                        badlock = (key, self.mc.get(key))
                        break
                if success:
                    if DEBUG:
                        logging.getLogger("mg.core.memcached.MemcachedLock").debug("[%s] Locked keys %s", self.value, locked)
                    self.locked = time.time()
                    self.onlocked()
                    return
                Tasklet.sleep(self.delay)
                if start is None:
                    start = time.time()
                elif time.time() > start + self.patience:
                    logging.getLogger("mg.core.memcached.MemcachedLock").error("[%s] Timeout waiting lock %s (locked by %s)", self.value, badlock[0], badlock[1])
                    logging.getLogger("mg.core.memcached.MemcachedLock").error(traceback.format_stack())
                    for key in self.keys:
                        self.mc.set(key, self.value, self.ttl)
                    logging.getLogger("mg.core.memcached.MemcachedLock").warning("[%s] Locked keys %s because of timeout", self.value, locked)
                    self.locked = time.time()
                    self.onlocked()
                    return
            except Exception:
                logging.getLogger("mg.core.memcached.MemcachedLock").error("[%s] Exception during locking. Unlock everything immediately", self.value)
                for k in locked:
                    self.mc.delete(k)
                raise

    def __exit__(self, type, value, tb):
        if self.mc is None:
            return
        if self.locked is not None:
            if time.time() < self.locked + self.ttl:
                for key in self.keys:
                    self.mc.delete(key)
                if DEBUG:
                    logging.getLogger("mg.core.memcached.MemcachedLock").debug("[%s] Unlocked keys %s", self.value, self.keys)
            else:
                logging.getLogger("mg.core.memcached.MemcachedLock").warning("[%s] Not locked keys %s because of ttl expired", self.value, self.keys)
            self.locked = None
            self.onunlocked()

    def trylock(self):
        if self.mc is None:
            return False
        locked = []
        try:
            for key in self.keys:
                if self.mc.add(key, self.value, self.ttl) != MemcacheResult.NOT_STORED:
                    locked.append(key)
                else:
                    if DEBUG:
                        logging.getLogger("mg.core.memcached.MemcachedLock").debug("[%s] Trylock failed. Rolling back keys %s", self.value, locked)
                    for k in locked:
                        self.mc.delete(k)
                    return False
        except Exception:
            logging.getLogger("mg.core.memcached.MemcachedLock").error("[%s] Exception during trylock. Unlock everything immediately", self.value)
            for k in locked:
                self.mc.delete(k)
            raise
        if DEBUG:
            logging.getLogger("mg.core.memcached.MemcachedLock").debug("[%s] Trylocked keys %s", self.value, locked)
        self.locked = time.time()
        self.onlocked()
        return True

    def unlock(self):
        self.__exit__(None, None, None)

    def onlocked(self):
        tasklet_locks = self.tasklet_locks()
        for key in self.keys:
            tasklet_locks.add(key)

    def onunlocked(self):
        tasklet_locks = self.tasklet_locks()
        for key in self.keys:
            tasklet_locks.discard(key)
