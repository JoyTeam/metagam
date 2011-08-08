from mg import *

class PaidServices(Module):
    def register(self):
        self.rhook("paidservices.available", self.srv_available)
        self.rhook("ext-socio.paid-services", self.ext_paid_services, priv="logged")
        self.rhook("ext-socio.paid-service", self.ext_paid_service, priv="logged")
        self.rhook("sociointerface.buttons", self.buttons)
        # coloured avatar
        self.rhook("paidservices.socio_coloured_avatar", self.srv_coloured_avatar)
        self.rhook("money-description.socio_coloured_avatar", self.money_description_coloured_avatar)
        # signature images
        self.rhook("paidservices.socio_signature_images", self.srv_signature_images)
        self.rhook("money-description.socio_signature_images", self.money_description_signature_images)
        # signature smiles
        self.rhook("paidservices.socio_signature_smiles", self.srv_signature_smiles)
        self.rhook("money-description.socio_signature_smiles", self.money_description_signature_smiles)
        # signature colours
        self.rhook("paidservices.socio_signature_colours", self.srv_signature_colours)
        self.rhook("money-description.socio_signature_colours", self.money_description_signature_colours)
        # premium pack
        self.rhook("paidservices.socio_premium_pack", self.srv_premium_pack)
        self.rhook("money-description.socio_premium_pack", self.money_description_premium_pack)

    def buttons(self, buttons):
        buttons.append({
            "id": "forum-paidservices",
            "href": "/socio/paid-services",
            "title": self._("Paid services"),
            "condition": ['glob', 'char'],
            "target": "_self",
            "block": "forum",
            "order": 3,
        })

    def srv_available(self, services):
        services.append({"id": "socio_coloured_avatar", "type": "socio"})
        services.append({"id": "socio_signature_images", "type": "socio"})
        services.append({"id": "socio_signature_smiles", "type": "socio"})
        services.append({"id": "socio_signature_colours", "type": "socio"})
        services.append({"id": "socio_premium_pack", "type": "socio"})

    def ext_paid_services(self):
        req = self.req()
        vars = {
            "title": self._("Forum paid services"),
            "menu_left": [
                {
                    "href": "/forum",
                    "html": self._("Forum"),
                }, {
                    "html": self._("Forum paid services"),
                    "lst": True
                }
            ]
        }
        service_ids = []
        self.call("paidservices.available", service_ids)
        service_ids = [srv for srv in service_ids if srv.get("type") == "socio"]
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
                    "href": "/forum",
                    "html": self._("Forum"),
                }, {
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
                    if pinfo.get("socio_success_url"):
                        self.call("socio.response", '%s <a href="%s">%s</a>' % (self._("Subscription successful."), pinfo["socio_success_url"], pinfo["socio_success_message"]), vars)
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
            "id": "socio_coloured_avatar",
            "name": self._("Coloured avatar on the forum"),
            "description": self._("Basically your avatar can be monochrome only. If you want coloured avatar you can use this option"),
            "subscription": True,
            "type": "socio",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 60 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "socio_success_url": "/forum/settings",
            "socio_success_message": self._("Now upload your new coloured avatar"),
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
            "id": "socio_signature_images",
            "name": self._("Images in the signature"),
            "description": self._("Basically your can not use images in your forum signature. If you want to use images you can use this option"),
            "subscription": True,
            "type": "socio",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 60 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "socio_success_url": "/forum/settings",
            "socio_success_message": self._("Now include some images to your signature"),
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
            "id": "socio_signature_smiles",
            "name": self._("Smiles in the signature"),
            "description": self._("Basically your can not use smiles in your forum signature. If you want to use smiles you can use this option"),
            "subscription": True,
            "type": "socio",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 60 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "socio_success_url": "/forum/settings",
            "socio_success_message": self._("Now include some smiles to your signature"),
        }

    # signature colours

    def money_description_signature_colours(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Colours in the signature for {period}"),
        }

    def srv_signature_colours(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        return {
            "id": "socio_signature_colours",
            "name": self._("Colours in the signature"),
            "description": self._("Basically your can not use colours in your forum signature. If you want to use colours you can use this option"),
            "subscription": True,
            "type": "socio",
            "default_period": 30 * 86400,
            "default_price": self.call("money.format-price", 10 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "socio_success_url": "/forum/settings",
            "socio_success_message": self._("Now include some colours to your signature"),
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
            "id": "socio_premium_pack",
            "name": self._("Premium pack on the forum"),
            "subscription": True,
            "description": self._("This option allows you to use coloured avatar and to include images, smiles and coloured text to your signature on the forum"),
            "pack": ["socio_coloured_avatar", "socio_signature_smiles", "socio_signature_images", "socio_signature_colours"],
            "type": "socio",
            "default_period": 365 * 86400,
            "default_price": self.call("money.format-price", 300 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
            "socio_success_url": "/forum/settings",
            "socio_success_message": self._("Now you can use all premium forum settings"),
        }
