from mg.mmorpg.combats.core import CombatObject
import mg

ENTRIES_PER_PAGE = 100

class DBCombatLog(mg.CassandraObject):
    clsname = "CombatLog"
    indexes = {
        "keep-started": [["keep"], "started"],
    }

class DBCombatLogList(mg.CassandraObjectList):
    objcls = DBCombatLog

class DBCombatLogPage(mg.CassandraObject):
    clsname = "CombatLogPage"

class DBCombatLogStat(mg.CassandraObject):
    clsname = "CombatLogStat"
    indexes = {
        "created": [[], "created"],
    }

class DBCombatLogStatList(mg.CassandraObjectList):
    objcls = DBCombatLogStat

class CombatLog(CombatObject):
    "CombatLog logs combat actions"
    def __init__(self, combat, fqn="mg.mmorpg.combats.logs.CombatLog"):
        CombatObject.__init__(self, combat, fqn)

    def syslog(self, entry):
        "Record entry to the machine readable log"

    def textlog(self, entry):
        "Record entry to the user readable log"

    def flush(self):
        "Flush buffers to the storage"

class CombatDatabaseLog(CombatLog):
    def __init__(self, combat, fqn="mg.mmorpg.combats.logs.CombatDatabaseLog"):
        CombatLog.__init__(self, combat, fqn)
        now = self.now()
        # create user log
        self.db_textlog = self.obj(DBCombatLog, "%s-user" % combat.uuid, data={})
        self.db_textlog.set("keep", 0)
        self.db_textlog.set("started", now)
        self.db_textlog.set("pages", 0)
        self.db_textlog.set("debug", 0)
        self.db_textlog.set("size", 256)
        self.db_textlog.store()
        # create debug log
        self.db_syslog = self.obj(DBCombatLog, "%s-debug" % combat.uuid, data={})
        self.db_syslog.set("keep", 0)
        self.db_syslog.set("started", now)
        self.db_syslog.set("pages", 0)
        self.db_syslog.set("debug", 1)
        self.db_syslog.set("size", 256)
        self.db_syslog.store()
        # buffer
        self.textlog_entries = []
        self.textlog_curpage = 0
        self.textlog_dirty = False
        self.syslog_entries = []
        self.syslog_curpage = 0
        self.syslog_dirty = False

    def syslog(self, entry):
        self.syslog_entries.append(entry)
        self.syslog_dirty = True
        if len(self.syslog_entries) >= ENTRIES_PER_PAGE:
            self.syslog_flush()
            self.syslog_curpage += 1
            self.syslog_entries = []

    def syslog_flush(self):
        if not self.syslog_dirty:
            return
        page = self.obj(DBCombatLogPage, "%s-%s" % (self.db_syslog.uuid, self.syslog_curpage), data={})
        page.set("entries", self.syslog_entries)
        page.store()
        self.db_syslog.set("pages", self.syslog_curpage + 1)
        self.db_syslog.store()
        self.syslog_dirty = False

    def textlog(self, entry):
        self.textlog_entries.append(entry)
        self.textlog_dirty = True
        if len(self.textlog_entries) >= ENTRIES_PER_PAGE:
            self.textlog_flush()
            self.textlog_curpage += 1
            self.textlog_entries = []

    def textlog_flush(self):
        if not self.textlog_dirty:
            return
        page = self.obj(DBCombatLogPage, "%s-%s" % (self.db_textlog.uuid, self.textlog_curpage), data={})
        page.set("entries", self.textlog_entries)
        page.store()
        self.db_textlog.set("pages", self.textlog_curpage + 1)
        self.db_textlog.store()
        self.textlog_dirty = False

    def flush(self):
        self.syslog_flush()
        self.textlog_flush()
