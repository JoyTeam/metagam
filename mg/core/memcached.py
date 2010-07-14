from concurrence.memcache.client import MemcacheConnection
import stackless
import re

class MemcachedPool(object):
    """
    Handles pool of MemcacheConnection objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, host=("127.0.0.1", 11211), size=10):
        """
        size - max amount of active memcached connections (None if no limit)
        """
        self.host = host
        self.connections = []
        self.size = size
        self.allocated = 0
        self.channel = None

    def new_connection(self):
        "Create a new MemcacheConnection and connect it"
        connection = MemcacheConnection(self.host)
        connection.connect()
        return connection

    def get(self):
        "Get a connection from the pool. If the pool is empty, current tasklet will be blocked"
        # The Pool contains at least one connection
        if len(self.connections) > 0:
            return self.connections.pop(0)

        # There are no connections in the pool, but we may allocate more
        if self.size is None or self.allocated < self.size:
            self.allocated += 1
            connection = self.new_connection()
            return connection

        # We may not allocate more connections. Locking on the channel
        if self.channel is None:
            self.channel = stackless.channel()
        return self.channel.receive()

    def put(self, connection):
        "Return a connection to the pool"
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
    
    def get(self, keys, default=None):
        connection = self.pool.get()
        try:
            res = connection.get(self.prefix + keys, default)
        except:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def get_multi(self, keys):
        connection = self.pool.get()
        try:
            got = connection.get_multi(map(lambda key: self.prefix + key, keys))
            res = {}
            for item in got[1].iteritems():
                (key, data) = item
                res[self.prefix_re.sub("", key)] = data
        except:
            self.pool.new()
            raise
        self.pool.put(connection)
        return res

    def set(self, key, data, expiration=0, flags=0):
        connection = self.pool.get()
        try:
            connection.set(self.prefix + key, data, expiration, flags)
        except:
            self.pool.new()
            raise
        self.pool.put(connection)

    def add(self, key, data, expiration=0, flags=0):
        connection = self.pool.get()
        try:
            connection.add(self.prefix + key, data, expiration, flags)
        except:
            self.pool.new()
            raise
        self.pool.put(connection)

    def replace(self, key, data, expiration=0, flags=0):
        connection = self.pool.get()
        try:
            connection.replace(self.prefix + key, data, expiration, flags)
        except:
            self.pool.new()
            raise
        self.pool.put(connection)

    def incr(self, key, increment):
        connection = self.pool.get()
        try:
            connection.incr(self.prefix + key, increment)
        except:
            self.pool.new()
            raise
        self.pool.put(connection)

    def decr(self, key, decrement):
        connection = self.pool.get()
        try:
            connection.decr(self.prefix + key, decrement)
        except:
            self.pool.new()
            raise
        self.pool.put(connection)

    def delete(self, key, expiration=0):
        connection = self.pool.get()
        try:
            connection.delete(self.prefix + key, expiration)
        except:
            self.pool.new()
            raise
        self.pool.put(connection)

