from mg import *
from mg.core.auth import *
from concurrence import Timeout, TimeoutError
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from uuid import uuid4
from mg.core.money_classes import *
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageFilter
import cStringIO
import xml.dom.minidom
import hashlib
import re
import random
import math

re_uuid_cmd = re.compile(r'^([0-9a-z]+)/(.+)$')
re_valid_code = re.compile(r'^[A-Z]{2,5}$')
re_questions = re.compile('\?')
re_invalid_symbol = re.compile(r'([^\w \-\.,:/])', re.UNICODE)
re_invalid_english_symbol = re.compile(r'([^a-zA-Z_ \-\.,:/])', re.UNICODE)
re_valid_real_price = re.compile(r'[1-9]\d*(?:\.\d\d?|)$')
re_decimal_comma = re.compile(',')

default_rates = {
    "RUB": 1,
    "USD": 28,
    "EUR": 40,
    "GBP": 45,
    "KZT": 19 / 100,
    "BYR": 56 / 10000,
    "UAH": 34.7092 / 10,
}

def getText(nodelist):
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc

class MoneyAdmin(Module):
    def register(self):
        self.rhook("ext-admin-money.give", self.admin_money_give, priv="users.money.give")
        self.rhook("headmenu-admin-money.give", self.headmenu_money_give)
        self.rhook("ext-admin-money.take", self.admin_money_take, priv="users.money.give")
        self.rhook("headmenu-admin-money.take", self.headmenu_money_take)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-money.account", self.admin_money_account, priv="users.money")
        self.rhook("headmenu-admin-money.account", self.headmenu_money_account)
        self.rhook("admin-game.recommended-actions", self.recommended_actions)
        self.rhook("ext-admin-money.currencies", self.admin_money_currencies, priv="money.currencies")
        self.rhook("headmenu-admin-money.currencies", self.headmenu_money_currencies)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-economy.index", self.menu_economy_index)
        self.rhook("constructor.project-params", self.project_params)
        self.rhook("objclasses.list", self.objclasses_list)

    def objclasses_list(self, objclasses):
        objclasses["Account"] = (Account, AccountList)
        objclasses["AccountLock"] = (AccountLock, AccountLockList)
        objclasses["AccountOperation"] = (AccountOperation, AccountOperationList)

    def menu_root_index(self, menu):
        menu.append({"id": "economy.index", "text": self._("Economy"), "order": 100})

    def menu_economy_index(self, menu):
        req = self.req()
        if req.has_access("money.currencies"):
            menu.append({"id": "money/currencies", "text": self._("Currencies"), "leaf": True, "even_unpublished": True})

    def headmenu_money_currencies(self, args):
        if args == "new" or args == "prenew":
            return [self._("New currency"), "money/currencies"]
        elif args:
            return [args, "money/currencies"]
        return self._("Currency editor")

    def admin_money_currencies(self):
        req = self.req()
        try:
            project = self.app().project
        except AttributeError:
            project = None
        with self.lock(["currencies"]):
            currencies = {}
            self.call("currencies.list", currencies)
            lang = self.call("l10n.lang")
            if req.args == "prenew":
                if req.ok():
                    errors = {}
                    name_en = req.param("name_en").strip().capitalize()
                    name_local = req.param("name_local").strip().capitalize()
                    if not name_local:
                        errors["name_local"] = self._("Currency name is mandatory")
                    if lang != "en":
                        if not name_en:
                            errors["name_en"] = self._("Currency name is mandatory")
                    if len(errors):
                        self.call("web.response_json", {"success": False, "errors": errors})
                    self.call("admin.redirect", "money/currencies/new", {
                        "name_local": self.call("l10n.literal_values_sample", name_local),
                        "name_plural": u"%s???" % self.stem(name_local),
                        "name_en": u"{0}???/{0}???".format(name_en),
                    })
                fields = []
                fields.append({"name": "name_local", "label": self._('Currency name')})
                if lang != "en":
                    fields.append({"name": "name_en", "label": self._('Currency name in English')})
                self.call("admin.form", fields=fields)
            elif req.args:
                if req.ok():
                    self.call("web.upload_handler")
                    code = req.param("code").strip()
                    name_en = req.param("name_en").strip()
                    name_local = req.param("name_local").strip()
                    name_plural = req.param("name_plural").strip()
                    description = req.param("description").strip()
                    precision = intz(req.param("precision"))
                    real = True if req.param("real") else False
                    real_price = req.param("real_price")
                    real_currency = req.param("v_real_currency")
                    # validating
                    errors = {}
                    errormsg = None
                    if req.args == "new":
                        if not code:
                            errors["code"] = self._("Currency code is mandatory")
                        elif len(code) < 2:
                            errors["code"] = self._("Minimal length is 3 letters")
                        elif len(code) > 5:
                            errors["code"] = self._("Maximal length is 5 letters")
                        elif not re_valid_code.match(code):
                            errors["code"] = self._("Currency code must contain capital latin letters only")
                        elif currencies.get(code):
                            errors["code"] = self._("This currency name is busy")
                        info = {}
                        currencies[code] = info
                    else:
                        info = currencies.get(req.args)
                    if not name_local:
                        errors["name_local"] = self._("Currency name is mandatory")
                    elif not self.call("l10n.literal_values_valid", name_local):
                        errors["name_local"] = self._("Invalid field format")
                    elif re_questions.search(name_local):
                        errors["name_local"] = self._("Replace '???' with correct endings")
                    else:
                        m = re_invalid_symbol.search(name_local)
                        if m:
                            sym = m.group(1)
                            errors["name_local"] = self._("Invalid symbol: '%s'") % htmlescape(sym)
                    if not name_plural:
                        errors["name_plural"] = self._("Currency name is mandatory")
                    elif re_questions.search(name_plural):
                        errors["name_plural"] = self._("Replace '???' with correct endings")
                    else:
                        m = re_invalid_symbol.search(name_plural)
                        if m:
                            sym = m.group(1)
                            errors["name_plural"] = self._("Invalid symbol: '%s'") % htmlescape(sym)
                        elif project and (project.get("moderation") or project.get("published")) and name_plural != info.get("name_plural") and info.get("real"):
                            errors["name_plural"] = self._("You can't change real money currency name after game publication")
                    if lang != "en":
                        if not name_en:
                            errors["name_en"] = self._("Currency name is mandatory")
                        elif re_questions.search(name_en):
                            errors["name_en"] = self._("Replace '???' with correct endings")
                        else:
                            values = name_en.split("/")
                            if len(values) != 2:
                                errors["name_en"] = self._("Invalid field format")
                            else:
                                m = re_invalid_english_symbol.search(name_en)
                                if m:
                                    sym = m.group(1)
                                    errors["name_en"] = self._("Invalid symbol: '%s'") % htmlescape(sym)
                                elif project and (project.get("moderation") or project.get("published")) and name_en != info.get("name_en") and info.get("real"):
                                    errors["name_en"] = self._("You can't change real money currency name after game publication")
                                else:
                                    for val in values:
                                        if val.lower() == "golds":
                                            errors["name_en"] = self._("en///Gold in plural is 'Gold'")
                    if precision < 0:
                        errors["precision"] = self._("Precision can't be negative")
                    elif precision > 4:
                        errors["precision"] = self._("Maximal supported precision is 4")
                    elif project and (project.get("moderation") or project.get("published")) and info.get("real") and precision != info.get("precision"):
                        errors["precision"] = self._("You can't change real money currency precision after game publication")
                    if real:
                        for c, i in currencies.iteritems():
                            if i.get("real") and c != req.args:
                                errormsg = self._("You already have a real money currency")
                                break
                        if precision != 0 and precision != 2:
                            errors["precision"] = self._("Real money currency must have precision 0 or 2 (limitation of the payment system)")
                    else:
                        if project and (project.get("moderation") or project.get("published")) and info.get("real"):
                            errormsg = self._("You can't remove real money currency after game publication")
                    if real:
                        if not real_price:
                            errors["real_price"] = self._("You must supply real money price for this currency")
                        elif not re_valid_real_price.match(real_price):
                            errors["real_price"] = self._("Invalid number format")
                        elif project and (project.get("moderation") or project.get("published")) and info.get("real_price") and float(real_price) != float(info.get("real_price")):
                            errors["real_price"] = self._("You can't change real money exchange rate after game publication")
                        if real_currency not in ["RUB", "USD", "EUR", "UAH", "BYR", "GBP", "KZT"]:
                            errors["v_real_currency"] = self._("Select real money currency")
                        elif project and (project.get("moderation") or project.get("published")) and real_currency != info.get("real_currency"):
                            errors["v_real_currency"] = self._("You can't change real money exchange rate after game publication")
                        if "real_price" not in errors and "v_real_currency" not in errors:
                            rate = self.stock_rate(real_currency)
                            real_roubles = float(real_price) * rate
                            min_step = real_roubles * (0.1 ** int(precision))
                            if min_step > 50:
                                errors["real_price"] = self._("Minimal step of payment in this currency is {min_step:f} roubles (1 {currency} = {rate} RUB, precision = {precision}). It is too big for micropayments. Lower you currency rate").format(min_step=min_step, currency=real_currency, rate=rate, precision=0.1**precision)
                    # images
                    image_data = req.param_raw("image")
                    image_obj = None
                    if image_data:
                        try:
                            image_obj = Image.open(cStringIO.StringIO(image_data))
                            if image_obj.load() is None:
                                raise IOError
                        except IOError:
                            errors["image"] = self._("Image format not recognized")
                        except OverflowError:
                            errors["image"] = self._("Image format not recognized")
                        else:
                            if image_obj.format == "GIF":
                                image_ext = "gif"
                                image_content_type = "image/gif"
                            elif image_obj.format == "PNG":
                                image_ext = "png"
                                image_content_type = "image/png"
                            elif image_obj.format == "JPEG":
                                image_ext = "jpg"
                                image_content_type = "image/jpeg"
                            else:
                                errors["image"] = self._("Image format must be GIF, JPEG or PNG")
                    icon_data = req.param_raw("icon")
                    icon_obj = None
                    if icon_data:
                        try:
                            icon_obj = Image.open(cStringIO.StringIO(icon_data))
                            if icon_obj.load() is None:
                                raise IOError
                        except IOError:
                            errors["icon"] = self._("Image format not recognized")
                        except OverflowError:
                            errors["icon"] = self._("Image format not recognized")
                        else:
                            if icon_obj.format == "GIF":
                                icon_ext = "gif"
                                icon_content_type = "image/gif"
                            elif icon_obj.format == "PNG":
                                icon_ext = "png"
                                icon_content_type = "image/png"
                            elif icon_obj.format == "JPEG":
                                icon_ext = "jpg"
                                icon_content_type = "image/jpeg"
                            else:
                                errors["icon"] = self._("Image format must be GIF, JPEG or PNG")
                    if len(errors) or errormsg:
                        self.call("web.response_json_html", {"success": False, "errors": errors, "errormsg": errormsg})
                    # storing
                    info["name_local"] = name_local
                    info["name_plural"] = name_plural
                    if lang == "en":
                        info["name_en"] = name_local
                    else:
                        info["name_en"] = name_en
                    info["precision"] = precision
                    info["format"] = "%.{0}f".format(precision) if precision else "%d"
                    info["description"] = description
                    info["real"] = real
                    if real:
                        info["real_price"] = floatz(real_price)
                        info["real_currency"] = real_currency
                        info["real_roubles"] = real_roubles
                    # storing images
                    old_images = []
                    if image_obj:
                        old_images.append(info.get("image"))
                        info["image"] = self.call("cluster.static_upload", "currencies", image_ext, image_content_type, image_data)
                    if icon_obj:
                        old_images.append(info.get("icon"))
                        info["icon"] = self.call("cluster.static_upload", "currencies", icon_ext, icon_content_type, icon_data)
                    config = self.app().config_updater()
                    config.set("money.currencies", currencies)
                    config.store()
                    for uri in old_images:
                        if uri:
                            self.call("cluster.static_delete", uri)
                    self.call("web.response_json_html", {"success": True, "redirect": "money/currencies"})
                elif req.args == "new":
                    description = ""
                    real = False
                    name_local = req.param("name_local")
                    name_plural = req.param("name_plural")
                    name_en = req.param("name_en")
                    precision = 2
                    real_price = 30
                    real_currency = "RUB"
                else:
                    info = currencies.get(req.args)
                    if not info:
                        self.call("web.not_found")
                    name_local = info.get("name_local")
                    name_plural = info.get("name_plural")
                    name_en = info.get("name_en")
                    precision = info.get("precision")
                    description = info.get("description")
                    real = info.get("real")
                    real_price = info.get("real_price")
                    real_currency = info.get("real_currency")
                fields = []
                if req.args == "new":
                    fields.append({"name": "code", "label": self._('Currency code (for example, GLD for gold, SLVR for silver, DMND for diamonds and so on).<br /><span class="no">You won\'t have an ability to change the code later. Think twice before saving</span>')})
                fields.append({"name": "name_local", "label": self._('Currency name: singular and plural forms delimited by "/". For example: "Dollar/Dollars"'), "value": name_local})
                fields.append({"name": "name_plural", "label": self._('Currency name: plural form. For example: "Dollars"'), "value": name_plural})
                if lang != "en":
                    fields.append({"name": "name_en", "label": self._('Currency name in English: singular and plural forms delimited by "/". For example: "Dollar/Dollars"'), "value": name_en})
                fields.append({"name": "precision", "label": self._("Values precision (number of digits after decimal point)"), "value": precision})
                fields.append({"name": "description", "label": self._("Currency description"), "type": "textarea", "value": description})
                fields.append({"name": "real", "label": self._("Real money. Set this checkbox if this currency is sold for real money. Your game must have one real money currency"), "type": "checkbox", "checked": real})
                fields.append({"name": "real_price", "label": self._("Real money price for 1 unit of the currency"), "value": real_price, "condition": "[real]"})
                fields.append({"name": "real_currency", "type": "combo", "label": self._("Real money currency"), "value": real_currency, "condition": "[real]", "values": [("RUB", "RUB"), ("USD", "USD"), ("EUR", "EUR"), ("UAH", "UAH"), ("BYR", "BYR"), ("GBP", "GBP"), ("KZT", "KZT")]})
                fields.append({"name": "image", "label": self._("Currency image (approx 60x60)"), "type": "fileuploadfield"})
                fields.append({"name": "icon", "label": self._("Currency icon (approx 16x16)"), "type": "fileuploadfield"})
                self.call("admin.form", fields=fields, modules=["FileUploadField"])
            else:
                rows = []
                for code in sorted(currencies.keys()):
                    info = currencies.get(code)
                    real = '<center>%s</center>' % ('<img src="/st/img/coins-16x16.png" alt="" /><br />%s %s' % (info.get("real_price"), info.get("real_currency")) if info.get("real") else '-')
                    declensions = []
                    for i in (0, 1, 2, 5, 10, 21):
                        declensions.append("<nobr>%d %s</nobr>" % (i, self.call("l10n.literal_value", i, info.get("name_local"))))
                    code = '<hook:admin.link href="money/currencies/{0}" title="{0}" />'.format(code)
                    if info.get("icon"):
                        code += ' <img src="%s" alt="" class="inline-icon" />' % info["icon"]
                    name = info.get("name_plural")
                    if info.get("image"):
                        name += '<br /><img src="%s" alt="" />' % info["image"]
                    rows.append([code, name, real, ", ".join(declensions)])
                vars = {
                    "tables": [
                        {
                            "links": [
                                {
                                    "hook": "money/currencies/prenew",
                                    "text": self._("New currency"),
                                    "lst": True,
                                }
                            ],
                            "header": [self._("Currency code"), self._("Currency name"), self._("Real money"), self._("Declension samples")],
                            "header_nowrap": True,
                            "rows": rows
                        }
                    ]
                }
                self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_money_give(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("Give money"), "auth/user-dashboard/%s?active_tab=money" % args]

    def admin_money_give(self):
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        currencies = {}
        self.call("currencies.list", currencies)
        amount = req.param("amount")
        currency = req.param("v_currency")
        if req.param("ok"):
            errors = {}
            self.call("money.valid_amount", amount, currency, errors, "amount", "v_currency")
            user_comment = req.param("user_comment").strip()
            admin_comment = req.param("admin_comment").strip()
            if not admin_comment:
                errors["admin_comment"] = self._("This field is mandatory")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            amount = float(amount)
            member = MemberMoney(self.app(), "user", user.uuid)
            member.credit(amount, currency, "admin-give", admin=req.user(), comment=user_comment)
            self.call("security.suspicion", admin=req.user(), action="money.give", member=user.uuid, amount=amount, currency=currency, comment=admin_comment)
            self.call("dossier.write", user=user.uuid, admin=req.user(), content=self._("Given {money_amount}: {comment}").format(money_amount=self.call("money.price-text", amount, currency), comment=admin_comment))
            self.call("admin.redirect", "auth/user-dashboard/%s" % user.uuid, {"active_tab": "money"})
        else:
            amount = "0"
        fields = []
        fields.append({"name": "amount", "label": self._("Give amount"), "value": amount})
        fields.append({"name": "currency", "label": self._("Currency"), "type": "combo", "value": currency, "values": [(code, info["name_plural"]) for code, info in currencies.iteritems()]})
        fields.append({"name": "user_comment", "label": self._("Comment for the user (can be empty)")})
        fields.append({"name": "admin_comment", "label": '%s%s' % (self._("Reason why do you give money to the user. Provide the real reason. It will be inspected by the MMO Constructor Security Dept"), self.call("security.icon") or "")})
        buttons = [{"text": self._("Give")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def headmenu_money_take(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("Take money"), "auth/user-dashboard/%s?active_tab=money" % args]

    def admin_money_take(self):
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        currencies = {}
        self.call("currencies.list", currencies)
        amount = req.param("amount")
        currency = req.param("v_currency")
        if req.param("ok"):
            errors = {}
            currency_info = currencies.get(currency)
            if currency_info is None:
                errors["v_currency"] = self._("Invalid currency")
            try:
                amount = float(amount)
                if amount <= 0:
                    errors["amount"] = self._("money///Amount must be greater than 0")
                elif currency_info is not None and amount != float(currency_info["format"] % amount):
                    errors["amount"] = self._("money///Invalid amount precision")
            except ValueError:
                errors["amount"] = self._("Invalid number format")
            user_comment = req.param("user_comment").strip()
            admin_comment = req.param("admin_comment").strip()
            if not admin_comment:
                errors["admin_comment"] = self._("This field is mandatory")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            member = MemberMoney(self.app(), "user", user.uuid)
            member.force_debit(amount, currency, "admin-take", admin=req.user(), comment=user_comment)
            self.call("security.suspicion", admin=req.user(), action="money.take", member=user.uuid, amount=amount, currency=currency, comment=admin_comment)
            self.call("dossier.write", user=user.uuid, admin=req.user(), content=self._("Taken {money_amount}: {comment}").format(money_amount=self.call("money.price-text", amount, currency), comment=admin_comment))
            self.call("admin.redirect", "auth/user-dashboard/%s" % user.uuid, {"active_tab": "money"})
        else:
            amount = "0"
        fields = []
        fields.append({"name": "amount", "label": self._("Take amount"), "value": amount})
        fields.append({"name": "currency", "label": self._("Currency"), "type": "combo", "value": currency, "values": [(code, info["name_plural"]) for code, info in currencies.iteritems()]})
        fields.append({"name": "user_comment", "label": self._("Comment for the user (can be empty)")})
        fields.append({"name": "admin_comment", "label": '%s%s' % (self._("Reason why do you give money to the user. Provide the real reason. It will be inspected by the MMO Constructor Security Dept"), self.call("security.icon") or "")})
        buttons = [{"text": self._("Take")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def headmenu_money_account(self, args):
        try:
            acc = self.obj(Account, args)
        except ObjectNotFoundException:
            return
        return [self._("Account %s") % acc.get("currency"), "auth/user-dashboard/%s?active_tab=money" % acc.get("member")]

    def admin_money_account(self):
        req = self.req()
        try:
            account = self.obj(Account, req.args)
        except ObjectNotFoundException:
            return
        currencies = {}
        self.call("currencies.list", currencies)
        operations = []
        lst = self.objlist(AccountOperationList, query_index="account", query_equal=account.uuid, query_reversed=True)
        lst.load(silent=True)
        for op in lst:
            rdescription = op.get("description")
            description = self.call("money-description.%s" % rdescription)
            if description:
                watchdog = 0
                while True:
                    watchdog += 1
                    if watchdog >= 100:
                        break
                    try:
                        rdescription = description["text"].format(**op.data)
                    except KeyError as e:
                        op.data[e.args[0]] = "{%s}" % e.args[0]
                    else:
                        break
            if op.get("comment"):
                rdescription = "%s: %s" % (rdescription, htmlescape(op.get("comment")))
            operations.append({
                "performed": self.call("l10n.time_local", op.get("performed")),
                "amount": op.get("amount"),
                "balance": op.get("balance"),
                "description": rdescription,
            })
        vars = {
            "Performed": self._("Performed"),
            "Amount": self._("Amount"),
            "Balance": self._("Balance"),
            "Description": self._("Description"),
            "operations": operations,
            "Update": self._("Update"),
            "account": {
                "uuid": account.uuid
            }
        }
        self.call("admin.response_template", "admin/money/account.html", vars)

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("users.money"):
            member = MemberMoney(self.app(), "user", user.uuid)
            links = []
            if req.has_access("users.money.give"):
                links.append({"hook": "money/give/%s" % user.uuid, "text": self._("Give money")})
                links.append({"hook": "money/take/%s" % user.uuid, "text": self._("Take money"), "lst": True})
            tbl = {
                "type": "money",
                "title": self._("Money"),
                "order": 20,
                "links": links,
                "header": [self._("Account Id"), self._("Currency"), self._("Balance"), self._("Locked"), self._("Low limit")],
                "rows": [('<hook:admin.link href="money/account/{0}" title="{0}" />'.format(a.uuid), a.get("currency"), a.get("balance"), a.get("locked"), a.get("low_limit")) for a in member.accounts]
            }
            tables.append(tbl)
            if len(member.locks):
                rows = []
                for l in member.locks:
                    description_info = member.description(l.get("description"))
                    if description_info:
                        desc = description_info["text"] % l.data
                    else:
                        desc = l.get("description")
                    rows.append((l.uuid, l.get("amount"), l.get("currency"), desc))
                tbl = {
                    "type": "money_locks",
                    "title": self._("Money locks"),
                    "order": 21,
                    "header": [self._("Lock ID"), self._("Amount"), self._("Currency"), self._("Description")],
                    "rows": rows
                }
                tables.append(tbl)

    def permissions_list(self, perms):
        perms.append({"id": "users.money", "name": self._("Access to users money")})
        perms.append({"id": "users.money.give", "name": self._("Giving and taking money")})
        perms.append({"id": "money.currencies", "name": self._("Currencies editor")})

    def recommended_actions(self, recommended_actions):
        req = self.req()
        if req.has_access("money.currencies"):
            if not self.call("money.real-currency"):
                recommended_actions.append({"icon": "/st/img/coins.png", "content": u'%s <hook:admin.link href="money/currencies" title="%s" />' % (self._("You have not configured real money currency yet. Before launching your game you must configure its real money system&nbsp;&mdash; set up a currency and set it the 'real money' attribute."), self._("Open currency settings")), "order": 90, "before_launch": True})

    def project_params(self, params):
        currencies = {}
        self.call("currencies.list", currencies)
        real_ok = False
        for code, cur in currencies.iteritems():
            if cur.get("real"):
                params.append({"name": self._("Real money name"), "value": cur.get("name_plural"), "moderated": True, "edit": "money/currencies", "rowspan": 4})
                params.append({"name": self._("Declensions"), "value": cur.get("name_local")})
                params.append({"name": self._("Real in English"), "value": cur.get("name_en"), "moderated": True})
                params.append({"name": self._("Exchange rate"), "value": "1 %s = %s %s" % (code, cur.get("real_price"), cur.get("real_currency")), "moderated": True})
                params.append({"name": self._("Exchange to roubles"), "value": "1 %s = %s RUB" % (code, cur.get("real_roubles")), "moderated": True})
                real_ok = True
        if not real_ok:
            params.append({"name": self._("Real money currency name"), "value": '<span class="no">%s</span>' % self._("absent"), "moderated": True})

    def stock_rate(self, currency):
        rates = self.stock_rates()
        if rates and currency in rates:
            return rates[currency]
        return default_rates.get(currency, 1)

    def stock_rates(self):
        rates = self.main_app().mc.get("cbr-stock-rates")
        if rates:
            return rates
        try:
            data = self.download("http://www.cbr.ru/scripts/XML_daily.asp")
        except DownloadError:
            return None
        rates = {}
        response = xml.dom.minidom.parseString(data)
        if response.documentElement.tagName == "ValCurs":
            valutes = response.documentElement.getElementsByTagName("Valute")
            for valute in valutes:
                code = None
                rate = None
                nominal = None
                for param in valute.childNodes:
                    if param.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
                        if param.tagName == "CharCode":
                            code = getText(param.childNodes)
                        elif param.tagName == "Value":
                            rate = float(re_decimal_comma.sub('.', getText(param.childNodes)))
                        elif param.tagName == "Nominal":
                            nominal = float(re_decimal_comma.sub('.', getText(param.childNodes)))
                if code and rate and nominal and code in default_rates:
                    rates[code] = rate / nominal
        self.debug("Loaded CBR stock rates: %s", rates)
        self.main_app().mc.set("cbr-stock-rates", rates)
        return rates

class Xsolla(Module):
    def register(self):
        self.rhook("ext-ext-payment.2pay", self.payment_xsolla, priv="public")
        self.rhook("money-description.xsolla-pay", self.money_description_xsolla_pay)
        self.rhook("money-description.xsolla-chargeback", self.money_description_xsolla_chargeback)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("xsolla.payport-params", self.payport_params)
        self.rhook("xsolla.payment-params", self.payment_params)
        self.rhook("xsolla.register", self.register_xsolla)
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("money.not-enough-funds", self.not_enough_funds, priority=10)
        self.rhook("money.donate-message", self.donate_message)
        self.rhook("constructor.project-options", self.project_options)

    def project_options(self, options):
        if self.req().has_access("constructor.projects-xsolla"):
            options.append({"title": self._("Xsolla integration"), "value": '<hook:admin.link href="constructor/project-xsolla/%s" title="%s" />' % (self.app().tag, self._("open dashboard"))})

    def append_args(self, options):
        args = {}
        self.call("xsolla.payment-args", args, options)
        append = ""
        for key, val in args.iteritems():
            if type(val) == unicode:
                val = val.encode("cp1251")
            append += '&%s=%s' % (key, urlencode(val))
        return append

    def donate_message(self, currency, **kwargs):
        project_id = intz(self.conf("xsolla.project-id"))
        if project_id:
            cinfo = self.call("money.currency-info", currency)
            if cinfo and cinfo.get("real"):
                return '<a href="//2pay.ru/oplata/?id=%d%s" target="_blank" onclick="try { parent.Xsolla.paystation(); return false; } catch (e) { return true; }">%s</a>' % (project_id, self.append_args(kwargs), self._("Open payment interface"))

    def not_enough_funds(self, currency, **kwargs):
        project_id = intz(self.conf("xsolla.project-id"))
        if project_id:
            cinfo = self.call("money.currency-info", currency)
            if cinfo and cinfo.get("real"):
                raise Hooks.Return('%s <a href="//2pay.ru/oplata/?id=%d%s" target="_blank" onclick="try { parent.Xsolla.paystation(); return false; } catch (e) { return true; }">%s</a>' % (self._("Not enough %s.") % (self.call("l10n.literal_value", 100, cinfo.get("name_local")) if cinfo else htmlescape(currency)), project_id, self.append_args(kwargs), self._("Open payment interface")))

    def money_description_xsolla_pay(self):
        return {
            "args": ["payment_id", "payment_performed"],
            "text": self._("Xsolla payment"),
        }

    def money_description_xsolla_chargeback(self):
        return {
            "args": ["payment_id"],
            "text": self._("Xsolla chargeback"),
        }

    def objclasses_list(self, objclasses):
        objclasses["PaymentXsolla"] = (PaymentXsolla, PaymentXsollaList)

    def payment_xsolla(self):
        req = self.req()
        command = req.param_raw("command")
        sign = req.param_raw("md5")
        result = None
        comment = None
        id = None
        id_shop = None
        sum = None
        self.debug("Xsolla Request: %s", req.param_dict())
        try:
            secret = self.conf("xsolla.secret")
            if type(secret) == unicode:
                secret = secret.encode("windows-1251")
            if secret is None or secret == "":
                result = 5
                comment = "Payments are not accepted for this project"
            elif command == "check":
                v1 = req.param_raw("v1")
                if sign is None or sign.lower() != hashlib.md5(command + v1 + secret).hexdigest().lower():
                    result = 3
                    comment = "Invalid MD5 signature"
                else:
                    v1 = v1.decode("windows-1251")
                    self.debug("Xsolla Request: command=check, v1=%s", v1)
                    if self.call("session.find_user", v1):
                        result = 0
                    else:
                        result = 2
            elif command == "pay":
                id = req.param_raw("id")
                sum = req.param_raw("sum")
                date = req.param_raw("date")
                v1 = req.param_raw("v1")
                if sign is None or sign.lower() != hashlib.md5(command + v1 + id + secret).hexdigest().lower():
                    result = 3
                    comment = "Invalid MD5 signature"
                else:
                    v1 = v1.decode("windows-1251")
                    sum_v = float(sum)
                    self.debug("Xsolla Request: command=pay, id=%s, v1=%s, sum=%s, date=%s", id, v1, sum, date)
                    user = self.call("session.find_user", v1)
                    if user:
                        with self.lock(["PaymentXsolla.%s" % id]):
                            try:
                                existing = self.obj(PaymentXsolla, id)
                                result = 0
                                id_shop = id
                                sum = str(existing.get("sum"))
                            except ObjectNotFoundException:
                                currency = self.call("money.real-currency")
                                cinfo = self.call("money.currency-info", currency)
                                amount_rub = floatz(req.param("transfer_sum"))
#                               amount_rub = cinfo.get("real_roubles", 1) * sum_v * 0.9
                                payment = self.obj(PaymentXsolla, id, data={})
                                payment.set("v1", v1)
                                payment.set("user", user.uuid)
                                payment.set("sum", sum_v)
                                payment.set("date", date)
                                payment.set("performed", self.now())
                                payment.set("amount_rub", amount_rub)
                                member = MemberMoney(self.app(), "user", user.uuid)
                                member.credit(sum_v, currency, "xsolla-pay", payment_id=id, payment_performed=date)
                                payment.store()
                                self.call("dbexport.add", "donate", user=user.uuid, amount=amount_rub)
                                result = 0
                                id_shop = id
                    else:
                        result = 2
            elif command == "cancel":
                id = req.param_raw("id")
                if sign is None or sign.lower() != hashlib.md5(command + id + secret).hexdigest().lower():
                    result = 3
                    comment = "Invalid MD5 signature"
                else:
                    self.debug("Xsolla Request: command=cancel, id=%s", id)
                    with self.lock(["PaymentXsolla.%s" % id]):
                        try:
                            payment = self.obj(PaymentXsolla, id)
                            if payment.get("cancelled"):
                                result = 0
                            else:
                                payment.set("cancelled", self.now())
                                member = MemberMoney(self.app(), "user", payment.get("user"))
                                member.force_debit(payment.get("sum"), self.call("money.real-currency"), "xsolla-chargeback", payment_id=id)
                                payment.store()
                                self.call("dbexport.add", "chargeback", user=payment.get("user"), amount=payment.get("amount_rub", 0))
                                result = 0
                        except ObjectNotFoundException:
                            result = 2
                    result = 0
                    id = None
            elif command is None:
                result = 4
                comment = "Command not supplied"
            else:
                self.debug("Xsolla Request: command=%s", command)
                result = 4
                comment = "This command is not implemented"
        except Exception as e:
            result = 1
            comment = str(e)
        doc = xml.dom.minidom.getDOMImplementation().createDocument(None, "response", None)
        response = doc.documentElement
        if id is not None:
            elt = doc.createElement("id")
            elt.appendChild(doc.createTextNode(id))
            response.appendChild(elt)
        if id_shop is not None:
            elt = doc.createElement("id_shop")
            elt.appendChild(doc.createTextNode(id_shop))
            response.appendChild(elt)
        if sum is not None:
            elt = doc.createElement("sum")
            elt.appendChild(doc.createTextNode(sum))
            response.appendChild(elt)
        if result is not None:
            elt = doc.createElement("result")
            elt.appendChild(doc.createTextNode(str(result)))
            response.appendChild(elt)
        if comment is not None:
            elt = doc.createElement("comment")
            elt.appendChild(doc.createTextNode(comment))
            response.appendChild(elt)
        self.debug("Xsolla Response: %s", response.toxml("utf-8"))
        self.call("web.response", doc.toxml("windows-1251"), "application/xml")

    def payport_params(self, params, owner_uuid):
        payport = {}
        try:
            owner = self.obj(User, owner_uuid)
        except ObjectNotFoundException:
            owner = None
        else:
            payport["email"] = jsencode(owner.get("email"))
            payport["name"] = jsencode(owner.get("name"))
        payport["project_id"] = self.conf("xsolla.project-id")
        payport["language"] = {"ru": 0, "fr": 2}.get(self.call("l10n.lang"), 1)
        params["xsolla_payport"] = payport

    def payment_params(self, params, owner_uuid):
        payment = {}
        try:
            owner = self.obj(User, owner_uuid)
        except ObjectNotFoundException:
            owner = None
        else:
            payment["email"] = urlencode(owner.get("email").encode("windows-1251"))
            payment["name"] = urlencode(owner.get("name").encode("windows-1251"))
        payment["project_id"] = self.conf("xsolla.project-id")
        payment["language"] = {"ru": 0, "fr": 2}.get(self.call("l10n.lang"), 1)
        params["xsolla_payment"] = payment

    def register_xsolla(self):
        self.info("Registering in the Xsolla system")
        project = self.app().project
        lang = self.call("l10n.lang")
        doc = xml.dom.minidom.getDOMImplementation().createDocument(None, "response", None)
        request = doc.documentElement
        # Master ID
        master_id = str(self.main_app().config.get("xsolla.contragent-id"))
        elt = doc.createElement("id")
        elt.appendChild(doc.createTextNode(master_id))
        request.appendChild(elt)
        # Project title
        elt = doc.createElement("name")
        elt.setAttribute("loc", lang)
        elt.appendChild(doc.createTextNode(project.get("title_short")))
        request.appendChild(elt)
        if lang != "en":
            elt = doc.createElement("name")
            elt.setAttribute("loc", "en")
            elt.appendChild(doc.createTextNode(project.get("title_en")))
            request.appendChild(elt)
        # Currencies setup
        currencies = {}
        self.call("currencies.list", currencies)
        real_ok = False
        for code, cur in currencies.iteritems():
            if cur.get("real"):
                # Currency name
                elt = doc.createElement("currency")
                elt.setAttribute("loc", lang)
                elt.appendChild(doc.createTextNode(cur.get("name_plural")))
                request.appendChild(elt)
                if lang != "en":
                    elt = doc.createElement("currency")
                    elt.setAttribute("loc", "en")
                    elt.appendChild(doc.createTextNode(cur.get("name_en").split("/")[1]))
                    request.appendChild(elt)
                # Currency precision
                elt = doc.createElement("natur")
                elt.appendChild(doc.createTextNode("0" if cur.get("precision") else "1"))
                request.appendChild(elt)
                # Currency rate
                elt = doc.createElement("price")
                elt.appendChild(doc.createTextNode(str(cur.get("real_price"))))
                request.appendChild(elt)
                elt = doc.createElement("valuta")
                currencies = {
                    "RUB": "1",
                    "USD": "2",
                    "EUR": "3",
                    "UAH": "4",
                    "BYR": "5",
                    "GBP": "7",
                    "KZT": "77",
                }
                currency = currencies.get(cur.get("real_currency"), "1")
                elt.appendChild(doc.createTextNode(currency))
                request.appendChild(elt)
                # Minimal and maximal amount
                elt = doc.createElement("min")
                elt.appendChild(doc.createTextNode(str(0.1 ** cur.get("precision"))))
                request.appendChild(elt)
                elt = doc.createElement("max")
                elt.appendChild(doc.createTextNode("0"))
                request.appendChild(elt)
                break
        # Enter character name
        elt = doc.createElement("v0")
        elt.setAttribute("loc", lang)
        elt.appendChild(doc.createTextNode(self._("Enter character name:")))
        request.appendChild(elt)
        if lang != "en":
            elt = doc.createElement("v0")
            elt.setAttribute("loc", "en")
            elt.appendChild(doc.createTextNode("Enter character name:"))
            request.appendChild(elt)
        # Character name
        elt = doc.createElement("v1")
        elt.setAttribute("loc", lang)
        elt.appendChild(doc.createTextNode(self._("Character name:")))
        request.appendChild(elt)
        if lang != "en":
            elt = doc.createElement("v1")
            elt.setAttribute("loc", "en")
            elt.appendChild(doc.createTextNode("Character name:"))
            request.appendChild(elt)
        # Secret key
        secret = uuid4().hex
        elt = doc.createElement("secretKey")
        elt.appendChild(doc.createTextNode(secret))
        request.appendChild(elt)
        # Random number
        rnd = str(random.randrange(0, 1000000000))
        elt = doc.createElement("randomNumber")
        elt.appendChild(doc.createTextNode(rnd))
        request.appendChild(elt)
        # url
        elt = doc.createElement("url")
        elt.appendChild(doc.createTextNode(self.app().canonical_domain))
        request.appendChild(elt)
        # imageURL
        elt = doc.createElement("imageURL")
        elt.appendChild(doc.createTextNode(project.get("logo")))
        request.appendChild(elt)
        # payURL
        elt = doc.createElement("payUrl")
        elt.appendChild(doc.createTextNode("http://%s/ext-payment/2pay" % self.app().canonical_domain))
        request.appendChild(elt)
        # Description
        elt = doc.createElement("desc")
        elt.appendChild(doc.createTextNode(self.conf("gameprofile.description")))
        request.appendChild(elt)
        xmldata = request.toxml("utf-8")
        self.debug(u"Xsolla request: %s", xmldata)
        # Signature
        sign_str = str("%s%s%s") % (master_id, rnd, self.main_app().config.get("xsolla.secret-addgame"))
        sign = hashlib.md5(sign_str).hexdigest().lower()
        self.debug(u"Xsolla signing string '%s': %s", sign_str, sign)
        query = "xml=%s&sign=%s" % (urlencode(xmldata), urlencode(sign))
        self.debug(u"Xsolla urlencoded query: %s", query)
        try:
            with Timeout.push(90):
                cnn = HTTPConnection()
                cnn.connect(("2pay.ru", 80))
                try:
                    request = HTTPRequest()
                    request.method = "POST"
                    request.path = "/api/game/index.php"
                    request.host = "2pay.ru"
                    request.body = query
                    request.add_header("Content-type", "application/x-www-form-urlencoded; charset=utf-8")
                    request.add_header("Content-length", len(query))
                    request.add_header("Connection", "close")
                    response = cnn.perform(request)
                    self.debug(u"Xsolla response: %s %s", response.status_code, response.body)
                    if response.status_code == 200:
                        response = xml.dom.minidom.parseString(response.body)
                        if response.documentElement.tagName == "response":
                            result = response.documentElement.getElementsByTagName("result")
                            if result and getText(result[0].childNodes) == "OK":
                                game_id = response.documentElement.getElementsByTagName("gameId")
                                if game_id:
                                    game_id = getText(game_id[0].childNodes)
                                    self.debug("game_id: %s", game_id)
                                    game_id = intz(game_id)
                                    config = self.app().config_updater()
                                    config.set("xsolla.secret", secret)
                                    config.set("xsolla.project-id", game_id)
                                    config.store()
                finally:
                    cnn.close()
        except IOError as e:
            self.error("Error registering in the Xsolla system: %s", e)
        except TimeoutError:
            self.error("Error registering in the Xsolla system: Timed out")

    def gameinterface_render(self, character, vars, design):
        if self.conf("xsolla.project-id"):
            vars["js_modules"].add("xsolla")
            vars["js_init"].append("Xsolla.project = %d;" % self.conf("xsolla.project-id"))
            vars["js_init"].append("Xsolla.name = '%s';" % jsencode(urlencode(character.name)))
            vars["js_init"].append("Xsolla.lang = '%s';" % self.call("l10n.lang"))

class XsollaAdmin(Module):
    def register(self):
        self.rhook("ext-admin-constructor.project-xsolla", self.project_xsolla, priv="constructor.projects-xsolla")
        self.rhook("headmenu-admin-constructor.project-xsolla", self.headmenu_project_xsolla)
        self.rhook("permissions.list", self.permissions_list)

    def project_xsolla(self):
        req = self.req()
        uuid = req.args
        cmd = ""
        m = re_uuid_cmd.match(req.args)
        if m:
            uuid, cmd = m.group(1, 2)
        app = self.app().inst.appfactory.get_by_tag(uuid)
        if app is None:
            self.call("web.not_found")
        if cmd == "":
            payments = []
            lst = app.objlist(PaymentXsollaList, query_index="date", query_reversed=True)
            lst.load(silent=True)
            for pay in lst:
                payments.append({
                    "id": pay.uuid,
                    "performed": self.call("l10n.time_local", pay.get("performed")),
                    "date": pay.get("date"),
                    "user": pay.get("user"),
                    "v1": htmlescape(pay.get("v1")) if pay.get("v1") else pay.get("user"),
                    "sum": pay.get("sum"),
                    "cancelled": pay.get("cancelled")
                })
            vars = {
                "project": {
                    "uuid": uuid
                },
                "EditSettings": self._("Edit settings"),
                "PaymentURL": self._("Payment URL"),
                "SecretCode": self._("Secret code"),
                "SecretCodeAddGame": self._("Secret code for adding games"),
                "TimeXsolla": self._("Xsolla time"),
                "OurTime": self._("Our time"),
                "User": self._("User"),
                "Amount": self._("Amount"),
                "Chargeback": self._("Chargeback"),
                "payments": payments,
                "Update": self._("Update"),
                "Id": self._("Id"),
                "ProjectID": self._("Project ID"),
                "ContragentID": self._("Contragent ID"),
            }
            vars["settings"] = {
                "secret": htmlescape(app.config.get("xsolla.secret")),
                "secret_addgame": htmlescape(app.config.get("xsolla.secret-addgame")),
                "project_id": htmlescape(app.config.get("xsolla.project-id")),
                "contragent_id": htmlescape(app.config.get("xsolla.contragent-id")),
                "payment_url": "http://%s/ext-payment/2pay" % app.canonical_domain,
            }
            self.call("admin.response_template", "admin/money/xsolla-dashboard.html", vars)
        elif cmd == "settings":
            secret = req.param("secret")
            secret_addgame = req.param("secret_addgame")
            project_id = req.param("project_id")
            contragent_id = req.param("contragent_id")
            if req.param("ok"):
                config = app.config_updater()
                config.set("xsolla.secret", secret)
                config.set("xsolla.secret-addgame", secret_addgame)
                config.set("xsolla.project-id", project_id)
                config.set("xsolla.contragent-id", contragent_id)
                config.store()
                self.call("admin.redirect", "constructor/project-xsolla/%s" % uuid)
            else:
                secret = app.config.get("xsolla.secret")
                secret_addgame = app.config.get("xsolla.secret-addgame")
                project_id = app.config.get("xsolla.project-id")
                contragent_id = app.config.get("xsolla.contragent-id")
            fields = []
            fields.append({"name": "project_id", "label": self._("Xsolla project id"), "value": project_id})
            fields.append({"name": "contragent_id", "label": self._("Xsolla contragent id"), "value": contragent_id})
            fields.append({"name": "secret", "label": self._("Xsolla secret"), "value": secret})
            fields.append({"name": "secret_addgame", "label": self._("Xsolla secret for adding games"), "value": secret_addgame})
            self.call("admin.form", fields=fields)
        else:
            self.call("web.not_found")

    def headmenu_project_xsolla(self, args):
        uuid = args
        cmd = ""
        m = re_uuid_cmd.match(args)
        if m:
            uuid, cmd = m.group(1, 2)
        if cmd == "":
            return [self._("Xsolla dashboard"), "constructor/project-dashboard/%s" % uuid]
        elif cmd == "settings":
            return [self._("Settings editor"), "constructor/project-xsolla/%s" % uuid]

    def permissions_list(self, perms):
        perms.append({"id": "constructor.projects-xsolla", "name": self._("Constructor: Xsolla integration")})

class Money(Module):
    def register(self):
        self.rhook("currencies.list", self.currencies_list, priority=-1000)
        self.rhook("money-description.admin-give", self.money_description_admin_give)
        self.rhook("money-description.admin-take", self.money_description_admin_take)
        self.rhook("money.obj", self.member_money)
        self.rhook("money.valid_amount", self.valid_amount)
        self.rhook("money.real-currency", self.real_currency)
        self.rhook("money.format-price", self.format_price)
        self.rhook("money.price-text", self.price_text)
        self.rhook("money.price-html", self.price_html)
        self.rhook("money.currency-info", self.currency_info)
        self.rhook("money.not-enough-funds", self.not_enough_funds)

    def not_enough_funds(self, currency, **kwargs):
        cinfo = self.call("money.currency-info", currency)
        return self._("Not enough %s") % (self.call("l10n.literal_value", 100, cinfo.get("name_local")) if cinfo else htmlescape(currency))

    def currencies_list(self, currencies):
        lst = self.conf("money.currencies")
        if lst:
            for code, info in lst.iteritems():
                info["code"] = code
                currencies[code] = info

    def real_currency(self):
        try:
            return self._real_currency
        except AttributeError:
            self._real_currency = None
            for code, cur in self.currencies().iteritems():
                if cur.get("real"):
                    self._real_currency = code
            return self._real_currency

    def money_description_admin_give(self):
        return {
            "args": ["admin"],
            "text": self._("Given by the administration"),
        }

    def money_description_admin_take(self):
        return {
            "args": ["admin"],
            "text": self._("Taken by the administration"),
        }

    def valid_amount(self, amount, currency, errors=None, amount_field=None, currency_field=None):
        valid = True
        # checking currency
        currencies = {}
        self.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            valid = False
            if errors is not None and currency_field:
                errors[currency_field] = self._("Invalid currency")
        # checking amount
        try:
            amount = float(amount)
            if amount <= 0:
                valid = False
                if errors is not None and amount_field:
                    errors[amount_field] = self._("Amount must be greater than 0")
            elif amount >= 1000000000:
                valid = False
                if errors is not None and amount_field:
                    errors[amount_field] = self._("Amount must be less than 1000000000")
            elif currency_info is not None and amount != float(currency_info["format"] % amount):
                valid = False
                if errors is not None and amount_field:
                    errors[amount_field] = self._("Invalid amount precision")
        except ValueError:
            valid = False
            if errors is not None and amount_field:
                errors[amount_field] = self._("Invalid number format")
        return valid

    def member_money(self, member_type, member_uuid):
        return MemberMoney(self.app(), member_type, member_uuid)

    def format_price(self, price, currency):
        cinfo = self.currency_info(currency)
        min_val = 0.1 ** cinfo["precision"]
        price = math.ceil(price / min_val) * min_val
        if price < min_val:
            price = min_val
        return price

    def price_text(self, price, currency):
        cinfo = self.currency_info(currency)
        text_price = cinfo["format"] % price
        text_currency = cinfo["code"]
        return '%s %s' % (text_price, text_currency)

    def price_html(self, price, currency):
        cinfo = self.currency_info(currency)
        if cinfo is None:
            return '%s ???' % price
        html_price = cinfo["format"] % price
        html_currency = '<img src="%s" alt="%s" />' % (cinfo["icon"], cinfo["code"]) if cinfo.get("icon") else cinfo["code"]
        return '<span class="price"><span class="money-amount">%s</span> <span class="money-currency">%s</span></span>' % (html_price, html_currency)

    def currencies(self):
        try:
            return self._currencies
        except AttributeError:
            self._currencies = {}
            self.call("currencies.list", self._currencies)
            return self._currencies

    def currency_info(self, currency):
        return self.currencies().get(currency)

class WebMoneyAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-auth.index", self.menu_auth_index)
        self.rhook("ext-admin-wmlogin.settings", self.auth_settings, priv="webmoney.auth")

    def permissions_list(self, perms):
        perms.append({"id": "webmoney.auth", "name": self._("WebMoney authentication settings")})

    def menu_auth_index(self, menu):
        req = self.req()
        if req.has_access("webmoney.auth"):
            menu.append({"id": "wmlogin/settings", "text": self._("WebMoney authentication"), "leaf": True, "order": 20})

    def auth_settings(self):
        req = self.req()
        if req.ok():
            config = self.app().config_updater()
            config.set("wmlogin.wmid", req.param("wmid"))
            config.set("wmlogin.rid", req.param("rid"))
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        fields = [
            {"name": "wmid", "label": self._("WMID for WMLogin"), "value": self.conf("wmlogin.wmid")},
            {"name": "rid", "label": self._("RID for URL '%s'") % ("http://%s/webmoney/checkticket" % req.host()), "value": self.conf("wmlogin.rid")},
        ]
        self.call("admin.form", fields=fields)

class WebMoney(Module):
    def register(self):
        self.rhook("ext-webmoney.checkticket", self.check_ticket, priv="logged")
        self.rhook("wmcert.get", self.wmcert_get)
        self.rhook("wmlogin.url", self.wmlogin_url)

    def check_ticket(self):
        req = self.req()
        self.debug("WMLogin auth: %s", req.param_dict())
        ticket = req.param("WmLogin_Ticket")
        authtype = req.param("WmLogin_AuthType")
        remote_addr = req.param("WmLogin_UserAddress")
        user_wmid = req.param("WmLogin_WMID")
        rid = req.param("WmLogin_UrlID")
        service_wmid = self.conf("wmlogin.wmid")
        if rid != self.conf("wmlogin.rid"):
            self.error("WMLogin received rid=%s, expected=%s", rid, self.conf("wmlogin.rid"))
            self.call("web.forbidden")
        try:
            # validating ticket
            doc = xml.dom.minidom.getDOMImplementation().createDocument(None, "request", None)
            request = doc.documentElement
            request.appendChild(doc.createElement("siteHolder")).appendChild(doc.createTextNode(service_wmid))
            request.appendChild(doc.createElement("user")).appendChild(doc.createTextNode(user_wmid))
            request.appendChild(doc.createElement("ticket")).appendChild(doc.createTextNode(ticket))
            request.appendChild(doc.createElement("urlId")).appendChild(doc.createTextNode(rid))
            request.appendChild(doc.createElement("authType")).appendChild(doc.createTextNode(authtype))
            request.appendChild(doc.createElement("userAddress")).appendChild(doc.createTextNode(remote_addr))
            response = self.wm_query("wm_login_gate", "login.wmtransfer.com", "/ws/authorize.xiface", request)
            doc = response.documentElement
            if doc.tagName != "response":
                raise RuntimeError("Unexpected response from WMLogin")
            retval = doc.getAttribute("retval")
            sval = doc.getAttribute("sval")
            if retval == "0":
                self.call("wmlogin.authorized", authtype=authtype, remote_addr=remote_addr, wmid=user_wmid)
            else:
                self.error("WMLogin auth failed: retval=%s, sval=%s", retval, sval)
                self.call("web.forbidden")
        except HTTPError:
            self.call("web.response_global", self._("Error connecting to the WebMoney server. Try again later"), {})

    def wm_query(self, gate_name, gate_host, url, request):
        reqdata = request.toxml("utf-8")
        self.debug("WM reqdata: %s", reqdata)
        wm_gate = self.app().inst.config.get(gate_name, "unknown:0").split(":")
        host = str(wm_gate[0])
        port = int(wm_gate[1])
        try:
            with Timeout.push(20):
                cnn = HTTPConnection()
                try:
                    cnn.connect((host, port))
                except IOError as e:
                    raise HTTPError("Error connecting to %s:%d" % (host, port))
                try:
                    request = cnn.post(str(url), reqdata)
                    request.host = gate_host
                    request.add_header("Content-type", "application/xml")
                    request.add_header("Content-length", len(reqdata))
                    request.add_header("Connection", "close")
                    response = cnn.perform(request)
                    if response.status_code != 200:
                        raise HTTPError("Error downloading http://%s:%s%s: %s" % (host, port, url, response.status))
                    response = xml.dom.minidom.parseString(response.body)
                    self.debug("WM request: %s", response.toxml("utf-8"))
                    return response
                except IOError as e:
                    raise HTTPError("Error downloading http://%s:%s%s: %s" % (host, port, url, str(e)))
                finally:
                    cnn.close()
        except TimeoutError:
            raise HTTPError("Timeout downloading http://%s:%s%s" % (host, port, url))

    def wmcert_get(self, wmid):
        doc = xml.dom.minidom.getDOMImplementation().createDocument(None, "request", None)
        request = doc.documentElement
        request.appendChild(doc.createElement("wmid")).appendChild(doc.createTextNode(""))
        request.appendChild(doc.createElement("passportwmid")).appendChild(doc.createTextNode(wmid))
        request.appendChild(doc.createElement("sign")).appendChild(doc.createTextNode(""))
        params = request.appendChild(doc.createElement("params"))
        params.appendChild(doc.createElement("dict")).appendChild(doc.createTextNode("0"))
        params.appendChild(doc.createElement("info")).appendChild(doc.createTextNode("0"))
        params.appendChild(doc.createElement("mode")).appendChild(doc.createTextNode("0"))
        response = self.wm_query("wm_passport_gate", "passport.webmoney.ru", "/asp/XMLGetWMPassport.asp", request)
        doc = response.documentElement
        if doc.tagName != "response":
            raise RuntimeError("Unexpected response from WMPassport")
        if doc.getAttribute("retval") != "0":
            return 0
        level = 0
        for cert in doc.getElementsByTagName("row"):
            if cert.getAttribute("recalled") == "0":
                lvl = int(cert.getAttribute("tid"))
                if lvl > level:
                    level = lvl
        return level
    
    def wmlogin_url(self):
        lang = self.call("l10n.lang")
        if lang == "ru":
            lang = "ru-RU"
        else:
            lang = "en-EN"
        return "https://login.wmtransfer.com/GateKeeper.aspx?RID=%s&lang=%s" % (self.conf("wmlogin.rid"), lang)
