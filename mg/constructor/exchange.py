from mg.constructor import *

class ExchangeRates(ConstructorModule):
    def register(self):
        self.rhook("exchange.rates", self.rates)

    def rates(self):
        return self.conf("exchange.rates", {})

    def child_modules(self):
        return ["mg.constructor.exchange.ExchangeRatesAdmin"]

class ExchangeRatesAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-economy.index", self.menu_economy_index)
        self.rhook("headmenu-admin-exchange.rates", self.headmenu_exchange_rates)
        self.rhook("ext-admin-exchange.rates", self.admin_exchange_rates, priv="exchange.rates")
        self.rhook("advice-admin-exchange.index", self.advice_exchange)

    def advice_exchange(self, hook, args, advice):
        advice.append({"title": self._("Exchange rates documentation"), "content": self._('You can find detailed information on the exchange rates system in the <a href="//www.%s/doc/currency-rates" target="_blank">exchange rates page</a> in the reference manual.') % self.main_host})

    def permissions_list(self, perms):
        perms.append({"id": "exchange.rates", "name": self._("Currency exchange rates configuration")})

    def menu_economy_index(self, menu):
        req = self.req()
        if req.has_access("exchange.rates"):
            menu.append({"id": "exchange/rates", "text": self._("Currency exchange rates"), "leaf": True, "order": 20})

    def headmenu_exchange_rates(self, args):
        return self._("Currency exchange rates")

    def admin_exchange_rates(self):
        req = self.req()
        currencies = {}
        self.call("currencies.list", currencies)
        currencies_list = [(code, info) for code, info in currencies.iteritems()]
        val = self.conf("exchange.rates", {})
        if req.ok():
            errors = {}
            new_val = {}
            for curr, cinfo in currencies_list:
                key = "val-%s" % curr
                val = req.param(key)
                if not val:
                    errors[key] = self._("This field is mandatory")
                elif not valid_nonnegative_float(val):
                    errors[key] = self._("This is not a number")
                else:
                    val = floatz(val)
                    if val < 0.000001:
                        errors[key] = self._("Minimal value is %f") % 0.000001
                    elif val > 1000000:
                        errors[key] = self._("Maximal value is %f") % 1000000
                    else:
                        new_val[curr] = val
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            config = self.app().config_updater()
            config.set("exchange.rates", new_val)
            config.store()
            self.call("admin.response", self._("Exchange rates stored"), {})
        fields = []
        for curr, cinfo in currencies_list:
            fields.append({"name": "val-%s" % curr, "label": self._("Relative value of {code} ({name})").format(code=curr, name=htmlescape(cinfo["name_plural"])), "value": val.get(curr, 1)})
        self.call("admin.form", fields=fields)
