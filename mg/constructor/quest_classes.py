from mg.core import Parsing
import re

class ParserError(Exception):
    def __init__(self, val, exc=None):
        self.val = val
        self.exc = exc

    def __str__(self):
        return self.val

    def __repr__(self):
        return self.val

class ParserResult(Exception):
    def __init__(self, val):
        self.val = val

#===============================================================================
# Tokens/precedences.  See Parsing documentation to learn about the
# significance of left-associative precedence.

class PQuestionOp(Parsing.Precedence):
    "%left pQuestionOp"
class TokenQuestion(Parsing.Token):
    "%token question [pQuestionOp]"
class TokenColon(Parsing.Token):
    "%token colon [pQuestionOp]"

class PAddOp(Parsing.Precedence):
    "%left pAddOp >pQuestionOp"
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
#class TokenComma(Parsing.Token):
#    "%token comma"

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
        ta = type(exprA.val)
        if ta is not list:
            if exprA.val:
                self.val = exprB.val
            else:
                self.val = exprC.val
        else:
            self.val = ["?", exprA.val, exprB.val, exprC.val]

    def reduceAdd(self, exprA, AddOp, exprB):
	"%reduce Expr AddOp Expr [pAddOp]"
        if exprA.val is None or exprB.val is None:
            self.val = None
            return
	if AddOp.variant == "plus":
            ta = type(exprA.val)
            tb = type(exprB.val)
            if ta is int and tb is int:
                self.val = exprA.val + exprB.val
            elif ta is not list and tb is not list:
                self.val = floatz(exprA.val) + floatz(exprB.val)
            else:
    	        self.val = ["+", exprA.val, exprB.val]
	elif AddOp.variant == "minus":
            ta = type(exprA.val)
            tb = type(exprB.val)
            if ta is int and tb is int:
                self.val = exprA.val - exprB.val
            elif ta is not list and tb is not list:
                self.val = floatz(exprA.val) - floatz(exprB.val)
            else:
                self.val = ["-", exprA.val, exprB.val]

    def reduceMul(self, exprA, MulOp, exprB):
	"%reduce Expr MulOp Expr [pMulOp]"
        if exprA.val is None or exprB.val is None:
            self.val = None
            return
	if MulOp.variant == "star":
            ta = type(exprA.val)
            tb = type(exprB.val)
            if ta is int and tb is int:
                self.val = exprA.val * exprB.val
            elif ta is not list and tb is not list:
                self.val = floatz(exprA.val) * floatz(exprB.val)
            else:
                self.val = ["*", exprA.val, exprB.val]
	elif MulOp.variant == "slash":
            ta = type(exprA.val)
            tb = type(exprB.val)
            if tb is not list and floatz(exprB.val) == 0:
                self.val = None
            else:
                if ta is int and tb is int:
                    self.val = float(exprA.val) / float(exprB.val)
                elif ta is not list and tb is not list:
                    self.val = floatz(exprA.val) / floatz(exprB.val)
                else:
                    self.val = ["/", exprA.val, exprB.val]

# This is the start symbol; there can be only one such class in the grammar.
class Result(Parsing.Nonterm):
    "%start"
    def reduce(self, e):
	"%reduce Expr"
        raise ParserResult(e.val)

class Parser(Parsing.Lr):
    re_token = re.compile(r'\s*(?:([+\-\*\/\.,\(\)\?:])|"([^"]+)"|\'([^\']+)\'|([a-z_][a-z_0-9]*)|(\d+\.\d+)|(\d+))', re.IGNORECASE)

    def __init__(self, spec):
	Parsing.Lr.__init__(self, spec)

    def scan(self, input):
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
#            ",": TokenComma,
        }

        input = input.strip()
        pos = 0
        while True:
            token_match = Parser.re_token.match(input, pos)
            if not token_match:
                if pos < len(input):
                    raise ParserError("Parse error near '%s'" % input[pos:])
                else:
                    break
            res = token_match.groups()
            token = None
            if res[0] is not None:
                cls = syms.get(res[0])
                if cls:
                    token = cls(self)
            elif res[1] is not None:
                token = TokenScalar(self, res[1])
            elif res[2] is not None:
                token = TokenScalar(self, res[2])
            elif res[3] is not None:
                if res[3] == "none":
                    token = TokenNone(self)
                else:
                    token = TokenIdentifier(self, res[3])
            elif res[4] is not None:
                token = TokenScalar(self, float(res[4]))
            elif res[5] is not None:
                token = TokenScalar(self,int(res[5]))
            if token is None:
                raise ParserError("Unknown token near '%s'" % input[pos:])
            try:
                self.token(token)
            except Parsing.SyntaxError as exc:
                raise ParserError("Parse error near '%s'" % input[pos:], exc)
            pos = token_match.end()
