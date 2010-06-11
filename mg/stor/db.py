from concurrence.http import HTTPConnection, HTTPRequest
import json
import re
import mg.tools
from mg.net.thr import Socket
from thrift.transport import TTransport
from cassandra import Cassandra
from cassandra.ttypes import *

class DatabaseError(Exception):
    "This exception can be raised during database queries"
    pass

class JSONError(DatabaseError):
    "JSON or UTF-8 decoding error"
    pass

class DatabasePool(object):
    """
    Handles pool of DatabaseConnection objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, hosts=(("127.0.0.1", 9160),), size=10):
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

    def get(self):
        "Get a connection from the pool. If the pool is empty, current tasklet will be blocked"
        # The Pool contains at least one connection
        if len(self.connections) > 0:
            return self.connections.pop(0)

        # There are no connections in the pool, but we may allocate more
        if self.allocated < self.size:
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

class DatabaseConnection(object):
    "DatabaseConnection - interface to Cassandra database engine"
    def __init__(self, hosts=(("127.0.0.1", 9160),)):
        """
        hosts - ((host, port), (host, port), ...)
        """
        object.__init__(self)
        self.hosts = hosts
        self.slash_re = re.compile("^/+")
        self.socket = None

    def __del__(self):
        self.disconnect()

    def connect(self):
        "Establish connection to the cluster"
        try:
            self.socket = Socket(self.hosts)
            self.transport = TTransport.TFramedTransport(self.socket)
            self.protocol = TBinaryProtocol.TBinaryProtocolAccelerated(self.transport)
            self.cass = Cassandra.Client(self.protocol)
            self.transport.open()
        except:
            self.socket = None
            self.transport = None
            self.protocol = None
            self.cass = None
            raise

    def disconnect(self):
        "Disconnect from the cluster"
        if self.socket:
            self.transport.close()
            self.socket = None
            self.transport = None
            self.protocol = None
            self.cass = None

    def set_keyspace(self, *args, **kwargs):
        return self.cass.set_keyspace(*args, **kwargs)

    def describe_keyspaces(self, *args, **kwargs):
        return self.cass.describe_keyspaces(*args, **kwargs)

    def describe_keyspace(self, *args, **kwargs):
        return self.cass.describe_keyspace(*args, **kwargs)

    def system_add_keyspace(self, *args, **kwargs):
        return self.cass.system_add_keyspace(*args, **kwargs)

    def system_add_column_family(self, *args, **kwargs):
        return self.cass.system_add_column_family(*args, **kwargs)

    def system_drop_column_family(self, *args, **kwargs):
        return self.cass.system_drop_column_family(*args, **kwargs)

class DatabaseDiff(object):
    "Difference between old and new configurations"
    def __init__(self):
        self.ops = []

    def __str__(self):
        return self.ops.__str__()

class DatabaseRestructure(object):
    "DatabaseRestructure creates missing column families and drops unused ones"
    def __init__(self, db, keyspace):
        """
        db - DatabaseConnection
        keyspace - keyspace for operations
        """
        self.db = db
        self.keyspace = keyspace

    def diff(self, config):
        "Perform all checks and returns diff of existing and target configuration"
        dbdiff = DatabaseDiff()
        keyspaces = self.db.describe_keyspaces()
        family_exists = dict()
        required = set()
        if not self.keyspace in keyspaces:
            dbdiff.ops.append(("cks", KsDef(name="mgtest", strategy_class="org.apache.cassandra.locator.RackUnawareStrategy", replication_factor=1, cf_defs=[])))
        else:
            family_exists = self.db.describe_keyspace(self.keyspace)
        for (name, cfdef) in config.items():
            if name in family_exists:
                existing = family_exists[name]
                if cfdef.column_type != existing["Type"] or "org.apache.cassandra.db.marshal." + cfdef.comparator_type != existing["CompareWith"] or cfdef.comment != existing["Desc"] or cfdef.clock_type != existing["ClockType"]:
                    dbdiff.ops.append(("df", name))
                    cfdef.table = self.keyspace
                    cfdef.name = name
                    dbdiff.ops.append(("cf", cfdef))
            else:
                cfdef.table = self.keyspace
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
                print "created column family %s: %s" % (cmd[1].name, self.db.system_add_column_family(cmd[1]))
            elif cmd[0] == "df":
                print "destoyed column family %s: %s" % (cmd[1], self.db.system_drop_column_family(self.keyspace, cmd[1]))
            elif cmd[0] == "cks":
                print "created keyspace %s: %s" % (cmd[1].name, self.db.system_add_keyspace(cmd[1]))
            else:
                print "invalid command %s" % cmd
