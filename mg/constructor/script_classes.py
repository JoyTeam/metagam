from mg import *
from mg.core import Parsing
import re

class ScriptParserError(Exception):
    def __init__(self, val, exc=None, **kwargs):
        self.val = val
        self.exc = exc
        self.kwargs = kwargs

    def __str__(self):
        return self.val.format(**self.kwargs)

    def __repr__(self):
        return self.val.format(**self.kwargs)

class ScriptParserResult(Exception):
    def __init__(self, val):
        self.val = val

class ScriptEnvironment(object):
    pass

class ScriptError(Exception):
    def __init__(self, val, env):
        self.val = val
        self.env = env

    def __str__(self):
        return self.val

    def __repr__(self):
        return self.val

class ScriptUnknownVariableError(ScriptError):
    pass

class ScriptTypeError(ScriptError):
    pass

class ScriptRuntimeError(ScriptError):
    pass

class ScriptUnusedError(ScriptError):
    pass

#===============================================================================
# Tokens/precedences.  See Parsing documentation to learn about the
# significance of left-associative precedence.

class PQuestionOp(Parsing.Precedence):
    "%left pQuestionOp"
class TokenQuestion(Parsing.Token):
    "%token question [pQuestionOp]"
class TokenColon(Parsing.Token):
    "%token colon [pQuestionOp]"

class POrOp(Parsing.Precedence):
    "%left pOrOp >pQuestionOp"
class TokenOr(Parsing.Token):
    "%token or [pOrOp]"

class PAndOp(Parsing.Precedence):
    "%left pAndOp >pOrOp"
class TokenAnd(Parsing.Token):
    "%token and [pAndOp]"

class PCompareOp(Parsing.Precedence):
    "%left pCompareOp >pAndOp"
class TokenEquals(Parsing.Token):
    "%token equals [pCompareOp]"
class TokenLessThan(Parsing.Token):
    "%token lt [pCompareOp]"
class TokenGreaterThan(Parsing.Token):
    "%token gt [pCompareOp]"
class TokenLessEqual(Parsing.Token):
    "%token le [pCompareOp]"
class TokenGreaterEqual(Parsing.Token):
    "%token ge [pCompareOp]"

class PAddOp(Parsing.Precedence):
    "%left pAddOp >pCompareOp"
class TokenPlus(Parsing.Token):
    "%token plus [pAddOp]"
class TokenMinus(Parsing.Token):
    "%token minus [pAddOp]"

class PMulOp(Parsing.Precedence):
    "%left pMulOp >pAddOp"
class TokenStar(Parsing.Token):
    "%token star [pMulOp]"
class TokenSlash(Parsing.Token):
    "%token slash [pMulOp]"

class PDotOp(Parsing.Precedence):
    "%left pDotOp >pMulOp"
class TokenDot(Parsing.Token):
    "%token dot [pDotOp]"

class TokenNone(Parsing.Token):
    "%token nonetoken"

class TokenComma(Parsing.Token):
    "%token comma"

class TokenFunc(Parsing.Token):
    "%token func"

class TokenScalar(Parsing.Token):
    "%token scalar"
    def __init__(self, parser, val):
        Parsing.Token.__init__(self, parser)
        self.val = val

class TokenIdentifier(Parsing.Token):
    "%token identifier"
    def __init__(self, parser, val):
        Parsing.Token.__init__(self, parser)
        self.val = val

class TokenParLeft(Parsing.Token):
    "%token parleft"
class TokenParRight(Parsing.Token):
    "%token parright"

#===============================================================================
# Nonterminals, with associated productions.  In traditional BNF, the following
# productions would look something like:

class AddOp(Parsing.Nonterm):
    "%nonterm"
    def reducePlus(self, plus):
	"%reduce plus"
	self.variant = "plus"

    def reduceMinus(self, minus):
	"%reduce minus"
	self.variant = "minus"

class MulOp(Parsing.Nonterm):
    "%nonterm"
    def reduceStar(self, star):
	"%reduce star"
	self.variant = "star"

    def reduceSlash(self, slash):
	"%reduce slash"
	self.variant = "slash"

class List(Parsing.Nonterm):
    "%nonterm"
    def reduceFirst(self, expr):
        "%reduce Expr"
        self.val = [expr.val]

    def reduceNext(self, lst, Comma, expr):
        "%reduce List comma Expr"
        self.val = lst.val + [expr.val]

class Expr(Parsing.Nonterm):
    "%nonterm"
    def reduceScalar(self, s):
	"%reduce scalar"
	self.val = s.val

    def reduceNone(self, n):
        "%reduce nonetoken"
        self.val = None

    def reduceIdentifier(self, i):
	"%reduce identifier"
	self.val = ["glob", i.val]

    def recuceDot(self, exprA, d, ident):
        "%reduce Expr dot identifier"
        self.val = [".", exprA.val, ident.val]

    def reducePar(self, ParLeft, ex, ParRight):
        "%reduce parleft Expr parright"
        self.val = ex.val

    def reduceQuestion(self, exprA, q, exprB, c, exprC):
        "%reduce Expr question Expr colon Expr [pQuestionOp]"
        self.val = ["?", exprA.val, exprB.val, exprC.val]

    def reduceEquals(self, exprA, EqualsOp, exprB):
        "%reduce Expr equals Expr [pCompareOp]"
        self.val = ["==", exprA.val, exprB.val]

    def reduceLessThan(self, exprA, LessThanOp, exprB):
        "%reduce Expr lt Expr [pCompareOp]"
        self.val = ["<", exprA.val, exprB.val]

    def reduceGreaterThan(self, exprA, GreaterThanOp, exprB):
        "%reduce Expr gt Expr [pCompareOp]"
        self.val = [">", exprA.val, exprB.val]

    def reduceLessThan(self, exprA, LessThanOp, exprB):
        "%reduce Expr le Expr [pCompareOp]"
        self.val = ["<=", exprA.val, exprB.val]

    def reduceGreaterThan(self, exprA, GreaterThanOp, exprB):
        "%reduce Expr ge Expr [pCompareOp]"
        self.val = [">=", exprA.val, exprB.val]

    def reduceAnd(self, exprA, AndOp, exprB):
        "%reduce Expr and Expr [pAndOp]"
        self.val = ["and", exprA.val, exprB.val]

    def reduceOr(self, exprA, OrOp, exprB):
        "%reduce Expr or Expr [pOrOp]"
        self.val = ["or", exprA.val, exprB.val]

    def reduceAdd(self, exprA, AddOp, exprB):
	"%reduce Expr AddOp Expr [pAddOp]"
	if AddOp.variant == "plus":
    	    self.val = ["+", exprA.val, exprB.val]
	elif AddOp.variant == "minus":
            self.val = ["-", exprA.val, exprB.val]

    def reduceMul(self, exprA, MulOp, exprB):
	"%reduce Expr MulOp Expr [pMulOp]"
	if MulOp.variant == "star":
            self.val = ["*", exprA.val, exprB.val]
	elif MulOp.variant == "slash":
            self.val = ["/", exprA.val, exprB.val]

    def reduceFunc(self, func, ParLeft, lst, ParRight):
        "%reduce func parleft List parright"
        self.val = ["call", func.fname] + lst.val

# This is the start symbol; there can be only one such class in the grammar.
class Result(Parsing.Nonterm):
    "%start"
    def reduce(self, e):
	"%reduce Expr"
        raise ScriptParserResult(e.val)

class ScriptParser(Parsing.Lr, Module):
    re_token = re.compile(r'\s*(?:(-?\d+\.\d+)|(-?\d+)|(==|>=|<=|>|<|\+|-|\*|/|\.|,|\(|\)|\?|:)|"([^"]+)"|\'([^\']+)\'|([a-z_][a-z_0-9]*))', re.IGNORECASE)
    syms = {
        "+": TokenPlus,
        "-": TokenMinus,
        "*": TokenStar,
        "/": TokenSlash,
        "(": TokenParLeft,
        ")": TokenParRight,
        "?": TokenQuestion,
        ":": TokenColon,
        ".": TokenDot,
        ",": TokenComma,
        "==": TokenEquals,
        ">": TokenGreaterThan,
        "<": TokenLessThan,
        ">=": TokenGreaterEqual,
        "<=": TokenLessEqual,
        "none": TokenNone,
        "and": TokenAnd,
        "or": TokenOr,
    }
    funcs = set(["min", "max"])

    def __init__(self, app, spec):
        Module.__init__(self, app, "mg.constructor.script_classes.ScriptParser")
	Parsing.Lr.__init__(self, spec)

    def scan(self, input):
        input = input.strip()
        pos = 0
        while True:
            token_match = ScriptParser.re_token.match(input, pos)
            if not token_match:
                if pos < len(input):
                    raise ScriptParserError(self._("Parse error near '{input}'"), input=input[pos:])
                else:
                    break
            res = token_match.groups()
            token = None
            if res[0] is not None:
                token = TokenScalar(self, float(res[0]))
            elif res[1] is not None:
                token = TokenScalar(self,int(res[1]))
            elif res[2] is not None:
                cls = ScriptParser.syms.get(res[2])
                if cls:
                    token = cls(self)
            elif res[3] is not None:
                token = TokenScalar(self, res[3])
            elif res[4] is not None:
                token = TokenScalar(self, res[4])
            elif res[5] is not None:
                cls = ScriptParser.syms.get(res[5])
                if cls:
                    token = cls(self)
                else:
                    if res[5] in ScriptParser.funcs:
                        token = TokenFunc(self)
                        token.fname = res[5]
                    else:
                        token = TokenIdentifier(self, res[5])
            if token is None:
                raise ScriptParserError(self._("Unknown token near '{input}'"), input=input[pos:])
            try:
                self.token(token)
            except Parsing.SyntaxError as exc:
                raise ScriptParserError(self._("Parse error near '{input}'"), input=input[pos:], exc=exc)
            pos = token_match.end()

class ScriptTextParser(Module):
    re_token = re.compile(r'(.*?){(?:([^}:]+)\:([^}]+)|([^}]+))}', re.DOTALL)

    def __init__(self, app, spec):
        Module.__init__(self, app, "mg.constructor.script_classes.ScriptTextParser")
        self.spec = spec
        self.tokens = []

    def scan(self, input):
        input = input.strip()
        pos = 0
        while True:
            token_match = ScriptTextParser.re_token.match(input, pos)
            if not token_match:
                if pos < len(input):
                    self.tokens.append(input[pos:])
                break
            res = token_match.groups()
            if res[0]:
                self.tokens.append(res[0])
            if res[1] is not None:
                # parsing index expression: {...?val1,val2,val3}
                parser = ScriptParser(self.app(), self.spec)
                try:
                    parser.scan(res[1])
                    try:
                        parser.eoi()
                    except Parsing.SyntaxError as e:
                        raise ScriptParserError(self._("Expression '%s' is invalid: unexpected end of line") % res[1])
                except ScriptParserResult as e:
                    self.tokens.append(["index", e.val] + res[2].split(","))
            elif res[3] is not None:
                # parsing script include: {...}
                parser = ScriptParser(self.app(), self.spec)
                try:
                    parser.scan(res[3])
                    try:
                        parser.eoi()
                    except Parsing.SyntaxError as e:
                        raise ScriptParserError(self._("Expression '%s' is invalid: unexpected end of line") % res[2])
                except ScriptParserResult as e:
                    self.tokens.append(e.val)
            pos = token_match.end()

    def eoi(self):
        raise ScriptParserResult(self.tokens)
