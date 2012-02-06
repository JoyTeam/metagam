from mg.constructor import *

default_sell_price = ["glob", "price"]
default_buy_price = ["*", ["glob", "price"], 0.1]

class Shops(ConstructorModule):
    def register(self):
        self.rhook("locfunctypes.list", self.locfunctypes_list)

    def child_modules(self):
        return ["mg.mmorpg.shops.ShopsAdmin"]

    def locfunctypes_list(self, types):
        types.append(("shop", self._("Shop")))

class ShopsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("item-categories.list", self.item_categories_list)
        self.rhook("locfunctypes.form", self.form_render)
        self.rhook("locfunctype-shop.store", self.form_store)
        self.rhook("locfunctype-shop.actions", self.actions)
        self.rhook("locfunctype-shop.action-assortment", self.assortment, priv="shops.config")
        self.rhook("locfunctype-shop.headmenu-assortment", self.headmenu_assortment)

    def permissions_list(self, perms):
        perms.append({"id": "shops.config", "name": self._("Shops configuration")})

    def item_categories_list(self, catgroups):
        catgroups.append({"id": "shops", "name": self._("Shops"), "order": 15, "description": self._("For goods being sold in shops")})

    def form_render(self, fields, func):
        fields.append({"name": "shop_sell_price", "label": self._("Sell price correction") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("shop_sell_price", default_sell_price)), "condition": "[tp]=='shop'"})
        fields.append({"name": "shop_buy_price", "label": self._("Buy price correction") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("shop_buy_price", default_buy_price)), "condition": "[tp]=='shop'"})

    def form_store(self, func, errors):
        req = self.req()
        char = self.character(req.user())
        currencies = {}
        self.call("currencies.list", currencies)
        if currencies:
            currency = currencies.keys()[0]
        else:
            currency = "GOLD"
        func["shop_sell_price"] = self.call("script.admin-expression", "shop_sell_price", errors, globs={"char": char, "price": 1, "currency": currency})
        func["shop_buy_price"] = self.call("script.admin-expression", "shop_buy_price", errors, globs={"char": char, "price": 1, "currency": currency})

    def actions(self, func, actions):
        req = self.req()
        actions.append({
            "id": "assortment",
            "text": self._("shop assortment"),
        })

    def headmenu_assortment(self, func, args):
        if args:
            categories = self.call("item-types.categories", "shops")
            for cat in categories:
                if cat["id"] == args:
                    return [htmlescape(cat["name"]), "assortment"]
        return self._("Assortment of '%s'") % htmlescape(func["title"])

    def assortment(self, func_id, base_url, func, args):
        categories = self.call("item-types.categories", "shops")
        if args:
            currencies = {}
            self.call("currencies.list", currencies)
            currencies_list = [(code, info["name_plural"]) for code, info in currencies.iteritems()]
            currencies_list.insert(0, (None, self._("currency///Auto")))
            item_types = []
            for item_type in self.item_types_all():
                cat = item_type.get("cat-shops")
                misc = None
                found = False
                for c in categories:
                    if c["id"] == cat:
                        found = True
                    if c.get("misc"):
                        misc = c["id"]
                if not found:
                    cat = misc
                if cat == args:
                    item_types.append(item_type)
            item_types.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x.name, y.name))
            settings = self.conf("shop-%s.assortment" % func_id, {})
            fields = []
            for item_type in item_types:
                uuid = item_type.uuid
                fields.append({"type": "header", "html": htmlescape(item_type.name)})
                fields.append({"type": "checkbox", "name": "sell-%s" % uuid, "checked": settings.get("sell-%s" % uuid), "label": self._("Shop sells these items")})
                fields.append({"type": "checkbox", "name": "buy-%s" % uuid, "checked": settings.get("buy-%s" % uuid), "label": self._("Shop buys these items"), "inline": True})
                fields.append({"name": "sell-store-%s" % uuid, "type": "checkbox", "checked": settings.get("sell-store-%s" % uuid), "label": self._("Sell from the store only"), "condition": "[sell-%s]" % uuid})
                fields.append({"name": "sell-price-%s" % uuid, "value": settings.get("sell-price-%s" % uuid), "label": self._("Sell price"), "condition": "[sell-%s]" % uuid})
                fields.append({"name": "sell-currency-%s" % uuid, "value": settings.get("sell-currency-%s" % uuid), "label": self._("Sell currency"), "type": "combo", "values": currencies_list, "inline": True, "condition": "[sell-%s]" % uuid})
                fields.append({"name": "buy-store-%s" % uuid, "type": "checkbox", "checked": settings.get("buy-store-%s" % uuid), "label": self._("Put bought items to the store"), "condition": "[buy-%s]" % uuid})
                fields.append({"name": "buy-price-%s" % uuid, "value": settings.get("buy-price-%s" % uuid), "label": self._("Buy price"), "condition": "[buy-%s]" % uuid})
                fields.append({"name": "buy-currency-%s" % uuid, "value": settings.get("buy-currency-%s" % uuid), "label": self._("Buy currency"), "type": "combo", "values": currencies_list, "inline": True, "condition": "[buy-%s]" % uuid})
            self.call("admin.advice", {"title": self._("Shop prices"), "content": self._("If a price is not specified balance price will be used. If currency is specified but price not then the balance price will be converted to the currency given")})
            self.call("admin.form", fields=fields)
        rows = []
        for cat in categories:
            rows.append([
                u'<hook:admin.link href="%s/assortment/%s" title="%s" />' % (base_url, cat["id"], htmlescape(cat["name"]))
            ])
        vars = {
            "tables": [
                {
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

