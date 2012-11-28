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

class CombatScript(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = []

    def reduceStatement(self, script, statement):
        "%reduce CombatScript CombatStatement"
        self.val = script.val[:]
        self.val.append(statement.val)

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
