from concurrence.http import HTTPConnection, HTTPRequest
import json
import re
import mg.core
from mg.core.tools import *
from concurrence.thr import Socket
from thrift.transport import TTransport
from cassandra.Cassandra import Client
from cassandra.ttypes import *
from uuid import uuid4
import socket
import logging
import time
import random
import stackless
import concurrence

cache_interval = 3600
max_index_length = 10000000

class CassandraError(Exception):
    "This exception can be raised during database queries"
    pass

class JSONError(CassandraError):
    "JSON or UTF-8 decoding error"
    pass

class ObjectNotFoundException(Exception):
    "CassandraObject not found"
    pass

class Cassandra(object):
    """
    Wrapper around CassandraConnection class. It puts CassandraConnection
    back to the pool on destruction
    """
    def __init__(self, pool, keyspace, mc):
        self.pool = pool
        self.keyspace = keyspace
        self.mc = mc
        self._last_time = 0
        self._last_time_cnt = 0

    def apply_keyspace(self, conn):
        if self.keyspace != conn.actual_keyspace:
            conn.set_keyspace(self.keyspace)

    def describe_keyspaces(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            res = conn.cass.describe_keyspaces(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def describe_keyspace(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            res = conn.cass.describe_keyspace(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def system_add_keyspace(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            res = conn.cass.system_add_keyspace(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def system_drop_keyspace(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            conn.set_keyspace("system")
            res = conn.cass.system_drop_keyspace(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def system_add_column_family(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.system_add_column_family(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()

    def system_drop_column_family(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.system_drop_column_family(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def insert(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.insert(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def get_slice(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.get_slice(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def multiget_slice(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.multiget_slice(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def batch_mutate(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.batch_mutate(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def insert(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.insert(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def remove(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.remove(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def get(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.get(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def get_count(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.get_count(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def get_range_slices(self, *args, **kwargs):
        conn = self.pool.cget()
        try:
            self.apply_keyspace(conn)
            res = conn.cass.get_range_slices(*args, **kwargs)
            self.pool.cput(conn)
            return res
        except:
            self.pool.new()
            raise

    def get_time(self):
        now = time.time() * 1000
        if self._last_time == now:
            self._last_time_cnt += 1
        else:
            self._last_time = now
            self._last_time_cnt = 0
        return now + self._last_time_cnt

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

    def dbget(self, keyspace, mc):
        "The same as cget, but returns Cassandra wrapper"
        return Cassandra(self, keyspace, mc)

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
    def __init__(self, db, uuid=None, data=None, dbprefix="", clsprefix="", silent=False):
        """
        db - Cassandra Object
        uuid - ID of object (None if newly created)
        data - preloaded object data (None is not loaded)
        """
        self.db = db
        self.dbprefix = dbprefix
        self.clsprefix = clsprefix
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

    def indexes(self):
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
        return {}

    def index_values(self):
        if self._indexes is None:
            self.calculate_indexes()
        return self._indexes

    def calculate_indexes(self):
        _indexes = {}
        for index_name, index in self.indexes().iteritems():
            values = []
            abort = False
            for field in index[0]:
                val = self.data.get(field)
                if val is None:
                    abort = True
                    break;
                values.append(val)
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
                    row_suffix = ""
                    for val in values:
                        row_suffix = "%s-%s" % (row_suffix, val)
                    _indexes[index_name] = [row_suffix, col]
        self._indexes = _indexes

    def load(self):
        """
        Load object from the database
        Raises ObjectNotFoundException
        """
        self._indexes = None
        row_mcid = self.clsprefix + self.uuid
        row_id = self.dbprefix + row_mcid
        self.data = self.db.mc.get(row_mcid)
        if self.data == "tomb":
#            print "LOAD(MC) %s %s" % (row_id, self.data)
            raise ObjectNotFoundException(row_id)
        elif self.data is None:
            try:
                col = self.db.get(row_id, ColumnPath("Objects", column="data"), ConsistencyLevel.QUORUM).column
            except NotFoundException:
                raise ObjectNotFoundException(row_id)
            self.data = json.loads(col.value)
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
        for index_name, columns in self.indexes().iteritems():
            key = index_values.get(index_name)
            old_key = old_index_values.get(index_name)
            if old_key != key:
                mcgroups.add("%s%s/VER" % (self.clsprefix, index_name))
                #print "\t\t%s: %s => %s" % (index_name, old_key, key)
                # deleting old index entry if exists
                if old_key is not None:
                    mutation = Mutation(deletion=Deletion(predicate=SlicePredicate([old_key[1].encode("utf-8")]), timestamp=timestamp))
                    index_row = (self.dbprefix + self.clsprefix + index_name + old_key[0]).encode("utf-8")
                    #print "delete: row=%s, column=%s" % (index_row, old_key[1].encode("utf-8"))
                    exists = mutations.get(index_row)
                    if exists:
                        exists["Objects"].append(mutation)
                    else:
                        mutations[index_row] = {"Objects": [mutation]}
                # creating new index entry if needed
                if key is not None:
                    mutation = Mutation(ColumnOrSuperColumn(Column(name=key[1].encode("utf-8"), value=self.uuid, timestamp=timestamp)))
                    index_row = (self.dbprefix + self.clsprefix + index_name + key[0]).encode("utf-8")
                    #print [ index_row, key[1] ]
                    #print "insert: row=%s, column=%s" % (index_row, key[1].encode("utf-8"))
                    exists = mutations.get(index_row)
                    if exists:
                        exists["Objects"].append(mutation)
                    else:
                        mutations[index_row] = {"Objects": [mutation]}
        # mutation of the object itself
        row_mcid = self.clsprefix + self.uuid
        row_id = self.dbprefix + row_mcid
        mutations[row_id] = {"Objects": [Mutation(ColumnOrSuperColumn(Column(name="data", value=json.dumps(self.data).encode("utf-8"), timestamp=timestamp)))]}
        logging.getLogger("mg.core.cass.CassandraObject").debug("STORE %s %s", row_id, self.data)
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
            for mcid in mcgroups:
                self.db.mc.incr(mcid)

    def remove(self):
        """
        Remove object from the database
        """
        #print "removing %s" % self.uuid
        timestamp = self.db.get_time()
        row_mcid = self.clsprefix + self.uuid
        row_id = self.dbprefix + row_mcid
        self.db.remove(row_id, ColumnPath("Objects"), timestamp, ConsistencyLevel.QUORUM)
        self.db.mc.set(row_mcid, "tomb", cache_interval)
        # removing indexes
        mutations = {}
        mcgroups = set()
        old_index_values = self.index_values()
        for index_name, key in old_index_values.iteritems():
            index_row = (self.dbprefix + self.clsprefix + index_name + key[0]).encode("utf-8")
            mutations[index_row] = {"Objects": [Mutation(deletion=Deletion(predicate=SlicePredicate([key[1].encode("utf-8")]), timestamp=timestamp))]}
            mcgroups.add("%s%s/VER" % (self.clsprefix, index_name))
            #print "delete: row=%s, column=%s" % (index_row, key[1].encode("utf-8"))
#       print "REMOVE %s" % row_id
        if len(mutations):
            self.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
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
    def __init__(self, db, uuids=None, dbprefix="", clsprefix="", cls=CassandraObject, query_index=None, query_equal=None, query_start="", query_finish="", query_limit=1000000, query_reversed=False):
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
        if uuids is not None:
            self.dict = [cls(db, uuid, {}, dbprefix=dbprefix, clsprefix=clsprefix) for uuid in uuids]
        elif query_index is not None:
            self.index_prefix_len = len(dbprefix) + len(clsprefix) + len(query_index) + 1
            grpmcid = "%s%s/VER" % (clsprefix, query_index)
            grpid = self.db.mc.get(grpmcid)
            if grpid is None:
                grpid = random.randint(0, 2000000000)
                self.db.mc.set(grpmcid, grpid)
            if type(query_equal) == list:
                # multiple keys
                mcids = []
                index_rows = []
                self.index_data = []
                for val in query_equal:
                    mcid = urlencode("%s%s-%s/%s/%s/%s/%s/%s" % (clsprefix, query_index, val, query_start, query_finish, query_limit, query_reversed, grpid))
                    mcids.append(mcid)
                    index_row = "%s%s%s-%s" % (dbprefix, clsprefix, query_index, val)
                    if type(index_row) == unicode:
                        index_row = index_row.encode("utf-8")
                    index_rows.append(index_row)
#               print "loading mcids %s" % mcids
                d = self.db.mc.get_multi(mcids)
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
                    d = self.db.multiget_slice(remain_index_rows, ColumnParent(column_family="Objects"), SlicePredicate(slice_range=SliceRange(start=query_start, finish=query_finish, reversed=query_reversed, count=query_limit)), ConsistencyLevel.QUORUM)
#                   print d
                    for index_row, index_data in d.iteritems():
                        self.index_rows[index_row] = [col.column.value for col in index_data]
                        index_data = [[col.column.name, col.column.value] for col in index_data]
                        self.index_data.extend(index_data)
                        mcid = urlencode("%s/%s/%s/%s/%s/%s" % (index_row[len(dbprefix):], query_start, query_finish, query_limit, query_reversed, grpid))
                        #logging.getLogger("mg.core.cass.CassandraObject").debug("storing mcid %s = %s", mcid, index_data)
                        if len(index_data) < max_index_length:
                            self.db.mc.set(mcid, index_data)
                        else:
                            self.db.mc.delete(mcid)
                self.index_data.sort(cmp=lambda x, y: cmp(x[0], y[0]), reverse=query_reversed)
                self.dict = [cls(db, col[1], {}, dbprefix=dbprefix, clsprefix=clsprefix) for col in self.index_data]
                #print "loaded index data %s" % self.index_data
            else:
                # single key
                mcid = urlencode("%s%s-%s/%s/%s/%s/%s/%s" % (clsprefix, query_index, query_equal, query_start, query_finish, query_limit, query_reversed, grpid))
                index_row = dbprefix + clsprefix + query_index
                if query_equal is not None:
                    index_row = index_row + "-" + query_equal
                if type(index_row) == unicode:
                    index_row = index_row.encode("utf-8")
#               print "loading mcid %s" % mcid
                d = self.db.mc.get(mcid)
                if d is not None:
                    self.index_rows[index_row] = [ent[1] for ent in d]
                    self.index_data = d
                else:
#                   print "loading index row %s" % index_row
                    d = self.db.get_slice(index_row, ColumnParent(column_family="Objects"), SlicePredicate(slice_range=SliceRange(start=query_start, finish=query_finish, reversed=query_reversed, count=query_limit)), ConsistencyLevel.QUORUM)
                    self.index_rows[index_row] = [col.column.value for col in d]
                    self.index_data = [[col.column.name, col.column.value] for col in d]
                    #logging.getLogger("mg.core.cass.CassandraObject").debug("storing mcid %s = %s", mcid, self.index_data)
                    if len(self.index_data) < max_index_length:
                        self.db.mc.set(mcid, self.index_data)
                    else:
                        self.db.mc.delete(mcid)
#               print "loaded index data " % self.index_data
                self.dict = [cls(db, col[1], {}, dbprefix=dbprefix, clsprefix=clsprefix) for col in self.index_data]
        else:
            raise RuntimeError("Invalid usage of CassandraObjectList")
        for obj in self.dict:
            obj._indexes = None

    def index_values(self, strip_prefix_len=0):
        strip_prefix_len += self.index_prefix_len
        res = []
        for key, values in self.index_rows.iteritems():
            stripped_key = key[strip_prefix_len:]
            for val in values:
                res.append((stripped_key, val))
        return res

    def load(self, silent=False):
        if len(self.dict) > 0:
            row_mcids = [(obj.clsprefix + obj.uuid) for obj in self.dict]
            mc_d = self.db.mc.get_multi(row_mcids)
            row_ids = [obj.dbprefix + mcid for mcid in row_mcids if mcid not in mc_d]
            db_d = self.db.multiget_slice(row_ids, ColumnParent(column_family="Objects"), SlicePredicate(column_names=["data"]), ConsistencyLevel.QUORUM) if len(row_ids) else {}
            recovered = False
            for obj in self.dict:
                obj.valid = True
                row_mcid = obj.clsprefix + obj.uuid
                row_id = obj.dbprefix + row_mcid
                data = mc_d.get(row_mcid)
                if data is not None:
#                   print "LOAD(MC) %s %s" % (obj.uuid, data)
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
                                        self.db.mc.incr("%s%s/VER" % (obj.clsprefix, self.query_index))
                                        break
                                if len(mutations):
                                    self.db.batch_mutate(dict([(index_row, {"Objects": mutations}) for index_row, values in self.index_rows.iteritems()]), ConsistencyLevel.QUORUM)
                        else:
                            raise ObjectNotFoundException("UUID %s (dbprefix %s, clsprefix %s) not found" % (obj.uuid, obj.dbprefix, obj.clsprefix))
                    else:
                        obj.data = data
                        obj.dirty = False
                else:
                    cols = db_d[row_id]
                    if len(cols) > 0:
                        obj.data = json.loads(cols[0].column.value)
                        obj.dirty = False
                        self.db.mc.add(row_mcid, obj.data, cache_interval)
#                        print "LOAD(DB) %s %s" % (obj.uuid, obj.data)
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
                                    self.db.mc.incr("%s%s/VER" % (obj.clsprefix, self.query_index))
                                    break
                            if len(mutations):
                                self.db.batch_mutate(dict([(index_row, {"Objects": mutations}) for index_row, values in self.index_rows.iteritems()]), ConsistencyLevel.QUORUM)
                    else:
                        raise ObjectNotFoundException("UUID %s (dbprefix %s, clsprefix %s) not found" % (obj.uuid, obj.dbprefix, obj.clsprefix))
            if recovered:
                self.dict = [obj for obj in self.dict if obj.valid]
        self._loaded = True

    def _load_if_not_yet(self, silent=False):
        if not self._loaded:
            self.load(silent);

    def store(self, dont_load=False):
        if not dont_load:
            self._load_if_not_yet()
        if len(self.dict) > 0:
            mutations = {}
            mcgroups = set()
            timestamp = None
            for obj in self.dict:
                if obj.dirty:
                    if timestamp is None:
                        timestamp = self.db.get_time()
                    obj.mutate(mutations, mcgroups, timestamp)
            if len(mutations) > 0:
                self.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
                for mcid in mcgroups:
                    self.db.mc.incr(mcid)

    def remove(self):
        self._load_if_not_yet(True)
        if len(self.dict) > 0:
            timestamp = self.db.get_time()
            mutations = {}
            mcgroups = set()
            for obj in self.dict:
                old_index_values = obj.index_values()
#               print "deleting %s. data: %s. index_values: %s" % (obj.uuid, obj.data, old_index_values)
                for index_name, key in old_index_values.iteritems():
                    index_row = (obj.dbprefix + obj.clsprefix + index_name + key[0]).encode("utf-8")
                    m = mutations.get(index_row)
                    mutation = Mutation(deletion=Deletion(predicate=SlicePredicate([key[1].encode("utf-8")]), timestamp=timestamp))
                    if m is None:
                        mutations[index_row] = {"Objects": [mutation]}
                    else:
                        m["Objects"].append(mutation)
                    mcgroups.add("%s%s/VER" % (obj.clsprefix, index_name))
                row_mcid = obj.clsprefix + obj.uuid
                row_id = obj.dbprefix + row_mcid
#               print "REMOVE %s" % row_id
                obj.db.remove(row_id, ColumnPath("Objects"), timestamp, ConsistencyLevel.QUORUM)
                obj.db.mc.set(row_mcid, "tomb", cache_interval)
                obj.dirty = False
                obj.new = False
            # removing indexes
            if len(mutations):
                self.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
                for mcid in mcgroups:
                    self.db.mc.incr(mcid)

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

    def append(self, item):
        self.dict.append(item)

    def data(self):
        res = []
        for d in self.dict:
            ent = d.data.copy()
            ent["uuid"] = d.uuid
            res.append(ent)
        return res

    def __str__(self):
        return self.__class__.__name__ + str(self.uuids())

    def sort(self, *args, **kwargs):
        return self.dict.sort(*args, **kwargs)

    def uuids(self):
        return [obj.uuid for obj in self.dict]
