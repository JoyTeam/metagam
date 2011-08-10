from mg import *

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

class PaymentXsolla(CassandraObject):
    _indexes = {
        "all": [[], "performed"],
        "user": [["user"], "performed"],
        "date": [[], "date"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "PaymentXsolla-"
        CassandraObject.__init__(self, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "PaymentXsolla-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return PaymentXsolla._indexes

class PaymentXsollaList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "PaymentXsolla-"
        kwargs["cls"] = PaymentXsolla
        CassandraObjectList.__init__(self, *args, **kwargs)

class MemberMoney(object):
    def __init__(self, app, member):
        self.app = app
        self.member = member

    @property
    def accounts(self):
        try:
            return self._accounts
        except AttributeError:
            pass
        lst = self.app.objlist(AccountList, query_index="member", query_equal=self.member)
        lst.load(silent=True)
        self._accounts = lst
        return lst

    @property
    def locks(self):
        try:
            return self._locks
        except AttributeError:
            pass
        lst = self.app.objlist(AccountLockList, query_index="member", query_equal=self.member)
        lst.load(silent=True)
        self._locks = lst
        return lst

    def account(self, currency, create=False):
        for acc in self.accounts:
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

