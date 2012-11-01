import mg
import mg.constructor
from mg.mmorpg.combats.core import CombatObject, Combat, CombatMember, CombatRunError, CombatUnavailableError
from mg.mmorpg.combats.turn_order import *
from mg.core.cluster import DBCluster
from concurrence import Tasklet, http
from concurrence.http import HTTPError
import re
import json
import os
from uuid import uuid4

re_valid_uuid = re.compile('^[a-f0-9]{32}$')

class CombatUnavailable(Exception):
    pass

class DBRunningCombat(mg.CassandraObject):
    clsname = "RunningCombat"
    indexes = {
        "all": [[], "created"],
    }

class DBRunningCombatList(mg.CassandraObjectList):
    objcls = DBRunningCombat

class CombatRunner(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("combat-run.daemon", self.run_daemon)
        self.rhook("cmb-combat.ping", self.ping, priv="public")

    def run_daemon(self, cobj):
        daemon_id = uuid4().hex
        cobj.set("started", self.now());
        cobj.set("daemonid", daemon_id)
        cobj.store()
        # Select host where to launch combat
        inst = self.app().inst
        cls = inst.cls
        daemons = self.int_app().obj(DBCluster, "daemons", silent=True)
        metagam_running = set()
        hosts = []
        for dmnid, dmninfo in daemons.data.items():
            if dmninfo.get("cls") != cls:
                continue
            for svcid, svcinfo in dmninfo.get("services", {}).iteritems():
                tp = svcinfo.get("type")
                if tp == "procman":
                    hosts.append({
                        "id": dmnid,
                        "hostid": dmninfo.get("hostid"),
                        "svcid": svcid,
                        "addr": svcinfo.get("addr"),
                        "port": svcinfo.get("port"),
                        "load": svcinfo.get("load", 0),
                    })
                elif tp == "metagam":
                    metagam_running.add(dmninfo.get("hostid"))
        hosts = [host for host in hosts if host["hostid"] in metagam_running]
        if not hosts:
            self.warning("No available hosts where to launch combat %s. Postponing launch", cobj.uuid)
            return
        hosts.sort(lambda x, y: cmp(x["load"], y["load"]))
        self.debug("Available hosts: %s", hosts)
        host = hosts[0]
        self.debug("Selected host %s to launch combat %s", host, cobj.uuid)
        val = self.call("cluster.query_server", host["addr"], host["port"], "/service/call/%s/newproc" % host["svcid"], timeout=20, params={
            "procid": "combat-%s" % daemon_id,
            "args": json.dumps([
                "%s/mg_combat" % inst.daemons_dir,
                self.app().tag,
                cobj.uuid,
                daemon_id,
                "-c",
                inst.config_filename
            ])
        })

    def ping(self):
        self.call("web.response_json", {"reply": "pong"})

class CombatRequest(mg.constructor.ConstructorModule):
    def __init__(self, app, fqn="mg.mmorpg.combats.requests.CombatRequest"):
        ConstructorModule.__init__(self, app, fqn)
        self.cobj = self.obj(DBRunningCombat, {})
        self.members = []
        self.cobj.set("members", self.members)

    def add_member(self, member):
        self.members.append(member)

    def set_rules(self, rules):
        mg.constructor.self.cobj.sent("rules", rules)

    def run(self):
        self.debug("Launching combat %s", self.cobj.uuid)
        self.call("combat-run.daemon", self.cobj)

class CombatService(CombatObject, mg.SingleApplicationWebService):
    def __init__(self, app, combat_id, daemon_id, fqn="mg.mmorpg.combats.daemon.CombatDaemon"):
        mg.SingleApplicationWebService.__init__(self, app, "combat-%s-%s" % (app.tag, combat_id), "combat", "cmb", fqn)
        self.combat_id = combat_id
        try:
            cobj = app.obj(DBRunningCombat, combat_id)
        except mg.ObjectNotFoundException:
            self.error("Combat daemon %s started (combat %s), but RunningCombat object not found", daemon_id, combat_id)
            os._exit(0)
        if cobj.get("daemonid") != daemon_id:
            self.error("Combat daemon %s started (combat %s), but RunningCombat contains another daemon id (%s)", daemon_id, combat_id, cobj.get("daemonid"))
            os._exit(0)
        self.cobj = cobj
        combat = Combat(app, cobj.get("rules", {}))
        CombatObject.__init__(self, combat, fqn, weak=False)

    def add_members(self):
        for minfo in self.cobj.get("members", []):
            # member
            mtype = minfo["type"]
            if mtype == "virtual":
                member = CombatMember(self.combat)
            else:
                makemember = getattr(mtype, "combat_member", None)
                if makemember is None:
                    raise CombatRunError(self._("This object cannot be a combat member: %s") % mtype)
                member = makemember(self.combat)
            member.set_team(minfo["team"])
            # control
            if "control" in minfo:
                control = minfo["control"]
                if control == "ai":
                    ai = AIController(member)
                    member.add_controller(ai)
                else:
                    raise CombatRunError(self._("Invalid controller type: %s") % control)
            # properties
            if "name" in minfo:
                member.set_name(minfo["name"])
            if "sex" in minfo:
                member.set_sex(minfo["sex"])
            # join
            self.combat.join(member)

    def run_combat(self):
        turn_order = CombatRoundRobinTurnOrder(self.combat)
        self.combat.run(turn_order)

    def run(self):
        self.app().inst.csrv = self
        try:
            self.add_members()
            self.run_combat()
            # external interface
            self.serve_any_port()
            self.debug("Combat %s listening at %s:%s", self.combat_id, self.addr[0], self.addr[1])
            self.cobj.set("host", self.addr[0])
            self.cobj.set("port", self.addr[1])
            self.cobj.store()
            # main loop
            while not self.combat.stage_flag("done"):
                self.combat.process()
                Tasklet.yield_()
        finally:
            self.app().inst.csrv = None

class CombatInterface(mg.constructor.ConstructorModule):
    def __init__(self, app, combat_id, fqn="mg.mmorpg.combats.daemons.CombatInterface"):
        mg.constructor.ConstructorModule.__init__(self, app, fqn)
        # access RunningCombat object
        if not re_valid_uuid.match(combat_id):
            raise CombatUnavailableError(combat_id)
        try:
            cobj = self.obj(DBRunningCombat, combat_id)
        except mg.ObjectNotFoundException:
            raise CombatUnavailableError(combat_id)
        # restart combat if needed
        attempts = 3
        while not cobj.get("host"):
            # wait for combat to run
            if cobj.get("started") > self.now(-10):
                Tasklet.sleep(1)
                try:
                    cobj.load()
                except mg.ObjectNotFoundException:
                    raise CombatUnavailableError(combat_id)
                continue
            # restart failed combat
            attempts -= 1
            if attempts < 0:
                raise CombatUnavailableError(combat_id)
            with self.lock(["CombatRun-%s" % combat_id]):
                try:
                    cobj.load()
                except mg.ObjectNotFoundException:
                    raise CombatUnavailableError(combat_id)
                if not cobj.get("host"):
                    self.debug("Relaunching combat %s", cobj.uuid)
                    self.call("combat-run.daemon", cobj)
        # combat daemon found
        self.combat_id = combat_id
        # find connection
        self.api_host = cobj.get("host")
        self.api_port = cobj.get("port")
        self.debug("Remote combat API URI: %s:%s", self.api_host, self.api_port)

    def query(self, uri, args={}):
        args["combat"] = self.combat_id
        try:
            res = self.call("cluster.query-server", self.api_host, self.api_port, "/service/call/combat-%s-%s%s" % (self.app().tag, self.combat_id, uri), args)
            if type(res) != dict:
                raise CombatUnavailable(self._("Invalid combat response: %s") % type(res).__name__)
            if type(res) != dict or res.get("combat") != self.combat_id:
                raise CombatUnavailable(self._("Invalid combat response (expected: %s, received: %s)") % (self.combat_id, res.get("combat")))
        except HTTPError as e:
            raise CombatUnavailable(e)

    def ping(self):
        return self.query("/combat/ping")
