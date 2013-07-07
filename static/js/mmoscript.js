/*
 * MMOScriptHTMLFormatter class is a formatter instance that converts
 * {class=...}...{/class} to HTML-valid <span class="...">...</span>
 * constructions.
 */
function MMOScriptHTMLFormatter()
{
}

MMOScriptHTMLFormatter.prototype.clsBegin = function (clsname) {
    return '<span class="' + clsname + '">';
};

MMOScriptHTMLFormatter.prototype.clsEnd = function () {
    return '</span>';
};

var MMOScript = {
    unaryOps: {
        'not': true,
        '~': true
    },
    binaryOps: {
        '+': true,
        '-': true,
        '*': true,
        '/': true,
        '==': true,
        '!=': true,
        'in': true,
        '<': true,
        '>': true,
        '<=': true,
        '>=': true,
        'and': true,
        'or': true,
        '&': true,
        '|': true
    },
    ternaryOps: {
        '?': true
    },
    defaultFormatter: new MMOScriptHTMLFormatter(),
    lang: 'en'
};

/*
 * Evaluate MMO Script expression
 *
 * @param{String} val       Syntax tree
 * @param{Object} env       Environment
 *      env.globs           Dictionary of global variables
 *
 * @returns                 Evaluated value
 *
 */
MMOScript.evaluate = function (val, env) {
    var self = this;
    if (typeof(val) != 'object') {
        return val;
    }
    var cmd = val[0];
    if (cmd == '+' || cmd == '-' || cmd == '*' || cmd == '/') {
        var arg1 = self.evaluate(val[1], env);
        var arg2 = self.evaluate(val[2], env);
        // concanenation
        if (cmd == '+' && self.isString(arg1) && self.isString(arg2)) {
            return arg1 + arg2;
        }
        // operation with numbers
        arg1 = self.toNumber(arg1);
        arg2 = self.toNumber(arg2);
        if (cmd == '+') {
            return arg1 + arg2;
        }
        if (cmd == '-') {
            return arg1 - arg2;
        }
        if (cmd == '*') {
            return arg1 * arg2;
        }
        if (cmd == '/') {
            return arg1 / arg2;
        }
    }
    if (cmd == '==' || cmd == '!=') {
        var arg1 = self.evaluate(val[1], env);
        var arg2 = self.evaluate(val[2], env);
        var s1 = self.isString(arg1);
        var s2 = self.isString(arg2);
        if (s1 && !s2) {
            arg1 = self.toNumber(arg1);
        } else if (s2 && !s1) {
            arg2 = self.toNumber(arg2);
        }
        if (cmd == '==') {
            return (arg1 == arg2) ? 1 : 0;
        } else {
            return (arg1 != arg2) ? 1 : 0;
        }
    }
    if (cmd == 'in') {
        var arg1 = self.toString(self.evaluate(val[1], env));
        var arg2 = self.toString(self.evaluate(val[2], env));
        return (arg2.indexOf(arg1) >= 0) ? 1 : 0;
    }
    if (cmd == '<' || cmd == '>' || cmd == '<=' || cmd == '>=') {
        var arg1 = self.toNumber(self.evaluate(val[1], env));
        var arg2 = self.toNumber(self.evaluate(val[2], env));
        if (cmd == '<') {
            return (arg1 < arg2) ? 1 : 0;
        }
        if (cmd == '>') {
            return (arg1 > arg2) ? 1 : 0;
        }
        if (cmd == '<=') {
            return (arg1 <= arg2) ? 1 : 0;
        }
        if (cmd == '>=') {
            return (arg1 >= arg2) ? 1 : 0;
        }
    }
    if (cmd == '~') {
        var arg1 = Math.floor(self.toNumber(self.evaluate(val[1], env)));
        return ~arg1;
    }
    if (cmd == '&') {
        var arg1 = Math.floor(self.toNumber(self.evaluate(val[1], env)));
        var arg2 = Math.floor(self.toNumber(self.evaluate(val[2], env)));
        return arg1 & arg2;
    }
    if (cmd == '|') {
        var arg1 = Math.floor(self.toNumber(self.evaluate(val[1], env)));
        var arg2 = Math.floor(self.toNumber(self.evaluate(val[2], env)));
        return arg1 | arg2;
    }
    if (cmd == 'not') {
        var arg1 = self.evaluate(val[1], env);
        return arg1 ? 0 : 1;
    }
    if (cmd == 'and') {
        var arg1 = self.evaluate(val[1], env);
        if (!arg1) {
            return arg1;
        }
        var arg2 = self.evaluate(val[2], env);
        return arg2;
    }
    if (cmd == 'or') {
        var arg1 = self.evaluate(val[1], env);
        if (arg1) {
            return arg1;
        }
        var arg2 = self.evaluate(val[2], env);
        return arg2;
    }
    if (cmd == '?') {
        var arg1 = self.evaluate(val[1], env);
        if (arg1) {
            return self.evaluate(val[2], env);
        } else {
            return self.evaluate(val[3], env);
        }
    }
    if (cmd == 'call') {
        var fname = val[1];
        if (fname == 'min' || fname == 'max') {
            var res = undefined;
            for (var i = 2; i < val.length; i++) {
                var v = self.toNumber(self.evaluate(val[i], env));
                if (fname == 'min') {
                    if (res === undefined || v < res) {
                        res = v;
                    }
                } else if (fname == 'max') {
                    if (res === undefined || v > res) {
                        res = v;
                    }
                }
            }
            return res;
        }
        if (fname == 'lc' || fname == 'uc') {
            var v = self.toString(self.evaluate(val[2], env));
            if (fname == 'lc') {
                return v.toLower();
            } else {
                return v.toUpper();
            }
        }
        if (fname == 'selrand') {
            var index = Math.floor(Math.random() * (val.length - 2));
            if (index >= 2 && index < val.length) {
                return self.evaluate(val[i], env);
            }
            return undefined;
        }
        if (fname == 'floor' || fname == 'round' || fname == 'ceil' || fname == 'abs' ||
                fname == 'sqrt' || fname == 'exp' || fname == 'sin' || fname == 'cos' ||
                fname == 'tan' || fname == 'asin' || fname == 'acos' || fname == 'atan' ||
                fname == 'log') {
            var v = self.toNumber(self.evaluate(val[2], env));
            return Math[fname](v);
        }
        if (fname == 'sqr') {
            var v = self.toNumber(self.evaluate(val[2], env));
            return v * v;
        }
        if (fname == 'pow') {
            var v1 = self.toNumber(self.evaluate(val[2], env));
            var v2 = self.toNumber(self.evaluate(val[3], env));
            return Math.pow(v1, v2);
        }
        return undefined;
    }
    if (cmd == 'random') {
        return Math.random();
    }
    if (cmd == 'glob') {
        var name = val[1];
        if (!env.globs) {
            return undefined;
        }
        return env.globs[name];
    }
    if (cmd == '.') {
        var obj = self.evaluate(val[1], env);
        if (obj) {
            if (obj.scriptAttr) {
                return obj.scriptAttr(val[2]);
            } else {
                return obj[val[2]];
            }
        }
        return undefined;
    }
    if (cmd == 'index') {
        if (val.length < 3) {
            return undefined;
        }
        var index = Math.floor(self.toNumber(self.evaluate(val[1], env))) + 2;
        if (index < 2) {
            index = 2;
        }
        if (index >= val.length) {
            index = val.length - 1;
        }
        return val[index];
    }
    if (cmd == 'numdecl') {
        var num = self.toNumber(self.evaluate(val[1], env));
        if (self.lang == 'ru') {
            if (num != Math.floor(num)) {
                return val[3];
            }
            if ((num % 100) >= 10 && (num % 100) <= 20) {
                return val[4];
            }
            if ((num % 10) >= 2 && (num % 10) <= 4) {
                return val[3];
            }
            if ((num % 10) == 1) {
                return val[2];
            }
            return val[4];
        }
        // English fallback
        if (num == 1) {
            return val[2];
        }
        return val[3];
    }
    if (cmd == 'clsbegin') {
        return self.formatter(env).clsBegin(self.evaluate(val[1]));
    }
    if (cmd == 'clsend') {
        return self.formatter(env).clsEnd();
    }
    return undefined;
};

/*
 * Return string formatter object to convert various {class=...}...{/class} to
 * output in desired string format.
 */
MMOScript.formatter = function (env) {
    return env.formatter || MMOScript.defaultFormatter;
};

/*
 * Traverse MMO Script syntax tree and extract all used parameters
 *
 * @param{String} val       Syntax tree
 * 
 * @returns{Array}          List of parameters. Every parameter is an
 *      array of components. For example: member.p_hp => ["member", "p_hp"]
 *
 */
MMOScript.dependencies = function (val) {
    var self = this;
    var res = {};
    self._dependencies(val, res);
    var resList = [];
    for (var key in res) {
        if (res.hasOwnProperty(key)) {
            resList.push(key.split('.'));
        }
    }
    return resList;
}

/*
 * Traverse MMO Script string syntax tree and extract all used parameters
 *
 * @param{String} val       String syntax tree
 * 
 * @returns{Array}          List of parameters. Every parameter is an
 *      array of components. For example: member.p_hp => ["member", "p_hp"]
 *
 */
MMOScript.dependenciesText = function (val) {
    var self = this;
    if (!val || !val.length) {
        return [];
    }
    if (typeof(val) === 'string') {
        return [];
    }
    var res = {};
    for (var i = 0; i < val.length; i++) {
        self._dependencies(val[i], res);
    }
    var resList = [];
    for (var key in res) {
        if (res.hasOwnProperty(key)) {
            resList.push(key.split('.'));
        }
    }
    return resList;
}

/*
 * Traverse MMO Script syntax tree and extract all used parameters.
 * Found parameters are stored in dict "res"
 */
MMOScript._dependencies = function (val, res) {
    var self = this;
    if (!val) {
        return;
    }
    var cmd = val[0];
    if (self.binaryOps[cmd]) {
        self._dependencies(val[1], res);
        self._dependencies(val[2], res);
    } else if (self.unaryOps[cmd] || cmd == 'index' || cmd == 'numdecl') {
        self._dependencies(val[1], res);
    } else if (self.ternaryOps[cmd]) {
        self._dependencies(val[1], res);
        self._dependencies(val[2], res);
        self._dependencies(val[3], res);
    } else if (cmd == 'call') {
        for (var i = 2; i < val.length; i++) {
            self._dependencies(val[i], res);
        }
    } else if (cmd == 'glob') {
        res[val[1]] = true;
    } else if (cmd == '.') {
        var varname = self._varname(val);
        if (varname) {
            res[varname] = true;
        }
    }
};

/*
 * Parse syntax tree like [".", ["glob", "combat"], "member"] and return parsed
 * name: "combat.member" or undefined if passed value is not varname
 */
MMOScript._varname = function (val) {
    var self = this;
    var cmd = val[0];
    if (cmd == 'glob') {
        return val[1];
    } else if (cmd == '.') {
        var varname = self._varname(val[1]);
        if (varname) {
            return varname + '.' + val[2];
        }
    }
    return undefined;
};

/*
 * Evaluate MMO Script text expression
 *
 * @param{String} val       Syntax tree
 * @param{Object} env       Environment
 *      env.globs           Dictionary of global variables
 *
 * @returns                 Evaluated string
 *
 */
MMOScript.evaluateText = function (val, env) {
    var self = this;
    if (typeof(val) !== 'object' || val.length == undefined) {
        return self.toString(val);
    }
    var res = '';
    for (var i = 0; i < val.length; i++) {
        var ent = val[i];
        if (typeof(ent) === 'object') {
            res += self.toString(self.evaluate(ent, env));
        } else {
            res += self.toString(ent);
        }
    }
    return res;
};

/*
 * Return true if val is string
 */
MMOScript.isString = function (val) {
    return typeof(val) == 'string';
};

/*
 * Return true if val is a number
 */
MMOScript.isNumber = function (val) {
    return typeof(val) == 'number';
};

/*
 * Convert passed arg to number. Unknown values
 * interpreted as 0.
 */
MMOScript.toNumber = function (val) {
    if (typeof(val) != 'number') {
        try {
            val = parseFloat(val);
        } catch (e) {
            val = 0;
        }
    }
    return val;
};

/*
 * Return string representation of passed value
 */
MMOScript.toString = function (val) {
    if (typeof(val) == 'undefined' || val == null) {
        return '';
    }
    return val + '';
};

/*
 * Dynamic Value is a function(t) representing a value changing
 * with time.
 */
function DynamicValue(val)
{
    var self = this;
    if (typeof(val) != 'object') {
        self.staticValue = val;
    } else {
        self.dynamic = true;
        self.expr = val;
    }
}

/*
 * Set maximal time until evaluation of the expression
 * should be performed.
 */
DynamicValue.prototype.setTill = function (till) {
    var self = this;
    self.till = till;
    self.tillDefined = true;
};

/*
 * Forget expression if "till" is set before specified time
 */
DynamicValue.prototype.forget = function (before) {
    var self = this;
    if (self.dynamic && self.tillDefined && self.till <= before) {
        self.staticValue = self.evaluate(self.till);
        self.dynamic = false;
    }
};

/*
 * Evaluate and return current value
 */
DynamicValue.prototype.evaluate = function (t) {
    var self = this;
    if (self.dynamic) {
        if (self.tillDefined && t > self.till) {
            t = self.till;
        }
        var env = {
            globs: {
                t: t
            }
        };
        return MMOScript.evaluate(self.expr, env);
    } else {
        return self.staticValue;
    }
};

/*
 * Evaluate and forget dynamic expression if "till" time passed
 */
DynamicValue.prototype.evaluateAndForget = function (t) {
    var self = this;
    self.forget(t);
    return self.evaluate(t);
};

loaded('mmoscript');
