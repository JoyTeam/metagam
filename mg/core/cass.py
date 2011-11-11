from concurrence.http import HTTPConnection, HTTPRequest
import json
import re
import mg.core
from mg.core.tools import *
from mg.core.memcached import MemcachedLock
from concurrence.thr import Socket
from thrift.transport import TTransport
from cassandra.Cassandra import Client
from cassandra.ttypes import *
from uuid import uuid4
from concurrence import TimeoutError, Tasklet, Timeout
import socket
import logging
import time
import random
import stackless
import concurrence
import re

cache_interval = 3600
max_index_length = 10000000

re_unconfigured_ks = re.compile(r'^Keyspace (.+) does not exist$')
re_unconfigured_cf = re.compile(r'^unconfigured columnfamily (.+)$')
re_notagree = re.compile(r'not yet agree')
re_remove_index_prefix = re.compile(r'^.+?_Index_eq-')
re_key_may_not_be_empty = re.compile(r'^Key may not be empty$')

class CassandraError(Exception):
    "This exception can be raised during database queries"
    pass

class JSONError(CassandraError):
    "JSON or UTF-8 decoding error"
    pass

class DatabaseError(CassandraError):
    def __init__(self, why):
        self.why = why

    def __str__(self):
        return self.why

    def __repr__(self):
        return self.why

class ObjectNotFoundException(Exception):
    "CassandraObject not found"
    pass

class RetryException(Exception):
    pass

class Cassandra(object):
    """
    Wrapper around CassandraConnection class. It puts CassandraConnection
    back to the pool on destruction
    """
    def __init__(self, pool, keyspace, mc, storage=0, app=None):
        self.pool = pool
        self.keyspace = keyspace
        self.mc = mc
        self._last_time = 0
        # 0 - single CF for all objects
        # 1 - separate CF for every class
        # 2 - several applications in the single keyspace (app is the actual app code)
        self.storage = storage
        self.app = app

    def apply_keyspace(self, conn):
        if self.keyspace != conn.actual_keyspace:
            conn.set_keyspace(self.keyspace)

    def execute(self, method_name, options, *args, **kwargs):
        conn = self.pool.cget()
        while True:
            try:
                method = getattr(conn.cass, method_name)
                try:
                    if options:
                        if options.get("sysspace"):
                            conn.set_keyspace("system")
                        elif options.get("space"):
                            self.apply_keyspace(conn)
                    res = method(*args, **kwargs)
                except NotFoundException:
                    raise
                except InvalidRequestException as e:
                    if re_key_may_not_be_empty.match(e.why):
                        raise DatabaseError(e.why)
                    if re_notagree.search(e.why):
                        raise RetryException
                    m = re_unconfigured_ks.match(e.why)
                    if m:
                        keyspace = m.group(1)
                        with MemcachedLock(self.mc, ["Cassandra-Reconfigure"], patience=1800):
                            logger = logging.getLogger("mg.core.cass.Cassandra")
                            # Avoiding multiple attempts to create single KS
                            if self.mc and self.mc.get("Cassandra-KS-%s" % keyspace):
                                logger.debug("Skipping creation of keyspace %s", keyspace)
                                raise RetryException
                            logger.debug("Creating keyspace %s", keyspace)
                            ksdef = KsDef()
                            ksdef.name = keyspace
                            ksdef.strategy_class = "org.apache.cassandra.locator.SimpleStrategy"
                            ksdef.replication_factor = self.replication_factor(conn.cass)
                            ksdef.cf_defs = []
                            sys_conn = self.pool.sys_connection()
                            sys_conn.cass.set_keyspace("system")
                            logger.debug("Created keyspace %s (replication factor %d): %s", ksdef.name, ksdef.replication_factor, sys_conn.cass.system_add_keyspace(ksdef))
                            # Setting flag that KS is created already
                            if self.mc:
                                self.mc.set("Cassandra-KS-%s" % keyspace, 1, 600)
                            with Timeout.push(30):
                                try:
                                    while True:
                                        versions = sys_conn.cass.describe_schema_versions()
                                        ver_list = [v for v in versions.keys() if v != 'UNREACHABLE']
                                        if len(ver_list) < 2:
                                            logger.debug("Cluster schema agree: %s", versions)
                                            break
                                        else:
                                            logger.debug("Cluster schema not yet agree: %s", versions)
                                            Tasklet.sleep(0.1)
                                except TimeoutError:
                                    raise RetryException
                        raise RetryException
                    m = re_unconfigured_cf.match(e.why)
                    if m:
                        family = m.group(1)
                        with MemcachedLock(self.mc, ["Cassandra-Reconfigure"], patience=1800):
                            logger = logging.getLogger("mg.core.cass.Cassandra")
                            # Avoiding multiple attempts to create single CF
                            if self.mc and self.mc.get("Cassandra-CF-%s-%s" % (self.keyspace, family)):
                                logger.debug("Skipping creation of column family %s.%s", self.keyspace, family)
                                raise RetryException
                            logger.debug("Creating column family %s.%s", self.keyspace, family)
                            cfdef = CfDef()
                            cfdef.keyspace = self.keyspace
                            cfdef.name = family
                            cfdef.key_cache_size = 50000
                            cfdef.key_cache_save_period_in_seconds = 3600
                            cfdef.memtable_throughput_in_mb = 10
                            cfdef.memtable_operations_in_millions = 100000 / 1e6
                            cfdef.gc_grace_seconds = 86400
                            cfdef.min_compaction_threshold = 2
                            cfdef.max_compaction_threshold = 4
                            sys_conn = self.pool.sys_connection()
                            sys_conn.cass.set_keyspace("system")
                            logger.debug("Created column family %s.%s: %s", self.keyspace, cfdef.name, sys_conn.cass.system_add_column_family(cfdef))
                            # Setting flag that CF is created already
                            if self.mc:
                                self.mc.set("Cassandra-CF-%s-%s" % (self.keyspace, family), 1, 600)
                            with Timeout.push(30):
                                try:
                                    while True:
                                        versions = sys_conn.cass.describe_schema_versions()
                                        ver_list = [v for v in versions.keys() if v != 'UNREACHABLE']
                                        if len(ver_list) < 2:
                                            logger.debug("Cluster schema agree: %s", versions)
                                            break
                                        else:
                                            logger.debug("Cluster schema not yet agree: %s", versions)
                                            Tasklet.sleep(0.1)
                                except TimeoutError:
                                    raise RetryException
                        raise RetryException
                    raise
                self.pool.success(conn)
                return res
            except AttributeError:
                self.pool.error(e)
                raise
            except TimeoutError:
                self.pool.error(e)
                raise
            except NotFoundException:
                self.pool.success(conn)
                raise
            except RetryException:
                self.pool.error()
                conn = self.pool.cget()
                Tasklet.sleep(0.1)
            except DatabaseError as e:
                self.pool.error()
                logger = logging.getLogger("mg.core.cass.Cassandra")
                logger.exception(e)
                raise
            except Exception as e:
                self.pool.error(e)
                conn = self.pool.cget()

    def describe_ring(self, *args, **kwargs):
        return self.execute("describe_ring", None, *args, **kwargs)

    def describe_keyspaces(self, *args, **kwargs):
        return self.execute("describe_keyspaces", None, *args, **kwargs)

    def describe_keyspace(self, *args, **kwargs):
        return self.execute("describe_keyspace", None, *args, **kwargs)

    def system_add_keyspace(self, *args, **kwargs):
        return self.execute("system_add_keyspace", None, *args, **kwargs)

    def system_drop_keyspace(self, *args, **kwargs):
        return self.execute("system_drop_keyspace", {"sysspace": True}, *args, **kwargs)

    def system_add_column_family(self, *args, **kwargs):
        return self.execute("system_add_column_family", {"space": True}, *args, **kwargs)

    def system_update_column_family(self, *args, **kwargs):
        return self.execute("system_update_column_family", {"space": True}, *args, **kwargs)

    def system_drop_column_family(self, *args, **kwargs):
        return self.execute("system_drop_column_family", {"space": True}, *args, **kwargs)

    def insert(self, *args, **kwargs):
        return self.execute("insert", {"space": True}, *args, **kwargs)

    def get_slice(self, *args, **kwargs):
        return self.execute("get_slice", {"space": True}, *args, **kwargs)

    def multiget_slice(self, *args, **kwargs):
        return self.execute("multiget_slice", {"space": True}, *args, **kwargs)

    def batch_mutate(self, *args, **kwargs):
        return self.execute("batch_mutate", {"space": True}, *args, **kwargs)

    def remove(self, *args, **kwargs):
        return self.execute("remove", {"space": True}, *args, **kwargs)

    def get(self, *args, **kwargs):
        return self.execute("get", {"space": True}, *args, **kwargs)

    def get_count(self, *args, **kwargs):
        return self.execute("get_count", {"space": True}, *args, **kwargs)

    def get_range_slices(self, *args, **kwargs):
        return self.execute("get_range_slices", {"space": True}, *args, **kwargs)

    def get_time(self):
        now = time.time() * 1000
        if now > self._last_time:
            self._last_time = now
        else:
            self._last_time += 1
        return self._last_time

    def replication_factor(self, cass):
        keyspaces = [ksdef.name for ksdef in cass.describe_keyspaces()]
        if "ringtest" not in keyspaces:
            logger = logging.getLogger("mg.core.cass.Cassandra")
            logger.debug("Created keyspace ringtest: %s", cass.system_add_keyspace(KsDef(name="ringtest", strategy_class="org.apache.cassandra.locator.SimpleStrategy", replication_factor=1, cf_defs=[])))
            logger.debug("Waiting 10 sec")
            Tasklet.sleep(10)
        ring = set()
        for ent in cass.describe_ring("ringtest"):
            for ip in ent.endpoints:
                ring.add(ip)
        replication_factor = len(ring)
        if replication_factor > 3:
            replication_factor = 3
        return replication_factor

class CassandraPool(object):
    """
    Handles pool of CassandraConnection objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, hosts=(("127.0.0.1", 9160),), size=256, primary_host_id=0):
        self.sys_host = tuple(hosts[0])
        self.hosts = [tuple(host) for host in hosts]
        self.primary_host = self.hosts.pop(primary_host_id)
        self.hosts.insert(0, self.primary_host)
        self.connections = []
        self.size = size
        self.allocated = 0
        self.channel = None
        self.success_counter = 0

    def set_host(self, hosts, primary_host_id=0):
        self.hosts = [tuple(host) for host in hosts]
        self.primary_host = self.hosts.pop(primary_host_id)
        self.hosts.insert(0, self.primary_host)
        del self.connections[:]

    def exception(self, *args, **kwargs):
        logging.getLogger("mg.core.cass.CassandraPool").exception(*args, **kwargs)

    def debug(self, *args, **kwargs):
        logging.getLogger("mg.core.cass.CassandraPool").debug(*args, **kwargs)

    def sys_connection(self):
        "Create a new CassandraConnection and connect to the system host (for schema changed)"
        connection = CassandraConnection(self.sys_host)
        connection.connect()
        return connection

    def new_connection(self):
        "Create a new CassandraConnection and connect to the first host in the list"
        connection = CassandraConnection(self.hosts[0])
        connection.connect()
        return connection

    def new_primary_connection(self):
        "Create a new CassandraConnection and connect to the primary host"
        connection = CassandraConnection(self.primary_host)
        connection.connect()
        return connection

    def error(self, exc=None):
        "Notify Pool that currently selected connection is bad"
        if exc is None:
            Tasklet.sleep(0.1)
            conn = self.new_connection()
            self.cput(conn)
            return
        while True:
            bad_host = self.hosts.pop(0)
            self.hosts.append(bad_host)
            del self.connections[:]
            self.debug("Cassandra server %s failed: %s. Trying %s", bad_host, exc, self.hosts[0])
            Tasklet.sleep(1)
            try:
                self.success_counter = 0
                conn = self.new_connection()
                self.cput(conn)
                return
            except Exception as e:
                exc = e

    def success(self, conn):
        "Notify Pool that connection 'conn' succeeded request"
        if conn.host == self.hosts[0]:
            self.success_counter += 1
            if self.success_counter >= 1000 and self.hosts[0] != self.primary_host:
                self.debug("Cassandra server %s succeeded %d operations. Probing primary host %s", self.hosts[0], self.success_counter, self.primary_host)
                self.success_counter = 0
                try:
                    primary_conn = self.new_primary_connection()
                except TimeoutError:
                    self.cput(conn)
                    raise
                except Exception as e:
                    self.debug("Primary host %s is still dead: %s", self.primary_host, e)
                    self.cput(conn)
                else:
                    self.debug("Connection to the primary host %s succeeded", self.primary_host)
                    for i in xrange(0, len(self.hosts)):
                        if self.hosts[i] == self.primary_host:
                            host = self.hosts.pop(i)
                            self.hosts.insert(0, host)
                    del self.connections[:]
                    self.cput(primary_conn)
            else:
                self.cput(conn)
        else:
            self.debug("Switching to the server %s", self.hosts[0])
            conn = self.new_connection()
            self.cput(conn)

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
            self.channel = concurrence.Channel()
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

    def dbget(self, keyspace, mc, storage=0, app=None):
        "The same as cget, but returns Cassandra wrapper"
        return Cassandra(self, keyspace, mc, storage, app)

class CassandraConnection(object):
    "CassandraConnection - interface to Cassandra database engine"
    def __init__(self, host=("127.0.0.1", 9160)):
        """
        host - (hostname, port)
        """
        object.__init__(self)
        self.host = host
        self.cass = None
        self.actual_keyspace = None

    def __del__(self):
        self.disconnect()

    def connect(self):
        "Establish connection to the cluster"
        try:
            sock = Socket([self.host])
            self.trans = TTransport.TFramedTransport(sock)
            proto = TBinaryProtocol.TBinaryProtocolAccelerated(self.trans)
            self.cass = Client(proto)
            self.trans.open()
            self.actual_keyspace = None
        except Exception:
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

class CassandraObject(object):
    """
    An ORM object
    """
    def __init__(self, db, uuid=None, data=None, silent=False):
        """
        db - Cassandra database
        uuid - ID of the object (None if newly created)
        data - preloaded object data (None is not loaded)
        """
        self.db = db
        if uuid is None:
            self.uuid = uuid4().hex
            self.new = True
            self.dirty = True
            self._indexes = {}
            if data is None:
                self.data = {}
            else:
                self.data = data
        else:
            if type(uuid) is unicode:
                uuid = uuid.encode("utf-8")
            self.uuid = uuid
            self.dirty = False
            self.new = False
            if data is None:
                try:
                    self.load()
                except ObjectNotFoundException:
                    if silent:
                        self.data = {}
                        self._indexes = {}
                    else:
                        raise
            else:
                self.data = data
                self._indexes = {}

    def get_indexes(self):
        """
        Returns structure describing object indexes. When an object changes it is reflected in its indexes. Format:
        {
          'name1': [['eqfield1']],                            # where eqfield1=<value1>
          'name2': [['eqfield1', 'eqfield2']],                # where eqfield1=<value1> and eqfield2=<value2>
          'name3': [[], 'ordfield'],                          # where ordfield between <value1> and <value2> order by ordfield
          'name4': [['eqfield1'], 'ordfield'],                # where eqfield1=<value1> and ordfield between <value2> and <value3> order by ordfield
          'name5': [['eqfield1', 'eqfield2'], 'ordfield'],    # where eqfield1=<value1> and eqfield2=<value2> and ordfield between <value3> and <value4> order by ordfield
        }
        """
        try:
            return self.__class__.indexes
        except AttributeError:
            return {}

    def index_values(self):
        if self._indexes is None:
            self.calculate_indexes()
        return self._indexes

    def calculate_indexes(self):
        _indexes = {}
        for index_name, index in self.get_indexes().iteritems():
            values = ["eq"]
            abort = False
            for field in index[0]:
                val = self.data.get(field)
                if val is None:
                    abort = True
                    break;
                values.append(unicode(val))
            if not abort:
                tokens = []
                for i in range(1, len(index)):
                    val = self.data.get(index[i])
                    if val is None:
                        abort = True
                        break
                    else:
                        tokens.append(unicode(val))
                if not abort:
                    tokens.append(self.uuid)
                    col = u"-".join(tokens)
                    row_id = u"-".join(values)
                    _indexes[index_name] = [row_id, col]
        self._indexes = _indexes

    def load(self):
        """
        Load object from the database
        Raises ObjectNotFoundException
        """
        self._indexes = None
        row_mcid = "%s-%s" % (self.__class__.clsname, self.uuid)
        self.data = self.db.mc.get(row_mcid) if self.db.mc else None
        if self.data == "tomb":
#            print "LOAD(MC) %s %s" % (row_id, self.data)
            self.data = {}
            raise ObjectNotFoundException(self.uuid)
        elif self.data is None:
            if len(self.uuid) == 0:
                raise ObjectNotFoundException(self.uuid)
            try:
                if self.db.storage == 0:
                    col = self.db.get("%s_Object_%s" % (self.__class__.clsname, self.uuid), ColumnPath("Data", column="data-%s" % self.uuid), ConsistencyLevel.QUORUM).column
                elif self.db.storage == 1:
                    col = self.db.get(self.uuid, ColumnPath("%s_Objects" % self.__class__.clsname, column="data-%s" % self.uuid), ConsistencyLevel.QUORUM).column
                elif self.db.storage == 2:
                    col = self.db.get("%s_%s" % (self.db.app, self.uuid), ColumnPath("%s_Objects" % self.__class__.clsname, column="data-%s" % self.uuid), ConsistencyLevel.QUORUM).column
            except NotFoundException:
                self.data = {}
                raise ObjectNotFoundException(self.uuid)
            self.data = json.loads(col.value)
            if self.db.mc:
                self.db.mc.add(row_mcid, self.data, cache_interval)
#            print "LOAD(DB) %s %s" % (row_id, self.data)
#        else:
#            print "LOAD(MC) %s %s" % (row_id, self.data)
        self.dirty = False

    def mutate(self, mutations, mcgroups, timestamp):
        """
        Returns mapping of row_key => [Mutation, Mutation, ...] if modified
        dirty flag is turned off
        """
        if not self.dirty:
            return
        # calculating index mutations
        old_index_values = self.index_values()
        self.calculate_indexes()
        index_values = self.index_values()
        #print "storing indexes\n\told: %s\n\tnew: %s" % (old_index_values, index_values)
        for index_name, columns in self.get_indexes().iteritems():
            key = index_values.get(index_name)
            old_key = old_index_values.get(index_name)
            if old_key != key:
                mcgroups.add("%s-%s/VER" % (self.__class__.clsname, index_name))
                #print "\t\t%s: %s => %s" % (index_name, old_key, key)
                # deleting old index entry if exists
                if old_key is not None:
                    mutation = Mutation(deletion=Deletion(predicate=SlicePredicate([old_key[1].encode("utf-8")]), timestamp=timestamp))
                    if self.db.storage == 0:
                        index_row = (u"%s_%s_Index_%s" % (self.__class__.clsname, index_name, old_key[0])).encode("utf-8")
                        cf = "Data"
                    elif self.db.storage == 1:
                        index_row = unicode(old_key[0]).encode("utf-8")
                        cf = "%s_Index_%s" % (self.__class__.clsname, index_name)
                    elif self.db.storage == 2:
                        index_row = (u"%s_%s_Index_%s" % (self.db.app, index_name, old_key[0])).encode("utf-8")
                        cf = "%s_Indexes" % self.__class__.clsname
                    #print "delete: row=%s, column=%s" % (index_row, old_key[1].encode("utf-8"))
                    m = mutations.get(index_row)
                    if m is None:
                        mutations[index_row] = {cf: [mutation]}
                    else:
                        mcf = m.get(cf)
                        if mcf is None:
                            m[cf] = [mutation]
                        else:
                            mcf.append(mutation)
                # creating new index entry if needed
                if key is not None:
                    mutation = Mutation(ColumnOrSuperColumn(Column(name=key[1].encode("utf-8"), value=self.uuid, timestamp=timestamp)))
                    if self.db.storage == 0:
                        index_row = (u"%s_%s_Index_%s" % (self.__class__.clsname, index_name, key[0])).encode("utf-8")
                        cf = "Data"
                    elif self.db.storage == 1:
                        index_row = unicode(key[0]).encode("utf-8")
                        cf = "%s_Index_%s" % (self.__class__.clsname, index_name)
                    elif self.db.storage == 2:
                        index_row = (u"%s_%s_Index_%s" % (self.db.app, index_name, key[0])).encode("utf-8")
                        cf = "%s_Indexes" % self.__class__.clsname
                    #print [ index_row, key[1] ]
                    #print "insert: row=%s, column=%s" % (index_row, key[1].encode("utf-8"))
                    m = mutations.get(index_row)
                    if m is None:
                        mutations[index_row] = {cf: [mutation]}
                    else:
                        mcf = m.get(cf)
                        if mcf is None:
                            m[cf] = [mutation]
                        else:
                            mcf.append(mutation)
        # mutation of the object itself
        mutation = Mutation(ColumnOrSuperColumn(Column(name="data-%s" % self.uuid, value=json.dumps(self.data).encode("utf-8"), timestamp=timestamp)))
        if self.db.storage == 0:
            cf = "Data"
            row_key = "%s_Object_%s" % (self.__class__.clsname, self.uuid)
        elif self.db.storage == 1:
            cf = "%s_Objects" % self.__class__.clsname
            row_key = self.uuid
        elif self.db.storage == 2:
            cf = "%s_Objects" % self.__class__.clsname
            row_key = "%s_%s" % (self.db.app, self.uuid)
        m = mutations.get(row_key)
        if m is None:
            mutations[row_key] = {cf: [mutation]}
        else:
            mcf = m.get(cf)
            if mcf is None:
                m[cf] = [mutation]
            else:
                mcf.append(mutation)
        logging.getLogger("mg.core.cass.CassandraObject").debug("STORE %s-%s-%s %s", self.db.keyspace, self.__class__.clsname, self.uuid, self.data)
        row_mcid = "%s-%s" % (self.__class__.clsname, self.uuid)
        if self.db.mc:
            self.db.mc.set(row_mcid, self.data, cache_interval)
        self.dirty = False
        self.new = False

    def store(self):
        """
        Store object in the database
        """
        if not self.dirty:
            return
        timestamp = self.db.get_time()
        mutations = {}
        mcgroups = set()
        self.mutate(mutations, mcgroups, timestamp)
        if len(mutations):
            self.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
            if self.db.mc:
                for mcid in mcgroups:
                    self.db.mc.incr(mcid)

    def remove(self):
        """
        Remove object from the database
        """
        #print "removing %s" % self.uuid
        timestamp = self.db.get_time()
        row_mcid = "%s-%s" % (self.__class__.clsname, self.uuid)
        if self.db.storage == 0:
            self.db.remove("%s_Object_%s" % (self.__class__.clsname, self.uuid), ColumnPath("Data"), timestamp, ConsistencyLevel.QUORUM)
        elif self.db.storage == 1:
            self.db.remove(self.uuid, ColumnPath("%s_Objects" % self.__class__.clsname), timestamp, ConsistencyLevel.QUORUM)
        elif self.db.storage == 2:
            self.db.remove("%s_%s" % (self.db.app, self.uuid), ColumnPath("%s_Objects" % self.__class__.clsname), timestamp, ConsistencyLevel.QUORUM)
        if self.db.mc:
            self.db.mc.set(row_mcid, "tomb", cache_interval)
        # removing indexes
        mutations = {}
        mcgroups = set()
        old_index_values = self.index_values()
        for index_name, key in old_index_values.iteritems():
            if self.db.storage == 0:
                index_row = (u"%s_%s_Index_%s" % (self.__class__.clsname, index_name, key[0])).encode("utf-8")
                cf = "Data"
            elif self.db.storage == 1:
                index_row = unicode(key[0]).encode("utf-8")
                cf = "%s_Index_%s" % (self.__class__.clsname, index_name)
            elif self.db.storage == 2:
                index_row = (u"%s_%s_Index_%s" % (self.db.app, index_name, key[0])).encode("utf-8")
                cf = "%s_Indexes" % self.__class__.clsname
            mutation = Mutation(deletion=Deletion(predicate=SlicePredicate([key[1].encode("utf-8")]), timestamp=timestamp))
            m = mutations.get(index_row)
            if m is None:
                mutations[index_row] = {cf: [mutation]}
            else:
                mcf = m.get(cf)
                if mcf is None:
                    m[cf] = [mutation]
                else:
                    mcf.append(mutation)
            mcgroups.add("%s-%s/VER" % (self.__class__.clsname, index_name))
            #print "delete: row=%s, column=%s" % (index_row, key[1].encode("utf-8"))
#       print "REMOVE %s" % row_id
        if len(mutations):
            self.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
            if self.db.mc:
                for mcid in mcgroups:
                    self.db.mc.incr(mcid)
        self.dirty = False
        self.new = False

    def get(self, key, default=None):
        """
        Get data key
        """
        return self.data.get(key, default)

    def touch(self):
        self.index_values()
        self.dirty = True

    def set(self, key, value):
        """
        Set data value
        """
        if type(value) == str:
            value = unicode(value, "utf-8")
        if self.data.get(key) != value:
            self.index_values()
            self.data[key] = value
            self.dirty = True

    def clear(self):
        """
        Clear all data
        """
        self.index_values()
        self.data = {}
        self.dirty = True

    def delkey(self, key):
        """
        Delete key
        """
        if self.data.has_key(key):
            self.index_values()
            del self.data[key]
            self.dirty = True

    def get_int(self, key):
        val = self.get(key)
        if val is None:
            return 0
        return int(val)

    def incr(self, key, incr=1):
        self.set(key, self.get_int(key) + incr)

    def decr(self, key, decr=1):
        self.set(key, self.get_int(key) - decr)

    def data_copy(self):
        copy = self.data.copy()
        copy["uuid"] = self.uuid
        return copy

class CassandraObjectList(object):
    def __init__(self, db, uuids=None, query_index=None, query_equal=None, query_start="", query_finish="", query_limit=1000000, query_reversed=False):
        """
        To access a list of known uuids:
        lst = CassandraObjectList(db, ["uuid1", "uuid2", ...])

        To query equal index 'name2' => [['eqfield1', 'eqfield2']]:
        lst = CassandraObjectList(db, query_index="name2", query_equal="value1-value2", query_limit=1000)

        To query equal index 'name2' for several index values:
        lst = CassandraObjectList(db, query_index="name2", query_equal=["value1-value2", "VALUE1-VALUE2", ...], query_limit=1000)

        To query ordered index 'name5' => [['eqfield1', 'eqfield2'], 'ordfield1', 'ordfield2']:
        lst = CassandraObjectList(db, query_index="name5", query_equal="value1-value2", query_start="OrdFrom", query_finish="OrdTo", query_reversed=True)
        """
        self.db = db
        self._loaded = False
        self.index_rows = {}
        self.query_index = query_index
        cls = self.__class__.objcls
        clsname = cls.clsname
        self.index_prefix_len = 0
        if uuids is not None:
            self.lst = [cls(db, uuid, {}) for uuid in uuids]
        elif query_index is not None:
            grpmcid = "%s-%s/VER" % (clsname, query_index)
            grpid = self.db.mc.get(grpmcid) if self.db.mc else None
            if grpid is None:
                grpid = random.randint(0, 2000000000)
                if self.db.mc:
                    self.db.mc.set(grpmcid, grpid)
            if type(query_equal) == list:
                # multiple keys
                mcids = []
                index_rows = []
                self.index_data = []
                for val in query_equal:
                    mcid = urlencode("%s-%s-%s/%s/%s/%s/%s/%s" % (clsname, query_index, val, query_start, query_finish, query_limit, query_reversed, grpid))
                    mcids.append(mcid)
                    if self.db.storage == 0:
                        index_row = "%s_%s_Index_eq-%s" % (clsname, query_index, val)
                    elif self.db.storage == 1:
                        index_row = "eq-%s" % val
                    elif self.db.storage == 2:
                        index_row = "%s_%s_Index_eq-%s" % (self.db.app, query_index, val)
                    if type(index_row) == unicode:
                        index_row = index_row.encode("utf-8")
                    index_rows.append(index_row)
#               print "loading mcids %s" % mcids
                d = self.db.mc.get_multi(mcids) if self.db.mc else {}
#               print d
                remain_index_rows = []
                for i in range(0, len(query_equal)):
                    index_row = index_rows[i]
                    index_data = d.get(mcids[i])
                    if index_data is not None:
#                       print "Storing: %s => %s" % (index_row, index_data)
                        self.index_rows[index_row] = [ent[1] for ent in index_data]
                        self.index_data.extend(index_data)
                    else:
                        remain_index_rows.append(index_row)
                if len(remain_index_rows):
#                   print "loading index rows %s" % remain_index_rows
                    if self.db.storage == 0:
                        cf = "Data"
                    elif self.db.storage == 1:
                        cf = "%s_Index_%s" % (clsname, query_index)
                    elif self.db.storage == 2:
                        cf = "%s_Indexes" % clsname
                    d = self.db.multiget_slice(remain_index_rows, ColumnParent(column_family=cf), SlicePredicate(slice_range=SliceRange(start=query_start, finish=query_finish, reversed=query_reversed, count=query_limit)), ConsistencyLevel.QUORUM)
#                   print d
                    for index_row, index_data in d.iteritems():
                        self.index_rows[index_row] = [col.column.value for col in index_data]
                        index_data = [[col.column.name, col.column.value] for col in index_data]
                        self.index_data.extend(index_data)
                        mcid = urlencode("%s-%s-%s/%s/%s/%s/%s/%s" % (clsname, query_index, index_row, query_start, query_finish, query_limit, query_reversed, grpid))
                        #logging.getLogger("mg.core.cass.CassandraObject").debug("storing mcid %s = %s", mcid, index_data)
                        if self.db.mc:
                            if len(index_data) < max_index_length:
                                self.db.mc.set(mcid, index_data)
                            else:
                                self.db.mc.delete(mcid)
                self.index_data.sort(cmp=lambda x, y: cmp(x[0], y[0]), reverse=query_reversed)
                self.lst = [cls(db, col[1], {}) for col in self.index_data]
                #print "loaded index data %s" % self.index_data
            else:
                # single key
                mcid = urlencode("%s-%s-%s/%s/%s/%s/%s/%s" % (clsname, query_index, query_equal, query_start, query_finish, query_limit, query_reversed, grpid))
                if self.db.storage == 0:
                    if query_equal is None:
                        index_row = "%s_%s_Index_eq" % (clsname, query_index)
                    else:
                        index_row = "%s_%s_Index_eq-%s" % (clsname, query_index, query_equal)
                elif self.db.storage == 1:
                    if query_equal is None:
                        index_row = "eq"
                    else:
                        index_row = "eq-%s" % query_equal
                elif self.db.storage == 2:
                    if query_equal is None:
                        index_row = "%s_%s_Index_eq" % (self.db.app, query_index)
                    else:
                        index_row = "%s_%s_Index_eq-%s" % (self.db.app, query_index, query_equal)
                if type(index_row) == unicode:
                    index_row = index_row.encode("utf-8")
#               print "loading mcid %s" % mcid
                d = self.db.mc.get(mcid) if self.db.mc else None
                if d is not None:
                    self.index_rows[index_row] = [ent[1] for ent in d]
                    self.index_data = d
                else:
#                   print "loading index row %s" % index_row
                    if self.db.storage == 0:
                        cf = "Data"
                    elif self.db.storage == 1:
                        cf = "%s_Index_%s" % (clsname, query_index)
                    elif self.db.storage == 2:
                        cf = "%s_Indexes" % clsname
                    d = self.db.get_slice(index_row, ColumnParent(column_family=cf), SlicePredicate(slice_range=SliceRange(start=query_start, finish=query_finish, reversed=query_reversed, count=query_limit)), ConsistencyLevel.QUORUM)
                    self.index_rows[index_row] = [col.column.value for col in d]
                    self.index_data = [[col.column.name, col.column.value] for col in d]
                    #logging.getLogger("mg.core.cass.CassandraObject").debug("storing mcid %s = %s", mcid, self.index_data)
                    if self.db.mc:
                        if len(self.index_data) < max_index_length:
                            self.db.mc.set(mcid, self.index_data)
                        else:
                            self.db.mc.delete(mcid)
#               print "loaded index data " % self.index_data
                self.lst = [cls(db, col[1], {}) for col in self.index_data]
        else:
            raise RuntimeError("Invalid usage of CassandraObjectList")
        for obj in self.lst:
            obj._indexes = None

    def index_values(self, strip_prefix_len=0):
        res = []
        for key, values in self.index_rows.iteritems():
            stripped_key = re_remove_index_prefix.sub('', key)
            stripped_key = stripped_key[strip_prefix_len:] if strip_prefix_len else stripped_key
            for val in values:
                res.append((stripped_key, val))
        return res

    def load(self, silent=False):
        if len(self.lst) > 0:
            clsname = self.__class__.objcls.clsname
            row_mcids = ["%s-%s" % (clsname, obj.uuid) for obj in self.lst]
            mc_d = self.db.mc.get_multi(row_mcids) if self.db.mc else {}
            if self.db.storage == 0:
                col_ids = [obj.uuid for obj in self.lst if "%s-%s" % (clsname, obj.uuid) not in mc_d]
                row_ids = ["%s_Object_%s" % (clsname, uuid) for uuid in col_ids]
                if row_ids:
                    db_d = self.db.multiget_slice(row_ids, ColumnParent(column_family="Data"), SlicePredicate(column_names=["data-%s" % uuid for uuid in col_ids]), ConsistencyLevel.QUORUM)
                else:
                    db_d = {}
            elif self.db.storage == 1:
                col_ids = [obj.uuid for obj in self.lst if "%s-%s" % (clsname, obj.uuid) not in mc_d]
                row_ids = col_ids
                if row_ids:
                    db_d = self.db.multiget_slice(row_ids, ColumnParent(column_family="%s_Objects" % clsname), SlicePredicate(column_names=["data-%s" % uuid for uuid in col_ids]), ConsistencyLevel.QUORUM)
                else:
                    db_d = {}
            elif self.db.storage == 2:
                col_ids = [obj.uuid for obj in self.lst if "%s-%s" % (clsname, obj.uuid) not in mc_d]
                row_ids = ["%s_%s" % (self.db.app, uuid) for uuid in col_ids]
                if row_ids:
                    db_d = self.db.multiget_slice(row_ids, ColumnParent(column_family="%s_Objects" % clsname), SlicePredicate(column_names=["data-%s" % uuid for uuid in col_ids]), ConsistencyLevel.QUORUM)
                else:
                    db_d = {}
            recovered = False
            for obj in self.lst:
                obj.valid = True
                row_mcid = "%s-%s" % (clsname, obj.uuid)
                data = mc_d.get(row_mcid)
                if data is not None:
                    #print "LOAD(MC) %s %s" % (obj.uuid, data)
                    if data == "tomb":
                        if silent:
                            obj.valid = False
                            recovered = True
                            if len(self.index_rows):
                                mutations = []
                                mcgroups = set()
                                timestamp = None
                                for col in self.index_data:
                                    if col[1] == obj.uuid:
                                        #print "read recovery. removing column %s from index row %s" % (col.column.name, self.index_row)
                                        if timestamp is None:
                                            timestamp = self.db.get_time()
                                        mutations.append(Mutation(deletion=Deletion(predicate=SlicePredicate([col[0]]), timestamp=timestamp)))
                                        if self.db.mc:
                                            self.db.mc.incr("%s-%s/VER" % (clsname, self.query_index))
                                        break
                                if len(mutations):
                                    if self.db.storage == 0:
                                        cf = "Data"
                                    elif self.db.storage == 1:
                                        cf = "%s_Index_%s" % (clsname, self.query_index)
                                    elif self.db.storage == 2:
                                        cf = "%s_Indexes" % clsname
                                    self.db.batch_mutate(dict([(index_row, {cf: mutations}) for index_row, values in self.index_rows.iteritems()]), ConsistencyLevel.QUORUM)
                        else:
                            raise ObjectNotFoundException("UUID %s (keyspace %s, cls %s) not found" % (obj.uuid, obj.db.keyspace, clsname))
                    else:
                        obj.data = data
                        obj.dirty = False
                else:
                    if self.db.storage == 0:
                        row_id = "%s_Object_%s" % (clsname, obj.uuid)
                    elif self.db.storage == 1:
                        row_id = obj.uuid
                    elif self.db.storage == 2:
                        row_id = "%s_%s" % (self.db.app, obj.uuid)
                    cols = db_d.get(row_id)
                    if cols:
                        obj.data = json.loads(cols[0].column.value)
                        obj.dirty = False
                        if self.db.mc:
                            self.db.mc.add(row_mcid, obj.data, cache_interval)
                        #print "LOAD(DB) %s %s" % (obj.uuid, obj.data)
                    elif silent:
                        obj.valid = False
                        recovered = True
                        if len(self.index_rows):
                            mutations = []
                            timestamp = None
                            for col in self.index_data:
                                if col[1] == obj.uuid:
                                    #print "read recovery. removing column %s from index row %s" % (col.column.name, self.index_row)
                                    if timestamp is None:
                                        timestamp = self.db.get_time()
                                    mutations.append(Mutation(deletion=Deletion(predicate=SlicePredicate([col[0]]), timestamp=timestamp)))
                                    if self.db.mc:
                                        self.db.mc.incr("%s-%s/VER" % (clsname, self.query_index))
                                    break
                            if len(mutations):
                                if self.db.storage == 0:
                                    cf = "Data"
                                elif self.db.storage == 1:
                                    cf = "%s_Index_%s" % (clsname, self.query_index)
                                elif self.db.storage == 2:
                                    cf = "%s_Indexes" % clsname
                                self.db.batch_mutate(dict([(index_row, {cf: mutations}) for index_row, values in self.index_rows.iteritems()]), ConsistencyLevel.QUORUM)
                    else:
                        raise ObjectNotFoundException("UUID %s (keyspace %s, cls %s) not found" % (obj.uuid, obj.db.keyspace, clsname))
            if recovered:
                self.lst = [obj for obj in self.lst if obj.valid]
        self._loaded = True

    def _load_if_not_yet(self, silent=False):
        if not self._loaded:
            self.load(silent);

    def store(self, dont_load=False):
        if not dont_load:
            self._load_if_not_yet()
        if len(self.lst) > 0:
            mutations = {}
            mcgroups = set()
            timestamp = None
            for obj in self.lst:
                if obj.dirty:
                    if timestamp is None:
                        timestamp = self.db.get_time()
                    obj.mutate(mutations, mcgroups, timestamp)
            if len(mutations) > 0:
                self.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
                if self.db.mc:
                    for mcid in mcgroups:
                        self.db.mc.incr(mcid)

    def remove(self):
        self._load_if_not_yet(True)
        if len(self.lst) > 0:
            timestamp = self.db.get_time()
            mutations = {}
            mcgroups = set()
            for obj in self.lst:
                old_index_values = obj.index_values()
#               print "deleting %s. data: %s. index_values: %s" % (obj.uuid, obj.data, old_index_values)
                for index_name, key in old_index_values.iteritems():
                    mutation = Mutation(deletion=Deletion(predicate=SlicePredicate([key[1].encode("utf-8")]), timestamp=timestamp))
                    if obj.db.storage == 0:
                        index_row = (u"%s_%s_Index_%s" % (obj.__class__.clsname, index_name, key[0])).encode("utf-8")
                        cf = "Data"
                    elif obj.db.storage == 1:
                        index_row = unicode(key[0]).encode("utf-8")
                        cf = "%s_Index_%s" % (obj.__class__.clsname, index_name)
                    elif obj.db.storage == 2:
                        index_row = (u"%s_%s_Index_%s" % (self.db.app, index_name, key[0])).encode("utf-8")
                        cf = "%s_Indexes" % obj.__class__.clsname
                    m = mutations.get(index_row)
                    if m is None:
                        mutations[index_row] = {cf: [mutation]}
                    else:
                        mcf = m.get(cf)
                        if mcf is None:
                            m[cf] = [mutation]
                        else:
                            mcf.append(mutation)
                    mcgroups.add("%s-%s/VER" % (obj.__class__.clsname, index_name))
                row_mcid = "%s-%s" % (obj.__class__.clsname, obj.uuid)
#               print "REMOVE %s" % row_id
                if obj.db.storage == 0:
                    row_id = "%s_Object_%s" % (obj.__class__.clsname, obj.uuid)
                    cf = "Data"
                elif obj.db.storage == 1:
                    row_id = obj.uuid
                    cf = "%s_Objects" % obj.__class__.clsname
                elif obj.db.storage == 2:
                    row_id = "%s_%s" % (self.db.app, obj.uuid)
                    cf = "%s_Objects" % obj.__class__.clsname
                obj.db.remove(row_id, ColumnPath(cf), timestamp, ConsistencyLevel.QUORUM)
                if obj.db.mc:
                    obj.db.mc.set(row_mcid, "tomb", cache_interval)
                obj.dirty = False
                obj.new = False
            # removing indexes
            if len(mutations):
                self.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
                if self.db.mc:
                    for mcid in mcgroups:
                        self.db.mc.incr(mcid)

    def __len__(self):
        return self.lst.__len__()

    def __getitem__(self, key):
        return self.lst.__getitem__(key)

    def __setitem__(self, key, value):
        return self.lst.__setitem__(key, value)

    def __delitem__(self, key):
        return self.lst.__delitem__(key)

    def __iter__(self):
        return self.lst.__iter__()

    def __reversed__(self):
        return self.lst.__reversed__()

    def __contains__(self, item):
        return self.lst.__contains__(item)

    def __getslice__(self, i, j):
        return self.lst.__getslice__(i, j)

    def __setslice__(self, i, j, sequence):
        return self.lst.__setslice__(i, j, sequence)

    def __delslice__(self, i, j):
        return self.lst.__delslice__(i, j)

    def append(self, item):
        self.lst.append(item)

    def data(self):
        res = []
        for d in self.lst:
            ent = d.data.copy()
            ent["uuid"] = d.uuid
            res.append(ent)
        return res

    def __str__(self):
        return self.__class__.__name__ + str(self.uuids())

    def sort(self, *args, **kwargs):
        return self.lst.sort(*args, **kwargs)

    def uuids(self):
        return [obj.uuid for obj in self.lst]
