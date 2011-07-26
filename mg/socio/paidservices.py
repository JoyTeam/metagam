from mg import *

class PaidServices(Module):
    def register(self):
        Module.register(self)
        self.rhook("paidservices.available", self.srv_available)
        self.rhook("paidservices.socio-available", self.srv_available)
        self.rhook("paidservices.socio-coloured-avatar", self.srv_coloured_avatar)
        self.rhook("ext-socio.paid-services", self.ext_paid_services, priv="logged")
        self.rhook("ext-socio.coloured-avatar", self.ext_coloured_avatar, priv="logged")
        self.rhook("money-description.socio-coloured-avatar", self.money_description_coloured_avatar)

    def money_description_coloured_avatar(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Coloured avatar for {period}"),
        }

    def srv_available(self, services):
        services.append("socio-coloured-avatar")

    def srv_coloured_avatar(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        srv = {
            "id": "socio-coloured-avatar",
            "name": self._("Coloured avatar on the forum"),
            "description": self._("Basically your avatar can be monochrome only. If you want coloured avatar you can use this option"),
            "subscription": True,
            "default_period": 60,
            #"default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 30 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "href": "/socio/coloured-avatar",
            "target": "_blank",
        }
        mod = self.call("modifiers.kind", req.user(), "socio-coloured-avatar")
        if mod:
            srv["active"] = True
            srv["active_till"] = mod.get("maxtill")
        else:
            srv["active"] = False
        return srv

    def ext_paid_services(self):
        req = self.req()
        vars = {
            "title": self._("Coloured avatars on the forum"),
            "menu_left": [
                {
                    "html": self._("Forum paid services"),
                    "lst": True
                }
            ]
        }
        service_ids = []
        self.call("paidservices.socio-available", service_ids)
        self.call("paidservices.render", service_ids, vars)
        self.call("socio.response_template", "paid-services.html", vars)

    def ext_coloured_avatar(self):
        req = self.req()
        vars = {
            "title": self._("Coloured avatars on the forum"),
            "menu_left": [
                {
                    "href": "/socio/paid-services",
                    "html": self._("Forum paid services"),
                }, {
                    "html": self._("Coloured avatar on the forum"),
                    "lst": True
                }
            ]
        }
        form = self.call("web.form")
        offer = intz(req.param("offer"))
        mod = self.call("modifiers.kind", req.user(), "socio-coloured-avatar")
        if mod:
            btn_title = self._("Prolong")
        else:
            btn_title = self._("Buy")
        form.add_message_top(self._("Basically your avatar can be monochrome only. If you want coloured avatar you can use this option"))
        offers = self.call("paidservices.offers", "socio-coloured-avatar")
        if req.ok():
            if offer < 0 or offer >= len(offers):
                form.error("offer", self._("Select an offer"))
            if not form.errors:
                o = offers[offer]
                if self.call("paidservices.prolong", "user", req.user(), "socio-coloured-avatar", o["period"], o["price"], o["currency"], auto_prolong=True):
                    self.call("socio.response", '%s <a href="/forum/settings">%s</a>' % (self._("Subscription successful."), self._("Now upload your new coloured avatar")), vars)
                else:
                    form.error("offer", self.call("money.not-enough-funds", o["currency"]))
        for i in xrange(0, len(offers)):
            o = offers[i]
            form.radio(o["html"], "offer", i, offer)
        form.submit(None, None, btn_title)
        self.call("socio.response", form.html(), vars)
