from mg.core.cass import CassandraPool
from cassandra.ttypes import *
from mg.core.common import *
from mg.core.tools import *
from mg.core.mysql import MySQLPool
from mg.core.memcached import MemcachedPool
from mg.core.config import DBConfigGroup
from mg.core.applications import Application, ApplicationFactory
from concurrence import Tasklet
from concurrence import dispatch as concurrence_dispatch
from concurrence.extra import Lock
import ConfigParser
import optparse
import logging
import logging.handlers
import re
import os

re_comma = re.compile('\s*,\s*')

CONFIG_FILE = "/etc/metagam/metagam.conf"

class Formatter(logging.Formatter):
    def format(self, record):
        self._fmt = utf2str(self._fmt)
        record.msg = utf2str(record.msg)
        for key, value in record.__dict__.items():
            if type(value) == unicode:
                record.__dict__[key] = value.encode("utf-8")
        record.args = tuple([utf2str(arg) for arg in record.args])
        if not record.__dict__.get("mg_formatted"):
            if record.__dict__.get("user"):
                record.msg = "user=%s %s" % (record.user, record.msg)
            if record.__dict__.get("ip"):
                record.msg = "ip=%s %s" % (record.ip, record.msg)
            if record.__dict__.get("app"):
                record.msg = "app=%s %s" % (record.app, record.msg)
            if record.__dict__.get("host"):
                record.msg = "host=%s %s" % (record.host, record.msg)
            record.mg_formatted = True
        s = logging.Formatter.format(self, record)
        if type(s) == unicode:
            s = s.encode("utf-8")
        return s

class Filter(logging.Filter):
    def filter(self, record):
        try:
            try:
                if record.args[0] == "200 OK" and record.args[1] == "/core/ping":
                    return 0
            except KeyError:
                pass
            except IndexError:
                pass
            except AttributeError:
                pass
            req = Tasklet.current().req
            record.host = req.environ.get("HTTP_X_REAL_HOST")
            record.ip = req.environ.get("HTTP_X_REAL_IP")
            app = req.app
            record.app = app.tag
            if req.__dict__.has_key("_session"):
                record.user = req.user()
        except AttributeError:
            pass
        return 1

class StderrFilter(Filter):
    def filter(self, record):
        try:
            if record.name == "WSGIServer":
                return 0
            if record.name == "mg.core.cass.CassandraObject" and record.levelname == "DEBUG":
                return 0
        except Exception:
            pass
        try:
            if record.args[0] == "200 OK" and record.args[1] == "/core/ping":
                return 0
        except Exception:
            pass
        return 1

class Instance(Loggable):
    """
    This is an executable instance. It keeps references to all major objects
    """
    def __init__(self, insttype, cls, addopt=[]):
        Loggable.__init__(self, "mg.core.processes.Instance")
        self.insttype = insttype
        self.cls = cls
        self.init_modules()
        self.init_cmdline(addopt)
        self.init_logger()

    def init_modules(self):
        self.modules = set()

    def init_cmdline(self, addopt):
        parser = optparse.OptionParser()
        parser.add_option("-c", "--config", action="store", help="Configuration file")
        for opt in addopt:
            parser.add_option(*opt[0], **opt[1])
        (options, args) = parser.parse_args()
        self.cmdline_options = options
        self.cmdline_args = args

    @property
    def config(self):
        try:
            return self._config
        except AttributeError:
            pass
        self.init_config()
        return self._config

    @property
    def instaddr(self):
        try:
            return self._instaddr
        except AttributeError:
            pass
        self.init_config()
        return self._instaddr

    def get_instid(self):
        try:
            return self._instid
        except AttributeError:
            pass
        self.init_config()
        return self._instid

    def set_instid(self, val):
        if not hasattr(self, "_instid"):
            self.init_config()
        self._instid = val

    instid = property(get_instid, set_instid)

    @property
    def config_filename(self):
        try:
            return self._config_filename
        except AttributeError:
            pass
        self.init_config()
        return self._config_filename

    def init_config(self):
        self._config = ConfigParser.RawConfigParser()
        self._config_filename = self.cmdline_options.config or CONFIG_FILE
        self._config.read(self._config_filename)
        self._instaddr = self.conf("global", "addr")
        if not self._instaddr:
            raise RuntimeError("Config key global.addr not found")
        self._instid = "%s-%s" % (self.insttype, self.conf("global", "id", self.instaddr))

    def conf(self, section, option, default=None):
        try:
            return self.config.get(section, option)
        except ConfigParser.NoSectionError:
            return default
        except ConfigParser.NoOptionError:
            return default

    def confint(self, section, option, default=None):
        try:
            return self.config.getint(section, option)
        except ConfigParser.NoSectionError:
            return default
        except ConfigParser.NoOptionError:
            return default

    def init_logger(self):
        if not getattr(logging, "mg_initialized", False):
            logging.mg_initialized = True

            modlogger = logging.getLogger("")
            modlogger.setLevel(logging.DEBUG)

            # syslog
            syslog_channel = logging.handlers.SysLogHandler(address="/dev/log")
            syslog_channel.setLevel(logging.DEBUG)
            formatter = Formatter(unicode(self.insttype + " cls=%(name)s %(message)s"))
            syslog_channel.setFormatter(formatter)
            filter = Filter()
            syslog_channel.addFilter(filter)
            modlogger.addHandler(syslog_channel)

            # stderr
            stderr_channel = logging.StreamHandler()
            stderr_channel.setLevel(logging.DEBUG)
            filter = StderrFilter()
            stderr_channel.addFilter(filter)
            formatter = Formatter(unicode("%(asctime)s " + self.insttype + " cls=%(name)s %(message)s"))
            stderr_channel.setFormatter(formatter)
            modlogger.addHandler(stderr_channel)

    @property
    def dbpool(self):
        try:
            return self._dbpool
        except AttributeError:
            pass
        self.init_cassandra()
        return self._dbpool

    @property
    def sys_conn(self):
        try:
            return self._sys_conn
        except AttributeError:
            pass
        self.init_cassandra()
        return self._sys_conn

    def init_cassandra(self):
        if not hasattr(self, "_dbpool"):
            cass_hosts = []
            for host in re_comma.split(self.conf("global", "cassandra", "127.0.0.1").strip()):
                cass_hosts.append((host, 9160))
            self.debug("Cassandra seed hosts: %s", cass_hosts)
            self._dbpool = CassandraPool(cass_hosts, primary_host_id=0)
        # get actual database cluster configuration from the database itself
        self._sys_conn = self._dbpool.sys_connection()
        cass_hosts = []
        for ent in self._sys_conn.cass.describe_ring("main"):
            for ip in ent.endpoints:
                cass_hosts.append((ip, 9160))
        self.debug("Cassandra hosts: %s", cass_hosts)
        self._dbpool.set_host(cass_hosts, primary_host_id=self.conf("global", "cassandra_primary_host_id", 0) % len(cass_hosts))

    def close_cassandra(self):
        if hasattr(self, "_dbpool"):
            delattr(self, "_dbpool")
            delattr(self, "_sys_conn")

    @property
    def dbconfig(self):
        try:
            return self._dbconfig
        except AttributeError:
            pass
        db = self.dbpool.dbget("int", mc=None, storage=1)
        self._dbconfig = DBConfigGroup(db, uuid="sysconfig", silent=True)
        return self._dbconfig

    @property
    def mcpool(self):
        try:
            return self._mcpool
        except AttributeError:
            pass
        mc_hosts = self.dbconfig.get("memcached", ["127.0.0.1"])
        mc_hosts = [(host, 11211) for host in mc_hosts]
        self.debug("Memcached hosts: %s", mc_hosts)
        if hasattr(self, "_mcpool"):
            self._mcpool.set_host(mc_hosts[0])
        else:
            self._mcpool = MemcachedPool(mc_hosts[0])
        return self._mcpool

    def close_memcached(self):
        if hasattr(self, "_mcpool"):
            delattr(self, "_mcpool")

    @property
    def sql_read(self):
        try:
            return self._sql_read
        except AttributeError:
            pass
        self.init_mysql()
        return self._sql_read

    @property
    def sql_write(self):
        try:
            return self._sql_write
        except AttributeError:
            pass
        self.init_mysql()
        return self._sql_write

    def init_mysql(self):
        # read hosts
        sql_read_hosts = self.dbconfig.get("mysql_read_server", ["127.0.0.1"])
        sql_read_hosts = [(host, 3306) for host in sql_read_hosts]
        self.debug("MySQL read hosts: %s", sql_read_hosts)
        # write hosts
        sql_write_hosts = self.dbconfig.get("mysql_write_server", ["127.0.0.1"])
        sql_write_hosts = [(host, 3306) for host in sql_write_hosts]
        self.debug("MySQL write hosts: %s", sql_write_hosts)
        # credentials
        user = self.dbconfig.get("mysql_user", "metagam")
        password = self.dbconfig.get("mysql_password")
        database = self.dbconfig.get("mysql_database", "metagam")
        self.debug("MySQL database: %s", database)
        self.debug("MySQL user: %s", user)
        # connect
        primary_host_id = self.conf("global", "mysql_primary_host_id", 0) % len(sql_read_hosts)
        if hasattr(self, "_sql_read"):
            self._sql_read.set_servers(sql_read_hosts, user, password, database, primary_host_id)
        else:
            self._sql_read = MySQLPool(sql_read_hosts, user, password, database, primary_host_id=primary_host_id)
        primary_host_id = self.conf("global", "mysql_primary_host_id", 0) % len(sql_write_hosts)
        if hasattr(self, "_sql_write"):
            self._sql_write.set_servers(sql_write_hosts, user, password, database, primary_host_id)
        else:
            self._sql_write = MySQLPool(sql_write_hosts, user, password, database, primary_host_id=primary_host_id)

    def close_mysql(self):
        if hasattr(self, "_sql_read"):
            self._sql_read.close_all()
            self._sql_write.close_all()
            delattr(self, "_sql_read")
            delattr(self, "_sql_write")

    @property
    def appfactory(self):
        try:
            return self._appfactory
        except AttributeError:
            pass
        self.init_appfactory()
        return self._appfactory

    def init_appfactory(self):
        self._appfactory = ApplicationFactory(self)

    def close_appfactory(self):
        if hasattr(self, "_appfactory"):
            delattr(self, "_appfactory")

    @property
    def int_app(self):
        try:
            return self._int_app
        except AttributeError:
            pass
        self._int_app = Application(self, "int", storage=1)
        self.appfactory.add(self.int_app)
        return self._int_app

    def close_app(self):
        if hasattr(self, "_int_app"):
            delattr(self, "_int_app")

    def close_all(self):
        self.close_app();
        self.close_appfactory()
        self.close_mysql()
        self.close_memcached()
        self.close_cassandra()

def dispatch(main):
    def _dispatch():
        try:
            main()
        except RuntimeError as e:
            logging.error(e)
        except Exception as e:
            logging.exception(e)
        finally:
            os._exit(0)
    concurrence_dispatch(_dispatch)
