from concurrence.http import HTTPConnection, HTTPRequest
import json
import re
import mg.core.tools
from mg.core.thr import Socket
from thrift.transport import TTransport
from cassandra.Cassandra import Client
from cassandra.ttypes import *
import socket
from mg.core import Module
import logging
from uuid import uuid4
import time

class CassandraError(Exception):
    "This exception can be raised during database queries"
    pass

class JSONError(CassandraError):
    "JSON or UTF-8 decoding error"
    pass

class Cassandra(object):
    """
    Wrapper around CassandraConnection class. It puts CassandraConnection
    back to the pool on destruction
    """
    def __init__(self, pool, keyspace):
        self.pool = pool
        self.keyspace = keyspace

    def apply_keyspace(self, conn):
        if self.keyspace != conn.actual_keyspace:
            conn.set_keyspace(self.keyspace)

    def describe_keyspaces(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            return conn.cass.describe_keyspaces(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def describe_keyspace(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            return conn.cass.describe_keyspace(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def system_add_keyspace(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            return conn.cass.system_add_keyspace(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def system_drop_keyspace(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            conn.set_keyspace("system")
            return conn.cass.system_drop_keyspace(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def system_add_column_family(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.system_add_column_family(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def system_drop_column_family(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.system_drop_column_family(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def insert(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.insert(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def get_slice(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.get_slice(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def multiget_slice(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.multiget_slice(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def batch_mutate(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.batch_mutate(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def insert(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.insert(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def remove(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.remove(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def get(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.get(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def get_count(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.get_count(*args, **kwargs)
        finally:
            self.pool.cput(conn)

    def get_range_slices(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            return conn.cass.get_range_slices(*args, **kwargs)
        finally:
            self.pool.cput(conn)

class CassandraPool(object):
    """
    Handles pool of CassandraConnection objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, hosts=(("127.0.0.1", 9160),), size=None):
        self.hosts = list(hosts)
        self.connections = []
        self.size = size
        self.allocated = 0
        self.channel = None

    def new_connection(self):
        "Create a new CassandraConnection and connect it"
        connection = CassandraConnection(self.hosts)
        connection.connect()
        self.hosts.append(self.hosts.pop(0))
        return connection

    def cget(self):
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

    def cput(self, connection):
        "Return a connection to the pool"
        # If somebody waits on the channel
        if self.channel is not None and self.channel.balance < 0:
            self.channel.send(connection)
        else:
            self.connections.append(connection)

    def new(self):
        "Put a new connection to the pool"
        self.cput(self.new_connection())

    def dbget(self, keyspace):
        "The same as cget, but returns Cassandra wrapper"
        return Cassandra(self, keyspace)

class CassandraConnection(object):
    "CassandraConnection - interface to Cassandra database engine"
    def __init__(self, hosts=(("127.0.0.1", 9160),)):
        """
        hosts - ((host, port), (host, port), ...)
        """
        object.__init__(self)
        self.hosts = hosts
        self.cass = None
        self.actual_keyspace = None

    def __del__(self):
        self.disconnect()

    def connect(self):
        "Establish connection to the cluster"
        try:
            sock = Socket(self.hosts)
            self.trans = TTransport.TFramedTransport(sock)
            proto = TBinaryProtocol.TBinaryProtocolAccelerated(self.trans)
            self.cass = Client(proto)
            self.trans.open()
            self.actual_keyspace = None
        except:
            self.cass = None
            raise

    def disconnect(self):
        "Disconnect from the cluster"
        if self.cass:
            self.trans.close()
            self.trans = None
            self.cass = None

    def set_keyspace(self, keyspace):
        self.actual_keyspace = keyspace
        self.cass.set_keyspace(keyspace)

class CassandraDiff(object):
    "Difference between old and new configurations"
    def __init__(self):
        self.ops = []

    def __str__(self):
        return self.ops.__str__()

class CassandraRestructure(object):
    "CassandraRestructure creates missing column families and drops unused ones"
    def __init__(self, db):
        """
        db - Cassandra object
        """
        self.db = db
        self.logger = logging.getLogger("mg.core.cass.CassandraRestructure")

    def diff(self, config):
        "Perform all checks and returns diff of existing and target configuration"
        dbdiff = CassandraDiff()
        keyspaces = self.db.describe_keyspaces()
        family_exists = dict()
        required = set()
        if not self.db.keyspace in keyspaces:
            dbdiff.ops.append(("cks", KsDef(name=self.db.keyspace, strategy_class="org.apache.cassandra.locator.RackUnawareStrategy", replication_factor=1, cf_defs=[])))
        else:
            family_exists = self.db.describe_keyspace(self.db.keyspace)
        for (name, cfdef) in config.items():
            if name in family_exists:
                existing = family_exists[name]
                if cfdef.column_type != existing["Type"] or "org.apache.cassandra.db.marshal." + cfdef.comparator_type != existing["CompareWith"] or cfdef.comment != existing["Desc"] or cfdef.clock_type != existing["ClockType"]:
                    dbdiff.ops.append(("df", name))
                    cfdef.table = self.db.keyspace
                    cfdef.name = name
                    dbdiff.ops.append(("cf", cfdef))
            else:
                cfdef.table = self.db.keyspace
                cfdef.name = name
                dbdiff.ops.append(("cf", cfdef))
            required.add(name)
        for name in family_exists:
            if name not in required:
                dbdiff.ops.append(("df", name))
        return dbdiff

    def apply(self, dbdiff):
        "Take diff and performs all required operations"
        for cmd in dbdiff.ops:
            if cmd[0] == "cf":
                self.logger.debug("created column family %s: %s", cmd[1].name, self.db.system_add_column_family(cmd[1]))
            elif cmd[0] == "df":
                self.logger.debug("destoyed column family %s: %s", cmd[1], self.db.system_drop_column_family(cmd[1]))
            elif cmd[0] == "cks":
                self.logger.debug("created keyspace %s: %s", cmd[1].name, self.db.system_add_keyspace(cmd[1]))
            else:
                self.logger.error("invalid command %s", cmd)

class CommonCassandraStruct(Module):
    def register(self):
        Module.register(self)
        self.rhook("core.dbstruct", self.cassandra_struct)
        self.rhook("core.dbapply", self.cassandra_apply)

    def cassandra_struct(self, dbstruct):
        dbstruct["Core"] = CfDef()
        dbstruct["Objects"] = CfDef()

    def cassandra_apply(self, dbstruct):
        db = self.db()
        restruct = CassandraRestructure(db)
        diff = restruct.diff(dbstruct)
        restruct.apply(diff)

class CassandraObject(object):
    """
    An ORM object
    """
    def __init__(self, db, uuid=None, data=None, prefix=""):
        """
        db - CassandraDatabase Object
        uuid - ID of object (None if newly created)
        data - preloaded object data (None is not loaded)
        """
        self.db = db
        self.prefix = prefix
        if uuid is None:
            self.uuid = re.sub(r'^urn:uuid:', '', uuid4().urn)
            self.new = True
            self.dirty = True
            if data is None:
                self.data = {}
            else:
                self.data = data
        else:
            self.uuid = uuid
            self.dirty = False
            self.new = False
            if data is None:
                self.load()
            else:
                self.data = data

    def indexes(self):
        """
        List of object indexes. Every index is a mapping: key => UUID
        When object is changed it is reflected in its indexes.
        Override to set your own index lists. Format:
        [
          ['field1', 'field2']
          ['field3', 'field2', 'field4']
        ]
        """
        return []

    def load(self):
        """
        Load object from the database
        Raises NotFoundException
        """
        col = self.db.get(self.prefix + self.uuid, ColumnPath("Objects", column="data"), ConsistencyLevel.QUORUM).column
        self.data = json.loads(col.value)
        self.dirty = False

    def store_data(self):
        """
        Returns JSON object or None if not modified
        dirty flag is turned down
        """
        if not self.dirty:
            return None
        self.dirty = False
        self.new = False
        return json.dumps(self.data)

    def store(self):
        """
        Store object in the database
        """
        data = self.store_data()
        if data is not None:
            timestamp = time.time() * 1000
            self.db.batch_mutate({(self.prefix + self.uuid): {"Objects": [Mutation(ColumnOrSuperColumn(Column(name="data", value=data, clock=Clock(timestamp=timestamp))))]}}, ConsistencyLevel.QUORUM)

    def remove(self):
        """
        Remove object from the database
        """
        timestamp = time.time() * 1000
        self.db.remove((self.prefix + self.uuid), ColumnPath("Objects"), Clock(timestamp=timestamp), ConsistencyLevel.QUORUM)
        self.dirty = False
        self.new = False

    def get(self, key):
        """
        Get data key
        """
        return self.data.get(key)

    def set(self, key, value):
        """
        Set data value
        """
        self.data[key] = value
        self.dirty = True

    def delkey(self, key):
        """
        Delete key
        """
        try:
            del self.data[key]
            self.dirty = True
        except KeyError:
            pass

class CassandraObjectList(object):
    def __init__(self, db, uuids, prefix=""):
        self.dict = [CassandraObject(db, uuid, {}, prefix) for uuid in uuids]
        self.load()

    def load(self):
        if len(self.dict) > 0:
            d = self.dict[0].db.multiget_slice([(obj.prefix + obj.uuid) for obj in self.dict], ColumnParent(column_family="Objects"), SlicePredicate(column_names=["data"]), ConsistencyLevel.QUORUM)
            for obj in self.dict:
                cols = d[obj.prefix + obj.uuid]
                if len(cols) > 0:
                    obj.data = json.loads(cols[0].column.value)
                    obj.dirty = False
                else:
                    raise NotFoundException("UUID %s (prefix %s) not found" % (obj.uuid, obj.prefix))

    def store(self):
        if len(self.dict) > 0:
            mutations = {}
            timestamp = time.time() * 1000
            for obj in self.dict:
                data = obj.store_data()
                if data is not None:
                    mutations[obj.prefix + obj.uuid] = {"Objects": [Mutation(ColumnOrSuperColumn(Column(name="data", value=data, clock=Clock(timestamp=timestamp))))]}
            if len(mutations) > 0:
                self.dict[0].db.batch_mutate(mutations, ConsistencyLevel.QUORUM)

    def remove(self):
        if len(self.dict) > 0:
            timestamp = time.time() * 1000
            for obj in self.dict:
                obj.db.remove(obj.prefix + obj.uuid, ColumnPath("Objects"), Clock(timestamp=timestamp), ConsistencyLevel.QUORUM)
                obj.dirty = False
                obj.new = False

    def __len__(self):
        return self.dict.__len__()

    def __getitem__(self, key):
        return self.dict.__getitem__(key)

    def __setitem__(self, key, value):
        return self.dict.__setitem__(key, value)

    def __delitem__(self, key):
        return self.dict.__delitem__(key)

    def __iter__(self):
        return self.dict.__iter__()

    def __reversed__(self):
        return self.dict.__reversed__()

    def __contains__(self, item):
        return self.dict.__contains__(item)

    def __getslice__(self, i, j):
        return self.dict.__getslice__(i, j)

    def __setslice__(self, i, j, sequence):
        return self.dict.__setslice__(i, j, sequence)

    def __delslice__(self, i, j):
        return self.dict.__delslice__(i, j)
