from mg.constructor import *
from mg.mmorpg.inventory_classes import dna_parse
import re

default_sell_price = ["glob", "price"]
default_buy_price = ["*", ["glob", "price"], 0.1]

re_sell_item = re.compile(r'^sell-([a-f0-9]{32})$')
re_request_item = re.compile(r'^([a-f0-9_]+)/(\d+\.\d+|\d+)/([A-Z0-9]+)/(\d+)$')

class DBShopOperation(CassandraObject):
    clsname = "ShopOperation"
    indexes = {
        "performed": [[], "performed"],
    }

class DBShopOperationList(CassandraObjectList):
    objcls = DBShopOperation

class ShopsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("item-categories.list", self.item_categories_list)
        self.rhook("admin-interfaces.form", self.form_render)
        self.rhook("admin-interface-shop.store", self.form_store)
        self.rhook("admin-interface-shop.actions", self.actions)
        self.rhook("admin-interface-shop.action-assortment", self.assortment, priv="shops.config")
        self.rhook("admin-interface-shop.headmenu-assortment", self.headmenu_assortment)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("admin-shops.stats", self.stats)
        self.rhook("admin-item-types.dim-list", self.dim_list)

    def dim_list(self, dimensions):
        dimensions.append({
            "id": "shops",
            "title": self._("Dimensions in shops"),
            "default": "60x60",
            "order": 30,
        })

    def schedule(self, sched):
        sched.add("admin-shops.stats", "8 0 * * *", priority=10)

    def objclasses_list(self, objclasses):
        objclasses["ShopOperation"] = (DBShopOperation, DBShopOperationList)

    def permissions_list(self, perms):
        perms.append({"id": "shops.config", "name": self._("Shops configuration")})

    def item_categories_list(self, catgroups):
        catgroups.append({"id": "shops", "name": self._("Shops"), "order": 15, "description": self._("For goods being sold in shops")})

    def form_render(self, fields, func):
        fields.append({"name": "shop_sell", "label": self._("This shop sells goods"), "type": "checkbox", "checked": func.get("shop_sell"), "condition": "[tp] == 'shop'"})
        fields.append({"name": "shop_sell_price", "label": self._("Sell price correction") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("shop_sell_price", default_sell_price)), "condition": "[tp]=='shop' && [shop_sell]"})
        fields.append({"name": "shop_buy", "label": self._("This shop buys goods"), "type": "checkbox", "checked": func.get("shop_buy"), "condition": "[tp] == 'shop'"})
        fields.append({"name": "shop_buy_price", "label": self._("Buy price correction") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("shop_buy_price", default_buy_price)), "condition": "[tp]=='shop' && [shop_buy]"})

    def form_store(self, func, errors):
        req = self.req()
        char = self.character(req.user())
        currencies = {}
        self.call("currencies.list", currencies)
        if currencies:
            currency = currencies.keys()[0]
        else:
            currency = "GOLD"
        item = self.call("admin-inventory.sample-item")
        # sell
        if req.param("shop_sell"):
            func["shop_sell"] = True
            func["shop_sell_price"] = self.call("script.admin-expression", "shop_sell_price", errors, globs={"char": char, "price": 1, "currency": currency, "item": item})
        else:
            func["shop_sell"] = False
        # buy
        if req.param("shop_buy"):
            func["shop_buy"] = True
            func["shop_buy_price"] = self.call("script.admin-expression", "shop_buy_price", errors, globs={"char": char, "price": 1, "currency": currency, "item": item})
        else:
            func["shop_buy"] = False
        if not func.get("shop_buy") and not func.get("shop_sell"):
            errors["v_tp"] = self._("Shop must either sell or buy goods (or both)")
        # default action
        if func.get("shop_sell"):
            func["default_action"] = "sell"
        elif func.get("shop_buy"):
            func["default_action"] = "buy"
        else:
            func["default_action"] = "sell"

    def actions(self, func_id, func, actions):
        req = self.req()
        actions.append({
            "id": "assortment",
            "text": self._("shop assortment"),
        })
        if req.has_access("inventory.track"):
            actions.append({
                "hook": "inventory/view/shop/{shop}".format(shop=func_id),
                "text": self._("shop store"),
            })

    def headmenu_assortment(self, func, args):
        if args:
            categories = self.call("item-types.categories", "admin")
            for cat in categories:
                if cat["id"] == args:
                    return [htmlescape(cat["name"]), "assortment"]
        return self._("Assortment of '%s'") % htmlescape(func["title"])

    def assortment(self, func_id, base_url, func, args):
        categories = self.call("item-types.categories", "admin")
        req = self.req()
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
            assortment = self.conf("shop-%s.assortment" % func_id, {})
            if req.ok():
                new_assortment = assortment.copy()
                errors = {}
                for item_type in item_types:
                    uuid = item_type.uuid
                    for tp in ["sell", "buy"]:
                        for key in ["%s-%s", "%s-store-%s", "%s-price-%s", "%s-currency-%s"]:
                            key2 = key % (tp, uuid)
                            if key2 in new_assortment:
                                del new_assortment[key2]
                        if func.get("shop_%s" % tp) and req.param("%s-%s" % (tp, uuid)):
                            new_assortment["%s-%s" % (tp, uuid)] = True
                            new_assortment["%s-store-%s" % (tp, uuid)] = True if req.param("%s-store-%s" % (tp, uuid)) else False
                            curr = req.param("v_%s-currency-%s" % (tp, uuid))
                            if curr:
                                cinfo = currencies.get(curr)
                                if not cinfo:
                                    errors["v_%s-currency-%s" % (tp, uuid)] = self._("Make a valid selection")
                                else:
                                    new_assortment["%s-currency-%s" % (tp, uuid)] = curr
                            price = req.param("%s-price-%s" % (tp, uuid)).strip()
                            if price != "":
                                if not valid_nonnegative_float(price):
                                    errors["%s-price-%s" % (tp, uuid)] = self._("Invalid number format")
                                else:
                                    price = float(price)
                                    if price > 1000000:
                                        errors["%s-price-%s" % (tp, uuid)] = self._("Maximal value is %d") % 1000000
                                    else:
                                        new_assortment["%s-price-%s" % (tp, uuid)] = price
                                if curr == "":
                                    errors["v_%s-currency-%s" % (tp, uuid)] = self._("Currency is not specified")
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                config = self.app().config_updater()
                config.set("shop-%s.assortment" % func_id, new_assortment)
                config.store()
                self.call("admin.redirect", "%s/assortment" % base_url)
            fields = []
            for item_type in item_types:
                uuid = item_type.uuid
                fields.append({"type": "header", "html": htmlescape(item_type.name)})
                if func.get("shop_sell"):
                    fields.append({"type": "checkbox", "name": "sell-%s" % uuid, "checked": assortment.get("sell-%s" % uuid), "label": self._("Shop sells these items")})
                if func.get("shop_buy"):
                    fields.append({"type": "checkbox", "name": "buy-%s" % uuid, "checked": assortment.get("buy-%s" % uuid), "label": self._("Shop buys these items"), "inline": True})
                if func.get("shop_sell"):
                    fields.append({"name": "sell-store-%s" % uuid, "type": "checkbox", "checked": assortment.get("sell-store-%s" % uuid), "label": self._("Sell from the store only"), "condition": "[sell-%s]" % uuid})
                    fields.append({"name": "sell-price-%s" % uuid, "value": assortment.get("sell-price-%s" % uuid), "label": self._("Sell price"), "condition": "[sell-%s]" % uuid})
                    fields.append({"name": "sell-currency-%s" % uuid, "value": assortment.get("sell-currency-%s" % uuid), "label": self._("Sell currency"), "type": "combo", "values": currencies_list, "inline": True, "condition": "[sell-%s]" % uuid})
                if func.get("shop_buy"):
                    fields.append({"name": "buy-store-%s" % uuid, "type": "checkbox", "checked": assortment.get("buy-store-%s" % uuid), "label": self._("Put bought items to the store"), "condition": "[buy-%s]" % uuid})
                    fields.append({"name": "buy-price-%s" % uuid, "value": assortment.get("buy-price-%s" % uuid), "label": self._("Buy price"), "condition": "[buy-%s]" % uuid})
                    fields.append({"name": "buy-currency-%s" % uuid, "value": assortment.get("buy-currency-%s" % uuid), "label": self._("Buy currency"), "type": "combo", "values": currencies_list, "inline": True, "condition": "[buy-%s]" % uuid})
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

    def stats(self):
        today = self.nowdate()
        yesterday = prev_date(today)
        lst = self.objlist(DBShopOperationList, query_index="performed", query_finish=today)
        lst.load(silent=True)
        operations = {}
        for ent in lst:
            shop = ent.get("shop")
            mode = ent.get("mode")
            ops = ent.get("operations")
            for dna, info in ops.iteritems():
                item_type, mods = dna_parse(dna)
                price = info.get("price")
                currency = info.get("currency")
                quantity = info.get("quantity")
                if item_type and price and quantity and currency:
                    key = "%s-%s-%s" % (shop, mode, currency)
                    try:
                        ops_list = operations[key]
                    except KeyError:
                        ops_list = {}
                        operations[key] = ops_list
                    amount = price * quantity
                    try:
                        ops_list[item_type][0] += amount
                        ops_list[item_type][1] += quantity
                    except KeyError:
                        ops_list[item_type] = [amount, quantity]
        if operations:
            self.call("dbexport.add", "shops_stats", date=yesterday, operations=operations)
        lst.remove()

class Shops(ConstructorModule):
    def register(self):
        self.rhook("interfaces.list", self.interfaces_list)
        self.rhook("interface-shop.action-sell", self.sell, priv="logged")
        self.rhook("interface-shop.action-buy", self.buy, priv="logged")
        self.rhook("money-description.shop-buy", self.money_description_shop_buy)
        self.rhook("money-description.shop-sell", self.money_description_shop_sell)
        self.rhook("money-description.shop-bought", self.money_description_shop_bought)
        self.rhook("money-description.shop-sold", self.money_description_shop_sold)
        self.rhook("item-types.dim-shops", self.dim_shops)

    def dim_shops(self):
        return self.conf("item-types.dim_shops", "60x60")

    def money_description_shop_buy(self):
        return {
            "args": [],
            "text": self._("Shop buy"),
        }

    def money_description_shop_sell(self):
        return {
            "args": [],
            "text": self._("Shop sell"),
        }

    def money_description_shop_bought(self):
        return {
            "args": [],
            "text": self._("Bought by the shop"),
        }

    def money_description_shop_sold(self):
        return {
            "args": [],
            "text": self._("Sold by the shop"),
        }

    def child_modules(self):
        return ["mg.mmorpg.shops.ShopsAdmin"]

    def interfaces_list(self, types):
        types.append(("shop", self._("Shop")))

    def shop_tp_menu(self, func, base_url, args, vars):
        entries = []
        if func.get("shop_sell"):
            entries.append({
                "id": "sell",
                "html": self._("menu///Buy"),
            })
        if func.get("shop_buy"):
            entries.append({
                "id": "buy",
                "html": self._("menu///Sell"),
            })
        if len(entries) >= 2:
            for e in entries:
                if args != e["id"]:
                    e["href"] = "%s/%s" % (base_url, e["id"])
            entries[-1]["lst"] = True
            vars["shop_func_menu"] = entries

    def transaction(self, mode, func_id, base_url, func, args, vars):
        self.shop_tp_menu(func, base_url, mode, vars)
        vars["title"] = func.get("title")
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        shop_inventory = self.call("inventory.get", "shop", func_id)
        # locking
        lock_objects = []
        if req.ok():
            lock_objects.append("ShopLock.%s" % func_id)
            lock_objects.append(character.lock)
            lock_objects.append(character.money.lock_key)
            lock_objects.append(character.inventory.lock_key)
            lock_objects.append(shop_inventory.lock_key)
        with self.lock(lock_objects):
            character.inventory.load()
            shop_inventory.load()
            # loading list of categories
            categories = self.call("item-types.categories", "shops")
            assortment = self.conf("shop-%s.assortment" % func_id, {})
            if mode == "sell":
                # loading shop store
                item_types = []
                max_quantity = {}
                for item_type, quantity in shop_inventory.items():
                    if assortment.get("sell-%s" % item_type.uuid) and assortment.get("sell-store-%s" % item_type.uuid):
                        item_types.append(item_type)
                        max_quantity[item_type.dna] = quantity
                # loading list of unlimited items to sell
                item_type_uuids = []
                for key in assortment.keys():
                    m = re_sell_item.match(key)
                    if not m:
                        continue
                    uuid = m.group(1)
                    if not assortment.get("sell-store-%s" % uuid):
                        item_type_uuids.append(uuid)
                # loading unlimited item types data
                item_types.extend(self.item_types_load(item_type_uuids))
            else:
                # loading character's inventory
                item_types = []
                max_quantity = {}
                for item_type, quantity in character.inventory.items():
                    if assortment.get("buy-%s" % item_type.uuid):
                        item_types.append(item_type)
                        max_quantity[item_type.dna] = quantity
            # user action
            if req.ok():
                errors = []
                user_requests = {}
                create_items = []
                discard_items = []
                transfer_items = []
                money = {}
                item_names = {}
                for ent in req.param("items").split(";"):
                    m = re_request_item.match(ent)
                    if not m:
                        errors.append(self._("Invalid request parameter: %s") % htmlescape(ent))
                        continue
                    dna, price, currency, quantity = m.group(1, 2, 3, 4)
                    price = floatz(price)
                    quantity = intz(quantity)
                    if price > 0 and quantity > 0:
                        if quantity >= 999999:
                            quantity = 999999
                        user_requests[dna] = {
                            "price": price,
                            "currency": currency,
                            "quantity": quantity,
                        }
                now = self.now()
                oplog = self.obj(DBShopOperation)
                oplog.set("performed", now)
                oplog.set("shop", func_id)
                oplog.set("character", character.uuid)
                oplog.set("mode", mode)
                oplog.set("operations", user_requests.copy())
            # processing catalog
            ritems = {}
            for item_type in item_types:
                if req.ok():
                    ureq = user_requests.get(item_type.dna)
                else:
                    ureq = None
                ritem = {
                    "type": item_type.uuid,
                    "dna": item_type.dna,
                    "name": htmlescape(item_type.name),
                    "image": item_type.image("shops"),
                    "description": item_type.get("description"),
                    "quantity": ureq["quantity"] if ureq else 0,
                    "qparam": "q_%s" % item_type.dna,
                    "min_quantity": 0,
                    "max_quantity": max_quantity[item_type.dna] if item_type.dna in max_quantity else 999999,
                    "show_max": item_type.dna in max_quantity,
                    "order": item_type.get("order", 0),
                }
                # item parameters
                params = []
                self.call("item-types.params-owner-important", item_type, params)
                params = [par for par in params if par.get("value_raw") and not par.get("price")]
                # item category
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
                if cat is None:
                    continue
                # item price
                price = assortment.get("%s-price-%s" % (mode, item_type.uuid))
                if price is None:
                    price = item_type.get("balance-price")
                    balance_currency = item_type.get("balance-currency")
                    # items without balance price and without shop price are ignores
                    if price is None:
                        continue
                    currency = assortment.get("%s-currency-%s" % (mode, item_type.uuid), balance_currency)
                    if currency != balance_currency:
                        # exchange rate conversion
                        rates = self.call("exchange.rates")
                        if rates is not None:
                            from_rate = rates.get(balance_currency)
                            to_rate = rates.get(currency)
                            if from_rate > 0 and to_rate > 0:
                                price *= from_rate / to_rate;
                else:
                    currency = assortment.get("%s-currency-%s" % (mode, item_type.uuid))
                if price is None:
                    price = 0
                # price correction
                if mode == "sell":
                    description = self._("Sell price evaluation")
                else:
                    description = self._("Buy price evaluation")
                price = self.call("script.evaluate-expression", func.get("shop_%s_price" % mode), globs={"char": character, "price": price, "currency": currency, "item": item_type}, description=description)
                price = floatz(price)
                # rendering price
                price = self.call("money.format-price", price, currency)
                value = self.call("money.price-html", price, currency)
                cinfo = self.call("money.currency-info", currency)
                params.insert(0, {
                    "name": '<span class="item-types-page-price-name">%s</span>' % (self._("Sell price") if mode == "sell" else self._("Buy price")),
                    "value": '<span class="item-types-page-price-value">%s</span>' % value,
                })
                ritem["price"] = price
                ritem["currency"] = currency
                ritem["cicon"] = cinfo["icon"]
                # storing item
                if params:
                    params[-1]["lst"] = True
                    ritem["params"] = params
                try:
                    ritems[cat].append(ritem)
                except KeyError:
                    ritems[cat] = [ritem]
                # trying to buy
                if req.ok():
                    if ureq:
                        if ureq["price"] != price or ureq["currency"] != currency:
                            errors.append(self._("Price of {item_name_gp} was changed (from {old_price} {old_currency} to {new_price} {new_currency})").format(item_name_gp=htmlescape(item_type.name_gp), old_price=ureq["price"], old_currency=ureq["currency"], new_price=price, new_currency=currency))
                        elif item_type.dna in max_quantity and ureq["quantity"] > max_quantity[item_type.dna]:
                            errors.append(self._("Not enough {item_name_gp}  ({available} pcs available)").format(item_name_gp=htmlescape(item_type.name_gp), available=max_quantity[item_type.dna]))
                        else:
                            # recording money amount
                            try:
                                money[currency] += price * ureq["quantity"]
                            except KeyError:
                                money[currency] = price * ureq["quantity"]
                            # recording money transaction comment
                            try:
                                comments = item_names[currency]
                            except KeyError:
                                comments = {}
                                item_names[currency] = comments
                            try:
                                comments[item_type.name] += ureq["quantity"]
                            except KeyError:
                                comments[item_type.name] = ureq["quantity"]
                            # recording operation
                            if mode == "sell":
                                if assortment.get("sell-store-%s" % item_type.uuid):
                                    transfer_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                                else:
                                    create_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                            else:
                                if assortment.get("buy-store-%s" % item_type.uuid):
                                    transfer_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                                else:
                                    discard_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                        del user_requests[item_type.dna]
            rcategories = []
            active_cat = req.param("cat")
            any_visible = False
            for cat in categories:
                if cat["id"] in ritems:
                    lst = ritems[cat["id"]]
                    lst.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["name"], y["name"]))
                    if active_cat:
                        visible = active_cat == cat["id"]
                    else:
                        visible = cat.get("default")
                    rcategories.append({
                        "id": cat["id"],
                        "name_html_js": jsencode(htmlescape(cat["name"])),
                        "visible": visible,
                        "items": lst,
                    })
                    if visible:
                        any_visible = True
            if not any_visible and rcategories:
                rcategories[0]["visible"] = True
            if req.ok():
                if user_requests:
                    errors.append(self._("Shop assortment changed"))
                if mode == "sell":
                    # checking available money
                    if not errors:
                        for currency, amount in money.iteritems():
                            if character.money.available(currency) < amount:
                                errors.append(self.call("money.not-enough-funds", currency))
                redirect = None
                if mode == "buy":
                    if not errors:
                        # transferring items
                        for ent in transfer_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            item_type_taken, quantity_taken = character.inventory._take_dna(item_type.dna, quantity, "shop-sell", performed=now, reftype=shop_inventory.owtype, ref=shop_inventory.uuid)
                            if quantity_taken is None:
                                raise RuntimeError("Could not take quantity={quantity}, dna={dna} from character's inventory (character={character})".format(quantity=quantity, dna=item_type.dna, character=character.uuid))
                            shop_inventory._give(item_type.uuid, quantity, "shop-bought", mod=item_type.mods, performed=now, reftype=character.inventory.owtype, ref=character.inventory.uuid)
                        # discarding items
                        for ent in discard_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            item_type_taken, quantity_taken = character.inventory._take_dna(item_type.dna, quantity, "shop-sell", performed=now)
                            if quantity_taken is None:
                                raise RuntimeError("Could not take quantity={quantity}, dna={dna} from character's inventory (character={character})".format(quantity=quantity, dna=item_type.dna, character=character.uuid))
                else:
                    if not errors:
                        # transferring items
                        for ent in transfer_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            item_type_taken, quantity_taken = shop_inventory._take_dna(item_type.dna, quantity, "shop-sold", performed=now, reftype=character.inventory.owtype, ref=character.inventory.uuid)
                            if quantity_taken is None:
                                raise RuntimeError("Could not take quantity={quantity}, dna={dna} from shop store (shop={shop})".format(quantity=quantity, dna=item_type.dna, shop=shop_inventory.uuid))
                            character.inventory._give(item_type.uuid, quantity, "shop-buy", mod=item_type.mods, performed=now, reftype=shop_inventory.owtype, ref=shop_inventory.uuid)
                        # giving items
                        for ent in create_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            character.inventory._give(item_type.uuid, quantity, "shop-buy", performed=now)
                            # obtaining inventory class
                            if not redirect:
                                # item inventory category
                                cat = item_type.get("cat-inventory")
                                misc = None
                                found = False
                                for c in self.call("item-types.categories", "inventory"):
                                    if c["id"] == cat:
                                        found = True
                                    if c.get("misc"):
                                        misc = c["id"]
                                if not found:
                                    cat = misc
                                if cat is not None:
                                    redirect = "/inventory?cat=%s#%s" % (cat, item_type.dna)
                # checking overweight conditions
                if mode == "sell":
                    if not errors:
                        errors = character.inventory.constraints_failed()
                # taking of giving money
                if not errors:
                    for currency, amount in money.iteritems():
                        curr_comments = []
                        for item_name, quantity in item_names[currency].iteritems():
                            curr_comments.append({
                                "name": item_name,
                                "quantity": quantity,
                            })
                        curr_comments.sort(cmp=lambda x, y: cmp(x["name"], y["name"]))
                        curr_comments = [ent["name"] if ent["quantity"] == 1 else "%s - %d %s" % (ent["name"], ent["quantity"], self._("pcs")) for ent in curr_comments]
                        comment = ", ".join(curr_comments)
                        if mode == "sell":
                            # debiting character's account
                            if not character.money.debit(amount, currency, "shop-buy", comment=comment, nolock=True, performed=now):
                                errors.append(self._("Technical error during debiting {amount} {currency} (available={available})").format(amount=amount, currency=currency, available=character.money.available(currency)))
                                break
                        else:
                            # crediting character's account
                            character.money.credit(amount, currency, "shop-sell", comment=comment, nolock=True, performed=now)
                            if redirect is None:
                                redirect = "/money/operations/%s" % currency
                if errors:
                    vars["error"] = u"<br />".join(errors)
                else:
                    oplog.store()
                    character.inventory.store()
                    shop_inventory.store()
                    if mode == "sell":
                        self.qevent("shop-bought", char=character)
                    else:
                        self.qevent("shop-sold", char=character)
                    self.call("web.redirect", redirect or "/inventory")
        if rcategories:
            vars["categories"] = rcategories
            vars["Total"] = self._("Total")
            if mode == "sell":
                vars["Submit"] = self._("Buy selected items")
            else:
                vars["Submit"] = self._("Sell selected items")
            content = self.call("game.parse_internal", "shop-items-layout.html", vars)
            content = self.call("game.parse_internal", "shop-items.html", vars, content)
        elif mode == "sell":
            content = self._("There are no items for sell at the moment")
        else:
            content = self._("You have no items for sell to this shop")
        self.call("game.response_internal", "shop-global.html", vars, content)

    def sell(self, func_id, base_url, func, args, vars):
        return self.transaction("sell", func_id, base_url, func, args, vars)

    def buy(self, func_id, base_url, func, args, vars):
        return self.transaction("buy", func_id, base_url, func, args, vars)

