from mg.core import Parsing
from mg.constructor.script_classes import *

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_param = re.compile(r'^p_([a-z_][a-z0-9_]*)$', re.IGNORECASE)

# To add a new event, condition or action:
#   1. create TokenXXX class
#   2. assign it a terminal symbol: syms["xxx"] = TokenXXX
#   3. write the syntax rule
#   4. write unparsing rule in mg.mmorpg.combats.scripts
#   5. implement the feature

class TokenDamage(Parsing.Token):
    "%token damage"

class TokenSet(Parsing.Token):
    "%token set"

class TokenSelect(Parsing.Token):
    "%token select"

class TokenSelectTarget(Parsing.Token):
    "%token selecttarget"

class TokenWhere(Parsing.Token):
    "%token where"

class TokenFrom(Parsing.Token):
    "%token from"

class TokenMembers(Parsing.Token):
    "%token members"

class TokenIf(Parsing.Token):
    "%token if"

class TokenElse(Parsing.Token):
    "%token else"

class TokenLog(Parsing.Token):
    "%token log"

class TokenSyslog(Parsing.Token):
    "%token syslog"

class TokenChat(Parsing.Token):
    "%token chat"

class CombatAttrKey(Parsing.Nonterm):
    "%nonterm"
    def reduceAttrKey(self, attrkey):
        "%reduce AttrKey"
        self.val = attrkey.val

    def reduceEvent(self, event):
        "%reduce damage"
        self.val = "damage"

class Attrs(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}
    
    def reduceAttr(self, attrs, key, a, value):
        "%reduce Attrs CombatAttrKey assign scalar"
        if key.val in attrs.val:
            raise Parsing.SyntaxError(a.script_parser._("Attribute '%s' was specified twice") % key.val)
        self.val = attrs.val.copy()
        self.val[key.val] = value.val

class ExprAttrs(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}
    
    def reduceAttr(self, attrs, key, a, expr):
        "%reduce ExprAttrs CombatAttrKey assign Expr"
        if key.val in attrs.val:
            raise Parsing.SyntaxError(a.script_parser._("Attribute '%s' was specified twice") % key.val)
        self.val = attrs.val.copy()
        self.val[key.val] = expr.val

def get_attr(any_obj, obj_name, attrs, attr, require=False):
    val = attrs.val.get(attr)
    if val is None:
        if require:
            raise Parsing.SyntaxError(any_obj.script_parser._("Attribute '{attr}' is required in the '{obj}'").format(obj=obj_name, attr=attr))
    return val

def get_str_attr(any_obj, obj_name, attrs, attr, require=False):
    val = get_attr(any_obj, obj_name, attrs, attr, require)
    if val is not None and type(val) != str and type(val) != unicode:
        raise Parsing.SyntaxError(any_obj.script_parser._("Attribute '{attr}' in the '{obj}' must be a string").format(obj=obj_name, attr=attr))
    return val

def validate_attrs(any_obj, obj_name, attrs, valid_attrs):
    for k, v in attrs.val.iteritems():
        if k not in valid_attrs:
            raise Parsing.SyntaxError(any_obj.script_parser._("'{obj}' has no attribute '{attr}'").format(obj=obj_name, attr=k))

class CombatStatement(Parsing.Nonterm):
    "%nonterm"
    def reduceDamage(self, cmd, obj, dot, attr, val):
        "%reduce damage Expr dot AttrKey Expr"
        if not re_param.match(attr.val):
            raise Parsing.SyntaxError(dot.script_parser._("Damage parameter must start with 'p_'"))
        self.val = ["damage", obj.val, attr.val, val.val]

    def reduceSet(self, st, lvalue, assign, rvalue):
        "%reduce set Expr assign Expr"
        if type(lvalue.val) != list or lvalue.val[0] != ".":
            raise Parsing.SyntaxError(assign.script_parser._("Invalid usage of assignment operator"))
        self.val = ["set", lvalue.val[1], lvalue.val[2], rvalue.val]

    def reduceSelectTarget(self, st, member, where, cond):
        "%reduce selecttarget Expr where Expr"
        self.val = ["selecttarget", member.val, cond.val]

    selectorFuncs = set(["min", "max", "count", "distinct", "sum", "mult"])

    def reduceSelect(self, st, lvalue, assign, select, func, parleft, val, parright, fr, datasrc, where):
        "%reduce set Expr assign select func parleft Expr parright from SelectorDataSource Where"
        if type(lvalue.val) != list or lvalue.val[0] != ".":
            raise Parsing.SyntaxError(assign.script_parser._("Invalid usage of assignment operator"))
        if func.fname not in self.selectorFuncs:
            raise Parsing.SyntaxError(assign.script_parser._("Function %s is not supported in selector context") % func.fname)
        self.val = ["select", lvalue.val[1], lvalue.val[2], func.fname, val.val, datasrc.val, where.val]

    def reduceIf(self, cmd, expr, curlyleft, actions, curlyright):
        "%reduce if Expr curlyleft CombatScript curlyright"
        self.val = ["if", expr.val, actions.val]

    def reduceIfElse(self, cmd, expr, curlyleft1, actions1, curlyright1, els, curlyleft2, actions2, curlyright2):
        "%reduce if Expr curlyleft CombatScript curlyright else curlyleft CombatScript curlyright"
        self.val = ["if", expr.val, actions1.val, actions2.val]

    def reduceLog(self, cmd, expr):
        "%reduce log scalar"
        self.val = ["log", cmd.script_parser.parse_text(expr.val, cmd.script_parser._("Log message"))]

    def reduceSyslog(self, cmd, expr):
        "%reduce syslog scalar"
        self.val = ["syslog", cmd.script_parser.parse_text(expr.val, cmd.script_parser._("Log message"))]

    def reduceChat(self, cmd, attrs):
        "%reduce chat ExprAttrs"
        text = get_str_attr(cmd, "chat", attrs, "text", require=True)
        text = cmd.script_parser.parse_text(text, cmd.script_parser._("Chat message"))
        channel = get_attr(cmd, "chat", attrs, "channel")
        validate_attrs(cmd, "chat", attrs, ["text", "channel"])
        args = {}
        if channel is not None:
            args["channel"] = channel
        self.val = ["chat", text, args]

class SelectorDataSource(Parsing.Nonterm):
    "%nonterm"
    def reduceMembers(self, val):
        "%reduce members"
        self.val = "members"

class Where(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = 1

    def reduceWhere(self, where, expr):
        "%reduce where Expr"
        self.val = expr.val

class CombatScript(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = []

    def reduceStatement(self, script, statement):
        "%reduce CombatScript CombatStatement"
        self.val = script.val[:]
        self.val.append(statement.val)

class Attrs(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}
    
    def reduceAttr(self, attrs, key, a, value):
        "%reduce Attrs CombatAttrKey assign scalar"
        if key.val in attrs.val:
            raise Parsing.SyntaxError(a.script_parser._("Attribute '%s' was specified twice") % key.val)
        self.val = attrs.val.copy()
        self.val[key.val] = value.val

class ExprAttrs(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}
    
    def reduceAttr(self, attrs, key, a, expr):
        "%reduce ExprAttrs CombatAttrKey assign Expr"
        if key.val in attrs.val:
            raise Parsing.SyntaxError(a.script_parser._("Attribute '%s' was specified twice") % key.val)
        self.val = attrs.val.copy()
        self.val[key.val] = expr.val

class CombatAttrKey(Parsing.Nonterm):
    "%nonterm"
    def reduceAttrKey(self, attrkey):
        "%reduce AttrKey"
        self.val = attrkey.val

# This is the start symbol; there can be only one such class in the grammar.
class Result(Parsing.Nonterm):
    "%start"
    def reduce(self, e):
        "%reduce CombatScript"
        raise ScriptParserResult(e.val)

class CombatScriptParser(ScriptParser):
    syms = ScriptParser.syms.copy()
    syms["damage"] = TokenDamage
    syms["set"] = TokenSet
    syms["selecttarget"] = TokenSelectTarget
    syms["where"] = TokenWhere
    syms["from"] = TokenFrom
    syms["members"] = TokenMembers
    syms["select"] = TokenSelect
    syms["if"] = TokenIf
    syms["else"] = TokenElse
    syms["log"] = TokenLog
    syms["syslog"] = TokenSyslog
    syms["chat"] = TokenChat

    funcs = ScriptParser.funcs.copy()
    funcs.add("count")
    funcs.add("distinct")
    funcs.add("sum")
    funcs.add("mult")

    def __init__(self, app, spec, general_spec):
        Module.__init__(self, app, "mg.mmorpg.combats.combat_parser.CombatScriptParser")
        Parsing.Lr.__init__(self, spec)
        self.general_spec = general_spec

    def parse_text(self, text, context):
        parser = ScriptTextParser(self.app(), self.general_spec)
        try:
            try:
                parser.scan(text)
                parser.eoi()
            except Parsing.SyntaxError as e:
                raise ScriptParserError(u"%s: %s" % (context, e))
            except ScriptParser as e:
                raise ScriptParserError(u"%s: %s" % (context, e))
        except ScriptParserResult as e:
            return e.val
        return None
