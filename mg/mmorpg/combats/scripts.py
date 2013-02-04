from mg.constructor import *
from mg.mmorpg.combats.combat_parser import *
from mg.mmorpg.combats.core import CombatAction, CombatError

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
            inst._combat_parser_spec = Parsing.Spec(sys.modules["mg.mmorpg.combats.combat_parser"], skinny=False)
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
                lines.append(u"%sdamage %s %s\n" % ("  " * indent, self.call("script.unparse-expression", [".", st[1], st[2]]), self.call("script.unparse-expression", st[3])))
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
                lines.append(u"%slog %s\n" % ("  " * indent, self.call("script.unparse-expression", self.call("script.unparse-text", st[1]))))
            elif st_cmd == "syslog":
                lines.append(u"%ssyslog %s\n" % ("  " * indent, self.call("script.unparse-expression", self.call("script.unparse-text", st[1]))))
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
        ## Dry run - generally impossible because uninitialized member parameters may lead to division errors
        #try:
        #    self.call("combats.execute-script", combat, expression, globs, handle_exceptions=False, real_execute=False)
        #except ScriptError as e:
        #    errors[name] = e.val
        #    return
        # Returning result
        return expression

class CombatScripts(ConstructorModule):
    def register(self):
        self.rhook("combats.execute-script", self.execute_script)
        self.rhook("exception.report", self.exception_report, priority=20)

    def child_modules(self):
        return ["mg.mmorpg.combats.scripts.CombatScriptsAdmin"]

    def combat_debug(self, combat, msg, **kwargs):
        "Delivering debug message to all combat members having access to debugging info"
        print "debug msg"
        for member in combat.members:
            char = member.param("char")
            if char:
                print "char=%s" % char
                if self.call("character.debug-access", char):
                    if callable(msg):
                        msg = msg()
                    self.call("debug-channel.character", char, msg, **kwargs)

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
        # debug info
        debug = self.conf("combats.debug")
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
                try:
                    obj.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", st[1]), env)
                if debug:
                    self.combat_debug(combat, lambda: self._("damaging {obj}.{attr}: {damage}").format(obj=obj, attr=attr, damage=damage), cls="combat-action", indent=indent)
                old_val = nn(obj.param(attr, handle_exceptions))
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
            elif st_cmd == "set":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of object"))
                attr = st[2]
                val = self.call("script.evaluate-expression", st[3], globs=globs, description=lambda: self._("Evaluation of value"))
                set_attr = getattr(obj, "script_set_attr", None)
                if not set_attr:
                    raise ScriptRuntimeError(self._("'%s' is not settable") % self.call("script.unparse-expression", st[1]), env)
                if debug:
                    self.combat_debug(combat, lambda: self._("setting {obj}.{attr} = {val}").format(obj=obj, attr=attr, val=val), cls="combat-action", indent=indent)
                if real_execute:
                    set_attr(attr, val, env)
            elif st_cmd == "selecttarget":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of member"))
                try:
                    obj.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", st[1]), env)
                if debug:
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
                    else:
                        raise ScriptRuntimeError(self._("Unknown data aggregation function: %s") % func)
                except TypeError:
                    raise ScriptRuntimeError(self._("Type mismatch error occured during data aggregation"))
                set_attr = getattr(obj, "script_set_attr", None)
                if not set_attr:
                    raise ScriptRuntimeError(self._("'%s' is not settable") % self.call("script.unparse-expression", st[1]), env)
                if debug:
                    self.combat_debug(combat, lambda: self._("setting {obj}.{attr} = {func}({data}) = {val}").format(obj=obj, attr=attr, val=val, func=func, data=u", ".join(data)), cls="combat-action", indent=indent)
                if real_execute:
                    set_attr(attr, val, env)
            elif st_cmd == "log":
                text = self.call("script.evaluate-text", st[1], globs=globs, description=lambda: self._("Evaluation of log text"))
                if debug:
                    self.combat_debug(combat, lambda: self._("writing to log: {text}").format(text=text), cls="combat-log", indent=indent)
                if real_execute:
                    combat.textlog({
                        "text": text
                    })
            elif st_cmd == "syslog":
                text = self.call("script.evaluate-text", st[1], globs=globs, description=lambda: self._("Evaluation of system log text"))
                if debug:
                    self.combat_debug(combat, lambda: self._("writing to system log: {text}").format(text=text), cls="combat-log", indent=indent)
                if real_execute:
                    combat.syslog({
                        "text": text
                    })
            elif st_cmd == "if":
                expr = st[1]
                val = self.call("script.evaluate-expression", expr, globs=globs, description=lambda: self._("Evaluation of condition"))
                if debug:
                    self.combat_debug(combat, lambda: self._("if {condition}: {result}").format(condition=self.call("script.unparse-expression", expr), result=self._("true") if val else self._("false")), cls="combat-condition", indent=indent + 2)
                if val:
                    execute_block(st[2], indent + 1)
                else:
                    if len(st) >= 4:
                        execute_actions(st[3], indent + 1)
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

    def exception_report(self, exception):
        if not issubclass(type(exception), CombatScriptError):
            return
        try:
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
            self.critical("Exception during exception reporting: %s", traceback.format_exc())

