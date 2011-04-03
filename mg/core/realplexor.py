from mg import *

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
                        chunk = reader.read_bytes(1024)
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
        except IOError:
            raise RealplexorError("IOError: %s" % e)

class Realplexor(Module):
    def register(self):
        Module.register(self)
        self.rhook("stream.send", self.send)

    def send(self, ids, data):
        self.debug("Sending to %s%s: %s" % (self.app().tag + "_", ids, data))
        rpl = RealplexorConcurrence(self.main_app().config.get("cluster.realplexor", "127.0.0.1"), 10010, self.app().tag + "_")
        rpl.send(ids, data)

class RealplexorDaemon(Daemon):
    def __init__(self, app, id="realplexor"):
        Daemon.__init__(self, app, "mg.core.realplexor.RealplexorDaemon", id)

    def main(self):
        rpl = RealplexorConcurrence(self.conf("cluster.realplexor", "127.0.0.1"), 10010)
        pos = 0
        check_pos = False
        timer = 0
        while True:
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
                        pos = 0
                        self.info("Realplexor server restarted. Resetting event position")
                    check_pos = False
                except RealplexorError:
                    self.error("Realplexor server is not available")
            try:
                for ev in rpl.cmdWatch(pos):
                    self.debug("Received realplexor event: %s", ev)
                    pos = ev["pos"]
            except RealplexorError as e:
                self.error("Error watching realplexor events: %s", e)
                check_pos = True
            Tasklet.sleep(1)

    def hello(self, *args, **kwargs):
        self.debug("Hello, world! args: %s, kwargs: %s", args, kwargs)
        return "It worked!"

class RealplexorAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-constructor.cluster", self.menu_constructor_cluster)
        self.rhook("ext-admin-constructor.realplexor-settings", self.realplexor_settings, priv="realplexor.config")
        self.rhook("headmenu-admin-constructor.realplexor-settings", self.headmenu_realplexor_settings)
        self.rhook("int-realplexor.daemon", self.daemon, priv="public")

    def permissions_list(self, perms):
        perms.append({"id": "realplexor.config", "name": self._("Realplexor configuration")})

    def menu_constructor_cluster(self, menu):
        req = self.req()
        if req.has_access("realplexor.config"):
            menu.append({"id": "constructor/realplexor-settings", "text": self._("Realplexor"), "leaf": True})

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