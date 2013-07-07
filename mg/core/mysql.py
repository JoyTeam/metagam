from concurrence.database.mysql import dbapi, client
from concurrence.database.mysql.client import ClientError
from mg.core.tools import *
from concurrence import Tasklet
import concurrence
import logging
import re
import random

re_placeholder = re.compile(r'\?')
re_escape = re.compile(r'(\0|\n|\r|\\|\')')
mysql_escape_str = {
    '\0': '\\0',
    '\n': '\\n',
    '\r': '\\r',
    '\\': '\\\\',
    "'": "\\'",
}

class MySQL(object):
    """
    Wrapper around MySQLConnection class. It puts MySQLConnection
    back to the pool on destruction
    """
    def __init__(self, pool, app=None):
        self.pool = pool
        self.app = app

    def _execute(self, method_name, options, *args, **kwargs):
        while True:
            try:
                conn = self.pool.cget()
            except IOError as e:
                self.pool.error(e)
            else:
                # connection is ready here
                try:
                    method = getattr(conn, method_name)
                except AttributeError:
                    self.pool.error(e)
                    raise
                # method is ready here
                try:
                    res = method(*args, **kwargs)
                except concurrence.TimeoutError as e:
                    self.pool.error(e)
                    raise
                except dbapi.IntegrityError:
                    self.pool.error()
                    conn = self.pool.cget()
                    raise
                else:
                    self.pool.success(conn)
                    return res

    def do(self, *args, **kwargs):
        return self._execute("do", None, *args, **kwargs)

    def selectall(self, *args, **kwargs):
        return self._execute("selectall", None, *args, **kwargs)

    def selectall_dict(self, *args, **kwargs):
        return self._execute("selectall_dict", None, *args, **kwargs)

class MySQLPool(object):
    """
    Handles pool of MySQLConnection objects, allowing get and put operations.
    Connections are created on demand
    """
    def __init__(self, hosts=(("127.0.0.1", 3306),), user="", passwd="", db="", size=4, primary_host_id=0):
        self.hosts = [tuple(host) for host in hosts]
        self.primary_host = self.hosts.pop(primary_host_id)
        self.hosts.insert(0, self.primary_host)
        self.connections = []
        self.size = size
        self.allocated = 0
        self.channel = None
        self.success_counter = 0
        self.user = user
        self.passwd = passwd
        self.db = db
        self._ping_tasklet = None

    def set_servers(self, hosts, user, passwd, db, primary_host_id=0):
        self.hosts = [tuple(host) for host in hosts]
        self.primary_host = self.hosts.pop(primary_host_id)
        self.hosts.insert(0, self.primary_host)
        self.user = user
        self.passwd = passwd
        self.db = db
        self.close_all()

    def close_all(self):
        del self.connections[:]
        self.allocated = 0
        if self._ping_tasklet is not None:
            self._ping_tasklet.kill()
            self._ping_tasklet = None

    def exception(self, *args, **kwargs):
        logging.getLogger("mg.core.mysql.MySQLPool").exception(*args, **kwargs)

    def debug(self, *args, **kwargs):
        logging.getLogger("mg.core.mysql.MySQLPool").debug(*args, **kwargs)

    def new_connection(self):
        "Create a new MySQLConnection and connect to the first host in the list"
        connection = MySQLConnection(self.hosts[0], self.user, self.passwd, self.db)
        connection.connect()
        if self._ping_tasklet is None:
            self._ping_tasklet = Tasklet.new(self.ping_tasklet)
            self._ping_tasklet()
        return connection

    def new_primary_connection(self):
        "Create a new MySQLConnection and connect to the primary host"
        connection = MySQLConnection(self.primary_host)
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
            self.close_all()
            self.debug("MySQL server %s failed: %s. Trying %s", bad_host, exc, self.hosts[0])
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
                self.debug("MySQL server %s succeeded %d operations. Probing primary host %s", self.hosts[0], self.success_counter, self.primary_host)
                self.success_counter = 0
                try:
                    primary_conn = self.new_primary_connection()
                except concurrence.TimeoutError:
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
                    self.close_all()
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

        # There are no connections in the pool, and we may allocate more
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

    def dbget(self, app=None):
        "The same as cget, but returns MySQL wrapper"
        return MySQL(self, app)

    def ping(self):
        conns = []
        while len(self.connections) > 0:
            conns.append(self.cget())
        for conn in conns:
            try:
                conn.do("select 1")
            except EOFError:
                pass
            except Exception as e:
                logging.getLogger("mg.core.mysql.MySQLPool").exception(e)
            else:
                self.cput(conn)

    def ping_tasklet(self):
        while True:
            Tasklet.sleep(random.randrange(25, 30))
            self.ping()

class MySQLConnection(object):
    "MySQLConnection - interface to MySQL database engine"
    def __init__(self, host=("127.0.0.1", 3306), user="", passwd="", db=""):
        """
        host - (hostname, port)
        """
        self.host = host
        self.user = user
        self.passwd = passwd
        self.db = db
        self.dbh = None
        self.result = None

    def __del__(self):
        self.disconnect()

    def connect(self):
        "Establish connection to the cluster"
        self.dbh = dbapi.Connection(host=str(self.host[0]), port=intz(self.host[1], 3306), user=str(self.user), passwd=str(self.passwd), db=str(self.db), autocommit=True, charset="utf-8")

    def disconnect(self):
        "Disconnect from the cluster"
        try:
            if self.dbh:
                self.dbh.close()
                self.dbh = None
        except Exception as e:
            logging.exception(e)

    def _close_result(self):
        if self.result is not None and isinstance(self.result, client.ResultSet):
            try:
                while True:
                    self.result_iter.next()
            except StopIteration:
                pass
            self.result.close()
        self.result = None
        self.result_iter = None
        self.rowcount = None
        self.lastrowid = None
        self.fields = None

    def execute(self, qry, *args):
        if type(args) is tuple:
            args = list(args)
        def esc(m):
            return mysql_escape_str[m.group(1)]
        def placeholder(m):
            arg = args.pop(0)
            if arg is None:
                return "null"
            if type(arg) is int or type(arg) is float:
                return str(arg)
            if type(arg) is unicode:
                arg = arg.encode("utf-8")
            elif type(arg) != str:
                arg = str(arg)
            return "'%s'" % re_escape.sub(esc, arg)
        self._close_result()
        qry = re_placeholder.sub(placeholder, qry)
        if type(qry) == unicode:
            qry = qry.encode("utf-8")
        result = self.dbh.client.query(qry)
        self.result = result
        self.result_iter = iter(result)
        if isinstance(result, client.ResultSet):
            self.fields = [name for name, type_code in result.fields]

    def do(self, *args):
        self.execute(*args)
        if isinstance(self.result, client.ResultSet):
            cnt = 0
            for row in self.result_iter:
                cnt += 1
            self.rowcount = cnt
        else:
            self.rowcount, self.lastrowid = self.result
        return self.rowcount

    def selectall(self, *args):
        self.execute(*args)
        if isinstance(self.result, client.ResultSet):
            return list(self.result_iter)
        else:
            return []

    def selectall_dict(self, *args):
        self.execute(*args)
        fields = self.fields
        nfields = len(fields)
        result = []
        if isinstance(self.result, client.ResultSet):
            for row in self.result_iter:
                result.append(dict([(fields[i], row[i]) for i in xrange(0, nfields)]))
        return result
