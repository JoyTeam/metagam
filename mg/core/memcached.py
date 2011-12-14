from concurrence.memcache.client import MemcacheConnection, MemcacheResult
from concurrence import Tasklet
import stackless
import re
import time
import logging
import traceback
import concurrence
import random

class MemcachedPool(object):
    """
    Handles pool of MemcacheConnection objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, host=("127.0.0.1", 11211), size=256):
        """
        size - max amount of active memcached connections (None if no limit)
        """
        self.host = tuple(host)
        self.connections = []
        self.size = size
        self.allocated = 0
        self.channel = None

    def set_host(self, host):
        self.host = tuple(host)
        del self.connections[:]

    def new_connection(self):
        "Create a new MemcacheConnection and connect it"
        try:
            connection = MemcacheConnection(self.host)
            connection.connect()
            return connection
        except IOError:
            return None

    def get(self):
        "Get a connection from the pool. If the pool is empty, current tasklet will be bleocked"
        # The Pool contains at least one connection
        if len(self.connections) > 0:
            return self.connections.pop(0)

        # There are no connections in the pool, but we may allocate more
        if self.size is None or self.allocated < self.size:
            self.allocated += 1
            return self.new_connection()

        # We may not allocate more connections. Locking on the channel
        if self.channel is None:
            self.channel = concurrence.Channel()
        return self.channel.receive()

    def put(self, connection):
        "Return a connection to the pool"
        # If memcached host changed
        if connection._address != self.host:
            self.put(self.new_connection())
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
        values = self.get_multi([key])
        return values.get(key, default)

    def get_multi(self, keys):
        connection = self.pool.get()
        if not connection:
            return {}
        try:
            got = connection.get_multi(map(lambda key: str(self.prefix + key), keys))
            if got[0] == MemcacheResult.ERROR or got[0] == MemcacheResult.TIMEOUT:
                self.pool.new()
                return {}
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
        except Exception:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def set(self, key, data, expiration=0, flags=0):
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
        ver = self.get("GRP-%s" % group)
        if ver is None:
            ver = random.randrange(0, 1000000000)
            self.set("GRP-%s" % group, ver)
        return ver

    def incr_ver(self, group):
        res = self.incr("GRP-%s" % group)
        if res[0] != MemcacheResult.OK:
            ver = random.randrange(0, 1000000000)
            self.set("GRP-%s" % group, ver)

    def ver(self, groups):
        key = '/ver'
        for g in groups:
            key += '/%s' % self.get_ver(g)
        return key

class MemcachedLock(object):
    """
    MemcachedLocker performs basic services on locking object using memcached INCR-DECR service
    """
    def __init__(self, mc, keys, patience=20, delay=0.1, ttl=30, value_prefix=""):
        """
        mc - Memcached instance
        keys - list of keys to lock
        """
        self.mc = mc
        self.keys = ["LOCK-" + str(key) for key in sorted(keys)]
        self.patience = patience
        self.delay = delay
        self.locked = None
        self.ttl = ttl
        self.value = str(value_prefix) + str(id(Tasklet.current()))

    def __del__(self):
        self.__exit__(None, None, None)

    def __enter__(self):
        if self.mc is None:
            return
        start = None
        while True:
            locked = []
            success = True
            badlock = None
            for key in self.keys:
                if self.mc.add(key, self.value, self.ttl) == MemcacheResult.STORED:
                    locked.append(key)
                else:
                    for k in locked:
                        self.mc.delete(k)
                    success = False
                    badlock = (key, self.mc.get(key))
                    break
            if success:
                self.locked = time.time()
                return
            Tasklet.sleep(self.delay)
            if start is None:
                start = time.time()
            elif time.time() > start + self.patience:
                logging.getLogger("mg.core.memcached.MemcachedLock").error("Timeout waiting lock %s (locked by %s)" % badlock)
                logging.getLogger("mg.core.memcached.MemcachedLock").error(traceback.format_stack())
                for key in self.keys:
                    self.mc.set(key, self.value, self.ttl)
                self.locked = time.time()
                return

    def __exit__(self, type, value, traceback):
        if self.mc is None:
            return
        if self.locked is not None:
            if time.time() < self.locked + self.ttl:
                for key in self.keys:
                    self.mc.delete(key)
            self.locked = None
