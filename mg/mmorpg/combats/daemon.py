import mg
import mg.constructor
from mg.mmorpg.combats.core import CombatObject, Combat, CombatMember, CombatRunError, CombatUnavailable, CombatLocker
from mg.mmorpg.combats.turn_order import *
from mg.core.cluster import DBCluster, HTTPConnectionRefused
from concurrence import Tasklet, http
from concurrence.http import HTTPError
import re
import json
import os
from uuid import uuid4

re_valid_uuid = re.compile('^[a-f0-9]{32}$')

class DBRunningCombat(mg.CassandraObject):
    clsname = "RunningCombat"
    indexes = {
        "all": [[], "created"],
    }

class DBRunningCombatList(mg.CassandraObjectList):
    objcls = DBRunningCombat

class CombatDaemonModule(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("web.response_json", self.response_json, priority=10)
        self.rhook("cmb-combat.ping", self.combat_ping, priv="public")
        self.rhook("cmb-combat.info", self.combat_info, priv="public")

    @property
    def combat(self):
        try:
            return self._combat
        except AttributeError:
            pass
        self._combat = self.app().inst.csrv.combat
        return self._combat

    def response_json(self, data):
        data["combat"] = self.combat.uuid

    def combat_ping(self):
        self.call("web.response_json", {
            "reply": "pong"
        })

    def combat_info(self):
        self.call("web.response_json", {
            "rules": self.combat.rules,
            "stage": self.combat.stage,
        })

class CombatRunner(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("combat-run.daemon", self.run_daemon)

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

class CombatRequest(mg.constructor.ConstructorModule):
    def __init__(self, app, fqn="mg.mmorpg.combats.requests.CombatRequest"):
        mg.constructor.ConstructorModule.__init__(self, app, fqn)
        self.cobj = self.obj(DBRunningCombat, data={})
        self.uuid = self.cobj.uuid
        self.members = []
        self.cobj.set("members", self.members)

    def add_member(self, member):
        self.members.append(member)

    def set_rules(self, rules):
        self.cobj.set("rules", rules)

    def run(self):
        self.debug("Launching combat %s", self.cobj.uuid)
        self.set_busy()
        self.call("combat-run.daemon", self.cobj)

    def set_busy(self):
        locker = CombatLocker(self.app(), self.cobj)
        locker.set_busy()

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
        combat = Combat(app, cobj.uuid, cobj.get("rules", {}))
        CombatObject.__init__(self, combat, fqn, weak=False)

    def add_members(self):
        for minfo in self.cobj.get("members", []):
            # member
            obj = minfo["object"]
            mtype = obj[0]
            if mtype == "virtual":
                member = CombatMember(self.combat)
            else:
                member = self.call("combats-%s.member" % mtype, self.combat, *obj[1:])
                if member is None:
                    raise CombatRunError(self._("Could not create combat member '%s'") % mtype)
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
                Tasklet.sleep(1)
        finally:
            self.app().inst.csrv = None

class CombatInterface(mg.constructor.ConstructorModule):
    def __init__(self, app, combat_id, fqn="mg.mmorpg.combats.daemons.CombatInterface"):
        mg.constructor.ConstructorModule.__init__(self, app, fqn)
        # access RunningCombat object
        if not re_valid_uuid.match(combat_id):
            raise CombatUnavailable(self._("Invalid combat idenfifier"))
        self.combat_id = combat_id
        try:
            cobj = self.obj(DBRunningCombat, combat_id)
        except mg.ObjectNotFoundException:
            raise CombatUnavailable(self._("Combat not found"))
        self.cobj = cobj
        try:
            # restart combat if needed
            attempts = 3
            while not cobj.get("host"):
                # wait for combat to run
                if cobj.get("started") > self.now(-10):
                    Tasklet.sleep(1)
                    try:
                        cobj.load()
                    except mg.ObjectNotFoundException:
                        raise CombatUnavailable(self._("Combat disappeared"))
                    continue
                # restart failed combat
                attempts -= 1
                if attempts < 0:
                    raise CombatUnavailable(self._("Failed to start combat server"))
                with self.lock(["Combat-%s" % combat_id]):
                    try:
                        cobj.load()
                    except mg.ObjectNotFoundException:
                        raise CombatUnavailable(self._("Combat disappeared"))
                    if not cobj.get("host"):
                        self.debug("Relaunching combat %s", cobj.uuid)
                        self.call("combat-run.daemon", cobj)
            # find connection
            self.api_host = cobj.get("host")
            self.api_port = cobj.get("port")
            self.debug("Remote combat API URI: %s:%s", self.api_host, self.api_port)
        except CombatUnavailable as e:
            self.cancel_combat(e)
            raise

    def cancel_combat(self, reason):
        with self.lock(["Combat-%s" % self.combat_id]):
            try:
                self.cobj.load()
            except mg.ObjectNotFoundException:
                return
            for minfo in self.cobj.get("members", []):
                obj = minfo["object"]
                mtype = obj[0]
                if mtype == "character":
                    char = self.character(obj[1])
                    self.call("debug-channel.character", char, self._("Cancelling combat {combat} ({reason}). Freeing members").format(combat=self.combat_id, reason=reason))
            locker = CombatLocker(self.app(), self.cobj)
            locker.unset_busy()
            self.cobj.remove()

    def query(self, uri, args={}):
        args["combat"] = self.combat_id
        try:
            try:
                res = self.call("cluster.query_server", self.api_host, self.api_port, "/service/call/combat-%s-%s%s" % (self.app().tag, self.combat_id, uri), args)
                if type(res) != dict:
                    raise CombatUnavailable(self._("Invalid combat response: %s") % type(res).__name__)
                if type(res) != dict or res.get("combat") != self.combat_id:
                    raise CombatUnavailable(self._("Invalid combat response (expected: {expected}, received: {received})").format(expected=self.combat_id, received=res.get("combat")))
                return res
            except HTTPConnectionRefused:
                raise CombatUnavailable(self._("Connection refused"))
        except CombatUnavailable as e:
            self.cancel_combat(e)
            raise

    def ping(self):
        return self.query("/combat/ping")
    
    @property
    def rules(self):
        return self.cinfo["rules"]

    @property
    def cinfo(self):
        try:
            return self._cinfo
        except AttributeError:
            pass
        self._cinfo = self.query("/combat/info")
        return self._cinfo
