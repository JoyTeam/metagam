from mg.constructor import *
from mg.mmorpg.combats.combat_parser import *
from mg.mmorpg.combats.core import CombatAction

class CombatSystemError(Exception):
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return self.val

class CombatScripts(ConstructorModule):
    def register(self):
        self.rhook("combats.parse-script", self.parse_script)
        self.rhook("combats.execute-script", self.execute_script)
        self.rhook("combats.unparse-script", self.unparse_script)

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

    def combat_debug(self, combat, msg, **kwargs):
        "Delivering debug message to all combat members having access to debugging info"
        for member in combat.members:
            try:
                char = member.character
            except AttributeError:
                pass
            else:
                if self.call("character.debug-access", char):
                    if callable(msg):
                        msg = msg()
                    self.call("debug-channel.character", char, msg, **kwargs)

    def execute_script(self, combat, code, globs={}, handle_exceptions=True):
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
                env.globs = globs
                env.description = self._("Statement '{statement}'").format(statement=self.call("combats.unparse-script", st).strip())
                return env
            st_cmd = st[0]
            if st_cmd == "damage":
                obj = self.call("script.evaluate-expression", st[1], globs=globs, description=lambda: self._("Evaluation of damage target member"))
                attr = st[2]
                damage = nn(self.call("script.evaluate-expression", st[3], globs=globs, description=lambda: self._("Evaluation of damage value")))
                if debug:
                    self.combat_debug(combat, lambda: self._("damaging {obj}.{attr}: {damage}").format(obj=obj, attr=attr, damage=damage), cls="combat-action", indent=indent)
                try:
                    obj.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not a combat member") % self.call("script.unparse-expression", st[1]), env)
                old_val = nn(obj.param(attr, handle_exceptions))
                if old_val > 0:
                    new_val = old_val - damage
                    if new_val < 0:
                        new_val = 0
                    obj.set_param(attr, new_val)
                    globs["last_damage"] = old_val - new_val
                else:
                    obj.set_param(attr, old_val)
                    globs["last_damage"] = 0
                # logging damage
                log = combat.log
                if log:
                    logent = {
                        "type": "damage",
                        "source": source_id,
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
                if debug:
                    self.combat_debug(combat, lambda: self._("setting {obj}.{attr} = {val}").format(obj=obj, attr=attr, val=val), cls="combat-action", indent=indent)
                try:
                    obj.is_a_combat_member()
                except AttributeError:
                    raise ScriptRuntimeError(self._("'%s' is not settable") % self.call("script.unparse-expression", st[1]), env)
                obj.script_set_attr(attr, val, env)
            else:
                raise CombatSystemError(self._("Unknown combat action '%s'") % st[0])
        def execute_block(block, indent):
            "Execute a block (list of statements)"
            for st in block:
                try:
                    execute_statement(st, indent)
                except ScriptError as e:
                    if handle_exceptions:
                        self.call("exception.report", e)
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

    def unparse_script(self, code, indent=0):
        lines = []
        for st in code:
            st_cmd = st[0]
            if st_cmd == "damage":
                lines.append(u"%sdamage %s %s\n" % ("  " * indent, self.call("script.unparse-expression", [".", st[1], st[2]]), self.call("script.unparse-expression", st[3])))
            elif st_cmd == "set":
                lines.append(u"%sset %s = %s\n" % ("  " * indent, self.call("script.unparse-expression", [".", st[1], st[2]]), self.call("script.unparse-expression", st[3])))
            else:
                lines.append(u"%s<<<%s: %s>>>\n" % ("  " * indent, self._("Invalid script parse tree"), st))
        return u"".join(lines)

class ScriptedCombatAction(CombatAction):
    "Behaviour of this CombatAction is defined via combat script"
    def __init__(self, combat, fqn="mg.mmorpg.combats.scripts.ScriptedCombatAction"):
        CombatAction.__init__(self, combat, fqn)

    def begin(self):
        globs = {"source": self.source}
        self.for_every_target(self.execute_script, self.script_code("begin-target"), globs)
        self.call("combats.execute-script", self.combat, self.script_code("begin"), globs=globs)

    def end(self):
        globs = {"source": self.source}
        self.for_every_target(self.execute_script, self.script_code("end-target"), globs)
        self.call("combats.execute-script", self.combat, self.script_code("end"), globs=globs)

    def script_code(self, tag):
        "Get combat script code (syntax tree)"
        return self.conf("combats-%s.action-%s" % (self.combat.rules, tag), [])
        
    def execute_script(self, target, code, globs):
        globs["target"] = target
        self.call("combats.execute-script", self.combat, code, globs=globs)
