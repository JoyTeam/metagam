from mg import *

class PaidServices(Module):
    def register(self):
        Module.register(self)
        self.rhook("paidservices.available", self.srv_available)
        self.rhook("ext-socio.paid-services", self.ext_paid_services, priv="logged")
        self.rhook("ext-socio.paid-service", self.ext_paid_service, priv="logged")
        # coloured avatar
        self.rhook("paidservices.socio-coloured-avatar", self.srv_coloured_avatar)
        self.rhook("money-description.socio-coloured-avatar", self.money_description_coloured_avatar)
        # signature images
        self.rhook("paidservices.socio-signature-images", self.srv_signature_images)
        self.rhook("money-description.socio-signature-images", self.money_description_signature_images)
        # signature smiles
        self.rhook("paidservices.socio-signature-smiles", self.srv_signature_smiles)
        self.rhook("money-description.socio-signature-smiles", self.money_description_signature_smiles)
        # premium pack
        self.rhook("paidservices.socio-premium-pack", self.srv_premium_pack)
        self.rhook("money-description.socio-premium-pack", self.money_description_premium_pack)

    def srv_available(self, services):
        services.append({"id": "socio-coloured-avatar", "type": "socio"})
        services.append({"id": "socio-signature-images", "type": "socio"})
        services.append({"id": "socio-signature-smiles", "type": "socio"})
        services.append({"id": "socio-premium-pack", "type": "socio"})

    def ext_paid_services(self):
        req = self.req()
        vars = {
            "title": self._("Forum paid services"),
        }
        service_ids = []
        self.call("paidservices.available", service_ids)
        servier_ids = [srv for srv in service_ids if srv.get("type") == "socio"]
        self.call("paidservices.render", service_ids, vars)
        self.call("socio.response_template", "paid-services.html", vars)

    def ext_paid_service(self):
        req = self.req()
        pinfo = self.call("paidservices.%s" % req.args)
        if pinfo.get("type") != "socio":
            self.call("web.not_found")
        vars = {
            "title": pinfo["name"],
            "menu_left": [
                {
                    "href": "/socio/paid-services",
                    "html": self._("Forum paid services"),
                }, {
                    "html": pinfo["name"],
                    "lst": True
                }
            ]
        }
        form = self.call("web.form")
        offer = intz(req.param("offer"))
        mod = self.call("modifiers.kind", req.user(), pinfo["id"])
        if mod:
            btn_title = self._("Prolong")
        else:
            btn_title = self._("Buy")
        form.add_message_top(pinfo["description"])
        offers = self.call("paidservices.offers", pinfo["id"])
        if req.ok():
            if offer < 0 or offer >= len(offers):
                form.error("offer", self._("Select an offer"))
            if not form.errors:
                o = offers[offer]
                if self.call("paidservices.prolong", "user", req.user(), pinfo["id"], o["period"], o["price"], o["currency"], auto_prolong=True, pack=pinfo.get("pack")):
                    if pinfo.get("success_url"):
                        self.call("socio.response", '%s <a href="%s">%s</a>' % (self._("Subscription successful."), pinfo["success_url"], pinfo["success_message"]), vars)
                    else:
                        self.call("web.redirect", "/socio/paid-services")
                else:
                    form.error("offer", self.call("money.not-enough-funds", o["currency"]))
        for i in xrange(0, len(offers)):
            o = offers[i]
            form.radio(o["html"], "offer", i, offer)
        form.submit(None, None, btn_title)
        self.call("socio.response", form.html(), vars)

    # coloured avatar

    def money_description_coloured_avatar(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Coloured avatar for {period}"),
        }

    def srv_coloured_avatar(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        return {
            "id": "socio-coloured-avatar",
            "name": self._("Coloured avatar on the forum"),
            "description": self._("Basically your avatar can be monochrome only. If you want coloured avatar you can use this option"),
            "subscription": True,
            "type": "socio",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 60 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "success_url": "/forum/settings",
            "success_message": self._("Now upload your new coloured avatar"),
        }

    # signature images

    def money_description_signature_images(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Images in the signature for {period}"),
        }

    def srv_signature_images(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        return {
            "id": "socio-signature-images",
            "name": self._("Images in the signature"),
            "description": self._("Basically your can not use images in your forum signature. If you want to use images you can use this option"),
            "subscription": True,
            "type": "socio",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 60 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "success_url": "/forum/settings",
            "success_message": self._("Now include some images to your signature"),
        }

    # signature smiles

    def money_description_signature_smiles(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Smiles in the signature for {period}"),
        }

    def srv_signature_smiles(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        return {
            "id": "socio-signature-smiles",
            "name": self._("Smiles in the signature"),
            "description": self._("Basically your can not use smiles in your forum signature. If you want to use smiles you can use this option"),
            "subscription": True,
            "type": "socio",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 60 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "success_url": "/forum/settings",
            "success_message": self._("Now include some smiles to your signature"),
        }

    # premium pack

    def money_description_premium_pack(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Socio premium pack for {period}"),
        }

    def srv_premium_pack(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        return {
            "id": "socio-premium-pack",
            "name": self._("Premium pack on the forum"),
            "subscription": True,
            "description": self._("This option allows you to use coloured avatar and to include images and smiles to your signature on the forum"),
            "pack": ["socio-coloured-avatar", "socio-signature-smiles", "socio-signature-images"],
            "type": "socio",
            "default_period": 365 * 86400,
            "default_price": self.call("money.format-price", 300 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "success_url": "/forum/settings",
            "success_message": self._("Now you can use all premium forum settings"),
        }
