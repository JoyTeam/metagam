from mg import *
from mg.core.auth import *
import xml.dom.minidom
import hashlib
import re

re_uuid_cmd = re.compile(r'^([0-9a-z]+)/(.+)$')

class Money2paySettings(CassandraObject):
    _indexes = {
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Money2paySettings-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Money2paySettings._indexes

class Account(CassandraObject):
    _indexes = {
        "all": [[]],
        "member": [["member"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Account-"
        CassandraObject.__init__(self, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Account-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Account._indexes

    def balance(self):
        return float(self.get("balance"))

    def low_limit(self):
        return float(self.get("low_limit"))

    def locked(self):
        return float(self.get("locked"))

    # credit and debit

    def credit(self, amount, currency_info):
        self.set("balance", currency_info["format"] % (self.balance() + amount))

    def force_debit(self, amount, currency_info):
        self.set("balance", currency_info["format"] % (self.balance() - amount))

    def debit(self, amount, currency_info):
        if self.balance() - self.locked() - amount < self.low_limit():
            return False
        self.force_debit(amount, currency_info)
        return True

    # money locking

    def force_lock(self, amount, currency_info):
        self.set("locked", currency_info["format"] % (self.locked() + amount))

    def unlock(self, amount, currency_info):
        val = self.locked() - amount
        if val < 0:
            val = 0
        self.set("locked", currency_info["format"] % val)

    def lock(self, amount, currency_info):
        if self.balance() - self.locked() - amount < self.low_limit():
            return False
        self.force_lock(amount, currency_info)
        return True

class AccountList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Account-"
        kwargs["cls"] = Account
        CassandraObjectList.__init__(self, *args, **kwargs)

class AccountLock(CassandraObject):
    _indexes = {
        "account": [["account"], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AccountLock-"
        CassandraObject.__init__(self, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AccountLock-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return AccountLock._indexes

class AccountLockList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AccountLock-"
        kwargs["cls"] = AccountLock
        CassandraObjectList.__init__(self, *args, **kwargs)

class AccountOperation(CassandraObject):
    _indexes = {
        "account": [["account"], "performed"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AccountOperation-"
        CassandraObject.__init__(self, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AccountOperation-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return AccountOperation._indexes

class AccountOperationList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "AccountOperation-"
        kwargs["cls"] = AccountOperation
        CassandraObjectList.__init__(self, *args, **kwargs)

class Payment2pay(CassandraObject):
    _indexes = {
        "all": [[], "performed"],
        "user": [["user"], "performed"],
        "date": [[], "date"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Payment2pay-"
        CassandraObject.__init__(self, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Payment2pay-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Payment2pay._indexes

class Payment2payList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Payment2pay-"
        kwargs["cls"] = Payment2pay
        CassandraObjectList.__init__(self, *args, **kwargs)

class MemberMoney(object):
    def __init__(self, app, member):
        self.app = app
        self.member = member

    def accounts(self):
        try:
            return self._accounts
        except AttributeError:
            pass
        list = self.app.objlist(AccountList, query_index="member", query_equal=self.member)
        list.load(silent=True)
        self._accounts = list
        return list

    def account(self, currency, create=False):
        for acc in self.accounts():
            if acc.get("currency") == currency:
                return acc
        if not create:
            return None
        account = self.app.obj(Account)
        account.set("member", self.member)
        account.set("balance", 0)
        account.set("currency", currency)
        account.set("locked", 0)
        account.set("low_limit", 0)
        account.store()
        return account

    def description(self, description):
        "Looks for description info"
        info = self.app.hooks.call("money-description.%s" % description)
        if info is None:
            raise RuntimeError("Invalid money transfer description")
        return info

    def description_validate(self, description, kwargs):
        info = self.description(description)
        for arg in info["args"]:
            if not kwargs.has_key(arg):
                raise RuntimeError("Missing argument %s for description %s" % (arg, description))

    def credit(self, amount, currency, description, **kwargs):
        self.description_validate(description, kwargs)
        currencies = {}
        self.app.hooks.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise RuntimeError("Invalid currency")
        with self.app.lock(["MemberMoney.%s" % self.member]):
            account = self.account(currency, True)
            account.credit(amount, currency_info)
            op = self.app.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op.set(key, val)
            op.set("account", account.uuid)
            op.set("performed", self.app.now())
            op.set("amount", currency_info["format"] % amount)
            op.set("balance", currency_info["format"] % account.balance())
            op.set("description", description)
            account.store()
            op.store()

    def debit(self, amount, currency, description, **kwargs):
        self.description_validate(description, kwargs)
        currencies = {}
        self.app.hooks.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise RuntimeError("Invalid currency")
        with self.app.lock(["MemberMoney.%s" % self.member]):
            account = self.account(currency, False)
            if account is None:
                return False
            if not account.debit(amount, currency_info):
                return False
            op = self.app.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op.set(key, val)
            op.set("account", account.uuid)
            op.set("performed", self.app.now())
            op.set("amount", currency_info["format"] % -amount)
            op.set("balance", currency_info["format"] % account.balance())
            op.set("description", description)
            account.store()
            op.store()
            return True

    def force_debit(self, amount, currency, description, **kwargs):
        self.description_validate(description, kwargs)
        currencies = {}
        self.app.hooks.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise RuntimeError("Invalid currency")
        with self.app.lock(["MemberMoney.%s" % self.member]):
            account = self.account(currency, True)
            account.force_debit(amount, currency_info)
            op = self.app.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op.set(key, val)
            op.set("account", account.uuid)
            op.set("performed", self.app.now())
            op.set("amount", currency_info["format"] % -amount)
            op.set("balance", currency_info["format"] % account.balance())
            op.set("description", description)
            account.store()
            op.store()

    def transfer(self, member, amount, currency, description, **kwargs):
        self.description_validate(description, kwargs)
        currencies = {}
        self.app.hooks.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise RuntimeError("Invalid currency")
        with self.app.lock(["MemberMoney.%s" % self.member, "MemberMoney.%s" % member]):
            target = MemberMoney(self.app, member)
            account_from = self.account(currency, False)
            if account_from is None:
                return False
            account_to = target.account(currency, True)
            if not account_from.debit(amount, currency_info):
                return False
            account_to.credit(amount, currency_info)
            performed = self.app.now()
            op1 = self.app.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op1.set(key, val)
            op1.set("account", account_from.uuid)
            op1.set("performed", performed)
            op1.set("amount", currency_info["format"] % -amount)
            op1.set("balance", currency_info["format"] % account_from.balance())
            op1.set("description", description)
            op2 = self.app.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op2.set(key, val)
            op2.set("account", account_to.uuid)
            op2.set("performed", performed)
            op2.set("amount", currency_info["format"] % amount)
            op2.set("balance", currency_info["format"] % account_to.balance())
            op2.set("description", description)
            op1.set("reference", op2.uuid)
            op2.set("reference", op1.uuid)
            account_from.store()
            account_to.store()
            op1.store()
            op2.store()
            return True
    
class Money(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-ext-payment.2pay", self.payment_2pay)
        self.rhook("constructor.user-options", self.user_options)
        self.rhook("constructor.project-options", self.project_options)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-constructor.project-2pay", self.project_2pay)
        self.rhook("headmenu-admin-constructor.project-2pay", self.headmenu_project_2pay)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-admin-money.accounts", self.admin_money_accounts)
        self.rhook("headmenu-admin-money.accounts", self.headmenu_money_accounts)
        self.rhook("ext-admin-money.give", self.admin_money_give)
        self.rhook("headmenu-admin-money.give", self.headmenu_money_give)
        self.rhook("ext-admin-money.take", self.admin_money_take)
        self.rhook("headmenu-admin-money.take", self.headmenu_money_take)
        self.rhook("currencies.list", self.currencies_list)
        self.rhook("money-description.admin-give", self.money_description_admin_give)
        self.rhook("money-description.admin-take", self.money_description_admin_take)
        self.rhook("money-description.2pay-pay", self.money_description_2pay_pay)
        self.rhook("money-description.2pay-chargeback", self.money_description_2pay_chargeback)
        self.rhook("ext-admin-money.account", self.admin_money_account)
        self.rhook("headmenu-admin-money.account", self.headmenu_money_account)

    def currencies_list(self, currencies):
        if self.app().tag == "main":
            currencies["MM$"] = {
                "format": "%.2f",
                "description": "MM$",
            }

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

    def money_description_2pay_pay(self):
        return {
            "args": ["payment_id", "payment_performed"],
            "text": self._("2pay payment"),
        }

    def money_description_2pay_chargeback(self):
        return {
            "args": ["payment_id"],
            "text": self._("2pay chargeback"),
        }

    def headmenu_money_give(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("Give money"), "money/accounts/%s" % args]

    def admin_money_give(self):
        self.call("session.require_permission", "users.money.give")
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
                    errors["amount"] = self._("Amount must be greater than 0")
                elif currency_info is not None and amount != float(currency_info["format"] % amount):
                    errors["amount"] = self._("Invalid amount precision")
            except ValueError:
                errors["amount"] = self._("Invalid number format")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            member = MemberMoney(self.app(), user.uuid)
            member.credit(amount, currency, "admin-give", admin=req.user())
            self.call("admin.redirect", "money/accounts/%s" % user.uuid)
        else:
            amount = "0"
        fields = []
        fields.append({"name": "amount", "label": self._("Give amount"), "value": amount})
        fields.append({"name": "currency", "label": self._("Currency"), "type": "combo", "value": currency, "values": [(code, info["description"]) for code, info in currencies.iteritems()], "allow_blank": True})
        buttons = [{"text": self._("Give")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def headmenu_money_take(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("Take money"), "money/accounts/%s" % args]

    def admin_money_take(self):
        self.call("session.require_permission", "users.money.give")
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
                    errors["amount"] = self._("Amount must be greater than 0")
                elif currency_info is not None and amount != float(currency_info["format"] % amount):
                    errors["amount"] = self._("Invalid amount precision")
            except ValueError:
                errors["amount"] = self._("Invalid number format")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            member = MemberMoney(self.app(), user.uuid)
            member.force_debit(amount, currency, "admin-take", admin=req.user())
            self.call("admin.redirect", "money/accounts/%s" % user.uuid)
        else:
            amount = "0"
        fields = []
        fields.append({"name": "amount", "label": self._("Take amount"), "value": amount})
        fields.append({"name": "currency", "label": self._("Currency"), "type": "combo", "value": currency, "values": [(code, info["description"]) for code, info in currencies.iteritems()], "allow_blank": True})
        buttons = [{"text": self._("Take")}]
        self.call("admin.form", fields=fields, buttons=buttons)

    def headmenu_money_account(self, args):
        try:
            acc = self.obj(Account, args)
        except ObjectNotFoundException:
            return
        return [acc.uuid, "money/accounts/%s" % acc.get("member")]

    def admin_money_account(self):
        self.call("session.require_permission", "users.money")
        req = self.req()
        try:
            account = self.obj(Account, req.args)
        except ObjectNotFoundException:
            return
        currencies = {}
        self.call("currencies.list", currencies)
        operations = []
        list = self.objlist(AccountOperationList, query_index="account", query_equal=account.uuid, query_reversed=True)
        list.load(silent=True)
        for op in list:
            description = self.call("money-description.%s" % op.get("description"))
            operations.append({
                "performed": op.get("performed"),
                "amount": op.get("amount"),
                "balance": op.get("balance"),
                "description": description["text"] if description else op.get("description")
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

    def headmenu_money_accounts(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("Accounts"), "constructor/user-dashboard/%s" % args]

    def admin_money_accounts(self):
        self.call("session.require_permission", "users.money")
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        member = MemberMoney(self.app(), user.uuid)
        accounts = member.accounts()
        vars = {
            "member": {
                "uuid": user.uuid
            },
            "AccountId": self._("Account Id"),
            "Balance": self._("Balance"),
            "Locked": self._("Locked"),
            "LowLimit": self._("Low limit"),
            "accounts": accounts.data(),
            "GiveMoney": self._("Give money"),
            "TakeMoney": self._("Take money"),
            "may_give": req.has_access("users.money.give"),
            "Currency": self._("Currency"),
        }
        self.call("admin.response_template", "admin/money/member.html", vars)

    def user_options(self, user, options):
        if self.req().has_access("users.money"):
            options.append({"title": self._("Money accounts"), "value": '<hook:admin.link href="money/accounts/%s" title="%s" />' % (user.uuid, self._("open list"))})

    def project_options(self, options):
        if self.req().has_access("constructor.projects-2pay"):
            options.append({"title": self._("2pay integration"), "value": '<hook:admin.link href="constructor/project-2pay/%s" title="%s" />' % (self.app().tag, self._("open dashboard"))})

    def headmenu_project_2pay(self, args):
        uuid = args
        cmd = ""
        m = re_uuid_cmd.match(args)
        if m:
            uuid, cmd = m.group(1, 2)
        if cmd == "":
            return [self._("2pay dashboard"), "constructor/project-dashboard/%s" % uuid]
        elif cmd == "settings":
            return [self._("Settings editor"), "constructor/project-2pay/%s" % uuid]

    def objclasses_list(self, objclasses):
        objclasses["Money2paySettings"] = (Money2paySettings, None)
        objclasses["Account"] = (Account, AccountList)
        objclasses["AccountLock"] = (AccountLock, AccountLockList)
        objclasses["AccountOperation"] = (AccountOperation, AccountOperationList)
        objclasses["Payment2pay"] = (Payment2pay, Payment2payList)

    def project_2pay(self):
        self.call("session.require_permission", "constructor.projects-2pay")
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
            list = self.objlist(Payment2payList, query_index="date", query_reversed=True)
            list.load(silent=True)
            for pay in list:
                payments.append({
                    "id": pay.uuid,
                    "performed": pay.get("performed"),
                    "date": pay.get("date"),
                    "user": pay.get("user"),
                    "v1": cgi.escape(pay.get("v1")) if pay.get("v1") else pay.get("user"),
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
                "Time2pay": self._("2pay time"),
                "OurTime": self._("Our time"),
                "User": self._("User"),
                "Amount": self._("Amount"),
                "Chargeback": self._("Chargeback"),
                "payments": payments,
                "Update": self._("Update"),
                "Id": self._("Id"),
            }
            try:
                settings = self.obj(Money2paySettings, "1")
                vars["settings"] = {
                    "secret": cgi.escape(settings.get("secret")),
                    "payment_url": "http://%s/ext-payment/2pay" % app.domain,
                }
            except ObjectNotFoundException:
                pass
            self.call("admin.response_template", "admin/money/2pay-dashboard.html", vars)
        elif cmd == "settings":
            secret = req.param("secret")
            settings = self.obj(Money2paySettings, "1", silent=True)
            if req.param("ok"):
                settings.set("secret", secret)
                settings.store()
                self.call("admin.redirect", "constructor/project-2pay/%s" % uuid)
            else:
                secret = settings.get("secret")
            fields = []
            fields.append({"name": "secret", "label": self._("2pay secret"), "value": secret})
            self.call("admin.form", fields=fields)
        else:
            self.call("web.not_found")

    def payment_2pay(self):
        req = self.req()
        command = req.param_raw("command")
        sign = req.param_raw("md5")
        result = None
        comment = None
        id = None
        id_shop = None
        sum = None
        try:
            settings = self.obj(Money2paySettings, "1", silent=True)
            secret = settings.get("secret")
            if type(secret) == unicode:
                secret = secret.encode("cp1251")
            if secret is None or secret == "":
                result = 5
                comment = "Payments are not accepted for this project"
            elif command == "check":
                v1 = req.param_raw("v1")
                if sign is None or sign.lower() != hashlib.md5(command + v1 + secret).hexdigest().lower():
                    result = 3
                    comment = "Invalid MD5 signature"
                else:
                    v1 = v1.decode("cp1251")
                    self.debug("2pay Request: command=check, v1=%s", v1)
                    if self.call("session.find_user", v1):
                        result = 0
                    else:
                        result = 2
            elif command == "pay":
                id = req.param_raw("id")
                id_shop = req.param_raw("id_shop")
                sum = req.param_raw("sum")
                date = req.param_raw("date")
                v1 = req.param_raw("v1")
                if sign is None or sign.lower() != hashlib.md5(command + v1 + id + secret).hexdigest().lower():
                    result = 3
                    comment = "Invalid MD5 signature"
                else:
                    v1 = v1.decode("cp1251")
                    sum_v = float(sum)
                    self.debug("2pay Request: command=pay, id=%s, v1=%s, sum=%s, date=%s", id, v1, sum, date)
                    user = self.call("session.find_user", v1)
                    if user:
                        with self.lock(["Payment2pay.%s" % id]):
                            try:
                                existing = self.obj(Payment2pay, id)
                                result = 0
                            except ObjectNotFoundException:
                                payment = self.obj(Payment2pay, id, data={})
                                payment.set("v1", v1)
                                payment.set("user", user.uuid)
                                payment.set("sum", sum_v)
                                payment.set("date", date)
                                payment.set("performed", self.now())
                                member = MemberMoney(self.app(), user.uuid)
                                member.credit(sum_v, "MM$", "2pay-pay", payment_id=id, payment_performed=date)
                                payment.store()
                                result = 0
                    else:
                        result = 2
            elif command == "cancel":
                id = req.param_raw("id")
                if sign is None or sign.lower() != hashlib.md5(command + id + secret).hexdigest().lower():
                    result = 3
                    comment = "Invalid MD5 signature"
                else:
                    self.debug("2pay Request: command=cancel, id=%s", id)
                    with self.lock(["Payment2pay.%s" % id]):
                        try:
                            payment = self.obj(Payment2pay, id)
                            if payment.get("cancelled"):
                                result = 0
                            else:
                                payment.set("cancelled", self.now())
                                member = MemberMoney(self.app(), payment.get("user"))
                                member.force_debit(payment.get("sum"), "MM$", "2pay-chargeback", payment_id=id)
                                payment.store()
                                result = 0
                        except ObjectNotFoundException:
                            result = 2
                    result = 0
            elif command is None:
                result = 4
                comment = "Command not supplied"
            else:
                self.debug("2pay Request: command=%s", command)
                result = 4
                comment = "This command is not implemented"
        except (TaskletExit, SystemExit, KeyboardInterrupt):
            raise
        except BaseException as e:
            result = 1
            comment = str(e)
        req.content_type = "application/xml"
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
        self.debug("2pay Response: %s", response.toxml("utf-8"))
        self.call("web.response", doc.toxml("cp1251"), {})

    def permissions_list(self, perms):
        if self.app().tag == "main":
            perms.append({"id": "constructor.projects-2pay", "name": self._("Constructor: 2pay integration")})
        perms.append({"id": "users.money", "name": self._("Constructor: access to users money")})
        perms.append({"id": "users.money.give", "name": self._("Constructor: giving and taking money")})

