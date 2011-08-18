from mg.core import Module
from cassandra.ttypes import *
from concurrence import Tasklet
import logging

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
        keyspaces = [ksdef.name for ksdef in self.db.describe_keyspaces()]
        family_exists = dict()
        required = set()
        if self.db.keyspace not in keyspaces:
            if "ringtest" not in keyspaces:
                self.logger.debug("created keyspace ringtest: %s", self.db.system_add_keyspace(KsDef(name="ringtest", strategy_class="org.apache.cassandra.locator.SimpleStrategy", replication_factor=1, cf_defs=[])))
                self.logger.debug("waiting 10 sec")
                Tasklet.sleep(10)
            ring = set()
            for ent in self.db.describe_ring("ringtest"):
                for ip in ent.endpoints:
                    ring.add(ip)
            replication_factor = len(ring)
            if replication_factor > 3:
                replication_factor = 3
            dbdiff.ops.append(("cks", KsDef(name=self.db.keyspace, strategy_class="org.apache.cassandra.locator.SimpleStrategy", replication_factor=replication_factor, cf_defs=[])))
        else:
            family_exists = dict([(cfdef.name, cfdef) for cfdef in self.db.describe_keyspace(self.db.keyspace).cf_defs])
        for (name, cfdef) in config.items():
            if name in family_exists:
                existing = family_exists[name]
                if cfdef.column_type != existing.column_type or "org.apache.cassandra.db.marshal." + cfdef.comparator_type != existing.comparator_type:
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
                cmd[1].keyspace = self.db.keyspace
                self.logger.debug("created column family %s: %s", cmd[1].name, self.db.system_add_column_family(cmd[1]))
            elif cmd[0] == "df":
                self.logger.debug("destroyed column family %s: %s", cmd[1], self.db.system_drop_column_family(cmd[1]))
            elif cmd[0] == "cks":
                self.logger.debug("created keyspace %s: %s", cmd[1].name, self.db.system_add_keyspace(cmd[1]))
            else:
                self.logger.error("invalid command %s", cmd)
                continue
            self.logger.debug("waiting 10 sec")
            Tasklet.sleep(10)

class CommonCassandraStruct(Module):
    def register(self):
        self.rhook("core.dbstruct", self.cassandra_struct)
        self.rhook("core.dbapply", self.cassandra_apply)

    def cassandra_struct(self, dbstruct):
        dbstruct["Objects"] = CfDef()
        dbstruct["Indexes"] = CfDef()

    def cassandra_apply(self, dbstruct):
        db = self.db()
        restruct = CassandraRestructure(db)
        diff = restruct.diff(dbstruct)
        restruct.apply(diff)

