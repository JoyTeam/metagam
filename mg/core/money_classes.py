from mg import *
import re

re_money_script_field = re.compile(r'^(balance|available)_(\S+)$')

class MoneyError(Exception):
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return self.val

class Account(CassandraObject):
    clsname = "Account"
    indexes = {
        "all": [[]],
        "member": [["member"]],
    }

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
        if self.available() - amount < self.low_limit() - 1e-6:
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
        if self.available() - amount < self.low_limit() - 1e-6:
            return False
        self.force_lock(amount, currency_info)
        return True

class AccountList(CassandraObjectList):
    objcls = Account

class AccountLock(CassandraObject):
    clsname = "AccountLock"
    indexes = {
        "account": [["account"], "created"],
        "member": [["member"], "created"],
    }

class AccountLockList(CassandraObjectList):
    objcls = AccountLock

class AccountOperation(CassandraObject):
    clsname = "AccountOperation"
    indexes = {
        "performed": [[], "performed"],
        "account": [["account"], "performed"],
    }

class AccountOperationList(CassandraObjectList):
    objcls = AccountOperation

class PaymentXsolla(CassandraObject):
    clsname = "PaymentXsolla"
    indexes = {
        "all": [[], "performed"],
        "user": [["user"], "performed"],
        "date": [[], "date"],
    }

class PaymentXsollaList(CassandraObjectList):
    objcls = PaymentXsolla

class MemberMoney(Module):
    def __init__(self, app, member_type, member, fqn="mg.core.money.MemberMoney"):
        Module.__init__(self, app, fqn)
        self.member_type = member_type
        self.member = member

    @property
    def accounts(self):
        try:
            return self._accounts
        except AttributeError:
            pass
        lst = self.objlist(AccountList, query_index="member", query_equal=self.member)
        lst.load(silent=True)
        self._accounts = lst
        return lst

    @property
    def locks(self):
        try:
            return self._locks
        except AttributeError:
            pass
        lst = self.objlist(AccountLockList, query_index="member", query_equal=self.member)
        lst.load(silent=True)
        self._locks = lst
        return lst

    def account(self, currency, create=False):
        for acc in self.accounts:
            if acc.get("currency") == currency:
                return acc
        if not create:
            return None
        account = self.obj(Account)
        account.set("member", self.member)
        account.set("balance", 0)
        account.set("currency", currency)
        account.set("locked", 0)
        account.set("low_limit", 0)
        account.store()
        del self._accounts
        return account

    def description(self, description):
        "Looks for description info"
        info = self.call("money-description.%s" % description)
        if info is None:
            raise MoneyError(self._("Invalid money transfer description"))
        return info

    def description_validate(self, description, kwargs):
        info = self.description(description)
        for arg in info["args"]:
            if not kwargs.has_key(arg):
                raise MoneyError(self._("Missing argument {arg} for description {desc}").format(arg=arg, desc=description))

    @property
    def lock_key(self):
        return "%s-Money.%s" % (self.member_type, self.member)

    def credit(self, amount, currency, description, **kwargs):
        if amount < 0:
            raise MoneyError(self._("Negative money amount"))
        if amount == 0:
            return
        self.description_validate(description, kwargs)
        currencies = {}
        self.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise MoneyError(self._("Invalid currency: %s") % currency)
        with Module.lock(self, [self.lock_key]):
            account = self.account(currency, True)
            account.credit(amount, currency_info)
            op = self.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op.set(key, val)
            op.set("account", account.uuid)
            op.set("currency", currency)
            op.set("performed", self.now())
            op.set("amount", currency_info["format"] % amount)
            op.set("balance", currency_info["format"] % account.balance())
            op.set("description", description)
            account.store()
            op.store()

    def debit(self, amount, currency, description, **kwargs):
        if amount < 0:
            raise MoneyError(self._("Negative money amount"))
        if amount == 0:
            return True
        self.description_validate(description, kwargs)
        currencies = {}
        self.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise MoneyError(self._("Invalid currency: %s") % currency)
        with Module.lock(self, [self.lock_key]):
            account = self.account(currency, False)
            if account is None:
                return False
            if not account.debit(amount, currency_info):
                return False
            op = self.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op.set(key, val)
            op.set("account", account.uuid)
            op.set("performed", self.now())
            op.set("amount", currency_info["format"] % -amount)
            op.set("balance", currency_info["format"] % account.balance())
            op.set("description", description)
            account.store()
            op.store()
            return True

    def force_debit(self, amount, currency, description, **kwargs):
        self.description_validate(description, kwargs)
        currencies = {}
        self.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise MoneyError(self._("Invalid currency: %s") % currency)
        with Module.lock(self, [self.lock_key]):
            account = self.account(currency, True)
            account.force_debit(amount, currency_info)
            op = self.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op.set(key, val)
            op.set("account", account.uuid)
            op.set("performed", self.now())
            op.set("amount", currency_info["format"] % -amount)
            op.set("balance", currency_info["format"] % account.balance())
            op.set("description", description)
            account.store()
            op.store()

    def transfer(self, target, amount, currency, description, **kwargs):
        self.description_validate(description, kwargs)
        currencies = {}
        self.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise MoneyError(self._("Invalid currency: %s") % currency)
        with Module.lock(self, [self.lock_key, target.lock_key]):
            account_from = self.account(currency, False)
            if account_from is None:
                return False
            account_to = target.account(currency, True)
            if not account_from.debit(amount, currency_info):
                return False
            account_to.credit(amount, currency_info)
            performed = self.now()
            op1 = self.obj(AccountOperation)
            for key, val in kwargs.iteritems():
                op1.set(key, val)
            op1.set("account", account_from.uuid)
            op1.set("performed", performed)
            op1.set("amount", currency_info["format"] % -amount)
            op1.set("balance", currency_info["format"] % account_from.balance())
            op1.set("description", description)
            op2 = self.obj(AccountOperation)
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
        self.call("currencies.list", currencies)
        currency_info = currencies.get(currency)
        if currency_info is None:
            raise MoneyError(self._("Invalid currency: %s") % currency)
        with Module.lock(self, [self.lock_key]):
            account = self.account(currency, False)
            if not account:
                return None
            lock = self.obj(AccountLock)
            lock.set("member", self.member)
            lock.set("account", account.uuid)
            lock.set("amount", currency_info["format"] % amount)
            lock.set("currency", currency)
            lock.set("description", description)
            lock.set("created", self.now())
            for key, val in kwargs.iteritems():
                lock.set(key, val)
            if not account.lock(amount, currency_info):
                return None
            account.store()
            lock.store()
            return lock

    def unlock(self, lock_uuid):
        currencies = {}
        self.call("currencies.list", currencies)
        with Module.lock(self, [self.lock_key]):
            try:
                lock = self.obj(AccountLock, lock_uuid)
            except ObjectNotFoundException:
                return None
            else:
                account = self.obj(Account, lock.get("account"))
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

    def script_attr(self, attr, handle_exceptions=True):
        m = re_money_script_field.match(attr)
        if m:
            field, currency = m.group(1, 2)
            if field == "balance":
                return self.balance(currency)
            elif field == "available":
                return self.available(currency)
        raise AttributeError(attr)

    def __repr__(self):
        return "[money %s.%s]" % (self.member_type, self.member)

    __str__ = __repr__
