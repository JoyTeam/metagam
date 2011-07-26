from mg.constructor import *
from mg.core.money_classes import *

class PaidServicesAdmin(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)

class PaidServices(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("ext-paidservices.index", self.paidservices_index, priv="logged")
        self.rhook("paidservices.offers", self.offers)
        self.rhook("paidservices.prolong", self.prolong)
        self.rhook("paidservices.render", self.render)
        self.rhook("modifiers.destroyed", self.modifiers_destroyed)

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "paidservices",
            "href": "/paidservices",
            "target": "main",
            "icon": "donate.png",
            "title": self._("Paid services"),
            "block": "left-menu",
            "order": 10,
        })

    def offers(self, srv):
        if type(srv) != dict:
            srv = self.call("paidservices.%s" % srv)
        offers = []
        if srv:
            offers.append({
                "price": srv["default_price"],
                "currency": srv["default_currency"],
                "period": srv.get("default_period"),
            })
        for offer in offers:
            if offer.get("period"):
                offer["html"] = self._('{price} for {period}').format(
                    price=self.call("money.price-html", offer["price"], offer["currency"]),
                    period=self.call("l10n.literal_interval", offer["period"], html=True),
                    period_a=self.call("l10n.literal_interval_a", offer["period"], html=True)
                )
            else:
                offer["html"] = self.call("money.price-html", offer["price"], offer["currency"])
        return offers
 
    def paidservices_index(self):
        service_ids = []
        self.call("paidservices.available", service_ids)
        vars = {}
        self.render(service_ids, vars)
        self.call("game.response_internal", "paid-services.html", vars)

    def render(self, service_ids, vars):
        services = []
        for srv_id in service_ids:
            srv = self.call("paidservices.%s" % srv_id)
            if not srv:
                continue
            active = srv.get("active")
            if active == True:
                if srv.get("active_till"):
                    srv["status"] = self._("service///active till %s") % self.call("l10n.timeencode2", srv["active_till"])
                else:
                    srv["status"] = self._("service///active")
                srv["status_cls"] = "service-active"
            elif active == False:
                srv["status"] = self._("service///inactive")
                srv["status_cls"] = "service-inactive"
            srv["offers"] = self.offers(srv)
            services.append(srv)
        vars["services"] = services
        vars["PaidService"] = self._("Paid service")
        vars["Description"] = self._("Description")
        vars["Price"] = self._("Price")
        vars["Status"] = self._("Status")

    def prolong(self, target_type, target, kind, period, price, currency, user=None, **kwargs):
        if user is None:
            req = self.req()
            user = req.user()
        with self.lock(["User.%s" % user]):
            money = MemberMoney(self.app(), user)
            if not money.debit(price, currency, kind, period=self.call("l10n.literal_interval", period), period_a=self.call("l10n.literal_interval_a", period)):
                return False
            self.call("modifiers.prolong", "user", user, kind, 1, period, **kwargs)
            return True

    def modifiers_destroyed(self, mod):
        print "modifiers_destroyed %s: %s" % (mod.uuid, mod.data)
        if not mod.get("auto_prolong"):
            return
        print "prolong ok"
        srv = self.call("paidservices.%s" % mod.get("kind"))
        if not srv:
            return
        print "srv ok"
        if mod.get("target_type") != "user":
            return
        user = mod.get("target")
        print "user ok: %s" % user
        for offer in self.offers(srv):
            if offer.get("period") == mod.get("period"):
                print "offer ok"
                self.call("paidservices.prolong", "user", user, mod.get("kind"), offer.get("period"), offer.get("price"), offer.get("currency"), user=user, auto_prolong=True)
                break
