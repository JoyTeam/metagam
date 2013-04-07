from concurrence.io import Socket
from concurrence.io.buffered import Buffer, BufferedReader, BufferedWriter
from concurrence import Tasklet
from uuid import uuid4
import mg
import json
import re
import socket
import os

max_frame_length = 50000

re_valid_id = re.compile('^\w+$')
re_split_headers = re.compile('\r?\n\r?\n')
re_http_status_line = re.compile('^HTTP/[\d\.]+\s+((\d+)\s+[^\r\n]*)')
re_content_length = re.compile('^Content-Length:\s*(\d+)', re.IGNORECASE | re.MULTILINE)
re_valid_numeric = re.compile('^[\d\.]+$')
re_watch_line = re.compile('^(\w+)\s+([^:]+):(\S+)\s*$')
re_valid_channel = re.compile('^([a-zA-Z0-9]+)_id_([0-9a-f]{32})$')

class RealplexorSocketError(Exception):
    pass

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
        data = json.dumps(data, skipkeys=True)
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
            raise RealplexorSocketError("Socket error: %s" % e)
        except socket.gaierror as e:
            raise RealplexorError("DNS error: %s" % e)
        except socket.timeout as e:
            raise RealplexorError("Timeout error: %s" % e)
        except IOError as e:
            raise RealplexorSocketError("IOError: %s" % e)

class Realplexor(mg.Module):
    def register(self):
        self.rhook("stream.send", self.send)
        self.rhook("stream.packet", self.packet)
        self.rhook("stream.packet-list", self.packet_list)
        self.rhook("stream.flush", self.flush)
        # It is important that Realplexor's request_processed called after all other handlers
        # that can send something via Realplexor
        self.rhook("web.request_processed", self.request_processed, priority=-10)
        self.rhook("realplexor.tasklet", self.tasklet)
        self.rhook("realplexor.host", self.realplexor_host)

    def realplexor_host(self):
        config = self.call("cluster.services")
        realplexor = config.get("realplexor")
        if not realplexor:
            raise RealplexorError("Realplexor is not running")
        return realplexor[0]["addr"]

    def send(self, ids, data):
        host = self.call("realplexor.host")
        if host:
            rpl = RealplexorConcurrence(host, 10010, self.app().tag + "_")
            rpl.send(ids, data)

    def packet(self, ids, method_cls, method, **kwargs):
        kwargs["method_cls"] = method_cls
        kwargs["method"] = method
        self.packet_list(ids, [kwargs])

    def packet_list(self, ids, pkt_list):
        if ids == None:
            session = self.req().session()
            if session is None:
                self.call("web.require_login")
            ids = "id_%s" % session.uuid
        # [a, b, c] will be sent immediately
        # a will be delayed
        # [a] will be delayed
        if type(ids) == list:
            if len(ids) == 1:
                ids = ids[0]
            else:
                self.flush()
                self.call("stream.send", ids, {"packets": pkt_list})
                return
        try:
            req = self.req()
        except AttributeError:
            self.call("stream.send", ids, {"packets": pkt_list})
        else:
            try:
                packets = req.stream_packets
            except AttributeError:
                packets = {}
                req.stream_packets = packets
                req.stream_packets_len = 0
            try:
                queue = packets[ids]
            except KeyError:
                queue = []
                packets[ids] = queue
            queue.extend(pkt_list)
            req.stream_packets_len += len("%s" % pkt_list)
            if req.stream_packets_len >= max_frame_length:
                self.flush()

    def flush(self):
        try:
            req = self.req()
        except AttributeError:
            return
        try:
            packets = req.stream_packets
        except AttributeError:
            pass
        else:
            for session_uuid, lst in packets.iteritems():
                self.call("stream.send", session_uuid, {"packets": lst})
            req.stream_packets = {}
            req.stream_packets_len = 0

    def request_processed(self):
        self.flush()

    def tasklet(self):
        "This tasklet is being run from main application"
        # Register service
        inst = self.app().inst
        int_app = inst.int_app
        srv = mg.SingleApplicationWebService(self.app(), "realplexor", "realplexor", "rpl")
        srv.set("webbackend", "realplexor")
        srv.set("webbackendport", 8088)
        srv.serve_any_port()
        int_app.call("cluster.register-service", srv)
        Tasklet.new(self.loop)()

    def loop(self):
        # Main loop
        resync = True
        self.call("stream.init")
        while True:
            try:
                rpl = RealplexorConcurrence("127.0.0.1", 10010)
                # resynchronization
                if resync:
                    resync = False
                    check_pos = False
                    pos = 0
                    timer = 0
                    idle_timer = 0
                timer += 1
                if timer >= 300:
                    timer = 0
                    check_pos = True
                idle_timer -= 1
                if idle_timer <= 0:
                    idle_timer = 30
                    self.call("stream.idle")
                if check_pos:
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
                except RealplexorSocketError as e:
                    self.error("Socket error when accessing realplexor: %s", e)
                    resync = True
                    env = os.environ.copy()
                    env["PERL5LIB"] = "/usr/lib/realplexor"
                    self.app().inst.int_app.call("procman.spawn",
                        ["/usr/sbin/realplexorbin", "/etc/realplexor.conf"],
                        env)
                    # Let procman start. If it won't start in 3 seconds one more attempt will be made. Multiple
                    # instances will be aborted automatically (bind() will return error to subsequent daemons)
                    Tasklet.sleep(3)
                except RealplexorError as e:
                    self.error("Error watching realplexor events: %s", e)
                    check_pos = True
            except Exception as e:
                self.exception(e)
            Tasklet.sleep(1)

class RealplexorDaemon(mg.Module):
    def register(self):
        self.rhook("services.list", self.services_list)

    def services_list(self, services):
        services["realplexor"] = {
            "executable": "mg_realplexor"
        }

class RealplexorAdmin(mg.Module):
    def register(self):
        self.rhook("menu-admin-cluster.monitoring", self.menu_cluster_monitoring)
        self.rhook("ext-admin-realplexor.monitor", self.realplexor_monitor, priv="monitoring")
        self.rhook("headmenu-admin-realplexor.monitor", self.headmenu_realplexor_monitor)

    def menu_cluster_monitoring(self, menu):
        req = self.req()
        if req.has_access("monitoring"):
            menu.append({"id": "realplexor/monitor", "text": self._("Realplexor"), "leaf": True})

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
        rpl = RealplexorConcurrence(self.call("realplexor.host"), 10010)
        for channel, listeners in rpl.cmdOnlineWithCounters().iteritems():
            m = re_valid_channel.match(channel)
            if m:
                project, session_uuid = m.group(1, 2)
                rows.append(['<hook:admin.link href="constructor/project-dashboard/{0}" title="{0}" />'.format(project), session_uuid, listeners])
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_realplexor_monitor(self, args):
        return self._("Realplexor monitor")

