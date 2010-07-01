from concurrence.http import HTTPConnection, HTTPRequest
import json
import re
import mg.tools
from mg.thr import Socket
from thrift.transport import TTransport
from cassandra import Cassandra
from cassandra.ttypes import *
import socket
from mg.core import Module
import logging

class DatabaseError(Exception):
    "This exception can be raised during database queries"
    pass

class JSONError(DatabaseError):
    "JSON or UTF-8 decoding error"
    pass

class Database(object):
    """
    Wrapper around DatabaseConnection class. It puts DatabaseConnection
    back to the pool on destruction
    """
    def __init__(self, conn, pool, keyspace):
        self.conn = conn
        self.pool = pool
        self.keyspace = keyspace

    def __del__(self):
        self.pool.cput(self.conn)

    def apply_keyspace(self):
        if self.keyspace != self.conn.actual_keyspace:
            self.conn.set_keyspace(self.keyspace)

    def describe_keyspaces(self, *args, **kwargs):
        return self.conn.cass.describe_keyspaces(*args, **kwargs)

    def describe_keyspace(self, *args, **kwargs):
        return self.conn.cass.describe_keyspace(*args, **kwargs)

    def system_add_keyspace(self, *args, **kwargs):
        return self.conn.cass.system_add_keyspace(*args, **kwargs)

    def system_drop_keyspace(self, *args, **kwargs):
        self.conn.set_keyspace("system")
        return self.conn.cass.system_drop_keyspace(*args, **kwargs)

    def system_add_column_family(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.system_add_column_family(*args, **kwargs)

    def system_drop_column_family(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.system_drop_column_family(*args, **kwargs)

    def insert(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.insert(*args, **kwargs)

    def get_slice(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.get_slice(*args, **kwargs)

    def multiget_slice(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.multiget_slice(*args, **kwargs)

    def batch_mutate(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.batch_mutate(*args, **kwargs)

    def insert(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.insert(*args, **kwargs)

    def remove(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.remove(*args, **kwargs)

    def get(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.get(*args, **kwargs)

    def get_count(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.get_count(*args, **kwargs)

    def get_range_slices(self, *args, **kwargs):
        self.apply_keyspace()
        return self.conn.cass.get_range_slices(*args, **kwargs)

class DatabasePool(object):
    """
    Handles pool of DatabaseConnection objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, hosts=(("127.0.0.1", 9160),), size=None):
        self.hosts = list(hosts)
        self.connections = []
        self.size = size
        self.allocated = 0
        self.channel = None

    def new_connection(self):
        "Create a new DatabaseConnection and connect it"
        connection = DatabaseConnection(self.hosts)
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
        "The same as cget, but returns Database wrapper"
        return Database(self.cget(), self, keyspace)

class DatabaseConnection(object):
    "DatabaseConnection - interface to Cassandra database engine"
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
            self.cass = Cassandra.Client(proto)
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

class DatabaseDiff(object):
    "Difference between old and new configurations"
    def __init__(self):
        self.ops = []

    def __str__(self):
        return self.ops.__str__()

class DatabaseRestructure(object):
    "DatabaseRestructure creates missing column families and drops unused ones"
    def __init__(self, db):
        """
        db - Database object
        """
        self.db = db
        self.logger = logging.getLogger("mg.cass.DatabaseRestructure")

    def diff(self, config):
        "Perform all checks and returns diff of existing and target configuration"
        dbdiff = DatabaseDiff()
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

class CommonDatabaseStruct(Module):
    def register(self):
        Module.register(self)
        self.rhook("core.dbstruct", self.database_struct)
        self.rhook("core.dbapply", self.database_apply)

    def database_struct(self, dbstruct):
        dbstruct["Core"] = CfDef()

    def database_apply(self, dbstruct):
        db = self.db()
        restruct = DatabaseRestructure(db)
        diff = restruct.diff(dbstruct)
        restruct.apply(diff)
