from mg import *
from mg.core.auth import *
import xml.dom.minidom
import hashlib
import re

re_uuid_cmd = re.compile(r'^([0-9a-z]+)/(.+)$')

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

    def available(self):
        return self.balance() - self.locked()

    # credit and debit

    def credit(self, amount, currency_info):
        self.set("balance", currency_info["format"] % (self.balance() + amount))

    def force_debit(self, amount, currency_info):
        self.set("balance", currency_info["format"] % (self.balance() - amount))

    def debit(self, amount, currency_info):
        if self.available() - amount < self.low_limit():
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
        if self.available() - amount < self.low_limit():
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
        "member": [["member"], "created"],
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

    def locks(self):
        list = self.app.objlist(AccountLockList, query_index="member", query_equal=self.member)
        list.load(silent=True)
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

    def lock(self, amount, currency, description, **kwargs):
        self.description_validate(description, kwargs)
        currencies = {}
        self.app.hooks.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise RuntimeError("Invalid currency")
        with self.app.lock(["MemberMoney.%s" % self.member]):
            account = self.account(currency, False)
            if not account:
                return None
            lock = self.app.obj(AccountLock)
            lock.set("member", self.member)
            lock.set("account", account.uuid)
            lock.set("amount", currency_info["format"] % amount)
            lock.set("currency", currency)
            lock.set("description", description)
            lock.set("created", self.app.now())
            for key, val in kwargs.iteritems():
                lock.set(key, val)
            if not account.lock(amount, currency_info):
                return None
            account.store()
            lock.store()
            return lock

    def unlock(self, lock_uuid):
        currencies = {}
        self.app.hooks.call("currencies.list", currencies)
        with self.app.lock(["MemberMoney.%s" % self.member]):
            try:
                lock = self.app.obj(AccountLock, lock_uuid)
            except ObjectNotFoundException:
                return None
            else:
                account = self.app.obj(Account, lock.get("account"))
                currency_info = currencies.get(account.get("currency"))
                if currency_info is None:
                    return None
                account.unlock(float(lock.get("amount")), currency_info)
                account.store()
                lock.remove()
                return lock

    def balance(self, currency):
        account = self.account(currency)
        if account is None:
            return 0
        return account.balance()
    
    def available(self, currency):
        account = self.account(currency)
        if account is None:
            return 0
        return account.available()
    
class Money(Module):
    def register(self):
        Module.register(self)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("auth.user-options", self.user_options)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("ext-admin-money.give", self.admin_money_give)
        self.rhook("headmenu-admin-money.give", self.headmenu_money_give)
        self.rhook("ext-admin-money.take", self.admin_money_take)
        self.rhook("headmenu-admin-money.take", self.headmenu_money_take)
        self.rhook("currencies.list", self.currencies_list, priority=-1000)
        self.rhook("money-description.admin-give", self.money_description_admin_give)
        self.rhook("money-description.admin-take", self.money_description_admin_take)
        self.rhook("ext-admin-money.account", self.admin_money_account)
        self.rhook("headmenu-admin-money.account", self.headmenu_money_account)
        self.rhook("money.member-money", self.member_money)
        self.rhook("money.valid_amount", self.valid_amount)

    def currencies_list(self, currencies):
        if self.app().tag == "main":
            currencies["MM$"] = {
                "format": "%.2f",
                "description": "MM$",
            }
        if not len(currencies):
            currencies["GLD"] = {
                "format": "%d",
                "description": self._("Gold")
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

    def headmenu_money_give(self, args):
        try:
            user = self.obj(User, args)
        except ObjectNotFoundException:
            return
        return [self._("Give money"), "auth/user-dashboard/%s" % args]

    def valid_amount(self, amount, currency, errors=None, amount_field=None, currency_field=None):
        print "called_valid_amount"
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
            elif currency_info is not None and amount != float(currency_info["format"] % amount):
                valid = False
                if errors is not None and amount_field:
                    errors[amount_field] = self._("Invalid amount precision")
        except ValueError:
            valid = False
            if errors is not None and amount_field:
                errors[amount_field] = self._("Invalid number format")
        return valid

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
            self.call("money.valid_amount", amount, currency, errors, "amount", "v_currency")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            member = MemberMoney(self.app(), user.uuid)
            member.credit(amount, currency, "admin-give", admin=req.user())
            self.call("admin.redirect", "auth/user-dashboard/%s" % user.uuid)
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
        return [self._("Take money"), "auth/user-dashboard/%s" % args]

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
            self.call("admin.redirect", "auth/user-dashboard/%s" % user.uuid)
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
        return [self._("Account %s") % acc.uuid, "auth/user-dashboard/%s" % acc.get("member")]

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
                "description": description["text"] % op.data if description else op.get("description")
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
        if self.req().has_access("users.money"):
            member = MemberMoney(self.app(), user.uuid)
            accounts = member.accounts()
            if len(accounts):
                tables.append({
                    "header": [self._("Account Id"), self._("Currency"), self._("Balance"), self._("Locked"), self._("Low limit")],
                    "rows": [('<hook:admin.link href="money/account/{0}" title="{0}" />'.format(a.uuid), a.get("currency"), a.get("balance"), a.get("locked"), a.get("low_limit")) for a in accounts]
                })
            locks = member.locks()
            if len(locks):
                rows = []
                for l in locks:
                    description_info = member.description(l.get("description"))
                    if description_info:
                        desc = description_info["text"] % l.data
                    else:
                        desc = l.get("description")
                    rows.append((l.uuid, l.get("amount"), l.get("currency"), desc))
                tables.append({
                    "header": [self._("Lock ID"), self._("Amount"), self._("Currency"), self._("Description")],
                    "rows": rows
                })

    def user_options(self, user, options):
        if self.req().has_access("users.money.give"):
            options.append({
                "title": self._("Money operations"),
                "value": u'<hook:admin.link href="money/give/{0}" title="{1}" /> &bull; <hook:admin.link href="money/take/{0}" title="{2}" />'.format(user.uuid, self._("Give money"), self._("Take money"))
            })

    def objclasses_list(self, objclasses):
        objclasses["Account"] = (Account, AccountList)
        objclasses["AccountLock"] = (AccountLock, AccountLockList)
        objclasses["AccountOperation"] = (AccountOperation, AccountOperationList)

    def permissions_list(self, perms):
        perms.append({"id": "users.money", "name": self._("Constructor: access to users money")})
        perms.append({"id": "users.money.give", "name": self._("Constructor: giving and taking money")})

    def member_money(self, member_uuid):
        return MemberMoney(self.app(), member_uuid)

class TwoPay(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-ext-payment.2pay", self.payment_2pay)
        self.rhook("ext-admin-constructor.project-2pay", self.project_2pay)
        self.rhook("headmenu-admin-constructor.project-2pay", self.headmenu_project_2pay)
        self.rhook("money-description.2pay-pay", self.money_description_2pay_pay)
        self.rhook("money-description.2pay-chargeback", self.money_description_2pay_chargeback)
        self.rhook("constructor.project-options", self.project_options)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("2pay.payport-params", self.payport_params)
        self.rhook("2pay.payment-params", self.payment_params)

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
                "ProjectID": self._("Project ID"),
            }
            vars["settings"] = {
                "secret": htmlescape(self.conf("2pay.secret")),
                "project_id": htmlescape(self.conf("2pay.project-id")),
                "payment_url": "http://%s/ext-payment/2pay" % app.domain,
            }
            self.call("admin.response_template", "admin/money/2pay-dashboard.html", vars)
        elif cmd == "settings":
            secret = req.param("secret")
            project_id = req.param("project_id")
            if req.param("ok"):
                config = self.app().config
                config.set("2pay.secret", secret)
                config.set("2pay.project-id", project_id)
                config.store()
                self.call("admin.redirect", "constructor/project-2pay/%s" % uuid)
            else:
                secret = self.conf("2pay.secret")
                project_id = self.conf("2pay.project-id")
            fields = []
            fields.append({"name": "project_id", "label": self._("2pay project id"), "value": project_id})
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
            secret = self.conf("2pay.secret")
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
                    self.debug("2pay Request: command=check, v1=%s", v1)
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
                    self.debug("2pay Request: command=pay, id=%s, v1=%s, sum=%s, date=%s", id, v1, sum, date)
                    user = self.call("session.find_user", v1)
                    if user:
                        with self.lock(["Payment2pay.%s" % id]):
                            try:
                                existing = self.obj(Payment2pay, id)
                                result = 0
                                id_shop = id
                                sum = str(existing.get("sum"))
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
                                id_shop = id
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
        self.call("web.response", doc.toxml("windows-1251"), {})

    def permissions_list(self, perms):
        if self.app().tag == "main":
            perms.append({"id": "constructor.projects-2pay", "name": self._("Constructor: 2pay integration")})

    def payport_params(self, params, owner_uuid):
        payport = {}
        try:
            owner = self.obj(User, owner_uuid)
        except ObjectNotFoundException:
            owner = None
        else:
            payport["email"] = jsencode(owner.get("email"))
            payport["name"] = jsencode(owner.get("name"))
        payport["project_id"] = self.conf("2pay.project-id")
        payport["language"] = {"ru": 0, "fr": 2}.get(self.call("l10n.lang"), 1)
        params["twopay_payport"] = payport

    def payment_params(self, params, owner_uuid):
        payment = {}
        try:
            owner = self.obj(User, owner_uuid)
        except ObjectNotFoundException:
            owner = None
        else:
            payment["email"] = urlencode(owner.get("email").encode("windows-1251"))
            payment["name"] = urlencode(owner.get("name").encode("windows-1251"))
        payment["project_id"] = self.conf("2pay.project-id")
        payment["language"] = {"ru": 0, "fr": 2}.get(self.call("l10n.lang"), 1)
        params["twopay_payment"] = payment
