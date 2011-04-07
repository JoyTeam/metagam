from mg import *
from mg.core.auth import Session, SessionList
import json
import re
import socket
from concurrence.io import Socket
from concurrence.io.buffered import Buffer, BufferedReader, BufferedWriter

re_valid_id = re.compile('^\w+$')
re_split_headers = re.compile('\r?\n\r?\n')
re_http_status_line = re.compile('^HTTP/[\d\.]+\s+((\d+)\s+[^\r\n]*)')
re_content_length = re.compile('^Content-Length:\s*(\d+)', re.IGNORECASE | re.MULTILINE)
re_valid_numeric = re.compile('^[\d\.]+$')
re_watch_line = re.compile('^(\w+)\s+([^:]+):(\S+)\s*$')
re_valid_channel = re.compile('^([a-zA-Z0-9]+)_id_([0-9a-f]{32})$')

class AppSession(CassandraObject):
    _indexes = {
        "timeout": [[], "timeout"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AppSession-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return AppSession._indexes

class AppSessionList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AppSession-"
        kwargs["cls"] = AppSession
        CassandraObjectList.__init__(self, *args, **kwargs)

class RealplexorError(Exception):
    pass

class RealplexorConcurrence(object):
    def __init__(self, host, port, namespace="", identifier="identifier"):
        """
        host, port - address of the realplexor IN socket
        namespace - namespace to use
        identifier - specify identifier marker instead of the default one
        """
        self.host = host
        self.port = port
        self.namespace = namespace
        self.identifier = identifier
        self.login = None
        self.password = None

    def logon(self, login, password):
        """
        Set login and password to access Realplexor (if the server needs it).
        This method does not check credentials correctness.
        """
        if self.login:
            raise RealplexorError("Already logged in")
        self.login = login
        self.password = password
        self.namespace = "%s_%s" % (self.login, self.namespace)

    def send(self, ids, data, show_only_for_ids=None):
        """
        Send data to realplexor
        ids contains target IDs. It may be:
        1. str - channel name
        2. list - list of channel names
        3. dict - {channel: cursor, channel: cursor, ...}
        data - your payload (will be JSON-encoded before sending)
        show_only_for_ids - Send this message to only those who also listen any of these IDs. 
            This parameter may be used to limit the visibility to a closed
            number of cliens: give each client an unique ID and enumerate
            client IDs in show_only_for_ids to inhibit sending messages to others.
        """
        data = json.dumps(data)
        pairs = []
        if type(ids) == type("") or type(ids) == unicode:
            if not re_valid_id.match(ids):
                raise RealplexorError("Realplexor id must be alphanumeric")
            ids = self.namespace + str(ids)
            pairs.append(ids)
        elif type(ids) == list:
            for id in ids:
                if not re_valid_id.match(id):
                    raise RealplexorError("Realplexor id must be alphanumeric")
                id = self.namespace + id
                pairs.append(id)
        elif type(ids) == dict:
            for id, cursor in ids.iteritems():
                if not re_valid_id.match(id):
                    raise RealplexorError("Realplexor id must be alphanumeric")
                id = self.namespace + id
                pairs.append("%s:%s" % (cursor, id))
        if show_only_for_ids:
            for id in show_only_for_ids:
                pairs.append("*%s%s" % (self.namespace, id))
        self._send(",".join(pairs), data)

    def cmdOnlineWithCounters(self, idPrefixes=None):
        """
        Returns dict of online IDs (keys) and number of online browsers
        for each ID. (Now "online" means "connected just now", it is
        very approximate; more precision is in TODO.)

        idPrefixes - if set, only online IDs with these prefixes are returned.
        Return value - {id => counter, id => counter, ...}
        """
        if len(self.namespace):
            if not idPrefixes:
                idPrefixes = [""]
            idPrefixes = [self.namespace + prefix for prefix in idPrefixes]
        resp = self._sendCmd("online" + (" " + " ".join(idPrefixes) if idPrefixes else "")).strip()
        if not resp:
            return {}
        result = {}
        for line in resp.splitlines():
            tokens = line.split(" ", 1)
            if not len(tokens[0]):
                continue
            if len(self.namespace) and tokens[0].startswith(self.namespace):
                tokens[0] = tokens[0][len(self.namespace):]
            result[tokens[0]] = int(tokens[1])
        return result

    def cmdOnline(self, idPrefixes=None):
        """
        Returns list of online IDs.

        idPrefixes - if set, only online IDs with these prefixes are returned.
        """
        return self.cmdOnlineWithCounters(idPrefixes).keys()

    def cmdWatch(self, fromPos, idPrefixes=None):
        """
        Returns all Realplexor events (e.g. ID offline/offline changes)
        happened after fromPos cursor.

        fromPos - Start watching from this cursor.
        idPrefixes - Watch only changes of IDs with these prefixes.

        Return value - [{"event": event, "pos": pos, "id": id}, ...]
        """
        if not fromPos:
            fromPos = 0
        if not re_valid_numeric.match(str(fromPos)):
            raise RealplexorError("Position value must be numeric, '%s' given" % fromPos)
        if len(self.namespace):
            if not idPrefixes:
                idPrefixes = [""]
            idPrefixes = [self.namespace + prefix for prefix in idPrefixes]
        resp = self._sendCmd(("watch %s" % fromPos) + (" " + " ".join(idPrefixes) if idPrefixes else "")).strip()
        events = []
        for line in resp.splitlines():
            m = re_watch_line.match(line)
            if not m:
                continue
            event, pos, id = m.group(1, 2, 3)
            if len(self.namespace) and id.startswith(self.namespace):
                id = id[len(self.namespace):]
            events.append({
                "event": event,
                "pos": pos,
                "id": id
            })
        return events

    def _sendCmd(self, cmd):
        return self._send(None, "%s\n" % cmd)

    def _send(self, identifier, body, timeout=30):
        try:
            conn = Socket.connect((self.host, self.port), timeout)
            try:
                req = u"POST / HTTP/1.1\r\nHost: %s\r\nContent-length: %d\r\nX-Realplexor: %s=%s%s\r\n\r\n%s" % (self.host, len(body), (self.identifier or ""), ("%s:%s@" % (self.login, self.password) if self.login else ""), identifier or "", body)
                if type(req) == unicode:
                    req = req.encode("utf-8")
                reader = BufferedReader(conn, Buffer(1024))
                writer = BufferedWriter(conn, Buffer(1024))
                writer.write_bytes(req)
                writer.flush()
                conn.socket.shutdown(socket.SHUT_WR)
                response = ""
                while True:
                    try:
                        chunk = reader.read_bytes_available()
                    except EOFError:
                        chunk = None
                    if not chunk:
                        break
                    response += chunk
                if response:
                    m = re_split_headers.split(response, 1)
                    if not m:
                        raise RealplexorError("Non-HTTP response received:\n%s" % response)
                    headers = m[0]
                    body = m[1]
                    m = re_http_status_line.match(headers)
                    if not m:
                        raise RealplexorError("Non-HTTP response received:\n%s" % response)
                    status, code = m.group(1, 2)
                    if code != "200":
                        raise RealplexorError("Request failed: %s\n%s" % (status, body))
                    m = re_content_length.search(headers)
                    if not m:
                        raise RealplexorError("No Content-Length header in response headers:\n%s" % headers)
                    expected_len = int(m.group(1))
                    if len(body) != expected_len:
                        raise RealplexorError("Response length (%d) is different from one specified in the Content-Length header (%d): possibly broken response" % (len(body), expected_len))
                    return body
                return response
            finally:
                conn.close()
        except socket.error as e:
            raise RealplexorError("Socket error: %s" % e)
        except socket.gaierror as e:
            raise RealplexorError("DNS error: %s" % e)
        except socket.timeout as e:
            raise RealplexorError("Timeout error: %s" % e)
        except IOError as e:
            raise RealplexorError("IOError: %s" % e)

class Realplexor(Module):
    def register(self):
        Module.register(self)
        self.rhook("stream.send", self.send)
        self.rhook("stream.connected", self.connected)
        self.rhook("stream.disconnected", self.disconnected)
        self.rhook("stream.login", self.login)
        self.rhook("stream.logout", self.logout)
        self.rhook("ext-stream.init", self.init, priv="logged")

    def send(self, ids, data):
        self.debug("Sending to %s%s: %s" % (self.app().tag + "_", ids, data))
        rpl = RealplexorConcurrence(self.main_app().config.get("cluster.realplexor", "127.0.0.1"), 10010, self.app().tag + "_")
        rpl.send(ids, data)

    def appsession(self, session_uuid):
        app_tag = self.app().tag
        sess = self.main_app().obj(AppSession, "%s-%s" % (app_tag, session_uuid), silent=True)
        sess.set("app", app_tag)
        sess.set("session", session_uuid)
        return sess

    def connected(self, session_uuid):
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                self.exception(e)
                return
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            character_uuid = appsession.get("character")
            if old_state == 3 and session.get("semi_user") == character_uuid:
                # went online after disconnection
                self.debug("Session %s went online after disconnection. State: %s => 2" % (session_uuid, old_state))
                appsession.set("state", 2)
                appsession.set("timeout", self.now(3600))
                # updating session
                session.set("user", character_uuid)
                session.set("character", 1)
                session.set("authorized", 1)
                session.set("updated", self.now())
                session.delkey("semi_user")
                # storing
                session.store()
                appsession.store()
                self.call("session.character-online", character_uuid)

    def init(self):
        req = self.req()
        session = req.session()
        with self.lock(["session.%s" % session.uuid]):
            session.load()
            # updating appsession
            appsession = self.appsession(session.uuid)
            character_uuid = appsession.get("character")
            if character_uuid:
                old_state = appsession.get("state")
                went_online = old_state == 3
                self.debug("Session %s connection initialized. State: %s => 2" % (session.uuid, old_state))
                appsession.set("state", 2)
                appsession.set("timeout", self.now(3600))
                appsession.set("character", character_uuid)
                # updating session
                session.set("user", character_uuid)
                session.set("character", 1)
                session.set("authorized", 1)
                session.set("updated", self.now())
                session.delkey("semi_user")
                # storing
                session.store()
                appsession.store()
                if went_online:
                    self.call("session.character-online", character_uuid)
                self.call("web.response_json", {"ok": 1})
            self.call("web.response_json", {"offline": 1})

    def disconnected(self, session_uuid):
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                self.exception(e)
                return
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            if old_state == 2:
                # online session disconnected
                self.debug("Session %s disconnected. State: %s => 3" % (session_uuid, old_state))
                appsession.set("state", 3)
                appsession.set("timeout", self.now(3600))
                character_uuid = appsession.get("character")
                # updating session
                user = session.get("user")
                if user:
                    session.set("semi_user", user)
                    session.delkey("user")
                session.delkey("character")
                session.delkey("authorized")
                session.set("updated", self.now())
                # storing
                session.store()
                appsession.store()
                self.call("session.character-offline", character_uuid)

    def login(self, session_uuid, character_uuid):
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                self.exception(e)
                return
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            went_online = not old_state or old_state == 3
            self.debug("Session %s logged in. State: %s => 1" % (session_uuid, old_state))
            appsession.set("state", 1)
            appsession.set("timeout", self.now(120))
            appsession.set("character", character_uuid)
            # updating session
            session.set("user", character_uuid)
            session.set("character", 1)
            session.set("authorized", 1)
            session.set("updated", self.now())
            session.delkey("semi_user")
            # storing
            session.store()
            appsession.store()
            if went_online:
                self.call("session.character-online", character_uuid)

    def logout(self, session_uuid):
        with self.lock(["session.%s" % session_uuid]):
            try:
                session = self.obj(Session, session_uuid)
            except ObjectNotFoundException as e:
                self.exception(e)
                return
            # updating appsession
            appsession = self.appsession(session_uuid)
            old_state = appsession.get("state")
            went_offline = old_state == 1 or old_state == 2
            self.debug("Session %s logged out. State: %s => None" % (session_uuid, old_state))
            character_uuid = appsession.get("character")
            # updating session
            user = session.get("user")
            if user:
                session.set("semi_user", user)
                session.delkey("user")
            session.delkey("character")
            session.delkey("authorized")
            session.set("updated", self.now())
            # storing
            session.store()
            appsession.remove()
            if went_offline:
                self.call("session.character-offline", character_uuid)

class RealplexorDaemon(Daemon):
    def __init__(self, app, id="stream"):
        Daemon.__init__(self, app, "mg.core.realplexor.RealplexorDaemon", id)
        self.permanent = True

    def main(self):
        resync = True
        while not self.terminate:
            try:
                rpl = RealplexorConcurrence(self.conf("cluster.realplexor", "127.0.0.1"), 10010)
                # resynchronization
                if resync:
                    resync = False
                    check_pos = False
                    pos = 0
                    timer = 0
                    self.info("Performing Realplexor synchronization")
                    # checking actual online
                    try:
                        counters = rpl.cmdOnlineWithCounters()
                    except RealplexorError as e:
                        self.error("Error getting realplexor online: %s", e)
                        resync = True
                    else:
                        for channel, listeners in counters.iteritems():
                            m = re_valid_channel.match(channel)
                            if m:
                                app_tag, session_uuid = m.group(1, 2)
                timer += 1
                if timer >= 300:
                    timer = 0
                    check_pos = True
                if check_pos:
                    self.debug("Checking realplexor position")
                    try:
                        last_pos = 0
                        for ev in rpl.cmdWatch(0):
                            last_pos = ev["pos"]
                        if last_pos < pos:
                            resync = True
                            self.info("Realplexor server restarted. Resetting event position")
                        check_pos = False
                    except RealplexorError:
                        self.error("Realplexor server is not available")
                try:
                    for ev in rpl.cmdWatch(pos):
                        self.debug("Received realplexor event: %s", ev)
                        pos = ev["pos"]
                        m = re_valid_channel.match(ev["id"])
                        if m:
                            app_tag, session_uuid = m.group(1, 2)
                            app = self.app().inst.appfactory.get_by_tag(app_tag)
                            if app is not None:
                                if ev["event"] == "online":
                                    app.hooks.call("stream.connected", session_uuid)
                                elif ev["event"] == "offline":
                                    app.hooks.call("stream.disconnected", session_uuid)
                except RealplexorError as e:
                    self.error("Error watching realplexor events: %s", e)
                    check_pos = True
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(1)

class RealplexorAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-constructor.cluster", self.menu_constructor_cluster)
        self.rhook("ext-admin-realplexor.settings", self.realplexor_settings, priv="realplexor.config")
        self.rhook("headmenu-admin-realplexor.settings", self.headmenu_realplexor_settings)
        self.rhook("menu-admin-cluster.monitoring", self.menu_cluster_monitoring)
        self.rhook("ext-admin-realplexor.monitor", self.realplexor_monitor, priv="monitoring")
        self.rhook("headmenu-admin-realplexor.monitor", self.headmenu_realplexor_monitor)
        self.rhook("int-realplexor.daemon", self.daemon, priv="public")
        self.rhook("daemons.permanent", self.daemons_permanent)
        self.rhook("objclasses.list", self.objclasses_list)

    def objclasses_list(self, objclasses):
        objclasses["AppSession"] = (AppSession, AppSessionList)

    def permissions_list(self, perms):
        perms.append({"id": "realplexor.config", "name": self._("Realplexor configuration")})

    def menu_constructor_cluster(self, menu):
        req = self.req()
        if req.has_access("realplexor.config"):
            menu.append({"id": "realplexor/settings", "text": self._("Realplexor"), "leaf": True})

    def menu_cluster_monitoring(self, menu):
        req = self.req()
        if req.has_access("monitoring"):
            menu.append({"id": "realplexor/monitor", "text": self._("Sessions"), "leaf": True})

    def realplexor_settings(self):
        req = self.req()
        realplexor = req.param("realplexor")
        if req.param("ok"):
            config = self.app().config
            config.set("cluster.realplexor", realplexor)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            realplexor = self.conf("cluster.realplexor", "127.0.0.1")
        fields = [
            {"name": "realplexor", "label": self._("Realplexor host name"), "value": realplexor},
        ]
        self.call("admin.form", fields=fields)

    def headmenu_realplexor_settings(self, args):
        return self._("Realplexor settings")

    def daemon(self):
        self.debug("Running realplexor daemon")
        daemon = RealplexorDaemon(self.main_app())
        daemon.run()
        self.call("web.response_json", {"ok": True})

    def realplexor_monitor(self):
        rows = []
        vars = {
            "tables": [
                {
                    "header": [self._("Project"), self._("Session"), self._("Listeners")],
                    "rows": rows
                }
            ]
        }
        rpl = RealplexorConcurrence(self.conf("cluster.realplexor", "127.0.0.1"), 10010)
        for channel, listeners in rpl.cmdOnlineWithCounters().iteritems():
            m = re_valid_channel.match(channel)
            if m:
                project, session_uuid = m.group(1, 2)
                rows.append(['<hook:admin.link href="constructor/project-dashboard/{0}" title="{0}" />'.format(project), session_uuid, listeners])
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_realplexor_monitor(self, args):
        return self._("Sessions monitor")

    def daemons_permanent(self, daemons):
        daemons.append({"cls": "metagam", "app": "main", "daemon": "stream", "url": "/realplexor/daemon"})

