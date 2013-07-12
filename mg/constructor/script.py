from mg import *
from mg.constructor import *
from mg.constructor.script_classes import *
import re
import traceback
import math

class HTMLFormatter(object):
    @staticmethod
    def clsbegin(clsname):
        return u'<span class="%s">' % clsname

    @staticmethod
    def clsend():
        return u'</span>';

class ScriptEngine(ConstructorModule):
    def register(self):
        self.rhook("script.help-icon-expressions", self.help_icon_expressions)
        self.rhook("exception.report", self.exception_report, priority=10)
        # Numerical expressions
        self.rhook("script.parse-expression", self.parse_expression)
        self.rhook("script.unparse-expression", self.unparse_expression)
        self.rhook("script.validate-expression", self.validate_expression)
        self.rhook("script.evaluate-expression", self.evaluate_expression)
        self.rhook("script.admin-expression", self.admin_expression)
        # Text expressions (templates)
        self.rhook("script.parse-text", self.parse_text)
        self.rhook("script.unparse-text", self.unparse_text)
        self.rhook("script.validate-text", self.validate_text)
        self.rhook("script.evaluate-text", self.evaluate_text)
        self.rhook("script.admin-text", self.admin_text)
        self.rhook("gameinterface.render", self.gameinterface_render)

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("mmoscript")
        vars["js_init"].append("MMOScript.lang = '%s';" % self.call("l10n.lang"))

    def help_icon_expressions(self, tag=None):
        icon = "%s-script.gif" % tag if tag else "script.gif"
        doc = tag or "script"
        return ' <a href="//www.%s/doc/%s" target="_blank"><img class="inline-icon" src="/st/icons/%s" alt="" title="%s" /></a>' % (self.main_host, doc, icon, self._("Scripting language reference"))

    @property
    def parser_spec(self):
        inst = self.app().inst
        try:
            return inst._parser_spec
        except AttributeError:
            inst._parser_spec = Parsing.Spec(sys.modules["mg.constructor.script_classes"], skinny=False)
            return inst._parser_spec

    def parse_expression(self, text):
        parser = ScriptParser(self.app(), self.parser_spec)
        try:
            parser.scan(text)
            # Tell the parser that the end of input has been reached.
            try:
                parser.eoi()
            except Parsing.SyntaxError as e:
                raise ScriptParserError("Expression unexpectedly ended", e)
        except ScriptParserResult as e:
            return e.val

    def priority(self, val):
        tp = type(val)
        if tp is not list:
            prio = 100
        elif val is None:
            prio = 100
        else:
            cmd = val[0]
            if cmd == 'glob':
                prio = 100
            elif cmd == "call":
                prio = 99
            elif cmd == '.':
                prio = 98
            elif cmd == '~':
                prio = 10
            elif cmd == '&':
                prio = 9
            elif cmd == '|':
                prio = 8
            elif cmd == '*' or cmd == '/' or cmd == '%':
                prio = 7
            elif cmd == '+' or cmd == '-':
                prio = 6
            elif cmd == "==" or cmd == "!=" or cmd == ">=" or cmd == "<=" or cmd == ">" or cmd == "<" or cmd == "in":
                prio = 5
            elif cmd == "not":
                prio = 4
            elif cmd == "and":
                prio = 3
            elif cmd == "or":
                prio = 2
            elif cmd == '?':
                prio = 1
            elif cmd == 'random':
                prio = 99
            else:
                raise ScriptParserError("Invalid cmd: '%s'" % cmd)
        return prio

    def wrap(self, val, parent, assoc=True):
        """
        If priority of parent operation is higher than val's,
        wrap 'val' in parenthesis.
        Anyway return unparsed value.
        """
        val_priority = self.priority(val)
        parent_priority = self.priority(parent)
        # Do not apply associativity assumptions to different operations.
        # Considering (A OP1 B) OP2 C != A OP1 (B OP2 C)
        if assoc and type(val) == list and val[0] != parent[0]:
            assoc = False
        if val_priority > parent_priority:
            return self.unparse_expression(val)
        elif (val_priority == parent_priority) and assoc:
            return self.unparse_expression(val)
        else:
            return '(%s)' % self.unparse_expression(val)

    def unparse_expression(self, val):
        tp = type(val)
        if tp is list:
            cmd = val[0]
            if cmd == "not":
                return 'not %s' % self.wrap(val[1], val)
            elif cmd == "~":
                return '~%s' % self.wrap(val[1], val)
            elif cmd == "-" and len(val) == 2:
                return '-%s' % self.wrap(val[1], val)
            elif cmd == '+' or cmd == '*' or cmd == "and" or cmd == "or" or cmd == "&" or cmd == "|":
                # (a OP b) OP c == a OP (b OP c)
                return '%s %s %s' % (self.wrap(val[1], val), cmd, self.wrap(val[2], val))
            elif cmd == '-' or cmd == '/' or cmd == '%' or cmd == "==" or cmd == "!=" or cmd == "<=" or cmd == ">=" or cmd == "<" or cmd == ">" or cmd == "in":
                # (a OP b) OP c != a OP (b OP c)
                return '%s %s %s' % (self.wrap(val[1], val), cmd, self.wrap(val[2], val, False))
            elif cmd == '?':
                return '%s ? %s : %s' % (self.wrap(val[1], val, False), self.wrap(val[2], val, False), self.wrap(val[3], val, False))
            elif cmd == '.':
                return '%s.%s' % (self.wrap(val[1], val), val[2])
            elif cmd == "glob":
                return val[1]
            elif cmd == "random":
                return "random"
            elif cmd == "call":
                return "%s(%s)" % (val[1], ", ".join([self.unparse_expression(arg) for arg in val[2:]]))
            else:
                return "<<<%s: %s>>>" % (self._("Invalid script parse tree"), cmd)
        elif tp is str or tp is unicode:
            if not re_dblquote.search(val):
                return '"%s"' % val
            elif not re_sglquote.search(val):
                return "'%s'" % val
            else:
                return '"%s"' % quotestr(val)
        elif tp is Vec3:
            return 'vec3(%s, %s, %s)' % (val.x, val.y, val.z)
        elif val is None:
            return "none"
        elif val is True:
            return 1
        elif val is False:
            return 0
        else:
            return str(val)

    def parse_text(self, text, skip_tokens=None):
        parser = ScriptTextParser(self.app(), self.parser_spec)
        parser.skip_tokens = skip_tokens
        try:
            parser.scan(text)
            # Tell the parser that the end of input has been reached.
            try:
                parser.eoi()
            except Parsing.SyntaxError as e:
                raise ScriptParserError("Expression unexpectedly ended", e)
        except ScriptParserResult as e:
            return e.val

    def unparse_text(self, val):
        if val is None:
            return ""
        if type(val) != list:
            return unicode(val)
        res = ""
        for arg in val:
            ta = type(arg)
            if ta is list:
                cmd = arg[0]
                if cmd == "index":
                    tokens = []
                    empty = True
                    for i in xrange(2, len(arg)):
                        argtxt = self.unparse_text([arg[i]])
                        tokens.append(argtxt)
                        if argtxt.strip():
                            empty = False
                    if not empty:
                        res += u"[%s:%s]" % (self.unparse_expression(arg[1]), ",".join(tokens))
                elif cmd == "numdecl":
                    tokens = []
                    empty = True
                    for i in xrange(2, len(arg)):
                        argtxt = self.unparse_text([arg[i]])
                        tokens.append(argtxt)
                        if argtxt.strip():
                            empty = False
                    if not empty:
                        res += u"[#%s:%s]" % (self.unparse_expression(arg[1]), ",".join(tokens))
                elif cmd == "clsbegin":
                    res += u"{class=%s}" % self.unparse_expression(arg[1])
                elif cmd == "clsend":
                    res += u"{/class}"
                else:
                    res += u'{%s}' % self.unparse_expression(arg)
            elif arg is not None:
                res += u'%s' % arg
        return res

    def evaluate_text(self, tokens, globs=None, used_globs=None, description=None, env=None, keep_globs=None):
        if type(tokens) != list:
            return unicode(tokens)
        if env is None:
            env = ScriptEnvironment()
        # globs
        if globs is not None:
            env.globs = globs
        elif not hasattr(env, "globs"):
            env.globs = {}
        # used_globs
        if used_globs is not None:
            env.used_globs = used_globs
        elif not hasattr(env, "used_globs"):
            env.used_globs = None
        # keep_globs
        if keep_globs is not None:
            env.keep_globs = keep_globs
        elif not hasattr(env, "keep_globs"):
            env.keep_globs = None
        # description
        if description is not None:
            env.description = description
        elif not hasattr(env, "description"):
            env.description = None
        # other fields
        save_val = getattr(env, "val", None)
        save_text = getattr(env, "text", None)
        env.val = tokens
        env.text = True
        # evaluating
        res = []
        partial = False
        for token in tokens:
            if type(token) is list:
                val = self._evaluate(token, env)
                tv = type(val)
                if val is None:
                    pass
                elif keep_globs and (tv is list):
                    partial = True
                    res.append(val)
                elif tv is str or tv is unicode or tv is int or tv is float:
                    res.append(u"%s" % val)
                else:
                    try:
                        res.append(unicode(val))
                    except Exception as e:
                        raise ScriptTypeError(self._("Couldn't convert '{token}' (type '{type}') to string: {exception}").format(token=self.unparse_expression(token), type=type(val).__name__, exception=e.__class__.__name__), env)
            else:
                res.append(u"%s" % token)
        # restoring
        env.val = save_val
        env.text = save_text
        if partial:
            # join sequental strings
            output = []
            for val in res:
                if type(val) == unicode:
                    if output and type(output[-1]) is unicode:
                        output[-1] += val
                        continue
                output.append(val)
            return output
        else:
            res = u"".join(res)
            return res

    def evaluate_expression(self, val, globs=None, used_globs=None, description=None, env=None, keep_globs=None):
        if env is None:
            env = ScriptEnvironment()
        # globs
        if globs is not None:
            env.globs = globs
        elif not hasattr(env, "globs"):
            env.globs = {}
        # used_globs
        if used_globs is not None:
            env.used_globs = used_globs
        elif not hasattr(env, "used_globs"):
            env.used_globs = None
        # keep_globs
        if keep_globs is not None:
            env.keep_globs = keep_globs
        elif not hasattr(env, "keep_globs"):
            env.keep_globs = None
        # description
        if description is not None:
            env.description = description
        elif not hasattr(env, "description"):
            env.description = None
        # other fields
        save_val = getattr(env, "val", None)
        save_text = getattr(env, "text", None)
        env.val = val
        env.text = False
        # evaluating
        res = self._evaluate(val, env)
        # restoring
        env.val = save_val
        env.text = save_text
        return res

    def isString(self, val):
        return type(val) is str or type(val) is unicode

    def toNumber(self, val):
        if type(val) is str or type(val) is unicode:
            return floatz(val)
        elif type(val) is not int and type(val) is not float:
            return 0
        else:
            return val

    def _evaluate(self, val, env):
        if type(val) is not list:
            return val
        # testing stack overflows
        try:
            sys._getframe(900)
        except ValueError:
            pass
        else:
            # this is a real error
            raise ScriptRuntimeError(self._("Max recursion depth exceeded"), env)
        cmd = val[0]
        if cmd == '+':
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Adding None does not affect the value
            if arg1 is None:
                return arg2
            if arg2 is None:
                return arg1
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            # Strings are concatenated
            if self.isString(arg1) and self.isString(arg2):
                return arg1 + arg2
            # Vectors can be added only to vectors
            if isinstance(arg1, Vec3):
                if isinstance(arg2, Vec3):
                    return Vec3(arg1.x + arg2.x, arg1.y + arg2.y, arg1.z + arg2.z)
                else:
                    return None
            if isinstance(arg2, Vec3):
                return None
            # Numeric operation
            arg1 = self.toNumber(arg1)
            arg2 = self.toNumber(arg2)
            return arg1 + arg2
        if cmd == '-':
            if len(val) == 2:
                arg1 = None
                arg2 = self._evaluate(val[1], env)
                # Partial evaluation
                if env.keep_globs and type(arg2) is list:
                    return [cmd, arg2]
            else:
                arg1 = self._evaluate(val[1], env)
                arg2 = self._evaluate(val[2], env)
                # Partial evaluation
                if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                    return [cmd, arg1, arg2]
            # Substracting None does not affect the value
            if arg2 is None:
                return arg1
            # Vectors are substracted only from vectors
            if isinstance(arg1, Vec3):
                if isinstance(arg2, Vec3):
                    return Vec3(arg1.x - arg2.x, arg1.y - arg2.y, arg1.z - arg2.z)
                else:
                    return None
            if isinstance(arg2, Vec3):
                if arg1 is None:
                    return Vec3(-arg2.x, -arg2.y, -arg2.z)
                else:
                    return None
            # Numeric operation
            arg1 = self.toNumber(arg1)
            arg2 = self.toNumber(arg2)
            return arg1 - arg2
        if cmd == '*':
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            # Vectors may be multiplied by numbers only
            if isinstance(arg1, Vec3):
                arg2 = self.toNumber(arg2)
                return Vec3(arg1.x * arg2, arg1.y * arg2, arg1.z * arg2)
            if isinstance(arg2, Vec3):
                arg1 = self.toNumber(arg1)
                return Vec3(arg2.x * arg1, arg2.y * arg1, arg2.z * arg1)
            # Numeric operation
            arg1 = self.toNumber(arg1)
            arg2 = self.toNumber(arg2)
            return arg1 * arg2
        if cmd == '/':
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                if arg2 == 0:
                    return None
                else:
                    return [cmd, arg1, arg2]
            # Vectors may be divided by numbers only
            if isinstance(arg1, Vec3):
                arg2 = self.toNumber(arg2)
                if arg2 == 0:
                    return None
                else:
                    return Vec3(float(arg1.x) / arg2, float(arg1.y) / arg2, float(arg1.z) / arg2)
            # Numeric operation
            arg1 = self.toNumber(arg1)
            arg2 = self.toNumber(arg2)
            if arg2 == 0:
                return None
            else:
                return float(arg1) / arg2
        if cmd == '%':
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                if arg2 == 0:
                    return None
                else:
                    return [cmd, arg1, arg2]
            arg1 = int(self.toNumber(arg1))
            arg2 = int(self.toNumber(arg2))
            if arg2 == 0:
                return None
            else:
                return arg1 % arg2
        elif cmd == "==" or cmd == "!=":
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            if isinstance(arg1, Vec3):
                if isinstance(arg2, Vec3):
                    equals = (arg1.x == arg2.x) and (arg1.y == arg2.y) and (arg1.z == arg2.z)
                else:
                    equals = False
            elif isinstance(arg2, Vec3):
                equals = False
            else:
                s1 = self.isString(arg1)
                s2 = self.isString(arg2)
                # Validating type of the left operand
                if s1 and not s2:
                    arg1 = floatz(arg1)
                # Validating type of the right operand
                if s2 and not s1:
                    arg2 = floatz(arg2)
                equals = arg1 == arg2
            # Evaluating
            if cmd == "==":
                return 1 if equals else 0
            else:
                return 0 if equals else 1
        elif cmd == "in":
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            arg1 = str2unicode(arg1)
            arg2 = str2unicode(arg2)
            return 1 if arg2.find(arg1) >= 0 else 0
        elif cmd == "<" or cmd == ">" or cmd == "<=" or cmd == ">=":
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            if isinstance(arg1, Vec3) and isinstance(arg2, Vec3):
                if arg1.x < arg2.x:
                    res = -1
                elif arg1.x > arg2.x:
                    res = 1
                elif arg1.y < arg2.y:
                    res = -1
                elif arg1.y > arg2.y:
                    res = 1
                elif arg1.z < arg2.z:
                    res = -1
                elif arg1.z > arg2.z:
                    res = 1
                else:
                    res = 0
            else:
                arg1 = self.toNumber(arg1)
                arg2 = self.toNumber(arg2)
                if arg1 < arg2:
                    res = -1
                elif arg1 > arg2:
                    res = 1
                else:
                    res = 0
            if cmd == "<":
                return 1 if res == -1 else 0
            if cmd == ">":
                return 1 if res == 1 else 0
            if cmd == "<=":
                return 1 if res <= 0 else 0
            if cmd == ">=":
                return 1 if res >= 0 else 0
        elif cmd == "~":
            arg1 = self._evaluate(val[1], env)
            # Partial evaluation
            if env.keep_globs and type(arg1) is list:
                return [cmd, arg1]
            arg1 = intz(arg1)
            return ~arg1
        elif cmd == "&":
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            arg1 = intz(arg1)
            arg2 = intz(arg2)
            return arg1 & arg2
        elif cmd == "|":
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            arg1 = intz(arg1)
            arg2 = intz(arg2)
            return arg1 | arg2
        elif cmd == "not":
            arg1 = self._evaluate(val[1], env)
            # Partial evaluation
            if env.keep_globs and type(arg1) is list:
                return [cmd, arg1]
            return 0 if arg1 else 1
        elif cmd == "and":
            arg1 = self._evaluate(val[1], env)
            # Full boolean eval
            if not arg1 and env.used_globs is None:
                return arg1
            arg2 = self._evaluate(val[2], env)
            if not arg1:
                return arg1
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            return arg2
        elif cmd == "or":
            arg1 = self._evaluate(val[1], env)
            # Full boolean eval
            if arg1 and env.used_globs is None and type(arg1) is not list:
                return arg1
            arg2 = self._evaluate(val[2], env)
            if arg1 and type(arg1) is not list:
                return arg1
            # Partial evaluation
            if env.keep_globs and (type(arg1) is list or type(arg2) is list):
                return [cmd, arg1, arg2]
            if arg1:
                return arg1
            return arg2
        elif cmd == '?':
            arg1 = self._evaluate(val[1], env)
            # Partial evaluation
            if env.keep_globs and type(arg1) is list:
                arg2 = self._evaluate(val[2], env)
                arg3 = self._evaluate(val[3], env)
                return [cmd, arg1, arg2, arg3]
            if env.used_globs is None:
                if arg1:
                    return self._evaluate(val[2], env)
                else:
                    return self._evaluate(val[3], env)
            else:
                arg2 = self._evaluate(val[2], env)
                arg3 = self._evaluate(val[3], env)
                if arg1:
                    return arg2
                else:
                    return arg3
        elif cmd == "call":
            fname = val[1]
            if fname == "min" or fname == "max":
                res = None
                res_unprocessed = []
                for i in xrange(2, len(val)):
                    v = self._evaluate(val[i], env)
                    # Partial evaluation
                    if env.keep_globs and type(v) is list:
                        res_unprocessed.append(v)
                        continue
                    if type(v) is str or type(v) is unicode:
                        v = floatz(v)
                    elif type(v) is not int and type(v) is not float:
                        v = 0
                    if fname == "min":
                        if res is None or v < res:
                            res = v
                    elif fname == "max":
                        if res is None or v > res:
                            res = v
                if res_unprocessed:
                    if res is not None:
                        res_unprocessed.append(res)
                    return [cmd, fname] + res_unprocessed
                return res
            elif fname == "lc" or fname == "uc":
                if len(val) != 3:
                    raise ScriptRuntimeError(self._("Function {fname} must be called with single argument").format(fname=fname), env)
                v = self._evaluate(val[2], env)
                # Partial evaluation
                if env.keep_globs and type(v) is list:
                    return [cmd, fname, v]
                v = str2unicode(v)
                if fname == "lc":
                    return v.lower()
                elif fname == "uc":
                    return v.upper()
            elif fname == "selrand":
                if len(val) >= 3:
                    args = val[2:]
                    # Partial evaluation
                    if env.keep_globs:
                        return [cmd, fname] + [self._evaluate(v, env) for v in args]
                    return self._evaluate(random.choice(args), env)
                return None
            elif fname == "floor" or fname == "round" or fname == "ceil" or fname == "abs" or fname == "sqrt" or fname == "sqr" or fname == "log" or fname == "exp" or fname == "sin" or fname == "cos" or fname == "tan" or fname == "asin" or fname == "acos" or fname == "atan":
                if len(val) != 3:
                    raise ScriptRuntimeError(self._("Function {fname} must be called with single argument").format(fname=fname), env)
                v = self._evaluate(val[2], env)
                # Partial evaluation
                if env.keep_globs and type(v) is list:
                    return [cmd, fname, v]
                if type(v) is str or type(v) is unicode:
                    v = floatz(v)
                elif type(v) is not int and type(v) is not float:
                    v = 0
                try:
                    if fname == "floor":
                        return math.floor(v)
                    elif fname == "round":
                        return round(v)
                    elif fname == "ceil":
                        return math.ceil(v)
                    elif fname == "abs":
                        return abs(v)
                    elif fname == "sqrt":
                        return math.sqrt(v)
                    elif fname == "sqr":
                        return v * v
                    elif fname == "log":
                        return math.log(v)
                    elif fname == "exp":
                        return math.exp(v)
                    elif fname == "sin":
                        return math.sin(v)
                    elif fname == "cos":
                        return math.cos(v)
                    elif fname == "tan":
                        return math.tan(v)
                    elif fname == "asin":
                        return math.asin(v)
                    elif fname == "acos":
                        return math.acos(v)
                    elif fname == "atan":
                        return math.atan(v)
                except ValueError:
                    return float('nan')
            elif fname == "pow":
                if len(val) != 4:
                    raise ScriptRuntimeError(self._("Function {fname} must be called with two arguments").format(fname=fname), env)
                v1 = self._evaluate(val[2], env)
                v2 = self._evaluate(val[3], env)
                # Partial evaluation
                if env.keep_globs and (type(v1) is list or type(v2) is list):
                    return [cmd, fname, v1, v2]
                if type(v1) is str or type(v1) is unicode:
                    v1 = floatz(v1)
                elif type(v1) is not int and type(v1) is not float:
                    v1 = 0
                if type(v2) is str or type(v2) is unicode:
                    v2 = floatz(v2)
                elif type(v2) is not int and type(v2) is not float:
                    v2 = 0
                try:
                    return math.pow(v1, v2)
                except ValueError:
                    return float('nan')
            elif fname == "vec3":
                if len(val) != 5:
                    raise ScriptRuntimeError(self._("Function {fname} must be called with three arguments").format(fname=fname), env)
                arg1 = self._evaluate(val[2], env)
                arg2 = self._evaluate(val[3], env)
                arg3 = self._evaluate(val[4], env)
                # Partial evaluation
                if env.keep_globs and (type(arg1) is list or type(arg2) is list or type(arg3) is list):
                    return [cmd, fname, arg1, arg2, arg3]
                arg1 = self.toNumber(arg1)
                arg2 = self.toNumber(arg2)
                arg3 = self.toNumber(arg3)
                return Vec3(arg1, arg2, arg3)
            else:
                raise ScriptRuntimeError(self._("Function {fname} is not supported in expression context").format(fname=fname), env)
        elif cmd == "random":
            # Partial evaluation
            if env.keep_globs:
                return [cmd]
            return random.random()
        elif cmd == "glob":
            name = val[1]
            # Partial evaluation
            if env.keep_globs and env.keep_globs.get(name):
                return [cmd, name]
            if name not in env.globs:
                return None
            obj = env.globs.get(name)
            if env.used_globs is not None:
                env.used_globs.add(name)
            if callable(obj):
                obj = obj()
                env.globs[name] = obj
            return obj
        elif cmd == ".":
            obj = self._evaluate(val[1], env)
            field = val[2]
            # Partial evaluation
            if env.keep_globs and type(obj) is list:
                return [cmd, obj, field]
            if obj is None:
                raise ScriptTypeError(self._("Empty value '{val}' has no attributes").format(val=self.unparse_expression(val[1])), env)
            if type(obj) is int:
                raise ScriptTypeError(self._("Integer '{val}' has no attributes").format(val=self.unparse_expression(val[1])), env)
            if type(obj) is float:
                raise ScriptTypeError(self._("Float '{val}' has no attributes").format(val=self.unparse_expression(val[1])), env)
            if type(obj) is str or type(obj) is str:
                raise ScriptTypeError(self._("String '{val}' has no attributes").format(val=self.unparse_expression(val[1])), env)
            getter = getattr(obj, "script_attr", None)
            if getter is None:
                raise ScriptTypeError(self._("Object '{val}' has no attributes").format(val=self.unparse_expression(val[1])), env)
            try:
                attval = getter(field, handle_exceptions=False)
            except AttributeError as e:
                raise ScriptTypeError(self._("Object '{val}' has no attribute '{att}'").format(val=self.unparse_expression(val[1]), att=field), env)
            return attval
        elif cmd == "index":
            if len(val) < 3:
                return None
            index = self._evaluate(val[1], env)
            # Partial evaluation
            if env.keep_globs and type(index) is list:
                return [cmd, index] + val[2:]
            index = intz(index) + 2
            if index < 2:
                index = 2
            if index >= len(val):
                index = len(val) - 1
            return val[index]
        elif cmd == "numdecl":
            if len(val) < 3:
                return None
            arg = self._evaluate(val[1], env)
            # Partial evaluation
            if env.keep_globs and type(arg) is list:
                return [cmd, arg] + val[2:]
            return self.call("l10n.literal_value", intz(arg), val[2:])
        elif cmd == "clsbegin":
            arg = self._evaluate(val[1], env)
            # Partial evaluation
            if env.keep_globs and type(arg) is list:
                return [cmd, arg]
            return self.formatter(env).clsbegin(arg)
        elif cmd == "clsend":
            return self.formatter(env).clsend()
        else:
            raise ScriptRuntimeError(self._("Unknown script engine operation: {op}").format(op=cmd), env)

    def formatter(self, env):
        return getattr(env, "formatter", HTMLFormatter)

    def validate_expression(self, *args, **kwargs):
        kwargs["text"] = False
        return self.validate(*args, **kwargs)

    def validate_text(self, *args, **kwargs):
        kwargs["text"] = True
        return self.validate(*args, **kwargs)

    def validate(self, val, globs={}, require_glob=None, text=False):
        if require_glob:
            used_globs = set()
        else:
            used_globs = None
        env = ScriptEnvironment()
        if text:
            self.evaluate_text(val, globs=globs, used_globs=used_globs, env=env)
        else:
            self.evaluate_expression(val, globs=globs, used_globs=used_globs, env=env)
        if require_glob:
            for name in require_glob:
                if name not in used_globs:
                    raise ScriptUnusedError(self._("You must use global variable '{var}' in your expression").format(var=name), env)

    def admin_expression(self, *args, **kwargs):
        kwargs["text"] = False
        return self.admin_field(*args, **kwargs)

    def admin_text(self, *args, **kwargs):
        kwargs["text"] = True
        return self.admin_field(*args, **kwargs)

    def admin_field(self, name, errors, globs={}, require_glob=None, text=False, skip_tokens=None, expression=None, mandatory=True):
        req = self.req()
        if expression is None:
            expression = req.param(name).strip()
        if expression == "":
            if mandatory:
                errors[name] = self._("This field is mandatory")
                return
            else:
                return None
        # Parsing
        try:
            if text:
                expression = self.call("script.parse-text", expression, skip_tokens=skip_tokens)
            else:
                expression = self.call("script.parse-expression", expression)
        except ScriptParserError as e:
            html = e.val.format(**e.kwargs)
            if e.exc:
                html += "\n%s" % e.exc
            errors[name] = html
            return
        # Evaluating
        try:
            self.validate(expression, globs=globs, require_glob=require_glob, text=text)
        except ScriptError as e:
            errors[name] = e.val
            return
        # Returning result
        return expression

    def exception_report(self, exception, e_type=None, e_value=None, e_traceback=None):
        if not isinstance(exception, ScriptError) and not isinstance(exception, TemplateException):
            return
        try:
            if e_type is None:
                e_type, e_value, e_traceback = sys.exc_info()
            try:
                req = self.req()
            except AttributeError:
                req = None
            project = self.app().project
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
                try:
                    if env.text:
                        vars["expression"] = htmlescape(self.call("script.unparse-text", env.val))
                    else:
                        vars["expression"] = htmlescape(self.call("script.unparse-expression", env.val))
                except AttributeError:
                    pass
            subj = utf2str(repr(exception))
            content = self.call("web.parse_template", "constructor/script-exception.html", vars)
            self.call("email.send", email, name, subj, content, immediately=True, subtype="html")
            raise Hooks.Return()
        except Hooks.Return:
            raise
        except Exception as e:
            self.critical("Exception during exception reporting: %s", "".join(traceback.format_exception(e_type, e_value, e_traceback)))

