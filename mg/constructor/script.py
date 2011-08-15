from mg import *
from mg.constructor import *
from mg.constructor.script_classes import *
import re
import traceback

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

    def help_icon_expressions(self):
        return ' <a href="//www.%s/doc/script" target="_blank"><img class="inline-icon" src="/st/icons/script.gif" alt="" title="%s" /></a>' % (self.app().inst.config["main_host"], self._("Scripting language reference"))

    @property
    def parser_spec(self):
        inst = self.app().inst
        try:
            return inst._parser_spec
        except AttributeError:
            inst._parser_spec = Parsing.Spec(sys.modules[__name__], skinny=False)
            return inst._parser_spec

    def parse_expression(self, text):
        parser = ScriptParser(self.app(), self.parser_spec)
        try:
            parser.scan(text)
            # Tell the parser that the end of input has been reached.
            try:
                parser.eoi()
            except Parsing.SyntaxError as e:
                raise ScriptParserError("Expression unexpectedly ended", exc)
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
                prio = 8
            elif cmd == '*' or cmd == '/':
                prio = 7
            elif cmd == '+' or cmd == '-':
                prio = 6
            elif cmd == "==" or cmd == ">=" or cmd == "<=" or cmd == ">" or cmd == "<":
                prio = 5
            elif cmd == "not":
                prio = 4
            elif cmd == "and":
                prio = 3
            elif cmd == "or":
                prio = 2
            elif cmd == '?':
                prio = 1
            else:
                raise ScriptParserError("Invalid cmd: '%s'" % cmd)
        return prio

    def wrap(self, val, parent, assoc=True):
        # If priority of parent operation is higher than ours
        # wrap in parenthesis
        val_priority = self.priority(val)
        parent_priority = self.priority(parent)
        if val_priority > parent_priority:
            return self.unparse_expression(val)
        elif val_priority == parent_priority and assoc:
            return self.unparse_expression(val)
        else:
            return '(%s)' % self.unparse_expression(val)

    def unparse_expression(self, val):
        tp = type(val)
        if tp is list:
            cmd = val[0]
            if cmd == "not":
                return 'not %s' % self.wrap(val[1], val)
            elif cmd == '+' or cmd == '*' or cmd == "and" or cmd == "or":
                # (a OP b) OP c == a OP (b OP c)
                return '%s %s %s' % (self.wrap(val[1], val), cmd, self.wrap(val[2], val))
            elif cmd == '-' or cmd == '/' or cmd == "==" or cmd == "<=" or cmd == ">=" or cmd == "<" or cmd == ">":
                # (a OP b) OP c != a OP (b OP c)
                return '%s %s %s' % (self.wrap(val[1], val), cmd, self.wrap(val[2], val, False))
            elif cmd == '?':
                return '%s ? %s : %s' % (self.wrap(val[1], val, False), self.wrap(val[2], val, False), self.wrap(val[3], val, False))
            elif cmd == '.':
                return '%s.%s' % (self.wrap(val[1], val), val[2])
            elif cmd == 'glob':
                return val[1]
            elif cmd == "call":
                return "%s(%s)" % (val[1], ", ".join([self.unparse_expression(arg) for arg in val[2:]]))
            else:
                raise ScriptParserError("Invalid cmd: '%s'" % cmd)
        elif tp is str or tp is unicode:
            if '"' in val:
                return "'%s'" % val
            else:
                return '"%s"' % val
        elif val is None:
            return "none"
        else:
            return str(val)

    def parse_text(self, text):
        parser = ScriptTextParser(self.app(), self.parser_spec)
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
                else:
                    res += u'{%s}' % self.unparse_expression(arg)
            elif arg is not None:
                res += u'%s' % arg
        return res

    def evaluate_text(self, tokens, globs={}, used_globs=None, description=None, env=None):
        if type(tokens) != list:
            return unicode(tokens)
        if env is None:
            env = ScriptEnvironment()
        env.globs = globs
        env.used_globs = used_globs
        env.description = description
        env.val = tokens
        env.text = True
        res = u""
        for token in tokens:
            if type(token) is list:
                val = self._evaluate(token, env)
                tv = type(val)
                if tv is None:
                    pass
                elif tv is str or tv is unicode or tv is int or tv is float:
                    res += u"%s" % val
                else:
                    raise ScriptTypeError(self._("Couldn't convert '{token}' (type '{type}') to string").format(token=self.unparse_expression(token), type=type(val).__name__), env)
            else:
                res += u"%s" % token
        return res

    def evaluate_expression(self, val, globs={}, used_globs=None, description=None, env=None):
        if env is None:
            env = ScriptEnvironment()
        env.globs = globs
        env.used_globs = used_globs
        env.description = description
        env.val = val
        env.text = False
        return self._evaluate(val, env)

    def _evaluate(self, val, env):
        if type(val) is not list:
            return val
        cmd = val[0]
        if cmd == '+' or cmd == '-' or cmd == '*' or cmd == '/':
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Strings concatenation
            if cmd == '+' and (type(arg1) is str or type(arg1) is unicode) and (type(arg2) is str or type(arg2) is unicode):
                return arg1 + arg2
            # Validating type of the left operand
            if type(arg1) is str or type(arg1) is unicode:
                arg1 = floatz(arg1)
            elif type(arg1) is not int and type(arg1) is not float:
                raise ScriptTypeError(self._("Left operand of '{operator}' must be numeric ('{val}' is '{type}')").format(operator=cmd, val=self.unparse_expression(val[1]), type=type(arg1).__name__), env)
            # Validating type of the right operand
            if type(arg2) is str or type(arg2) is unicode:
                arg2 = floatz(arg2)
            elif type(arg2) is not int and type(arg2) is not float:
                raise ScriptTypeError(self._("Right operand of '{operator}' must be numeric ('{val}' is {type}'").format(operator=cmd, val=self.unparse_expression(val[2]), type=type(arg2).__name__), env)
            # Evaluating
            if cmd == '+':
                return arg1 + arg2
            elif cmd == '-':
                return arg1 - arg2
            elif cmd == '*':
                return arg1 * arg2
            elif cmd == '/':
                if arg2 == 0:
                    raise ScriptRuntimeError(self._("Division by zero: '{val}' == 0").format(val=self.unparse_expression(val[2])), env)
                else:
                    return float(arg1) / arg2
        elif cmd == "==":
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            s1 = type(arg1) is str or type(arg1) is unicode
            s2 = type(arg2) is str or type(arg2) is unicode
            # Validating type of the left operand
            if s1 and not s2:
                arg1 = floatz(arg1)
            # Validating type of the right operand
            if s2 and not s1:
                arg2 = floatz(arg2)
            # Evaluating
            return 1 if arg1 == arg2 else 0
        elif cmd == "<" or cmd == ">" or cmd == "<=" or cmd == ">=":
            arg1 = self._evaluate(val[1], env)
            arg2 = self._evaluate(val[2], env)
            # Validating type of the left operand
            if type(arg1) is str or type(arg1) is unicode:
                arg1 = floatz(arg1)
            elif type(arg1) is not int and type(arg1) is not float:
                raise ScriptTypeError(self._("Left operand of '{operator}' must be numeric ('{val}' is '{type}')").format(operator=cmd, val=self.unparse_expression(val[1]), type=type(arg1).__name__), env)
            # Validating type of the right operand
            if type(arg2) is str or type(arg2) is unicode:
                arg2 = floatz(arg2)
            elif type(arg2) is not int and type(arg2) is not float:
                raise ScriptTypeError(self._("Right operand of '{operator}' must be numeric ('{val}' is '{type}')").format(operator=cmd, val=self.unparse_expression(val[2]), type=type(arg2).__name__), env)
            if cmd == "<":
                return 1 if arg1 < arg2 else 0
            if cmd == ">":
                return 1 if arg1 > arg2 else 0
            if cmd == "<=":
                return 1 if arg1 <= arg2 else 0
            if cmd == ">=":
                return 1 if arg1 >= arg2 else 0
        elif cmd == "not":
            arg1 = self._evaluate(val[1], env)
            return 0 if arg1 else 1
        elif cmd == "and":
            arg1 = self._evaluate(val[1], env)
            # Full boolean eval
            if not arg1 and env.used_globs is None:
                return arg1
            arg2 = self._evaluate(val[2], env)
            if not arg1:
                return arg1
            return arg2
        elif cmd == "or":
            arg1 = self._evaluate(val[1], env)
            # Full boolean eval
            if arg1 and env.used_globs is None:
                return arg1
            arg2 = self._evaluate(val[2], env)
            return arg2
        elif cmd == '?':
            arg1 = self._evaluate(val[1], env)
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
                for i in xrange(2, len(val)):
                    v = self._evaluate(val[i], env)
                    if type(v) is str or type(v) is unicode:
                        v = floatz(v)
                    elif type(v) is not int and type(v) is not float:
                        raise ScriptTypeError(self._("Arguments of '{func}' must be numeric ('{val}' is '{type}')").format(func=fname, val=self.unparse_expression(val[i]), type=type(v).__name__), env)
                    if fname == "min":
                        if res is None or v < res:
                            res = v
                    elif fname == "max":
                        if res is None or v > res:
                            res = v
                return res
            else:
                raise ScriptRuntimeError(self._("Unknown script engine function: {fname}").format(fname=fname), env)
        elif cmd == "glob":
            name = val[1]
            if name not in env.globs:
                raise ScriptUnknownVariableError(self._("Global variable '{glob}' not found").format(glob=name), env)
            obj = env.globs.get(name)
            if env.used_globs is not None:
                env.used_globs.add(name)
            return obj
        elif cmd == ".":
            obj = self._evaluate(val[1], env)
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
                attval = getter(val[2])
            except AttributeError:
                raise ScriptTypeError(self._("Object '{val}' has no attribute '{att}'").format(val=self.unparse_expression(val[1]), att=val[2]), env)
            return attval
        elif cmd == "index":
            index = intz(self._evaluate(val[1], env)) + 2
            if index < 2:
                index = 2
            if index >= len(val):
                index = len(val) - 1
            return val[index]
        else:
            raise ScriptRuntimeError(self._("Unknown script engine operation: {op}").format(op=cmd), env)

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

    def admin_field(self, name, errors, globs={}, require_glob=None, text=False):
        req = self.req()
        expression = req.param(name)
        if not expression:
            errors[name] = self._("This field is mandatory")
            return
        # Parsing
        try:
            if text:
                expression = self.call("script.parse-text", expression)
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

    def exception_report(self, exception):
        if not issubclass(type(exception), ScriptError):
            return
        try:
            req = self.req()
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
            for key, values in req.param_dict().iteritems():
                params.append({"key": htmlescape(key), "values": []})
                for val in values:
                    params[-1]["values"].append(htmlescape(val))
            if len(params):
                vars["params"] = params
            vars["host"] = htmlescape(req.host())
            vars["uri"] = htmlescape(req.uri())
            session = req.session()
            if session:
                vars["session"] = session.data_copy()
            vars["text"] = htmlescape(exception.val)
            vars["context"] = htmlescape(exception.env.description)
            if exception.env.text:
                vars["expression"] = htmlescape(self.call("script.unparse-text", exception.env.val))
            else:
                vars["expression"] = htmlescape(self.call("script.unparse-expression", exception.env.val))
            subj = u"%s" % exception
            content = self.call("web.parse_template", "constructor/script-exception.html", vars)
            self.call("email.send", email, name, subj, content, immediately=True, subtype="html")
            raise Hooks.Return()
        except Hooks.Return:
            raise
        except Exception as e:
            self.critical("Exception during exception reporting: %s", traceback.format_exc())

