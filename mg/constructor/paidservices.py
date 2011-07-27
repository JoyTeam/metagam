from mg.constructor import *
from mg.core.money_classes import *
import re

re_cmd = re.compile(r'^(enable|disable)/(\S+)$')
re_cmd_edit = re.compile(r'^(\S+)/(\d+|new)$')

class PaidServices(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("paidservices.offers", self.offers)
        self.rhook("paidservices.prolong", self.prolong)
        self.rhook("paidservices.render", self.render)
        self.rhook("modifiers.destroyed", self.modifiers_destroyed)
        self.rhook("ext-paidservices.index", self.paidservices_index, priv="logged")
        self.rhook("ext-paidservices.prolong-enable", self.paidservices_prolong, priv="logged")
        self.rhook("ext-paidservices.prolong-disable", self.paidservices_prolong, priv="logged")

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
        if not srv:
            return []
        offers = self.conf("paidservices.offers-%s" % srv["id"])
        if offers is None:
            offers = []
            offers.append({
                "price": srv["default_price"],
                "currency": srv["default_currency"],
                "period": srv.get("default_period"),
            })
            config = self.app().config_updater()
            config.set("paidservices.offers-%s" % srv["id"], offers)
            config.store()
        roffers = []
        for offer in offers:
            roffer = offer.copy()
            if offer.get("period"):
                roffer["html"] = self._('{price} for {period}').format(
                    price=self.call("money.price-html", offer["price"], offer["currency"]),
                    period=self.call("l10n.literal_interval", offer["period"], html=True),
                    period_a=self.call("l10n.literal_interval_a", offer["period"], html=True)
                )
            else:
                roffer["html"] = self.call("money.price-html", offer["price"], offer["currency"])
            roffers.append(roffer)
        return roffers
 
    def paidservices_index(self):
        service_ids = []
        self.call("paidservices.available", service_ids)
        vars = {}
        self.render(service_ids, vars)
        self.call("game.response_internal", "paid-services.html", vars)

    def render(self, service_ids, vars):
        req = self.req()
        services = []
        for srv_id in service_ids:
            srv = self.call("paidservices.%s" % srv_id)
            if not srv:
                continue
            if not self.conf("paidservices.enabled-%s" % srv_id, srv["default_enabled"]):
                continue
            if srv.get("subscription"):
                mod = self.call("modifiers.kind", req.user(), srv["id"])
                if mod:
                    if mod.get("maxtill"):
                        srv["status"] = self._("service///active till %s") % self.call("l10n.timeencode2", mod["maxtill"])
                    else:
                        srv["status"] = self._("service///active")
                    srv["status_cls"] = "service-active"
                    auto_prolong = False
                    for m in mod["mods"]:
                        if m.get("auto_prolong"):
                            auto_prolong = True
                    if auto_prolong:
                        srv["auto_prolong"] = {
                            "status": self._("Auto prolong: enabled"),
                            "href": "/paidservices/prolong-disable/%s" % srv["id"],
                            "cmd": self._("disable"),
                        }
                    else:
                        srv["auto_prolong"] = {
                            "status": self._("Auto prolong: disabled"),
                            "href": "/paidservices/prolong-enable/%s" % srv["id"],
                            "cmd": self._("enable"),
                        }
                else:
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
        if not mod.get("auto_prolong"):
            return
        srv = self.call("paidservices.%s" % mod.get("kind"))
        if not srv:
            return
        if mod.get("target_type") != "user":
            return
        user = mod.get("target")
        for offer in self.offers(srv):
            if offer.get("period") == mod.get("period"):
                self.call("paidservices.prolong", "user", user, mod.get("kind"), offer.get("period"), offer.get("price"), offer.get("currency"), user=user, auto_prolong=True)
                break

    def paidservices_prolong(self):
        req = self.req()
        with self.lock(["Modifiers.%s" % req.user()]):
            mod = self.call("modifiers.kind", req.user(), req.args)
            if mod:
                auto_prolong = True if req.hook == "prolong-enable" else False
                for m in mod["mods"]:
                    m.set("auto_prolong", auto_prolong)
                    m.store()
            self.call("web.redirect", req.param("redirect") or "/paidservices")

class PaidServicesAdmin(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-economy.index", self.menu_economy_index)
        self.rhook("ext-admin-paidservices.editor", self.admin_paidservices_editor, priv="paidservices.editor")
        self.rhook("headmenu-admin-paidservices.editor", self.headmenu_paidservices_editor)
        
    def permissions_list(self, perms):
        perms.append({"id": "paidservices.editor", "name": self._("Paid services editor")})

    def menu_economy_index(self, menu):
        menu.append({"id": "paidservices/editor", "text": self._("Paid services"), "icon": "/st-mg/menu/coin.gif", "leaf": True})

    def headmenu_paidservices_editor(self, args):
        if args:
            m = re_cmd_edit.match(args)
            if m:
                srv_id, offer_id = m.group(1, 2)
                if offer_id == "new":
                    return [self._("New offer"), "paidservices/editor/%s" % srv_id]
                else:
                    return [self._("Offer %s") % offer_id, "paidservices/editor/%s" % srv_id]
            srv = self.call("paidservices.%s" % args)
            if srv:
                return [srv["name"], "paidservices/editor"]
            else:
                return [htmlescape(args), "paidservices/editor"]
        return self._("Paid services")

    def admin_paidservices_editor(self):
        req = self.req()
        m = re_cmd.match(req.args)
        if m:
            cmd, srv_id = m.group(1, 2)
            config = self.app().config_updater()
            config.set("paidservices.enabled-%s" % srv_id, True if cmd == "enable" else False)
            config.store()
            self.call("admin.redirect", "paidservices/editor")
        elif req.args:
            m = re_cmd_edit.match(req.args)
            if m:
                srv_id, offer_id = m.group(1, 2)
            else:
                srv_id = req.args
                offer_id = None
            srv = self.call("paidservices.%s" % srv_id)
            if srv:
                self.paidservice_editor(srv, offer_id)
            self.call("admin.redirect", "paidservices/editor")
        service_ids = []
        self.call("paidservices.available", service_ids)
        rows = []
        for srv_id in service_ids:
            srv = self.call("paidservices.%s" % srv_id)
            if not srv:
                continue
            # current status
            status = self.conf("paidservices.enabled-%s" % srv_id, srv["default_enabled"])
            if status:
                status = '%s<br /><hook:admin.link href="paidservices/editor/disable/%s" title="%s" />' % (self._("service///enabled"), srv_id, self._("disable"))
            else:
                status = '%s<br /><hook:admin.link href="paidservices/editor/enable/%s" title="%s" />' % (self._("service///disabled"), srv_id, self._("enable"))
            # offers list
            offers = self.call("paidservices.offers", srv)
            offers = ['<div>%s</div>' % off["html"] for off in offers]
            offers.append('<hook:admin.link href="paidservices/editor/%s" title="%s" />' % (srv_id, self._("edit")))
            offers = ''.join(offers)
            rows.append([
                srv.get("name"),
                status,
                offers,
            ])
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Paid service"),
                        self._("Status"),
                        self._("Prices"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def paidservice_editor(self, srv, offer_id):
        offers = self.call("paidservices.offers", srv)
        if offer_id is None:
            rows = []
            for i in xrange(0, len(offers)):
                offer = offers[i]
                cinfo = self.call("money.currency-info", offer["currency"])
                if not cinfo:
                    continue
                rows.append([
                    offer.get("period"),
                    '%s %s' % (cinfo["format"] % offer["price"], offer["currency"]),
                    offer["html"],
                    '<hook:admin.link href="paidservices/editor/%s/%d" title="%s" />' % (srv["id"], i, self._("edit")),
                    '<hook:admin.link href="paidservices/editor/%s/del/%d" title="%s" confirm="%s" />' % (srv["id"], i, self._("delete"), self._("Are you sure want to delete this offer?")),
                ])
            vars = {
                "tables": [
                    {
                        "links": [
                            {"hook": "paidservices/editor/%s/new" % srv["id"], "text": self._("New offer"), "lst": True}
                        ],
                        "header": [
                            self._("Duration"),
                            self._("Price"),
                            self._("Representation"),
                            self._("Editing"),
                            self._("Deletion"),
                        ],
                        "rows": rows,
                    }
                ]
            }
            self.call("admin.response_template", "admin/common/tables.html", vars)
        currencies = {}
        self.call("currencies.list", currencies)
        req = self.req()
        if req.ok():
            price = req.param("price")
            currency = req.param("v_currency")
            period = req.param("period")
            errors = {}
            if not price:
                errors["price"] = self._("This field is mandatory")
            elif not valid_nonnegative_float(price):
                errors["price"] = self._("Invalid number format")
            if not currency:
                errors["v_currency"] = self._("This field is mandatory")
            else:
                cinfo = currencies.get(currency)
                if not cinfo:
                    errors["v_currency"] = self._("Select valid currency")
            if "price" not in errors and "v_currency" not in errors:
                price = cinfo["format"] % float(price)
                if float(price) == 0:
                    errors["price"] = self._("Price is too low")
            if not period:
                errors["period"] = self._("This field is mandatory")
            elif not valid_nonnegative_int(period):
                errors["period"] = self._("Invalid number format")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            offers = self.conf("paidservices.offers-%s" % srv["id"], [])
            if offer_id == "new":
                offers.append({
                    "period": int(period),
                    "price": float(price),
                    "currency": currency,
                })
            else:
                offer_id = int(offer_id)
                if offer_id < len(offers):
                    offers[offer_id]["period"] = int(period)
                    offers[offer_id]["price"] = float(price)
                    offers[offer_id]["currency"] = currency
            offers.sort(cmp=lambda x, y: cmp(x.get("period"), y.get("period")))
            config = self.app().config_updater()
            config.set("paidservices.offers-%s" % srv["id"], offers)
            config.store()
            self.call("admin.redirect", "paidservices/editor/%s" % srv["id"])
        if offer_id == "new":
            currency = None
            price = None
            for code, info in currencies.iteritems():
                if info.get("real"):
                    currency = code
                    price = 150 / info.get("real_roubles", 1)
            period = 2592000
        else:
            offer_id = int(offer_id)
            if offer_id >= len(offers):
                self.call("admin.redirect", "paidservices/editor")
            offer = offers[offer_id]
            period = offer.get("period")
            price = offer["price"]
            currency = offer["currency"]
        if price and currency:
            cinfo = self.call("money.currency-info", currency)
            price = cinfo["format"] % price
        fields = [
            {"name": "period", "label": self._("Period (in seconds)"), "value": period},
            {"name": "price", "label": self._("Price"), "value": price},
            {"name": "currency", "label": self._("Currency"), "value": currency, "type": "combo", "values": [(code, info["name_plural"]) for code, info in currencies.iteritems()], "inline": True},
        ]
        self.call("admin.form", fields=fields)
