from mg.constructor import *
from mg.mmorpg.combats.combat_parser import *
from mg.mmorpg.combats.core import CombatAction, CombatError, CombatRunError
import re
import random
import json

re_comma = re.compile(r'\s*,\s*')
re_colon = re.compile(r'\s*:\s*')

parser_debug = False

class CombatScriptError(CombatError):
    def __init__(self, val, env):
        CombatError.__init__(self, val)
        self.env = env

    def __str__(self):
        return utf2str(self.val)

class CombatSystemError(Exception):
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return self.val

class CombatScriptsAdmin(ConstructorModule):
    def register(self):
        self.rhook("combats-admin.parse-script", self.parse_script)
        self.rhook("combats-admin.unparse-script", self.unparse_script)
        self.rhook("combats-admin.script-field", self.script_field)

    @property
    def general_parser_spec(self):
        inst = self.app().inst
        try:
            return inst._parser_spec
        except AttributeError:
            inst._parser_spec = Parsing.Spec(sys.modules["mg.constructor.script_classes"], skinny=False)
            return inst._parser_spec

    @property
    def combat_parser_spec(self):
        inst = self.app().inst
        try:
            return inst._combat_parser_spec
        except AttributeError:
            kwargs = {
                "skinny": False
            }
            if parser_debug:
                kwargs["verbose"] = True
                kwargs["logFile"] = "CombatParser.log"
            inst._combat_parser_spec = Parsing.Spec(sys.modules["mg.mmorpg.combats.combat_parser"], **kwargs)
            return inst._combat_parser_spec

    def parse_script(self, text):
        parser = CombatScriptParser(self.app(), self.combat_parser_spec, self.general_parser_spec)
        try:
            parser.scan(text)
            # Tell the parser that the end of input has been reached.
            try:
                parser.eoi()
            except Parsing.SyntaxError as e:
                raise ScriptParserError(self._("Script unexpectedly ended"), e)
        except ScriptParserResult as e:
            return e.val

    def unparse_script(self, code, indent=0):
        if code is None:
            return ""
        lines = []
        for st in code:
            st_cmd = st[0]
            if st_cmd == "damage":
                result = u"%sdamage %s %s" % ("  " * indent, self.call("script.unparse-expression", [".", st[1], st[2]]), self.call("script.unparse-expression", st[3]))
                if len(st) >= 5:
                    attrs = st[4]
                    if "maxval" in attrs:
                        result += u" maxval=%s" % self.call("script.unparse-expression", attrs["maxval"])
                result += "\n"
                lines.append(result)
            elif st_cmd == "heal":
                result = u"%sheal %s %s" % ("  " * indent, self.call("script.unparse-expression", [".", st[1], st[2]]), self.call("script.unparse-expression", st[3]))
                if len(st) >= 5:
                    attrs = st[4]
                    if "maxval" in attrs:
                        result += u" maxval=%s" % self.call("script.unparse-expression", attrs["maxval"])
                result += "\n"
                lines.append(result)
            elif st_cmd == "set":
                lines.append(u"%sset %s = %s\n" % ("  " * indent, self.call("script.unparse-expression", [".", st[1], st[2]]), self.call("script.unparse-expression", st[3])))
            elif st_cmd == "selecttarget":
                lines.append(u"%sselecttarget %s where %s\n" % ("  " * indent, self.call("script.unparse-expression", st[1]), self.call("script.unparse-expression", st[2])))
            elif st_cmd == "select":
                lines.append(u"%sset %s = select %s(%s) from %s%s\n" % ("  " * indent, self.call("script.unparse-expression", [".", st[1], st[2]]), st[3], self.call("script.unparse-expression", st[4]), st[5], ("" if st[6] == 1 else " where %s" % self.call("script.unparse-expression", st[6]))))
            elif st_cmd == "if":
                result = "  " * indent + ("if %s {" % self.call("script.unparse-expression", st[1]))
                result += "\n%s%s}" % (self.unparse_script(st[2], indent + 1), "  " * indent)
                if len(st) >= 4 and st[3]:
                    result += " else {\n%s%s}" % (self.unparse_script(st[3], indent + 1), "  " * indent)
                result += "\n"
                lines.append(result)
            elif st_cmd == "log":
                args = u''
                if len(st) >= 3:
                    for key in sorted(st[2].keys()):
                        args += u" %s=%s" % (key, self.call("script.unparse-expression", st[2][key]))
                lines.append(u"%slog %s%s\n" % ("  " * indent, self.call("script.unparse-expression", self.call("script.unparse-text", st[1])), args))
            elif st_cmd == "syslog":
                args = u''
                if len(st) >= 3:
                    for key in sorted(st[2].keys()):
                        args += u" %s=%s" % (key, self.call("script.unparse-expression", st[2][key]))
                lines.append(u"%ssyslog %s%s\n" % ("  " * indent, self.call("script.unparse-expression", self.call("script.unparse-text", st[1])), args))
            elif st_cmd == "chat":
                result = "  " * indent + "chat %s" % self.call("script.unparse-expression", self.call("script.unparse-text", st[1]))
                args = st[2]
                if "channel" in args:
                    result += " channel=%s" % self.call("script.unparse-expression", args["channel"])
                if "cls" in args:
                    result += " cls=%s" % self.call("script.unparse-expression", args["cls"])
                result += "\n"
                lines.append(result)
            elif st_cmd == "action":
                args = st[2]
                result = "  " * indent + "action %s %s" % (self.call("script.unparse-expression", args["source"]), self.call("script.unparse-expression", st[1]))
                attrs = args.get("attrs")
                if attrs:
                    for k in sorted(attrs.keys()):
                        result += " %s=%s" % (k, self.call("script.unparse-expression", attrs[k]))
                result += "\n"
                lines.append(result)
            elif st_cmd == "turn":
                cmd = st[1]
                args = st[2]
                result = "  " * indent + "turn %s" % self.call("script.unparse-expression", cmd)
                for k in sorted(args.keys()):
                    result += " %s=%s" % (k, self.call("script.unparse-expression", args[k]))
                result += "\n"
                lines.append(result)
            elif st_cmd == "randomaction":
                result = "  " * indent + "randomaction %s %s" % (self.call("script.unparse-expression", st[1]), self.call("script.unparse-expression", self.call("script.unparse-text", st[2])))
                attrs = st[3]
                for k in sorted(attrs.keys()):
                    result += " %s=%s" % (k, self.call("script.unparse-expression", attrs[k]))
                result += "\n"
                lines.append(result)
            elif st_cmd == "giveturn":
                result = "  " * indent + "giveturn %s\n" % self.call("script.unparse-expression", st[1])
                lines.append(result)
            elif st_cmd == "sound":
                result = "  " * indent + "sound %s" % self.call("script.unparse-expression", self.call("script.unparse-text", st[1]))
                options = st[2]
                if "target" in options:
                    result += " target=%s" % self.call("script.unparse-expression", options["target"])
                if "mode" in options:
                    result += " mode=%s" % self.call("script.unparse-expression", options["mode"])
                if "volume" in options:
                    result += " volume=%s" % self.call("script.unparse-expression", options["volume"])
                result += "\n"
                lines.append(result)
            elif st_cmd == "music":
                result = "  " * indent + "music %s" % self.call("script.unparse-expression", st[1])
                options = st[2]
                if "target" in options:
                    result += " target=%s" % self.call("script.unparse-expression", options["target"])
                if "fade" in options:
                    result += " fade=%s" % self.call("script.unparse-expression", options["fade"])
                if "volume" in options:
                    result += " volume=%s" % self.call("script.unparse-expression", options["volume"])
                result += "\n"
                lines.append(result)
            elif st_cmd == "musicstop":
                result = "  " * indent + "music stop"
                options = st[1]
                if "target" in options:
                    result += " target=%s" % self.call("script.unparse-expression", options["target"])
                if "fade" in options:
                    result += " fade=%s" % self.call("script.unparse-expression", options["fade"])
                result += "\n"
                lines.append(result)
            else:
                lines.append(u"%s<<<%s: %s>>>\n" % ("  " * indent, self._("Invalid script parse tree"), st))
        return u"".join(lines)

    def script_field(self, combat, name, errors, globs={}, expression=None, mandatory=True):
        req = self.req()
        if expression is None:
            expression = req.param(name).strip()
        if mandatory and expression == "":
            errors[name] = self._("This field is mandatory")
            return
        # Parsing
        try:
            expression = self.call("combats-admin.parse-script", expression)
        except ScriptParserError as e:
            html = e.val.format(**e.kwargs)
            if e.exc:
                html += "\n%s" % e.exc
            errors[name] = html
            return
        return expression

class ActionLog(ConstructorModule):
    def __init__(self, app, fqn="mg.mmorpg.combat.scripts.ActionLog"):
        ConstructorModule.__init__(self, app, fqn)
        self.hits = []

    def add(self, hit):
        self.hits.append(hit)

    def __unicode__(self):
        return self.call("l10n.literal_enumeration", self.hits)

    def __str__(self):
        return utf2str(unicode(self))

class CombatScripts(ConstructorModule):
    def register(self):
        self.rhook("combats.execute-script", self.execute_script)
        self.rhook("exception.report", self.exception_report, priority=20)
        self.rhook("combats.debug", self.combat_debug)

    def child_modules(self):
        return ["mg.mmorpg.combats.scripts.CombatScriptsAdmin"]

    def combat_debug(self, combat, msg, **kwargs):
        "Show combat debug message"
        if combat.rulesinfo.get("debug_script_chat"):
            for member in combat.members:
                char = getattr(member, "char", None)
                if char:
                    if self.call("character.debug-access", char):
                        if callable(msg):
                            msg = msg()
                        self.call("debug-channel.character", char, msg, **kwargs)
        if combat.rulesinfo.get("debug_script_log"):
            kwargs = kwargs.copy()
            if callable(msg):
                msg = msg()
            kwargs["text"] = msg
            combat.syslog(kwargs)

    def execute_script(self, combat, code, globs={}, handle_exceptions=True, real_execute=True, description=None):
        if code is None:
            return
        globs["combat"] = combat
        # indenting
        tasklet = Tasklet.current()
        old_indent = getattr(tasklet, "combat_indent", None)
        if old_indent is None:
            indent = 0
        else:
            indent = old_indent + 4
            tasklet.combat_indent = indent
        def execute_statement(st, indent):
            "Execute statement of a combat script"
            def env():
                env = ScriptEnvironment()
                env.combat = combat
                env.globs = globs
                env.statement = st
                env.description = description
                env.combat_script = True
                return env
            st_cmd = st[0]
            if st_cmd == "damage":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of damage target member"))
                attr = st[2]
                damage = nn(self.call("script.evaluate-expression", st[3], globs=globs, description=lambda: self._("Evaluation of damage value")))
                if len(st) >= 5:
                    attrs = st[4]
                else:
                    attrs = {}
                try:
                    obj.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", st[1]), env)
                self.combat_debug(combat, lambda: self._("damaging {obj}.{attr}: {damage}").format(obj=obj, attr=attr, damage=damage), cls="combat-action", indent=indent)
                old_val = nn(obj.param(attr, handle_exceptions))
                if not globs.get("action_log") or not isinstance(globs["action_log"], ActionLog):
                    globs["action_log"] = ActionLog(self.app())
                if old_val > 0:
                    new_val = old_val - damage
                    if new_val < 0:
                        new_val = 0
                    if real_execute:
                        obj.set_param(attr, new_val)
                    globs["last_damage"] = old_val - new_val
                else:
                    if real_execute:
                        obj.set_param(attr, old_val)
                    globs["last_damage"] = 0
                    new_val = old_val
                new_val_str = unicode(nn(new_val))
                if "maxval" in attrs:
                    maxval = self.call("script.evaluate-expression", attrs["maxval"], globs=globs, description=lambda: self._("Evaluation of maximal value"))
                    new_val_str += u"/%s" % maxval
                globs["action_log"].add(u'<span class="combat-log-member combat-log-target">%s</span> <span class="combat-log-damage">-%s</span> <span class="combat-log-hp">[%s]</span>' % (obj.name, nn(damage), new_val_str))
                if real_execute:
                    # logging damage
                    log = combat.log
                    if log:
                        logent = {
                            "type": "damage",
                            "target": obj.id,
                            "param": attr,
                            "damage": damage,
                            "oldval": old_val,
                            "newval": new_val,
                        }
                        if "source" in globs:
                            logent["source"] = globs["source"].id
                        log.syslog(logent)
            elif st_cmd == "heal":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of heal target member"))
                attr = st[2]
                heal = nn(self.call("script.evaluate-expression", st[3], globs=globs, description=lambda: self._("Evaluation of heal value")))
                if len(st) >= 5:
                    attrs = st[4]
                else:
                    attrs = {}
                try:
                    obj.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", st[1]), env)
                self.combat_debug(combat, lambda: self._("healing {obj}.{attr}: {heal}").format(obj=obj, attr=attr, heal=heal), cls="combat-action", indent=indent)
                old_val = nn(obj.param(attr, handle_exceptions))
                if not globs.get("action_log") or not isinstance(globs["action_log"], ActionLog):
                    globs["action_log"] = ActionLog(self.app())
                if "maxval" in attrs:
                    maxval = self.call("script.evaluate-expression", attrs["maxval"], globs=globs, description=lambda: self._("Evaluation of maximal value"))
                else:
                    maxval = None
                if old_val > 0:
                    new_val = old_val + heal
                    if maxval is not None and new_val > maxval:
                        new_val = maxval
                    if real_execute:
                        obj.set_param(attr, new_val)
                    globs["last_heal"] = new_val - old_val
                else:
                    if real_execute:
                        obj.set_param(attr, old_val)
                    globs["last_heal"] = 0
                    new_val = old_val
                new_val_str = unicode(nn(new_val))
                if "maxval" in attrs:
                    new_val_str += u"/%s" % maxval
                globs["action_log"].add(u'<span class="combat-log-member combat-log-target">%s</span> <span class="combat-log-heal">+%s</span> <span class="combat-log-hp">[%s]</span>' % (obj.name, nn(heal), new_val_str))
                if real_execute:
                    # logging heal
                    log = combat.log
                    if log:
                        logent = {
                            "type": "heal",
                            "target": obj.id,
                            "param": attr,
                            "heal": heal,
                            "oldval": old_val,
                            "newval": new_val,
                        }
                        if "source" in globs:
                            logent["source"] = globs["source"].id
                        log.syslog(logent)
            elif st_cmd == "set":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of object"))
                attr = st[2]
                val = self.call("script.evaluate-expression", st[3], globs=globs, description=lambda: self._("Evaluation of value"))
                set_attr = getattr(obj, "script_set_attr", None)
                if not set_attr:
                    raise ScriptRuntimeError(self._("'%s' is not settable") % self.call("script.unparse-expression", st[1]), env)
                tval = type(val)
                if tval != str and tval != type(None) and tval != unicode and tval != long and tval != float and tval != bool and tval != int:
                    raise ScriptRuntimeError(self._("Can't assign compound values ({val}) to the attributes").format(val=tval.__name__ if tval else None), env)
                self.combat_debug(combat, lambda: self._("setting {obj}.{attr} = {val}").format(obj=obj, attr=attr, val=val), cls="combat-action", indent=indent)
                if real_execute:
                    set_attr(attr, val, env)
            elif st_cmd == "selecttarget":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of member"))
                try:
                    obj.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", st[1]), env)
                self.combat_debug(combat, lambda: self._("selecting target for {member}").format(member=obj), cls="combat-action", indent=indent)
                if real_execute:
                    obj.select_target(st[2], env)
            elif st_cmd == "select":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of object"))
                attr = st[2]
                datasrc = st[5]
                data = []
                if datasrc == "members":
                    if combat.members:
                        for member in combat.members:
                            globs["member"] = member
                            if self.call("script.evaluate-expression", st[6], globs=globs, description=lambda: self._("Evaluation of the condition")):
                                data.append(self.call("script.evaluate-expression", st[4], globs=globs, description=lambda: self._("Evaluation of the data")))
                        del globs["member"]
                else:
                    raise ScriptRuntimeError(self._("Unknown data source for select: %s") % datasrc)
                func = st[3]
                try:
                    if func == "max":
                        val = None
                        for v in data:
                            if val is None or v > val:
                                val = v
                    elif func == "min":
                        val = None
                        for v in data:
                            if val is None or v < val:
                                val = v
                    elif func == "distinct":
                        values = set()
                        val = 0
                        for v in data:
                            if v not in values:
                                values.add(v)
                                val += 1
                    elif func == "sum":
                        val = 0
                        for v in data:
                            val += v
                    elif func == "mult":
                        val = 1
                        for v in data:
                            val *= v
                    elif func == "count":
                        val = len(data)
                    else:
                        raise ScriptRuntimeError(self._("Unknown data aggregation function: %s") % func)
                except TypeError:
                    raise ScriptRuntimeError(self._("Type mismatch error occured during data aggregation"))
                set_attr = getattr(obj, "script_set_attr", None)
                if not set_attr:
                    raise ScriptRuntimeError(self._("'%s' is not settable") % self.call("script.unparse-expression", st[1]), env)
                self.combat_debug(combat, lambda: self._("setting {obj}.{attr} = {func}({data}) = {val}").format(obj=obj, attr=attr, val=val, func=func, data=u", ".join([str2unicode(item) for item in data])), cls="combat-action", indent=indent)
                if real_execute:
                    set_attr(attr, val, env)
            elif st_cmd == "log":
                text = self.call("script.evaluate-text", st[1], globs=globs, description=lambda: self._("Evaluation of log text"))
                args = {
                    "text": text
                }
                if len(st) >= 3:
                    for key in st[2].keys():
                        args[key] = self.call("script.evaluate-expression", st[2][key], globs=globs, description=lambda: self._("Evaluation of combat log {key} attribute").format(key=key))
                self.combat_debug(combat, lambda: self._("writing to log: {text}").format(text=text), cls="combat-log", indent=indent)
                if real_execute:
                    combat.textlog(args)
            elif st_cmd == "syslog":
                text = self.call("script.evaluate-text", st[1], globs=globs, description=lambda: self._("Evaluation of system log text"))
                args = {
                    "text": text
                }
                if len(st) >= 3:
                    for key in st[2].keys():
                        args[key] = self.call("script.evaluate-expression", st[2][key], globs=globs, description=lambda: self._("Evaluation of combat system log {key} attribute").format(key=key))
                self.combat_debug(combat, lambda: self._("writing to system log: {text}").format(text=text), cls="combat-log", indent=indent)
                if real_execute:
                    combat.syslog(args)
            elif st_cmd == "if":
                expr = st[1]
                val = self.call("script.evaluate-expression", expr, globs=globs, description=lambda: self._("Evaluation of condition"))
                self.combat_debug(combat, lambda: self._("if {condition}: {result}").format(condition=self.call("script.unparse-expression", expr), result=self._("true") if val else self._("false")), cls="combat-condition", indent=indent)
                if val:
                    execute_block(st[2], indent + 1)
                else:
                    if len(st) >= 4:
                        execute_block(st[3], indent + 1)
            elif st_cmd == "chat":
                html = self.call("script.evaluate-text", st[1], globs=globs, description=lambda: self._("Evaluation of chat HTML"))
                args = st[2]
                if "channel" in args:
                    channel = self.call("script.evaluate-expression", args["channel"], globs=globs, description=lambda: self._("Evaluation of chat channel"))
                    channel = utf2str(unicode(channel))
                else:
                    channel = "wld"
                if "cls" in args:
                    cls = self.call("script.evaluate-expression", args["cls"], globs=globs, description=lambda: self._("Evaluation of chat class"))
                else:
                    cls = "combat"
                self.combat_debug(combat, lambda: self._("sending chat message to channel {channel}: {msg}").format(channel=htmlescape(str2unicode(channel)), msg=htmlescape(str2unicode(html))), cls="combat-action", indent=indent)
                self.call("chat.message", html=html, cls=cls, hide_time=True, hl=True, channel=channel)
            elif st_cmd == "action":
                tp = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of combat action"))
                if type(tp) != str and type(tp) != unicode:
                    raise ScriptRuntimeError(self._("Action type '%s' is not a string") % self.call("script.unparse-expression", st[1]), env)
                args = st[2]
                source = self.call("script.evaluate-expression", args["source"], globs=globs, description=lambda: self._("Evaluation of combat action source"))
                try:
                    source.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("Source '%s' is not a combat member") % self.call("script.unparse-expression", source), env)
                targets = source.targets
                if not targets:
                    raise ScriptRuntimeError(self._("Targets list '%s' is empty") % self.call("script.unparse-expression", targets), env)
                action = CombatAction(combat)
                action.set_code(tp)
                for tid in targets:
                    target = combat.member(tid)
                    if not target:
                        raise ScriptRuntimeError(self._("Combat member '%s' not found") % self.call("script.unparse-expression", tid), env)
                    action.add_target(target)
                attrs = args.get("attrs")
                if attrs:
                    for k, v in attrs.iteritems():
                        action.set_attribute(k, self.call("script.evaluate-expression", v, globs=globs, description=lambda: self._("Evaluation of combat action attribute '%s'") % k))
                self.combat_debug(combat, lambda: self._("selecting action {act} for member {source}: targets={targets}, attrs={attrs}").format(act=tp, source=source.id, targets=targets, attrs=json.dumps(action.attrs)), cls="combat-action", indent=indent)
                source.enqueue_action(action)
            elif st_cmd == "turn":
                cmd = st[1]
                args = st[2]
                combat.turn_order.command(cmd, args)
                self.combat_debug(combat, lambda: self._("executing turn order command: {cmd}").format(cmd=cmd), cls="combat-action", indent=indent)
            elif st_cmd == "randomaction":
                source = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of combat action source"))
                try:
                    source.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", st[1]), env)
                actions = self.call("script.evaluate-text", st[2], globs=globs, description=lambda: self._("Evaluation of random actions list"))
                attrs = st[3]
                actions = re_comma.split(actions)
                selected_actions = []
                for act in actions:
                    act = act.strip()
                    tokens = re_colon.split(act)
                    if len(tokens) != 2:
                        raise ScriptRuntimeError(self._("Invalid action descriptor: '%s'. Expected format: ACTIONCODE:WEIGHT") % act, env)
                    if not valid_nonnegative_float(tokens[1]):
                        raise ScriptRuntimeError(self._("Invalid action descriptor: '%s'. Weight must be a valid number") % act, env)
                    actinfo = combat.actions.get(tokens[0])
                    if actinfo is None:
                        raise ScriptRuntimeError(self._("Invalid action descriptor: '%s'. This action does not exist") % act, env)
                    weight = floatz(tokens[1])
                    if weight > 0:
                        if source.action_available(actinfo):
                            selected_actions.append({
                                "action": actinfo,
                                "weight": weight
                            })
                # Try to choose random actions from the list provided
                while selected_actions:
                    total_weight = 0
                    for act in selected_actions:
                        total_weight += act["weight"]
                    num = random.random() * total_weight
                    for i in xrange(0, len(selected_actions)):
                        act = selected_actions[i]
                        if num < act["weight"]:
                            act = act["action"]
                            del selected_actions[i]
                            # Try to choose targets for the action
                            targets = []
                            for m in combat.members:
                                if not m.active:
                                    continue
                                if source.target_available(act, m):
                                    targets.append(m)
                            # Evaluate number of targets
                            targets_min = source.targets_min(act)
                            targets_max = source.targets_max(act)
                            random.shuffle(targets)
                            self.combat_debug(combat, lambda: self._("trying to choose targets for action {act} of member {source} (min={min}, max={max}, targets={targets})").format(act=act["code"], source=source.id, targets=[t.id for t in targets], min=targets_min, max=targets_max), cls="combat-action", indent=indent)
                            if len(targets) > targets_max:
                                del targets[targets_max:]
                            if len(targets) < targets_min:
                                break
                            # Execute selected action
                            action = CombatAction(combat)
                            action.set_code(act["code"])
                            for m in targets:
                                action.add_target(m)
                            for k, v in attrs.iteritems():
                                action.set_attribute(k, self.call("script.evaluate-expression", v, globs=globs, description=lambda: self._("Evaluation of combat action attribute '%s'") % k))
                            self.combat_debug(combat, lambda: self._("selecting action {act} for member {source}: targets={targets}, attrs={attrs}").format(act=act["code"], source=source.id, targets=[t.id for t in targets], attrs=json.dumps(action.attrs)), cls="combat-action", indent=indent)
                            source.enqueue_action(action)
                            return
                        num -= act["weight"]
            elif st_cmd == "giveturn":
                member = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of combat action source"))
                if member.may_turn:
                    self.combat_debug(combat, lambda: self._("can't give right turn to member {member}").format(member=member), cls="combat-action", indent=indent)
                else:
                    self.combat_debug(combat, lambda: self._("giving turn right to member {member}").format(member=member), cls="combat-action", indent=indent)
                    member.turn_give()
            elif st_cmd == "sound":
                url = self.call("script.evaluate-text", st[1], globs=globs, description=lambda: self._("Evaluation of the sound URL to play"))
                options = st[2]
                attrs = {}
                if "mode" in options:
                    mode = self.call("script.evaluate-expression", options["mode"], globs=globs, description=lambda: self._("Evaluation of 'mode' argument"))
                    if mode != "wait" and mode != "overlap" and mode != "stop":
                        raise ScriptRuntimeError(self._("Invalid value for 'mode' attribute: '%s'") % mode, env)
                    attrs["mode"] = mode
                if "volume" in options:
                    volume = self.call("script.evaluate-expression", options["volume"], globs=globs, description=lambda: self._("Evaluation of 'volume' argument"))
                    if type(volume) != int:
                        raise ScriptRuntimeError(self._("Invalid value type for 'volume' attribute: '%s'") % type(volume).__name__, env)
                    attrs["volume"] = volume
                if "target" in options:
                    target = self.call("script.evaluate-expression", options["target"], globs=globs, description=lambda: self._("Evaluation of 'target' argument"))
                    try:
                        target.is_a_combat_member()
                    except AttributeError:
                        raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", options["target"]), env)
                    self.combat_debug(combat, lambda: self._("playing sound {url} for {member}").format(url=url.split("/")[-1], member=target), cls="quest-action", indent=indent)
                    target.sound(url, **attrs)
                else:
                    self.combat_debug(combat, lambda: self._("playing sound {url} for everybody").format(url=url.split("/")[-1]), cls="quest-action", indent=indent)
                    for member in combat.members:
                        member.sound(url, **attrs)
            elif st_cmd == "music":
                playlist = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of the music playlist"))
                options = st[2]
                attrs = {}
                if "fade" in options:
                    fade = self.call("script.evaluate-expression", options["fade"], globs=globs, description=lambda: self._("Evaluation of 'fade' argument"))
                    if type(fade) != int:
                        raise ScriptRuntimeError(self._("Invalid value type for 'fade' attribute: '%s'") % type(fade).__name__, env)
                    attrs["fade"] = fade
                if "volume" in options:
                    volume = self.call("script.evaluate-expression", options["volume"], globs=globs, description=lambda: self._("Evaluation of 'volume' argument"))
                    if type(volume) != int:
                        raise ScriptRuntimeError(self._("Invalid value type for 'volume' attribute: '%s'") % type(volume).__name__, env)
                    attrs["volume"] = volume
                if "target" in options:
                    target = self.call("script.evaluate-expression", options["target"], globs=globs, description=lambda: self._("Evaluation of 'target' argument"))
                    try:
                        target.is_a_combat_member()
                    except AttributeError:
                        raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", options["target"]), env)
                    self.combat_debug(combat, lambda: self._("playing music {playlist} for {member}").format(playlist=playlist, member=target), cls="quest-action", indent=indent)
                    target.music(playlist, **attrs)
                else:
                    self.combat_debug(combat, lambda: self._("playing music {playlist} for everybody").format(playlist=playlist), cls="quest-action", indent=indent)
                    for member in combat.members:
                        member.music(playlist, **attrs)
            elif st_cmd == "musicstop":
                options = st[1]
                attrs = {}
                if "fade" in options:
                    fade = self.call("script.evaluate-expression", options["fade"], globs=globs, description=lambda: self._("Evaluation of 'fade' argument"))
                    if type(fade) != int:
                        raise ScriptRuntimeError(self._("Invalid value type for 'fade' attribute: '%s'") % type(fade).__name__, env)
                    attrs["fade"] = fade
                if "target" in options:
                    target = self.call("script.evaluate-expression", options["target"], globs=globs, description=lambda: self._("Evaluation of 'target' argument"))
                    try:
                        target.is_a_combat_member()
                    except AttributeError:
                        raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", options["target"]), env)
                    self.combat_debug(combat, lambda: self._("stopping music for {member}").format(member=target), cls="quest-action", indent=indent)
                    target.music(None, **attrs)
                else:
                    self.combat_debug(combat, lambda: self._("stopping music for everybody"), cls="quest-action", indent=indent)
                    for member in combat.members:
                        member.music(None, **attrs)
            else:
                raise CombatSystemError(self._("Unknown combat action '%s'") % st[0])
        def execute_block(block, indent):
            "Execute a block (list of statements)"
            for st in block:
                try:
                    execute_statement(st, indent)
                except ScriptError as e:
                    if handle_exceptions:
                        # Promote ScriptError to CombatScriptError
                        if not e.env:
                            e.env = ScriptEnvironment()
                            e.env.combat = combat
                            e.env.globs = globs
                            e.env.description = description
                            e.env.combat_script = True
                        else:
                            if callable(e.env):
                                e.env = e.env()
                        if callable(e.env.description):
                            e.env.description = e.env.description()
                        desc = description() if callable(description) else description
                        if desc != e.env.description:
                            e.env.description = u"%s / %s" % (desc, e.env.description)
                        e.env.combat = combat
                        e.env.statement = st
                        self.call("exception.report", CombatScriptError(e.val, e.env))
                        self.combat_debug(combat, e.val, cls="combat-error", indent=indent)
                    else:
                        raise
                except Exception as e:
                    if handle_exceptions:
                        self.exception(e)
                        self.combat_debug(combat, self._("System exception: %s") % e.__class__.__name__, cls="combat-error", indent=indent)
                    else:
                        raise
        try:
            execute_block(code, 0)
        finally:
            tasklet.combat_indent = old_indent

    def exception_report(self, exception, e_type=None, e_value=None, e_traceback=None):
        if not isinstance(exception, CombatScriptError) and not isinstance(exception, CombatRunError):
            return
        try:
            if e_type is None:
                e_type, e_value, e_traceback = sys.exc_info()
            try:
                req = self.req()
            except AttributeError:
                req = None
            project = getattr(self.app(), "project", None)
            if not project:
                raise exception
            owner = self.main_app().obj(User, project.get("owner"))
            name = owner.get("name")
            email = owner.get("email")
            vars = {
                "RequestParameters": self._("Request parameters"),
                "Session": self._("Session"),
                "Host": self._("Host"),
                "URL": self._("URL"),
                "Context": self._("Context"),
                "Expression": self._("Expression"),
                "Rules": self._("Rules"),
                "Combat": self._("Combat"),
                "Statement": self._("Statement"),
            }
            params = []
            if req:
                for key, values in req.param_dict().iteritems():
                    params.append({"key": htmlescape(key), "values": []})
                    for val in values:
                        params[-1]["values"].append(htmlescape(val))
            if len(params):
                vars["params"] = params
            if req:
                vars["host"] = htmlescape(req.host())
                vars["uri"] = htmlescape(req.uri())
                session = req.session()
                if session:
                    vars["session"] = session.data_copy()
            try:
                vars["text"] = htmlescape(exception.val)
            except AttributeError:
                vars["text"] = htmlescape(str(exception))
            try:
                env = exception.env
            except AttributeError:
                pass
            else:
                if env:
                    if callable(env):
                        env = env()
                    if callable(env.description):
                        env.description = env.description()
                    vars["context"] = htmlescape(env.description)
                    if getattr(env, "statement", None):
                        vars["statement"] = htmlescape(self.call("combats-admin.unparse-script", [env.statement]).strip())
                    try:
                        if env.text:
                            vars["expression"] = htmlescape(self.call("script.unparse-text", env.val))
                        else:
                            vars["expression"] = htmlescape(self.call("script.unparse-expression", env.val))
                    except AttributeError:
                        pass
                try:
                    combat = env.combat
                except AttributeError:
                    pass
                else:
                    vars["combat"] = combat.uuid
                    vars["rules"] = combat.rules
            subj = str(exception)
            content = self.call("web.parse_template", "constructor/script-exception.html", vars)
            self.call("email.send", email, name, subj, content, immediately=True, subtype="html")
            raise Hooks.Return()
        except Hooks.Return:
            raise
        except Exception as e:
            self.critical("Exception during exception reporting: %s", "".join(traceback.format_exception(e_type, e_value, e_traceback)))

