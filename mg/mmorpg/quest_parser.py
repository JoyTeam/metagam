from mg.core import Parsing
from mg.constructor.script_classes import *

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_param = re.compile(r'^p_([a-z_][a-z0-9_]*)$', re.IGNORECASE)
re_valid_template = re.compile(r'^[a-zA-Z][a-zA-Z0-9\-]*\.html$')

# To add a new event, condition or action:
#   1. create TokenXXX class
#   2. assign it a terminal symbol: syms["xxx"] = TokenXXX
#   3. write the syntax rule
#   4. write unparsing rule in mg.mmorpg.quests
#   5. implement the feature

class TokenEvent(Parsing.Token):
    "%token event"

class TokenTeleported(Parsing.Token):
    "%token teleported"

class TokenMessage(Parsing.Token):
    "%token message"

class TokenError(Parsing.Token):
    "%token error"

class TokenRequire(Parsing.Token):
    "%token require"

class TokenCall(Parsing.Token):
    "%token call"

class TokenGive(Parsing.Token):
    "%token give"

class TokenTake(Parsing.Token):
    "%token take"

class TokenIf(Parsing.Token):
    "%token if"

class TokenElse(Parsing.Token):
    "%token else"

class TokenFinish(Parsing.Token):
    "%token finish" 

class TokenFail(Parsing.Token):
    "%token fail"

class TokenLock(Parsing.Token):
    "%token lock"

class TokenExpired(Parsing.Token):
    "%token expired"

class TokenTimer(Parsing.Token):
    "%token timer"

class TokenTimeout(Parsing.Token):
    "%token timeout"

class TokenItemUsed(Parsing.Token):
    "%token itemused"

class TokenDialog(Parsing.Token):
    "%token dialog"

class TokenText(Parsing.Token):
    "%token text"

class TokenButton(Parsing.Token):
    "%token button"

class TokenTemplate(Parsing.Token):
    "%token template"

class TokenTitle(Parsing.Token):
    "%token title"

class TokenWeight(Parsing.Token):
    "%token weight"

class TokenRegistered(Parsing.Token):
    "%token registered"

class TokenOffline(Parsing.Token):
    "%token offline"

class TokenTeleport(Parsing.Token):
    "%token teleport"

class TokenChat(Parsing.Token):
    "%token chat"

class TokenJavaScript(Parsing.Token):
    "%token javascript"

class TokenClicked(Parsing.Token):
    "%token clicked"

class TokenClass(Parsing.Token):
    "%token class"

class TokenSelected(Parsing.Token):
    "%token selected"

class TokenShop(Parsing.Token):
    "%token shop"

class TokenBought(Parsing.Token):
    "%token bought"

class TokenSold(Parsing.Token):
    "%token sold"

class TokenWear(Parsing.Token):
    "%token wear"

class TokenUnwear(Parsing.Token):
    "%token unwear"

class TokenDrop(Parsing.Token):
    "%token drop"

class TokenModifier(Parsing.Token):
    "%token modifier"

class TokenRemove(Parsing.Token):
    "%token remove"

class TokenSet(Parsing.Token):
    "%token set"

class TokenInput(Parsing.Token):
    "%token input"

class TokenDefault(Parsing.Token):
    "%token default"

class TokenPaidService(Parsing.Token):
    "%token paidservice"

class TokenCombat(Parsing.Token):
    "%token combat"

class TokenVirtual(Parsing.Token):
    "%token virtual"

class TokenMember(Parsing.Token):
    "%token member"

class QuestAttrKey(Parsing.Nonterm):
    "%nonterm"
    def reduceAttrKey(self, attrkey):
        "%reduce AttrKey"
        self.val = attrkey.val

    def reduceEvent(self, event):
        "%reduce event"
        self.val = "event"

    def reduceTimeout(self, event):
        "%reduce timeout"
        self.val = "timeout"

    def reduceText(self, event):
        "%reduce text"
        self.val = "text"

class Attrs(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}
    
    def reduceAttr(self, attrs, key, a, value):
        "%reduce Attrs QuestAttrKey assign scalar"
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
        "%reduce ExprAttrs QuestAttrKey assign Expr"
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

# ============================
#          EVENTS
# ============================
class EventType(Parsing.Nonterm):
    "%nonterm"
    def reduceEvent(self, ev, eventid):
        "%reduce event scalar"
        if type(eventid.val) != str and type(eventid.val) != unicode:
            raise Parsing.SyntaxError(ev.script_parser._("Event id must be a string"))
        elif not re_valid_identifier.match(eventid.val):
            raise Parsing.SyntaxError(ev.script_parser._("Event identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        self.val = [["event", eventid.val], None]

    def reduceTeleported(self, ev, attrs):
        "%reduce teleported Attrs"
        validate_attrs(ev, "teleported", attrs, ["from", "to"])
        self.val = [["teleported"], attrs.val]

    def reduceExpired(self, ev, modid):
        "%reduce expired scalar"
        if type(modid.val) != str and type(modid.val) != unicode:
            raise Parsing.SyntaxError(ev.script_parser._("Modifier id must be a string"))
        elif not re_valid_identifier.match(modid.val):
            raise Parsing.SyntaxError(ev.script_parser._("Modifier identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        self.val = [["expired", "mod", modid.val], None]

    def reduceTimeout(self, ev, timerid):
        "%reduce timeout scalar"
        if type(timerid.val) != str and type(timerid.val) != unicode:
            raise Parsing.SyntaxError(ev.script_parser._("Timer id must be a string"))
        elif not re_valid_identifier.match(timerid.val):
            raise Parsing.SyntaxError(ev.script_parser._("Timer identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        self.val = [["expired", "timer", timerid.val], None]

    def reduceItemUsed(self, ev, action):
        "%reduce itemused scalar"
        if type(action.val) != str and type(action.val) != unicode:
            raise Parsing.SyntaxError(ev.script_parser._("Action code must be a string"))
        elif not re_valid_identifier.match(action.val):
            raise Parsing.SyntaxError(ev.script_parser._("Action code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        self.val = [["item", action.val], None]

    def reduceButton(self, ev, attrs):
        "%reduce button Attrs"
        ident = get_str_attr(ev, "button", attrs, "id", require=True)
        if not re_valid_identifier.match(ident):
            raise Parsing.SyntaxError(ev.script_parser._("Button identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        text = get_str_attr(ev, "button", attrs, "text", require=True)
        text = ev.script_parser.parse_text(text, ev.script_parser._("Button text"))
        validate_attrs(ev, "button", attrs, ["id", "text"])
        self.val = [["button", ident, text], None]

    def reduceRegistered(self, ev):
        "%reduce registered"
        self.val = [["registered"], None]

    def reduceOnline(self, ev):
        "%reduce online"
        self.val = [["online"], None]

    def reduceOffline(self, ev):
        "%reduce offline"
        self.val = [["offline"], None]

    def reduceClicked(self, ev, ident):
        "%reduce clicked scalar"
        if type(ident.val) != str and type(ident.val) != unicode:
            raise Parsing.SyntaxError(ev.script_parser._("Event identifier must be a string"))
        elif not re_valid_identifier.match(ident.val):
            raise Parsing.SyntaxError(ev.script_parser._("Event identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        self.val = [["clicked", ident.val], None]

    def reduceClassSelected(self, ev, ev2):
        "%reduce class selected"
        self.val = [["charclass-selected"], None]

    def reduceShopBought(self, ev, ev2):
        "%reduce shop bought"
        self.val = [["shop-bought"], None]

    def reduceShopSold(self, ev, ev2):
        "%reduce shop sold"
        self.val = [["shop-sold"], None]

    def reduceEquipWear(self, ev, ev2):
        "%reduce equip wear"
        self.val = [["equip-wear"], None]

    def reduceEquipUnwear(self, ev, ev2):
        "%reduce equip unwear"
        self.val = [["equip-unwear"], None]

    def reduceEquipDrop(self, ev, ev2):
        "%reduce equip drop"
        self.val = [["equip-drop"], None]

    def reducePaidService(self, ev):
        "%reduce paidservice"
        self.val = [["paidservice"], None]

# ============================
#          ACTIONS
# ============================
class QuestAction(Parsing.Nonterm):
    "%nonterm"
    def reduceMessage(self, msg, expr):
        "%reduce message scalar"
        self.val = ["message", msg.script_parser.parse_text(expr.val, msg.script_parser._("action///Quest message"))]

    def reduceError(self, err, expr):
        "%reduce error scalar"
        self.val = ["error", err.script_parser.parse_text(expr.val, err.script_parser._("action///Quest error"))]

    def reduceRequire(self, req, expr):
        "%reduce require Expr"
        self.val = ["require", expr.val]

    def reduceCall(self, call, attrs):
        "%reduce call ExprAttrs"
        event = get_str_attr(call, "call", attrs, "event", require=True)
        quest = get_str_attr(call, "call", attrs, "quest")
        char = get_attr(call, "call", attrs, "char")
        validate_attrs(call, "call", attrs, ["quest", "event", "char"])
        if not re_valid_identifier.match(event):
            raise Parsing.SyntaxError(call.script_parser._("Event identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        args = {}
        if char is not None:
            args["char"] = char
        if quest:
            if not re_valid_identifier.match(quest):
                raise Parsing.SyntaxError(call.script_parser._("Quest identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
            self.val = ["call2", quest, event, args]
        else:
            self.val = ["call2", None, event, args]

    def reduceGive(self, cmd, attrs):
        "%reduce give ExprAttrs"
        item = attrs.val.get("item")
        currency = attrs.val.get("currency")
        if item is None and currency is None:
            raise Parsing.SyntaxError(cmd.script_parser._("Attributes '{attr1}' or '{attr2}' are required in the '{obj}'").format(attr1="item", attr2="currency", obj="give"))
        if item is not None and currency is not None:
            raise Parsing.SyntaxError(cmd.script_parser._("Attributes '{attr1}' and '{attr2}' can't be used simultaneously in the '{obj}'").format(attr1="item", attr2="currency", obj="give"))
        if item is not None:
            mods = {}
            for key, val in attrs.val.iteritems():
                if key == "item" or key == "quantity":
                    continue
                m = re_param.match(key)
                if m:
                    param = m.group(1)
                    pinfo = cmd.script_parser.call("item-types.param", param)
                    if not pinfo:
                        raise Parsing.SyntaxError(cmd.script_parser._("Items has no parameter %s") % param)
                    elif pinfo.get("type", 0) != 0:
                        raise Parsing.SyntaxError(cmd.script_parser._("Parameter %s is not stored in the database") % param)
                    mods[param] = val
                else:
                    raise Parsing.SyntaxError(cmd.script_parser._("'{obj}' has no attribute '{attr}'").format(obj="give", attr=key))
            item = get_str_attr(cmd, "give", attrs, "item", require=True)
            quantity = get_attr(cmd, "give", attrs, "quantity")
            if quantity is None:
                quantity = 1
            self.val = ["giveitem", item, mods, quantity]
        elif currency is not None:
            amount = get_attr(cmd, "give", attrs, "amount", require=True)
            currency = get_attr(cmd, "give", attrs, "currency", require=True)
            comment = get_str_attr(cmd, "give", attrs, "comment")
            validate_attrs(cmd, "give", attrs, ["amount", "currency", "comment"])
            self.val = ["givemoney", amount, currency, comment]

    def reduceTake(self, cmd, attrs):
        "%reduce take ExprAttrs"
        tp = attrs.val.get("type")
        dna = attrs.val.get("dna")
        currency = attrs.val.get("currency")
        cnt = (1 if tp else 0) + (1 if dna else 0) + (1 if currency else 0)
        if cnt == 0:
            raise Parsing.SyntaxError(cmd.script_parser._("Attributes '{attr1}', '{attr2}' or '{attr3}' are required in the '{obj}'").format(attr1="type", attr2="dna", attr3="currency", obj="take"))
        elif cnt > 1:
            raise Parsing.SyntaxError(cmd.script_parser._("Attributes '{attr1}', '{attr2}' and '{attr3}' can't be used simultaneously in the '{obj}'").format(attr1="type", attr2="dna", attr3="currency", obj="take"))
        onfail = get_str_attr(cmd, "take", attrs, "onfail")
        if onfail and not re_valid_identifier.match(onfail):
            raise Parsing.SyntaxError(cmd.script_parser._("Event identifier 'onfail' must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        if tp or dna:
            quantity = attrs.val.get("quantity")
            fractions = attrs.val.get("fractions")
            validate_attrs(cmd, "take", attrs, ["type", "dna", "quantity", "onfail", "fractions"])
            if quantity is not None and fractions is not None:
                raise Parsing.SyntaxError(cmd.script_parser._("Quantity and fractions can't be specified at the same time"))
            if fractions is not None and dna:
                raise Parsing.SyntaxError(cmd.script_parser._("Fractions can't be specified for 'dna=...'. Use 'type=...' instead"))
            self.val = ["takeitem", tp, dna, quantity, onfail, fractions]
        elif currency:
            amount = attrs.val.get("amount")
            comment = get_str_attr(cmd, "take", attrs, "comment")
            validate_attrs(cmd, "take", attrs, ["amount", "currency", "onfail", "comment"])
            self.val = ["takemoney", amount, currency, onfail, comment]

    def reduceIf(self, cmd, expr, curlyleft, actions, curlyright):
        "%reduce if Expr curlyleft QuestActions curlyright"
        self.val = ["if", expr.val, actions.val]

    def reduceIfElse(self, cmd, expr, curlyleft1, actions1, curlyright1, els, curlyleft2, actions2, curlyright2):
        "%reduce if Expr curlyleft QuestActions curlyright else curlyleft QuestActions curlyright"
        self.val = ["if", expr.val, actions1.val, actions2.val]

    def reduceSet(self, st, lvalue, assign, rvalue):
        "%reduce set Expr assign Expr"
        if type(lvalue.val) != list or lvalue.val[0] != ".":
            raise Parsing.SyntaxError(assign.script_parser._("Invalid usage of assignment operator"))
        self.val = ["set", lvalue.val[1], lvalue.val[2], rvalue.val]

    def reduceFinish(self, cmd):
        "%reduce finish"
        self.val = ["destroy", True]

    def reduceFail(self, cmd):
        "%reduce fail"
        self.val = ["destroy", False]

    def reduceLock(self, cmd, attrs):
        "%reduce lock ExprAttrs"
        timeout = get_attr(cmd, "lock", attrs, "timeout")
        validate_attrs(cmd, "lock", attrs, ["timeout"])
        self.val = ["lock", timeout]

    def reduceTimer(self, cmd, attrs):
        "%reduce timer ExprAttrs"
        tid = get_str_attr(cmd, "timer", attrs, "id", require=True)
        if not re_valid_identifier.match(tid):
            raise Parsing.SyntaxError(cmd.script_parser._("Timer identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        timeout = get_attr(cmd, "timer", attrs, "timeout", require=True)
        validate_attrs(cmd, "timer", attrs, ["id", "timeout"])
        self.val = ["timer", tid, timeout]

    def reduceModifier(self, cmd, attrs):
        "%reduce modifier ExprAttrs"
        mid = get_str_attr(cmd, "modifier", attrs, "id", require=True)
        if not re_valid_identifier.match(mid):
            raise Parsing.SyntaxError(cmd.script_parser._("Modifier identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        add = get_attr(cmd, "modifier", attrs, "add")
        prolong = get_attr(cmd, "modifier", attrs, "prolong")
        val = get_attr(cmd, "modifier", attrs, "val")
        validate_attrs(cmd, "modifier", attrs, ["id", "add", "prolong", "val"])
        if add is not None and prolong is not None:
            raise Parsing.SyntaxError(cmd.script_parser._("You must specify either 'add' or 'prolong' attribute"))
        elif add is not None:
            self.val = ["modifier", mid, "add", add]
        elif prolong is not None:
            self.val = ["modifier", mid, "prolong", prolong]
        else:
            self.val = ["modifier", mid, "add", None]
        if val is not None:
            self.val.append(val)

    def reduceModifierRemove(self, cmd, cmd1, attrs):
        "%reduce modifier remove ExprAttrs"
        mid = get_str_attr(cmd, "modifier", attrs, "id", require=True)
        if not re_valid_identifier.match(mid):
            raise Parsing.SyntaxError(cmd.script_parser._("Modifier identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        validate_attrs(cmd, "modifier", attrs, ["id"])
        self.val = ["modremove", mid]

    def reduceDialog(self, cmd, curlyleft, content, curlyright):
        "%reduce dialog curlyleft DialogContent curlyright"
        self.val = ["dialog", content.val]

    def reduceRandom(self, cmd, curlyleft, content, curlyright):
        "%reduce random curlyleft RandomContent curlyright"
        self.val = ["random", content.val]

    def reduceTeleport(self, cmd, loc):
        "%reduce teleport Expr"
        self.val = ["teleport", loc.val]

    def reduceChat(self, cmd, text, attrs):
        "%reduce chat scalar ExprAttrs"
        text = cmd.script_parser.parse_text(text.val, cmd.script_parser._("Chat message"))
        channel = get_attr(cmd, "chat", attrs, "channel")
        public = get_attr(cmd, "chat", attrs, "public")
        cls = get_attr(cmd, "chat", attrs, "cls")
        validate_attrs(cmd, "chat", attrs, ["text", "channel", "public", "cls"])
        args = {}
        if channel is not None:
            args["channel"] = channel
        if public is not None:
            args["public"] = public
        if cls is not None:
            args["cls"] = cls
        self.val = ["chat", text, args]

    def reduceJavaScript(self, cmd, javascript):
        "%reduce javascript scalar"
        if type(javascript.val) != str and type(javascript.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Location id must be a string"))
        self.val = ["javascript", javascript.val]

    def reduceCombat(self, cmd, attrs, curlyleft, content, curlyright):
        "%reduce combat ExprAttrs curlyleft CombatContent curlyright"
        options = content.val.copy()
        rules = get_str_attr(cmd, "combat", attrs, "rules")
        validate_attrs(cmd, "combat", attrs, ["rules"])
        if rules is not None and not re_valid_identifier.match(rules):
            raise Parsing.SyntaxError(cmd.script_parser._("Combat rules identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        if rules is not None:
            options["rules"] = rules
        self.val = ["combat", options]

class RandomContent(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = []

    def reduceVariant(self, content, w, weight, c, actions):
        "%reduce RandomContent weight Expr colon QuestActions"
        self.val = [ent for ent in content.val]
        self.val.append([weight.val, actions.val])

class CombatContent(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {
            "members": []
        }

    def reduceMember(self, content, cmd, mtype, attrs):
        "%reduce CombatContent member CombatMemberType ExprAttrs"
        # validating attributes
        team = get_attr(cmd, "member", attrs, "team", require=True)
        control = get_attr(cmd, "member", attrs, "control")
        name = get_str_attr(cmd, "member", attrs, "name")
        sex = get_attr(cmd, "member", attrs, "sex")
        ai = get_attr(cmd, "member", attrs, "ai")
        validate_attrs(cmd, "member", attrs, ["team", "name", "sex", "control", "ai"])
        # reducing
        self.val = content.val.copy()
        member = {
            "type": mtype.val,
            "team": team,
        }
        if name is not None:
            member["name"] = cmd.script_parser.parse_text(name, cmd.script_parser._("Combat member name"))
        if control is not None:
            member["control"] = control
        if sex is not None:
            member["sex"] = sex
        if ai is not None:
            member["ai"] = ai
        self.val["members"] = self.val["members"] + [member]

    def reduceTitle(self, content, cmd, title):
        "%reduce CombatContent title scalar"
        if type(title) != str and type(title) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Combat title must be a string"))
        title = cmd.script_parser.parse_text(title, cmd.script_parser._("Combat title"))
        self.val = content.val.copy()
        self.val["title"] = title

class CombatMemberType(Parsing.Nonterm):
    "%nonterm"
    def reduceExpression(self, expr):
        "%reduce Expr"
        self.val = ["expr", expr.val]

    def reduceVirtual(self, cmd):
        "%reduce virtual"
        self.val = ["virtual"]

class DialogContent(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}

    def reduceText(self, content, cmd, text):
        "%reduce DialogContent text scalar"
        self.val = content.val.copy()
        if "text" in self.val:
            raise Parsing.SyntaxError(cmd.script_parser._("Dialog can't contain multiple 'text' entries"))
        if type(text.val) != str and type(text.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Dialog text must be a string"))
        self.val["text"] = cmd.script_parser.parse_text(text.val, cmd.script_parser._("Dialog text"))

    def reduceTitle(self, content, cmd, title):
        "%reduce DialogContent title scalar"
        self.val = content.val.copy()
        if "title" in self.val:
            raise Parsing.SyntaxError(cmd.script_parser._("Dialog can't contain multiple 'title' entries"))
        if type(title.val) != str and type(title.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Dialog title must be a string"))
        self.val["title"] = cmd.script_parser.parse_text(title.val, cmd.script_parser._("Dialog title"))

    def reduceButton(self, content, default, cmd, curlyleft, button, curlyright):
        "%reduce DialogContent DefaultSelector button curlyleft ButtonContent curlyright"
        self.val = content.val.copy()
        button_val = button.val.copy()
        if default.val:
            button_val["default"] = True
        try:
            self.val["buttons"].append(button_val)
        except KeyError:
            self.val["buttons"] = [button_val]
        default = 0
        for btn in self.val["buttons"]:
            if btn.get("default"):
                default += 1
                if default >= 2:
                    raise Parsing.SyntaxError(cmd.script_parser._("Dialog can't contain more than 1 default button"))

    def reduceTemplate(self, content, cmd, tpl):
        "%reduce DialogContent template scalar"
        self.val = content.val.copy()
        if "template" in self.val:
            raise Parsing.SyntaxError(cmd.script_parser._("Dialog can't contain multiple 'template' entries"))
        if type(tpl.val) != str and type(tpl.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Dialog template name must be a string"))
        elif not re_valid_template.match(tpl.val):
            raise Parsing.SyntaxError(cmd.script_parser._("Dialog template name must start with latin letter. Other symbols may be latin letters, digits or '-'. File name extension must be .html"))
        self.val["template"] = tpl.val

    def reduceInput(self, content, cmd, inpid, curlyleft, inp, curlyright):
        "%reduce DialogContent input scalar curlyleft InputContent curlyright"
        self.val = content.val.copy()
        inputs = self.val.get("inputs")
        if not inputs:
            inputs = []
            self.val["inputs"] = inputs
        if type(inpid.val) != str and type(inpid.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Input identifier name must be a string"))
        elif not re_valid_identifier.match(inpid.val):
            raise Parsing.SyntaxError(cmd.script_parser._("Input identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        for i in inputs:
            if i["id"] == inpid.val:
                raise Parsing.SyntaxError(cmd.script_parser._("Input identifiers must be unique"))
        inpval = inp.val.copy()
        inpval["id"] = inpid.val
        inputs.append(inpval)

class DefaultSelector(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = False

    def reduceDefault(self, cmd):
        "%reduce default"
        self.val = True

class ButtonContent(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}

    def reduceText(self, content, cmd, text):
        "%reduce ButtonContent text scalar"
        self.val = content.val.copy()
        if "text" in self.val:
            raise Parsing.SyntaxError(cmd.script_parser._("Button can't contain multiple 'text' entries"))
        if type(text.val) != str and type(text.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Button text must be a string"))
        self.val["text"] = cmd.script_parser.parse_text(text.val, cmd.script_parser._("Button text"))

    def reduceEvent(self, content, cmd, eventid):
        "%reduce ButtonContent event scalar"
        self.val = content.val.copy()
        if "event" in self.val:
            raise Parsing.SyntaxError(cmd.script_parser._("Button can't contain multiple 'event' entries"))
        if type(eventid.val) != str and type(eventid.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Button event identifier must be a string"))
        elif not re_valid_identifier.match(eventid.val):
            raise Parsing.SyntaxError(cmd.script_parser._("Button event identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
        self.val["event"] = eventid.val

class InputContent(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = {}

    def reduceText(self, content, cmd, text):
        "%reduce InputContent text scalar"
        self.val = content.val.copy()
        if "text" in self.val:
            raise Parsing.SyntaxError(cmd.script_parser._("Input can't contain multiple 'text' entries"))
        if type(text.val) != str and type(text.val) != unicode:
            raise Parsing.SyntaxError(cmd.script_parser._("Input text must be a string"))
        self.val["text"] = cmd.script_parser.parse_text(text.val, cmd.script_parser._("Input text"))

class QuestActions(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = []

    def reduceAction(self, actions, action):
        "%reduce QuestActions QuestAction"
        self.val = actions.val + [action.val]

class QuestHandlers(Parsing.Nonterm):
    "%nonterm"
    def reduceEmpty(self):
        "%reduce"
        self.val = []
    
    def reduceHandler(self, handlers, evtype, cl, actions, cr):
        "%reduce QuestHandlers EventType curlyleft QuestActions curlyright"
        info = {
            "type": evtype.val[0]
        }
        if actions.val:
            info["act"] = actions.val
        if evtype.val[1]:
            info["attrs"] = evtype.val[1]
        self.val = handlers.val + [["hdl", info]]

class QuestState(Parsing.Nonterm):
    "%nonterm"
    def reduce(self, handlers):
        "%reduce QuestHandlers"
        self.val = ["state", {}]
        if handlers.val:
            self.val[1]["hdls"] = handlers.val

# This is the start symbol; there can be only one such class in the grammar.
class Result(Parsing.Nonterm):
    "%start"
    def reduce(self, e):
        "%reduce QuestState"
        raise ScriptParserResult(e.val)

class QuestScriptParser(ScriptParser):
    syms = ScriptParser.syms.copy()
    syms["event"] = TokenEvent
    syms["message"] = TokenMessage
    syms["error"] = TokenError
    syms["teleported"] = TokenTeleported
    syms["require"] = TokenRequire
    syms["call"] = TokenCall
    syms["give"] = TokenGive
    syms["if"] = TokenIf
    syms["else"] = TokenElse
    syms["finish"] = TokenFinish
    syms["fail"] = TokenFail
    syms["lock"] = TokenLock
    syms["expired"] = TokenExpired
    syms["timer"] = TokenTimer
    syms["timeout"] = TokenTimeout
    syms["itemused"] = TokenItemUsed
    syms["dialog"] = TokenDialog
    syms["text"] = TokenText
    syms["title"] = TokenTitle
    syms["button"] = TokenButton
    syms["template"] = TokenTemplate
    syms["take"] = TokenTake
    syms["weight"] = TokenWeight
    syms["registered"] = TokenRegistered
    syms["offline"] = TokenOffline
    syms["teleport"] = TokenTeleport
    syms["chat"] = TokenChat
    syms["javascript"] = TokenJavaScript
    syms["clicked"] = TokenClicked
    syms["class"] = TokenClass
    syms["selected"] = TokenSelected
    syms["shop"] = TokenShop
    syms["sold"] = TokenSold
    syms["bought"] = TokenBought
    syms["wear"] = TokenWear
    syms["unwear"] = TokenUnwear
    syms["drop"] = TokenDrop
    syms["modifier"] = TokenModifier
    syms["remove"] = TokenRemove
    syms["set"] = TokenSet
    syms["input"] = TokenInput
    syms["default"] = TokenDefault
    syms["paidservice"] = TokenPaidService
    syms["combat"] = TokenCombat
    syms["virtual"] = TokenVirtual
    syms["member"] = TokenMember

    def __init__(self, app, spec, general_spec):
        Module.__init__(self, app, "mg.mmorpg.quest_parser.QuestScriptParser")
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
