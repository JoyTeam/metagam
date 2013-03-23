import mg
import mg.constructor
from mg.mmorpg.combats.core import *
from mg.mmorpg.combats.turn_order import *
from mg.mmorpg.combats.ai import AIController
from mg.mmorpg.combats.logs import CombatDatabaseLog
from mg.core.cluster import DBCluster, HTTPConnectionRefused
from concurrence import Tasklet, http
from concurrence.http import HTTPError
import re
import json
import os
from uuid import uuid4

re_valid_uuid = re.compile('^[a-f0-9]{32}$')
re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)

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
        self.rhook("cmb-combat.state", self.combat_state, priv="public")
        self.rhook("cmb-combat.action", self.combat_action, priv="public")

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
            "title": self.combat.title,
            "stage": self.combat.stage,
        })

    @property
    def controller(self):
        req = self.req()
        char_id = req.param("char")
        if not char_id:
            self.call("web.forbidden");
        tag = "character-%s" % char_id
        for controller in self.combat.controllers:
            if tag in controller.tags:
                return controller
        self.call("web.forbidden")

    def combat_state(self):
        req = self.req()
        self.controller.request_state(req.param("marker"))
        self.call("web.response_json", {"ok": 1})

    def combat_action(self):
        req = self.req()
        data = json.loads(req.param("data"))
        code = data.get("action")
        if (type(code) != str and type(code) != unicode) or not re_valid_identifier.match(code):
            self.call("web.response_json", {"error": self._("Invalid combat action")})
        # check action availability
        act = None
        for a in self.combat.actionsinfo:
            if a["code"] == code:
                act = a
                break
        if act is None:
            self.call("web.response_json", {"error": self._("Non-existent combat action")})
        if not self.controller.member.action_available(act):
            self.call("web.response_json", {"error": self._("This action is not available")})
        action = CombatAction(self.combat)
        action.set_code(code)
        # check targets
        if act["targets"] == "none":
            pass
        elif act["targets"] == "myself":
            action.add_target(self.controller.member)
        else:
            target_cnt = 0
            if type(data.get("targets")) == list:
                for targetId in data.get("targets"):
                    if type(targetId) != int:
                        self.call("web.response_json", {"error": self._("Invalid target identifier")})
                    member = self.combat.member(targetId)
                    if not member:
                        self.call("web.response_json", {"error": self._("Target with given id not found")})
                    if not self.controller.member.target_available(act, member):
                        self.call("web.response_json", {"error": self._("Target '%s' is not available for this action") % member.name})
                    action.add_target(member)
                    target_cnt += 1
            targets_min = self.controller.member.targets_min(act)
            if target_cnt < targets_min:
                self.call("web.response_json", {"error": self._("Minimal number of targets is %d") % targets_min})
            targets_max = self.controller.member.targets_max(act)
            if target_cnt > targets_max:
                self.call("web.response_json", {"error": self._("Maximal number of targets is %d") % targets_max})
        # check attributes
        for attr in act.get("attributes", []):
            val = data.get(attr["code"])
            print attr["code"], "=", val
            if attr["type"] == "static":
                found = False
                for v in attr["values"]:
                    if v["code"] == val:
                        found = True
                        break
                if not found:
                    self.call("web.response_json", {"error": self._("Invalid value: %s") % attr["name"]})
                action.set_attribute(attr["code"], val)
            elif attr["type"] == "int":
                action.set_attribute(attr["code"], intz(val))
        self.controller.member.enqueue_action(action)
        self.call("web.response_json", {"ok": 1})

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

    def set_title(self, title):
        self.cobj.set("title", title)

    def set_flags(self, flags):
        self.cobj.set("flags", flags)

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
        log = CombatDatabaseLog(combat)
        combat.set_log(log)
        CombatObject.__init__(self, combat, fqn, weak=False)
        combat.set_title(cobj.get("title", self._("Combat")))
        if cobj.get("flags"):
            combat.set_flags(cobj.get("flags"))

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
                    aitype = minfo.get("ai")
                    if not aitype:
                        raise CombatRunError(self._("AI type not specified for combat member '%s'") % mtype)
                    ctl = AIController(member, aitype)
                elif control == "web":
                    char = minfo.get("control_char") or member.param("char")
                    if not char:
                        raise CombatRunError(self._("Controlling character not specified for combat member '%s' with web controller") % mtype)
                    ctl = WebController(member, char)
                else:
                    raise CombatRunError(self._("Invalid controller type: %s") % control)
                member.add_controller(ctl)
            # properties
            if "name" in minfo:
                member.set_name(minfo["name"])
            if "sex" in minfo:
                member.set_sex(minfo["sex"])
            # override parameters
            if "params" in minfo:
                for key, val in minfo["params"].iteritems():
                    member.set_param(key, val)
            # join
            self.combat.join(member)

    def run_combat(self):
        turn_order = CombatRoundRobinTurnOrder(self.combat)
        turn_order.timeout = self.combat.rulesinfo.get("turn_timeout", 30)
        self.combat.run(turn_order)

    def run(self):
        self.app().inst.csrv = self
        try:
            self.add_members()
            self.run_combat()
            # external interface
            self.serve_any_port()
            if self.addr and self.addr[0] and self.addr[1]:
                self.debug("Combat %s listening at %s:%s", self.combat_id, self.addr[0], self.addr[1])
            self.cobj.set("host", self.addr[0])
            self.cobj.set("port", self.addr[1])
            self.cobj.store()
            # main loop
            while not self.combat.stopped():
                self.combat.process()
            self.combat.notify_stopped()
            # free members
            locker = CombatLocker(self.app(), self.cobj)
            locker.unset_busy()
            self.cobj.remove()
        except CombatRunError as e:
            self.call("exception.report", e)
            self.call("combats.debug", self.combat, e.val, cls="combat-error")
        finally:
            self.combat.close()
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
            #self.debug("Remote combat API URI: %s:%s", self.api_host, self.api_port)
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
            except HTTPError:
                raise CombatUnavailable(self._("Port reused by another service"))
            except HTTPConnectionRefused:
                raise CombatUnavailable(self._("Connection refused"))
        except CombatUnavailable as e:
            self.cancel_combat(e)
            raise

    def ping(self):
        return self.query("/combat/ping")
    
    @property
    def rules(self):
        return self.cobj.get("rules")

    @property
    def cinfo(self):
        try:
            return self._cinfo
        except AttributeError:
            pass
        self._cinfo = self.query("/combat/info")
        return self._cinfo

    @property
    def state(self):
        try:
            return self._state
        except AttributeError:
            pass
        self._state = self.query("/combat/state")
        return self._state

    def state_for_interface(self, char, marker):
        return self.query("/combat/state", {"char": char.uuid, "marker": marker})

    def action(self, char, data):
        return self.query("/combat/action", {"char": char.uuid, "data": json.dumps(data)})

class WebController(CombatMemberController):
    def __init__(self, member, char, fqn="mg.mmorpg.combats.daemons.WebController"):
        CombatMemberController.__init__(self, member, fqn)
        self.char = char
        self.tags.add("character-%s" % char.uuid)
        self.outbound = []

    def send(self, method, **kwargs):
        kwargs["method_cls"] = "combat"
        kwargs["method"] = method
        kwargs["combat"] = self.combat.uuid
        self.outbound.append(kwargs)

    def flush(self):
        if self.outbound:
            outbound = self.outbound
            self.outbound = []
            self.call("stream.character-list", self.char, outbound)

    def deliver_marker(self, marker):
        self.outbound = []
        self.char.invalidate_sessions()
        self.send("state_marker", marker=marker)

    def deliver_combat_params(self, params):
        self.send("combat_params", params=params)

    def deliver_member_joined(self, member):
        self.send("member_joined", member=member.id)

    def deliver_member_params(self, member, params):
        self.send("member_params", member=member.id, params=params)

    def deliver_myself(self):
        self.send("myself", member=self.member.id)

    def deliver_action(self, action):
        act = {
            "code": action.get("code"),
            "name": action.get("name"),
            "attributes": action.get("attributes", []),
        }
        self.send("action", action=act)

    def deliver_available_actions(self, actions):
        self.send("available_actions", actions=actions)

    def deliver_turn_got(self):
        self.send("turn_got")

    def deliver_turn_lost(self):
        self.send("turn_lost")

    def deliver_turn_timeout(self):
        self.send("turn_timeout")

    def deliver_log(self, entries):
        self.send("log", entries=entries)
