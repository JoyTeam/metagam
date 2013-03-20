from mg.mmorpg.combats.core import CombatObject
import mg
import mg.constructor
import json
from mg.core.tools import utf2str

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
        "stored-created": [["stored"], "created"],
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
        self.db_textlog.set("rules", combat.rules)
        self.db_textlog.set("keep", 0)
        self.db_textlog.set("started", now)
        self.db_textlog.set("debug", 0)
        self.db_textlog.set("per_page", ENTRIES_PER_PAGE)
        self.db_textlog.store()
        # create debug log
        self.db_syslog = self.obj(DBCombatLog, "%s-debug" % combat.uuid, data={})
        self.db_syslog.set("rules", combat.rules)
        self.db_syslog.set("keep", 0)
        self.db_syslog.set("started", now)
        self.db_syslog.set("debug", 1)
        self.db_syslog.set("per_page", ENTRIES_PER_PAGE)
        self.db_syslog.store()
        # buffer
        self.textlog_entries = []
        self.textlog_curpage = 0
        self.textlog_dirty = False
        self.textlog_total_entries = 0
        self.textlog_total_size = 256
        self.syslog_entries = []
        self.syslog_curpage = 0
        self.syslog_dirty = False
        self.syslog_total_entries = 0
        self.syslog_total_size = 256

    def syslog(self, entry):
        self.syslog_entries.append(entry)
        self.syslog_dirty = True
        self.syslog_total_entries += 1
        self.syslog_total_size += len(json.dumps(entry)) + 8
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
        self.db_syslog.set("entries", self.syslog_total_entries)
        self.db_syslog.set("size", self.syslog_total_size)
        self.db_syslog.store()
        self.syslog_dirty = False

    def textlog(self, entry):
        self.textlog_entries.append(entry)
        self.textlog_dirty = True
        self.textlog_total_entries += 1
        self.textlog_total_size += len(json.dumps(entry)) + 8
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
        self.db_textlog.set("entries", self.textlog_total_entries)
        self.db_textlog.set("size", self.textlog_total_size)
        self.db_textlog.store()
        self.textlog_dirty = False

    def flush(self):
        self.syslog_flush()
        self.textlog_flush()

    def set_title(self, title):
        self.db_syslog.set("title", title)
        self.db_textlog.set("title", title)

class CombatLogViewer(mg.constructor.ConstructorModule):
    def __init__(self, app, tp, uuid, fqn="mg.mmorpg.combats.logs.CombatLogViewer"):
        mg.constructor.ConstructorModule.__init__(self, app, fqn)
        self.tp = tp
        self.uuid = uuid
        self.log = self.obj(DBCombatLog, "%s-%s" % (uuid, tp), silent=True)

    @property
    def valid(self):
        return self.log.get("started") is not None

    @property
    def rules(self):
        return self.log.get("rules")

    @property
    def title(self):
        return self.log.get("title")

    @property
    def started(self):
        return self.log.get("started")

    @property
    def keep(self):
        return self.log.get("keep")

    @property
    def pages(self):
        return self.log.get("pages")

    @property
    def size(self):
        return self.log.get("size")

    def __len__(self):
        return self.log.get("entries")

    @property
    def per_page(self):
        return self.log.get("per_page")

    def entries(self, start, stop):
        "Start included, stop not included"
        per_page = self.per_page
        start_page = start / per_page
        stop_page = (stop - 1) / per_page + 1
        for pageno in xrange(start_page, stop_page):
            try:
                page = self.obj(DBCombatLogPage, "%s-%s" % (self.log.uuid, pageno))
            except mg.ObjectNotFoundException:
                self.warning(self.__("Page %{page}d of log %{log}s is not available").format(page=pageno, log=self.log.uuid))
            else:
                page_entries = page.get("entries") or []
                start_index = start - pageno * per_page
                stop_index = stop - pageno * per_page
                if start_index < 0:
                    start_index = 0
                if stop_index >= len(page_entries):
                    stop_index = len(page_entries)
                for ent in xrange(start_index, stop_index):
                    yield page_entries[ent]
