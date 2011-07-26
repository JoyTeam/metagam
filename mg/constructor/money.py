from mg import *
from mg.constructor import *
from mg.core.money_classes import *

operations_per_page = 50

class Money(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("ext-money.index", self.money_index, priv="logged")
        self.rhook("ext-money.operations", self.money_operations, priv="logged")

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "money",
            "href": "/money",
            "target": "main",
            "icon": "money.png",
            "title": self._("Money"),
            "block": "top-menu",
            "order": 0,
        })

    def money_index(self):
        req = self.req()
        character = self.character(req.user())
        money = character.money
        currencies = {}
        self.call("currencies.list", currencies)
        accounts = []
        for currency, currency_info in currencies.iteritems():
            account = money.account(currency)
            if account:
                balance = nn(account.get("balance"))
                locked = nn(account.get("locked"))
            else:
                balance = 0
                locked = 0
            raccount = {
                "currency": currency_info,
                "balance": balance,
                "balance_currency": self.call("l10n.literal_value", balance, currency_info.get("name_local")),
                "locked": locked,
                "locked_currency": self.call("l10n.literal_value", locked, currency_info.get("name_local")),
            }
            menu = []
            menu.append({"href": "/money/operations/%s" % currency, "html": self._("money///open history")})
            if currency_info.get("real"):
                menu.append({"href": "javascript:void(0)", "onclick": "parent.Xsolla.paystation(); return false", "html": self._("money///buy %s") % currency_info.get("name_plural", "").lower()})
            if menu:
                menu[-1]["lst"] = True
                raccount["menu"] = menu
            accounts.append(raccount)
        vars = {
            "accounts": accounts,
            "Money": self._("Money"),
        }
        self.call("game.response_internal", "money-accounts.html", vars)

    def money_operations(self):
        req = self.req()
        character = self.character(req.user())
        money = character.money
        currencies = {}
        self.call("currencies.list", currencies)
        currency = req.args
        currency_info = currencies.get(currency)
        if not currency_info:
            self.call("web.redirect", "/money")
        vars = {
            "ret": {
                "href": "/money",
                "html": self._("Return"),
            }
        }
        account = money.account(currency)
        self.render_operations(account, vars)
        self.call("game.response_internal", "money-operations.html", vars)

    def render_operations(self, account, vars):
        req = self.req()
        if account:
            page = intz(req.param("page"))
            lst = self.objlist(AccountOperationList, query_index="account", query_equal=account.uuid, query_reversed=True)
            pages = (len(lst) - 1) / operations_per_page + 1
            if pages < 1:
                pages = 1
            if page < 1:
                page = 1
            if page > pages:
                page = pages
            del lst[page * operations_per_page:]
            del lst[0:(page - 1) * operations_per_page]
            lst.load()
            operations = []
            for op in lst:
                description = self.call("money-description.%s" % op.get("description"))
                rop = {
                    "performed": self.call("l10n.timeencode2", op.get("performed")),
                    "amount": op.get("amount"),
                    "balance": op.get("balance"),
                    "cls": "money-plus" if op.get("balance") >= 0 else "money-minus",
                }
                rop["description"] = op.get("description")
                if description:
                    watchdog = 0
                    while True:
                        watchdog += 1
                        if watchdog >= 100:
                            break
                        try:
                            rop["description"] = description["text"].format(**op.data)
                        except KeyError as e:
                            op.data[e.args[0]] = "{%s}" % e.args[0]
                        else:
                            break
                operations.append(rop)
            vars["operations"] = operations
            if pages > 1:
                url = req.uri()
                vars["pages"] = [{"html": pg, "href": "%s?page=%d" % (url, pg) if pg != page else None} for pg in xrange(1, pages + 1)]
                vars["pages"][-1]["lst"] = True
        vars["Performed"] = self._("moneyop///Performed")
        vars["Amount"] = self._("moneyop///Amount")
        vars["Balance"] = self._("moneyop///Balance")
        vars["Description"] = self._("moneyop///Description")
