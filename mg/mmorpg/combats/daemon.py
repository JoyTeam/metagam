from mg.constructor import *
from mg.mmorpg.combats.core import CombatObject, Combat, CombatMember, CombatRunError
from mg.mmorpg.combats.turn_order import *
from concurrence import Tasklet, http
import re
import json

re_valid_uuid = re.compile('^[a-f0-9]{32}$')

class CombatUnavailable(Exception):
    pass

class DBRunningCombat(CassandraObject):
    clsname = "RunningCombat"
    indexes = {
        "all": [[], "created"],
    }

class DBRunningCombatList(CassandraObjectList):
    objcls = DBRunningCombat

class CombatRequest(ConstructorModule):
    def __init__(self, app, fqn="mg.mmorpg.combats.requests.CombatRequest"):
        ConstructorModule.__init__(self, app, fqn)
        self.members = []
        self.rules = None

    def add_member(self, member):
        self.members.append(member)

    def run(self):
        self.debug("Running combat")
        combat = Combat(self.app(), self.rules)
        daemon = CombatDaemon(combat)
        for minfo in self.members:
            # member
            mtype = minfo["type"]
            if mtype == "virtual":
                member = CombatMember(combat)
            else:
                makemember = getattr(mtype, "combat_member", None)
                if makemember is None:
                    raise CombatRunError(self._("This object cannot be a combat member: %s") % mtype)
                member = makemember(combat)
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
            # joining
            combat.join(member)
        # running combat
        turn_order = CombatRoundRobinTurnOrder(combat)
        combat.run(turn_order)
        daemon.run()

class CombatDaemon(CombatObject, Daemon):
    def __init__(self, combat, fqn="mg.mmorpg.combats.daemon.CombatDaemon"):
        CombatObject.__init__(self, combat, fqn, weak=False)
        Daemon.__init__(self, combat.app(), fqn, combat.uuid)
        self.api_server = http.WSGIServer(self.api_request)
        self.api_host = self.app().inst.int_host
        self.api_port = self.serve_any_port(self.api_host)
        if self.api_port is None:
            raise CombatRunError(self._("No free TCP ports to launch combat daemon"))

    def serve_any_port(self, hostaddr):
        for port in range(3000, 65536):
            try:
                try:
                    self.api_server.serve((hostaddr, port))
                    self.info("serving %s:%d", hostaddr, port)
                    return port
                except socket.error as err:
                    if err.errno == 98:
                        pass
                    else:
                        raise
            except Exception as err:
                self.error(u"Listen %s:%d: %s (%s)", hostaddr, port, err, err)
        return None

    def main(self):
        obj = self.obj(DBRunningCombat, self.combat.uuid, {})
        obj.set("api_host", self.api_host)
        obj.set("api_port", self.api_host)
        obj.store()
        try:
            while not self.combat.stage_flag("done"):
                self.combat.process()
                Tasklet.yield_()
        finally:
            obj.destroy()

    def api_request(self, environ, start_response):
        "Process combat API request"
        start_response("200 OK", [
            ("Content-type", "application/json")
        ])
        return json.dumps({"foo": "bar"}).encode("utf-8")

class CombatInterface(ConstructorModule):
    def __init__(self, app, combat_uuid, fqn="mg.mmorpg.combats.daemons.CombatInterface"):
        ConstructorModule.__init__(self, app, fqn)
        if not re_valid_uuid.match(combat_uuid):
            raise ObjectNotFoundException(combat_uuid)
        self.combat_uuid = combat_uuid
        obj = self.obj(DBRunningCombat, combat_uuid)
        self.api_host = obj.get("api_host")
        self.api_port = obj.get("api_port")
        print "Remote combat API URI: %s:%s" % (self.api_host, self.api_port)

    def query(self, uri, args={}):
        args["combat"] = self.combat_uuid
        try:
            res = self.call("cluster.query-server", self.api_host, self.api_port, uri, args)
            if type(res) != dict or res.get("combat") != self.combat_uuid:
                raise CombatUnavailable(self._("Invalid combat response (combat field is %s)") % res.get("combat"))
        except HTTPError as e:
            raise CombatUnavailable(e)

    def ping(self):
        return self.query("/combat/ping")
