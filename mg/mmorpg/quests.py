from mg.constructor import *
from mg.mmorpg.quest_parser import *
import re

re_info = re.compile(r'^([a-z0-9_]+)/(.+)$', re.IGNORECASE)
re_state = re.compile(r'^state/(.+)$', re.IGNORECASE)
re_param = re.compile(r'^p_(.+)$')

class DBCharQuests(CassandraObject):
    clsname = "CharQuests"

class DBCharQuestsList(CassandraObjectList):
    objcls = DBCharQuests

class QuestError(Exception):
    def __init__(self, val):
        self.val = val

class CharQuests(ConstructorModule):
    def __init__(self, app, uuid):
        Module.__init__(self, app, "mg.mmorpg.quests.CharQuests")
        self.uuid = uuid

    @property
    def lock_key(self):
        return "CharQuests.%s" % self.uuid

    @property
    def char(self):
        try:
            return self._char
        except AttributeError:
            self._char = self.character(self.uuid)
            return self._char

    def load(self):
        try:
            self._quests = self.obj(DBCharQuests, self.uuid)
        except ObjectNotFoundException:
            self._quests = self.obj(DBCharQuests, self.uuid, data={})

    def store(self):
        # storing database object
        self._quests.store()

    def get(self, qid, param, default=None):
        if not getattr(self, "_quests", None):
            self.load()
        quest = self._quests.get(qid)
        if quest is None:
            return default
        else:
            return quest.get(param, default)

    def set(self, qid, param, val):
        if not getattr(self, "_quests", None):
            self.load()
        quest = self._quests.get(qid)
        if quest is None:
            if param != "state":
                raise QuestError(self._("Quest '{quest}' is not taken yet when trying to set attribute {attr}").format(quest=qid, attr=param))
            old_val = "init"
            self._quests.set(qid, {param: val})
        else:
            old_val = quest.get(param)
            quest[param] = val
            self.touch()
        return old_val

    def destroy(self, qid):
        if not getattr(self, "_quests", None):
            self.load()
        self._quests.delkey(qid)

    def touch(self):
        self._quests.touch()

    def quest(self, qid):
        return CharQuest(self, qid)

    def locked(self, qid):
        return self.char.modifiers.get("q_%s_locked" % qid)

    def lock(self, qid, timeout=None):
        if timeout is None:
            till = None
        else:
            timeout = intz(timeout)
            if timeout <= 0:
                return
            till = self.now(timeout)
        self.char.modifiers.add("q_%s_locked" % qid, 1, till)

class CharQuest(object):
    def __init__(self, quests, qid):
        self.quests = quests
        self.qid = qid

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "state":
            return self.quests.get(self.qid, attr, "init")
        elif attr == "locked":
            return 1 if self.locked else 0
        elif attr == "notlocked":
            return 0 if self.locked else 1
        else:
            m = re_param.match(attr)
            if m:
                param = m.group(1)
                return self.quests.get(self.qid, param)
            else:
                if handle_exceptions:
                    return None
                else:
                    raise AttributeError(attr)

    def script_set_attr(self, attr, val):
        m = re_param.match(attr)
        if m:
            param = m.group(1)
            return self.quests.set(self.qid, param, val)
        else:
            raise AttributeError(attr)

    def store(self):
        self.quests.store()

    def __str__(self):
        return "%s.[quest %s]" % (htmlescape(self.quests.char), self.qid)

    __repr__ = __str__

    @property
    def locked(self):
        return self.quests.locked(self.qid)

def parse_quest_tp(qid, tp):
    if tp[0] == "event":
        return "event-%s-%s" % (qid, tp[1])
    else:
        return "-".join(tp)

class QuestsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-quests.index", self.menu_quests_index)
        self.rhook("headmenu-admin-quests.editor", self.headmenu_quests_editor)
        self.rhook("ext-admin-quests.editor", self.admin_quests_editor, priv="quests.editor")
        self.rhook("advice-admin-quests.index", self.advice_quests)
        self.rhook("quest-admin.script-field", self.quest_admin_script_field)
        self.rhook("quest-admin.unparse-script", self.quest_admin_unparse_script)

    def permissions_list(self, perms):
        perms.append({"id": "quests.editor", "name": self._("Quest engine: editor")})

    def menu_root_index(self, menu):
        menu.append({"id": "quests.index", "text": self._("Quests and triggers"), "order": 25})

    def menu_quests_index(self, menu):
        req = self.req()
        if req.has_access("quests.editor"):
            menu.append({"id": "quests/editor", "text": self._("Quests editor"), "order": 20, "leaf": True})

    def advice_quests(self, hook, args, advice):
        advice.append({"title": self._("Quests documentation"), "content": self._('You can find detailed information on the quests engine in the <a href="//www.%s/doc/quests" target="_blank">quests engine page</a> in the reference manual.') % self.app().inst.config["main_host"]})

    def headmenu_quests_editor(self, args):
        if args == "new":
            return [self._("New quest"), "quests/editor"]
        elif args:
            m = re_info.match(args)
            if m:
                qid, cmd = m.group(1, 2)
                if cmd == "info":
                    quest = self.conf("quests.list", {}).get(qid)
                    if quest:
                        return [htmlescape(quest["name"]), "quests/editor"]
                else:
                    m = re_state.match(cmd)
                    if m:
                        cmd = m.group(1)
                        if cmd == "new":
                            return [self._("New state"), "quests/editor/%s/info" % qid]
                        else:
                            m = re_info.match(cmd)
                            if m:
                                pass
                            else:
                                return [self._("State %s") % cmd, "quests/editor/%s/info" % qid]
            else:
                return [self._("Parameters"), "quests/editor/%s/info" % htmlescape(args)]
        return self._("Quests")

    def admin_quests_editor(self):
        req = self.req()
        if req.args:
            with self.lock(["QuestsEditor"]):
                m = re_info.match(req.args)
                if m:
                    return self.admin_quest_editor(m.group(1), m.group(2))
                quest_list = self.conf("quests.list", {})
                if req.args == "new":
                    quest = {
                    }
                else:
                    quest = quest_list.get(req.args)
                    if not quest:
                        self.call("admin.redirect", "quests/editor")
                if req.ok():
                    errors = {}
                    # id
                    qid = req.param("id").strip()
                    if not qid:
                        errors["id"] = self._("This field is mandatory")
                    elif qid == "new":
                        errors["id"] = self._("Identifer 'new' is reserved")
                    elif not re_valid_identifier.match(qid):
                        errors["id"] = self._("Quest identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
                    elif qid != req.args and qid in quest_list:
                        errors["id"] = self._("Quest with the same identifier already exists")
                    # name
                    name = req.param("name").strip()
                    if not name:
                        errors["name"] = self._("This field is mandatory")
                    else:
                        quest["name"] = name
                    # flags
                    quest["enabled"] = True if req.param("enabled") else False
                    if errors:
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # storing
                    config = self.app().config_updater()
                    if req.args == "new":
                        quest_list[qid] = quest
                    else:
                        if req.args != qid:
                            del quest_list[req.args]
                            quest_list[qid] = quest
                            old_states = self.conf("quest-%s.states" % req.args)
                            if old_states is not None:
                                config.delete("quest-%s.states" % req.args)
                                config.set("quest-%s.states" % qid, old_states)
                    config.set("quests.list", quest_list)
                    self.update_quest_handlers(config)
                    config.store()
                    self.call("admin.redirect", "quests/editor/%s/info" % qid)
                fields = [
                    {"name": "id", "value": "" if req.args == "new" else req.args, "label": self._("Quest identifier")},
                    {"name": "name", "value": quest.get("name"), "label": self._("Quest name")},
                    {"name": "enabled", "checked": quest.get("enabled"), "label": self._("Quest is enabled for everybody (if this checkbox is disabled the quest is available for administrators only)"), "type": "checkbox"},
                ]
                self.call("admin.form", fields=fields)
        rows = []
        quest_list = [(qid, quest) for qid, quest in self.conf("quests.list", {}).iteritems()]
        quest_list.sort(cmp=lambda x, y: cmp(x[0], y[0]))
        for qid, quest in quest_list:
            qid_html = qid
            name_html = htmlescape(quest["name"])
            if quest.get("enabled"):
                qid_html = u'<span class="admin-enabled">%s</span>' % qid_html
                name_html = u'<span class="admin-enabled">%s</span>' % name_html
            rows.append([
                qid_html,
                name_html,
                u'<hook:admin.link href="quests/editor/%s/info" title="%s" />' % (qid, self._("edit")),
                u'<hook:admin.link href="quests/editor/%s/del" title="%s" confirm="%s" />' % (qid, self._("delete"), self._("Are you sure want to delete this quest?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "quests/editor/new", "text": self._("New quest"), "lst": True}
                    ],
                    "header": [
                        self._("Quest ID"),
                        self._("Quest name"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def update_quest_handlers(self, config):
        events = set(config.get("quests.events", []))
        handlers = {}
        for qid, quest in config.get("quests.list", {}).iteritems():
            for sid, state in config.get("quest-%s.states" % qid, {}).iteritems():
                script = state.get("script")
                if script:
                    if script[0] != "state":
                        raise RuntimeError(self._("Invalid quest states object. Expected {expected}. Found: {found}").format(expected="state", found=script[0]))
                    if "hdls" in script[1]:
                        for handler in script[1]["hdls"]:
                            if handler[0] != "hdl":
                                raise RuntimeError(self._("Invalid quest states object. Expected {expected}. Found: {found}").format(expected="hdl", found=script[0]))
                            tp = handler[1]["type"]
                            tp = parse_quest_tp(qid, tp)
                            events.add(tp)
                            try:
                                handlers[tp].add((qid, sid))
                            except KeyError:
                                handlers[tp] = set([(qid, sid)])
        for event in events:
            lst = handlers.get(event)
            if lst:
                config.set("qevent-%s.handlers" % event, [[qid, sid] for qid, sid in lst])
            else:
                config.delete("qevent-%s.handlers" % event)
        config.set("quests.events", handlers.keys())

    def admin_quest_editor(self, qid, cmd):
        req = self.req()
        if cmd == "del":
            config = self.app().config_updater()
            lst = self.conf("quests.list", {})
            try:
                del lst[qid]
            except KeyError:
                pass
            config.set("quests.list", lst)
            config.delete("quest-%s.states" % qid)
            self.update_quest_handlers(config)
            config.store()
            self.call("admin.redirect", "quests/editor")
        elif cmd == "info":
            quest_list = self.conf("quests.list", {})
            quest = quest_list.get(qid)
            if not quest:
                self.call("admin.redirect", "quests/editor")
            rows = []
            states = [(sid, state) for sid, state in self.conf("quest-%s.states" % qid, {}).iteritems()]
            states.sort(cmp=lambda x, y: cmp(x[1].get("order", 0), y[1].get("order", 0)) or cmp(x[0], y[0]))
            for sid, state in states:
                rows.append([
                    sid,
                    u'<hook:admin.link href="quests/editor/%s/state/%s" title="%s" />' % (qid, sid, self._("edit")),
                    u'<hook:admin.link href="quests/editor/%s/state/%s/del" title="%s" confirm="%s" />' % (qid, sid, self._("delete"), self._("Are you sure want to delete this state?")),
                ])
            vars = {
                "tables": [
                    {
                        "links": [
                            {"hook": "quests/editor/%s" % qid, "text": self._("Edit quest parameters")},
                            {"hook": "quests/editor/%s/state/new" % qid, "text": self._("New quest state"), "lst": True}
                        ],
                        "header": [
                            self._("State"),
                            self._("Editing"),
                            self._("Deletion"),
                        ],
                        "rows": rows
                    }
                ]
            }
            self.call("admin.response_template", "admin/common/tables.html", vars)
        else:
            m = re_state.match(cmd)
            if m:
                cmd = m.group(1)
                states = self.conf("quest-%s.states" % qid, {})
                m = re_info.match(cmd)
                if m:
                    sid, cmd = m.group(1, 2)
                    if cmd == "del":
                        config = self.app().config_updater()
                        try:
                            del states[sid]
                        except KeyError:
                            pass
                        config.set("quest-%s.states" % qid, states)
                        self.update_quest_handlers(config)
                        config.store()
                        self.call("admin.redirect", "quests/editor/%s/info" % qid)
                    self.call("admin.redirect", "quests/editor/%s/info" % qid)
                if cmd == "new":
                    order = 0
                    for state in states.values():
                        if order is None or state.get("order", 0) > order:
                            order = state.get("order", 0)
                    show_sid = "" if states else "init"
                    state = {
                        "order": order + 10
                    }
                else:
                    state = states.get(cmd)
                    if state is None:
                        self.call("admin.redirect", "quests/editor/%s/info" % qid)
                    show_sid = cmd
                if req.ok():
                    errors = {}
                    # id
                    sid = req.param("id").strip()
                    if not sid:
                        errors["id"] = self._("This field is mandatory")
                    elif sid == "new":
                        errors["id"] = self._("Identifer 'new' is reserved")
                    elif not re_valid_identifier.match(sid):
                        errors["id"] = self._("State identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
                    elif sid != cmd and sid in states:
                        errors["id"] = self._("State with the same identifier already exists")
                    # order
                    state["order"] = floatz(req.param("order"))
                    # description
                    char = self.character(req.user())
                    state["description"] = self.call("script.admin-text", "description", errors, globs={"char": char}, mandatory=False)
                    # script
                    state["script"] = self.call("quest-admin.script-field", "script", errors, globs={"char": char}, mandatory=False)
                    if errors:
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # storing
                    config = self.app().config_updater()
                    if cmd == "new":
                        states[sid] = state
                    else:
                        if cmd != sid:
                            del states[cmd]
                            states[sid] = state
                    config.set("quest-%s.states" % qid, states)
                    self.update_quest_handlers(config)
                    config.store()
                    self.call("admin.redirect", "quests/editor/%s/info" % qid)
                fields = [
                    {"name": "id", "value": show_sid, "label": self._("State identifier")},
                    {"name": "order", "value": state.get("order"), "label": self._("Sorting order"), "inline": True},
                    {"name": "description", "value": self.call("script.unparse-text", state.get("description")), "type": "textarea", "label": self._("Quest state description for the quest log (for instance, task for player)") + self.call("script.help-icon-expressions")},
                    {"name": "script", "value": self.call("quest-admin.unparse-script", state.get("script")), "type": "textarea", "label": self._("Quest script") + self.call("script.help-icon-expressions", "quests"), "height": 300},
                ]
                self.call("admin.form", fields=fields)
        self.call("admin.redirect", "quests/editor/%s/info" % qid)

    def quest_admin_script_field(self, name, errors, globs={}, expression=None, mandatory=True):
        req = self.req()
        if expression is None:
            expression = req.param(name).strip()
        if mandatory and expression == "":
            errors[name] = self._("This field is mandatory")
            return
        # Parsing
        try:
            expression = self.call("quests.parse-script", expression)
        except ScriptParserError as e:
            html = e.val.format(**e.kwargs)
            if e.exc:
                html += "\n%s" % e.exc
            errors[name] = html
            return
        # Evaluating
        try:
            env = ScriptEnvironment()
            env.globs = globs
            self.quest_script_validate(expression, env)
        except ScriptError as e:
            errors[name] = e.val
            return
        # Returning result
        return expression

    def quest_script_validate(self, val, env):
        if type(val) != list:
            raise ScriptParserError(self._("Script validation error. Expected list, received %s") % type(val).__name__)
        objtype = val[0]
        if objtype == "state":
            if val[1].get("hdls"):
                for handler in val[1]["hdls"]:
                    if handler[0] != "hdl":
                        raise ScriptError(self._("Handler expected in the handlers list. Received: %s") % handler[0], env)
                    self.quest_script_validate(handler, env)
        elif objtype == "hdl":
            if val[1].get("act"):
                for act in val[1]["act"]:
                    self.quest_script_validate(act, env)

    def quest_admin_unparse_script(self, val, indent=0):
        if val is None:
            return ""
        if type(val) != list:
            raise ScriptParserError(self._("Script unparse error. Expected list, received %s") % type(val).__name__)
        if len(val) == 0 or type(val[0]) == list:
            # list of objects
            return u"".join([self.quest_admin_unparse_script(ent, indent) for ent in val])
        else:
            objtype = val[0]
            if val[0] == "state":
                return self.quest_admin_unparse_script(val[1].get("hdls"))
            elif val[0] == "hdl":
                result = "  " * indent + self.quest_admin_unparse_script(val[1]["type"])
                attrs = val[1].get("attrs")
                if attrs:
                    attrs = [(k, v) for k, v in attrs.iteritems()]
                    attrs.sort(cmp=lambda x, y: cmp(x[0], y[0]))
                    result += u"".join([" %s=%s" % (k, self.call("script.unparse-expression", v)) for k, v in attrs])
                actions = val[1].get("act")
                if actions:
                    result += " {\n" + self.quest_admin_unparse_script(actions, indent + 1) + "}\n"
                else:
                    result += " {}\n"
                return result
            elif val[0] == "event":
                return u"event %s" % self.call("script.unparse-expression", val[1])
            elif val[0] == "teleported":
                return "teleported"
            elif val[0] == "require":
                return "  " * indent + u"require %s\n" % self.call("script.unparse-expression", val[1])
            elif val[0] == "call":
                if len(val) == 2:
                    return "  " * indent + u"call event=%s\n" % self.call("script.unparse-expression", val[1])
                else:
                    return "  " * indent + u"call quest=%s event=%s\n" % (self.call("script.unparse-expression", val[1]), self.call("script.unparse-expression", val[2]))
            elif val[0] == "message" or val[0] == "error":
                s = self.call("script.unparse-text", val[1])
                if not re_dblquote.search(s):
                    return "  " * indent + u'%s "%s"\n' % (val[0], s)
                elif not re_sglquote.search(s):
                    return "  " * indent + u"%s '%s'\n" % (val[0], s)
                else:
                    return "  " * indent + u'%s "%s"\n' % (val[0], quotestr(s))
            elif val[0] == "giveitem":
                attrs = [("p_%s" % k, v) for k, v in val[2].iteritems()]
                attrs.sort(cmp=lambda x, y: cmp(x[0], y[0]))
                attrs = u"".join([" %s=%s" % (k, self.call("script.unparse-expression", v)) for k, v in attrs])
                result = "  " * indent + "give item=" + self.call("script.unparse-expression", val[1])
                if len(val) >= 4:
                    quantity = val[3]
                else:
                    quantity = 1
                if quantity != 1:
                    result += " quantity=%s" % self.call("script.unparse-expression", quantity)
                result += attrs + "\n"
                return result
            elif val[0] == "if":
                result = "  " * indent + ("if %s {" % self.call("script.unparse-expression", val[1]))
                result += "\n%s%s}" % (self.quest_admin_unparse_script(val[2], indent + 1), "  " * indent)
                if len(val) >= 4 and val[3]:
                    result += " else {\n%s%s}" % (self.quest_admin_unparse_script(val[3], indent + 1), "  " * indent)
                result += "\n"
                return result
            elif val[0] == "set":
                return "  " * indent + ("set %s.%s = %s\n" % (self.call("script.unparse-expression", val[1]), val[2], self.call("script.unparse-expression", val[3])))
            elif val[0] == "destroy":
                return "  " * indent + "%s\n" % ("finish" if val[1] else "fail")
            elif val[0] == "lock":
                attrs = ""
                if val[1] is not None:
                    attrs += ' timeout=%s' % self.call("script.unparse-expression", val[1])
                return "  " * indent + "lock%s\n" % attrs
            else:
                return "  " * indent + "<<<%s: %s>>>\n" % (self._("Invalid script parse tree"), objtype)

class Quests(ConstructorModule):
    def register(self):
        self.rhook("quests.parse-script", self.parse_script)
        self.rhook("quests.event", self.quest_event)
        self.rhook("quests.char", self.get_char)

    def child_modules(self):
        return ["mg.mmorpg.quests.QuestsAdmin"]

    @property
    def general_parser_spec(self):
        inst = self.app().inst
        try:
            return inst._parser_spec
        except AttributeError:
            inst._parser_spec = Parsing.Spec(sys.modules["mg.constructor.script_classes"], skinny=False)
            return inst._parser_spec

    @property
    def quest_parser_spec(self):
        inst = self.app().inst
        try:
            return inst._quest_parser_spec
        except AttributeError:
            inst._quest_parser_spec = Parsing.Spec(sys.modules["mg.mmorpg.quest_parser"], skinny=False)
            return inst._quest_parser_spec

    def parse_script(self, text):
        parser = QuestScriptParser(self.app(), self.quest_parser_spec, self.general_parser_spec)
        try:
            parser.scan(text)
            # Tell the parser that the end of input has been reached.
            try:
                parser.eoi()
            except Parsing.SyntaxError as e:
                raise ScriptParserError(self._("Expression unexpectedly ended"), e)
        except ScriptParserResult as e:
            return e.val

    def quest_event(self, event, **kwargs):
        # loading list of quests handling this type of event
        char = kwargs.get("char")
        if not char:
            return
        tasklet = Tasklet.current()
        old_indent = getattr(tasklet, "quest_indent", None)
        if old_indent is None:
            indent = 0
        else:
            indent = old_indent + 3
        tasklet.quest_indent = indent
        try:
            def event_str():
                event_str = self._(u"event=%s") % event
                for key in sorted(kwargs.keys()):
                    if key != "char":
                        val = kwargs[key]
                        if val:
                            event_str += u', %s=%s' % (key, val)
                return event_str
            if indent == 0:
                self.call("debug-channel.character", char, event_str, cls="quest-first-event", indent=indent)
            else:
                self.call("debug-channel.character", char, event_str, cls="quest-event", indent=indent)
            # loading list of handlers
            quests_states = self.conf("qevent-%s.handlers" % event)
            if not quests_states:
                return
            # checking for character states and choosing quests
            quests = set()
            for ent in quests_states:
                quest = ent[0]
                state = ent[1]
                if char.quests.get(quest, "state", "init") == state:
                    quests.add(quest)
            quests = [quest for quest in quests]
            quests.sort()
            # loading quests configuration
            self.app().config.load_groups(["quest-%s" % quest for quest in quests])
            # executing quests scripts
            def eval_description():
                return self._("Quest '{quest}', event '{event}'").format(quest=quest, event=event)
            for quest in quests:
                try:
                    states = self.conf("quest-%s.states" % quest, {})
                    state_id = char.quests.get(quest, "state", "init")
                    state = states.get(state_id)
                    self.call("debug-channel.character", char, lambda: self._("quest={quest}, state={state}").format(quest=quest, state=state_id), cls="quest-handler", indent=indent+1)
                    if not state:
                        continue
                    script = state.get("script")
                    if not script:
                        continue
                    if script[0] != "state":
                        continue
                    script = script[1]
                    hdls = script.get("hdls")
                    if not hdls:
                        continue
                    for hdl in hdls:
                        if hdl[0] != "hdl":
                            continue
                        handler = hdl[1]
                        tp = handler.get("type")
                        if not tp:
                            continue
                        tp = parse_quest_tp(quest, tp)
                        if event != tp:
                            continue
                        act = handler.get("act")
                        if not act:
                            continue
                        kwargs["quest"] = CharQuest(char.quests, quest)
                        modified_objects = set()
                        def execute_actions(actions, indent):
                            # testing stack overflows
                            try:
                                sys._getframe(900)
                            except ValueError:
                                pass
                            else:
                                # this is a real error
                                raise ScriptRuntimeError(self._("Max recursion depth exceeded"), env())
                            def env():
                                env = ScriptEnvironment()
                                env.globs = kwargs
                                env.description = self._("Quest '{quest}', event '{event}'").format(quest=quest, event=event)
                                return env
                            for cmd in actions:
                                try:
                                    cmd_code = cmd[0]
                                    if cmd_code == "message" or cmd_code == "error":
                                        message = self.call("script.evaluate-text", cmd[1], globs=kwargs, description=eval_description)
                                        self.call("debug-channel.character", char, lambda: u'%s "%s"' % (cmd_code, quotestr(message)), cls="quest-action", indent=indent+2)
                                        getattr(char, cmd_code)(message)
                                    elif cmd_code == "require":
                                        res = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                        if not res:
                                            self.call("debug-channel.character", char, lambda: u'%s: %s' % (self.call("script.unparse-expression", cmd[1]), self._("false")), cls="quest-condition", indent=indent+2)
                                            break
                                    elif cmd_code == "call":
                                        if len(cmd) == 2:
                                            ev = "event-%s-%s" % (quest, cmd[1])
                                        else:
                                            ev = "event-%s-%s" % (cmd[1], cmd[2])
                                        self.call("debug-channel.character", char, lambda: self._("calling event %s") % ev, cls="quest-action", indent=indent+2)
                                        self.qevent(ev, char=char)
                                    elif cmd_code == "giveitem":
                                        item_type_uuid = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                        mods = {}
                                        mods_list = []
                                        for param, value in cmd[2].iteritems():
                                            val = self.call("script.evaluate-expression", value, globs=kwargs, description=eval_description)
                                            mods[param] = val
                                            mods_list.append((param, val))
                                        quantity = intz(self.call("script.evaluate-expression", cmd[3], globs=kwargs, description=eval_description))
                                        if quantity > 0:
                                            item_type = self.item_type(item_type_uuid, mods=mods)
                                            if item_type.valid:
                                                def message():
                                                    res = self._("giving {item_name}, quantity={quantity}").format(item_name=item_type.name, quantity=quantity)
                                                    if mods_list:
                                                        mods_list.sort(cmp=lambda x, y: cmp(x[0], y[0]))
                                                        res += ", %s" % ", ".join([u"p_%s=%s" % (k, v) for k, v in mods_list])
                                                    return res
                                                self.call("debug-channel.character", char, message, cls="quest-action", indent=indent+2)
                                                char.inventory.give(item_type_uuid, quantity, "quest.give", quest=quest, mod=mods)
                                                # information message: 'You have got ...'
                                                item_name = item_type.name
                                                try:
                                                    char.quest_given[item_name] += quantity
                                                except AttributeError:
                                                    char.quest_given = {item_name: quantity}
                                                except KeyError:
                                                    char.quest_given[item_name] = quantity
                                    elif cmd_code == "if":
                                        expr = cmd[1]
                                        val = self.call("script.evaluate-expression", expr, globs=kwargs, description=eval_description)
                                        self.call("debug-channel.character", char, lambda: self._("if {condition}: {result}").format(condition=self.call("script.unparse-expression", expr), result=self._("true") if val else self._("false")), cls="quest-condition", indent=indent+2)
                                        if val:
                                            execute_actions(cmd[2], indent+1)
                                        else:
                                            if len(cmd) >= 4:
                                                execute_actions(cmd[3], indent+1)
                                    elif cmd_code == "set":
                                        obj = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                        attr = cmd[2]
                                        val = self.call("script.evaluate-expression", cmd[3], globs=kwargs, description=eval_description)
                                        self.call("debug-channel.character", char, lambda: self._("setting {obj}.{attr} = {val}").format(obj=self.call("script.unparse-expression", cmd[1]), attr=cmd[2], val=htmlescape(val)), cls="quest-action", indent=indent+2)
                                        set_attr = getattr(obj, "script_set_attr", None)
                                        if not set_attr:
                                            if getattr(obj, "script_attr", None):
                                                raise ScriptRuntimeError(self._("'%s' has no settable attributes") % self.call("script.unparse-expression", cmd[1]), env())
                                            else:
                                                raise ScriptRuntimeError(self._("'%s' is not an object") % self.call("script.unparse-expression", cmd[1]), env())
                                        try:
                                            set_attr(attr, val)
                                            modified_objects.add(obj)
                                        except AttributeError as e:
                                            if str(e) == attr:
                                                raise ScriptRuntimeError(self._("'{obj}.{attr}' is not settable").format(obj=self.call("script.unparse-expression", cmd[1]), attr=cmd[2]), env())
                                            else:
                                                raise
                                    elif cmd_code == "destroy":
                                        if cmd[1]:
                                            self.call("debug-channel.character", char, lambda: self._("quest finished"), cls="quest-action", indent=indent+2)
                                        else:
                                            self.call("debug-channel.character", char, lambda: self._("quest failed"), cls="quest-action", indent=indent+2)
                                            char.error(self._("Quest failed"))
                                        char.quests.destroy(quest)
                                    elif cmd_code == "lock":
                                        if cmd[1] is None:
                                            self.call("debug-channel.character", char, lambda: self._("locking quest infinitely"), cls="quest-action", indent=indent+2)
                                            char.quests.lock(quest)
                                        else:
                                            timeout = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                            self.call("debug-channel.character", char, lambda: self._("locking quest for %s sec") % timeout, cls="quest-action", indent=indent+2)
                                            char.quests.lock(quest, timeout)
                                    else:
                                        raise RuntimeError(self._("Unknown quest action: %s") % cmd_code)
                                except QuestError as e:
                                    e = ScriptError(e.val, env())
                                    self.call("exception.report", e)
                                    self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent+2)
                                except ScriptError as e:
                                    self.call("exception.report", e)
                                    self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent+2)
                                except Exception as e:
                                    self.exception(e)
                                    self.call("debug-channel.character", char, self._("System exception: %s") % e.__class__.__name__, cls="quest-error", indent=indent+2)
                        execute_actions(act, indent)
                        for obj in modified_objects:
                            obj.store()
                except QuestError as e:
                    raise ScriptError(e.val, env())
        except ScriptError as e:
            self.call("exception.report", e)
            self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent)
        except Exception as e:
            self.exception(e)
            self.call("debug-channel.character", char, self._("System exception: %s") % e.__class__.__name__, cls="quest-error", indent=indent)
        finally:
            tasklet.quest_indent = old_indent
            if old_indent is None:
                quest_given = getattr(char, "quest_given", None)
                if quest_given:
                    tokens = []
                    for key, val in quest_given.iteritems():
                        name = key
                        if val > 1:
                            name += " &mdash; %s" % (self._("%d pcs") % val)
                        tokens.append(name)
                    tokens.sort()
                    char.message(u"<br />".join(tokens), title=self._("You have got:"))

    def get_char(self, uuid):
        return CharQuests(self.app(), uuid)
