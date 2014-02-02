#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

from mg.constructor import *
from mg.core.money_classes import *
import re
from uuid import uuid4

min_auto_prolong = 86400

re_cmd = re.compile(r'^(enable|disable)/(\S+)$')
re_cmd_edit = re.compile(r'^(\S+)/(\d+|new)$')
re_cmd_del = re.compile(r'^(\S+)/del/(\d+)$')
re_cmd_pack = re.compile(r'^pack/(\S+)$')
re_del = re.compile(r'del/(\S+)')
re_valid_identifier = re.compile(r'^u_[a-z0-9_]+$', re.IGNORECASE)

class PaidServices(ConstructorModule):
    def register(self):
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("paidservices.offers", self.offers)
        self.rhook("paidservices.prolong", self.prolong)
        self.rhook("paidservices.render", self.render)
        self.rhook("modifier.prolong", self.modifier_prolong)
        self.rhook("ext-paidservices.index", self.paidservices_index, priv="logged")
        self.rhook("ext-paidservices.paid-service", self.ext_paid_service, priv="logged")
        self.rhook("ext-paidservices.prolong-enable", self.paidservices_prolong, priv="logged")
        self.rhook("ext-paidservices.prolong-disable", self.paidservices_prolong, priv="logged")
        self.rhook("paidservices.available", self.available, priority=100)
        for srv_id in self.conf("paidservices.manual-packs", []):
            self.rhook("paidservices.%s" % srv_id["id"], curry(self.manual_info, srv_id["id"]))
            self.rhook("money-description.%s" % srv_id["id"], curry(self.manual_money_description, srv_id["id"]))

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
            if srv.get("default_price"):
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
                roffer["html"] = self._('{price} forever').format(
                    price=self.call("money.price-html", offer["price"], offer["currency"]),
                )
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
        character = self.character(req.user())
        services = []
        for srv_id in service_ids:
            srv = self.call("paidservices.%s" % srv_id["id"])
            if not srv:
                continue
            if not self.conf("paidservices.enabled-%s" % srv_id["id"], srv.get("default_enabled")):
                continue
            if srv.get("subscription"):
                mod = character.modifiers.get(srv["id"])
                if mod:
                    if mod.get("maxtill"):
                        srv["status"] = self._("service///active till %s") % self.call("l10n.time_local", mod["maxtill"])
                    else:
                        srv["status"] = self._("service///active")
                    srv["status_cls"] = "service-active"
                    auto_prolong = False
                    enable_auto_prolong = False
                    for m in mod["mods"]:
                        if m.get("period") and m.get("period") >= min_auto_prolong and not m.get("dependent"):
                            enable_auto_prolong = True
                            if m.get("auto_prolong"):
                                auto_prolong = True
                    if enable_auto_prolong:
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
            if not srv["offers"]:
                continue
            info = self.conf("paidservices.info-%s" % srv_id["id"])
            if info:
                srv["name"] = info.get("name")
                srv["description"] = info.get("description")
                srv["order"] = info.get("order")
            services.append(srv)
        services.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x.get("name"), y.get("name")))
        vars["services"] = services
        vars["PaidService"] = self._("Paid service")
        vars["Description"] = self._("Description")
        vars["Price"] = self._("Price")
        vars["Status"] = self._("Status")
        vars["YourMoney"] = self._("Your money")
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
            html = self.call("money.price-html", balance, currency)
            donate = self.call("money.donate-message", currency, character=character)
            if donate:
                html = '%s (%s)' % (html, donate)
            accounts.append({
                "html": html,
            })
        if accounts:
            accounts[-1]["lst"] = True
            vars["money"] = accounts

    def prolong(self, mods, kind, period, price, currency, user=None, **kwargs):
        money = self.call("money.obj", mods.target_type, mods.uuid)
        with self.lock(["User.%s" % user]):
            if not money.debit(price, currency, kind, period=self.call("l10n.literal_interval", period) if period else None, period_a=self.call("l10n.literal_interval_a", period) if period else None):
                return False
            with self.lock([mods.lock_key]):
                mods.load()
                if period:
                    mods._prolong(kind, 1, period, **kwargs)
                else:
                    mods._add(kind, 1, None, **kwargs)
                pack = kwargs.get("pack")
                if pack:
                    kwargs["auto_prolong"] = False
                    kwargs["dependent"] = kind
                    del kwargs["pack"]
                    for kind in pack:
                        # disabling auto_prolong for all dependent kinds
                        mod = mods.get(kind)
                        if mod:
                            for m in mod["mods"]:
                                if m.get("auto_prolong"):
                                    del m["auto_prolong"]
                                m["dependent"] = kind
                        # prolonging given kind
                        if period:
                            mods._prolong(kind, 1, period, **kwargs)
                        else:
                            mods._add(kind, 1, None, **kwargs)
                mods.store(remove_expired=True)
        mods.notify()
        if mods.target_type == "user":
            char = self.character(mods.uuid)
            if char.valid:
                self.qevent("paidservice", char=char, mod=kind, period=period)
        return True

    def modifier_prolong(self, mods, mod):
        srv = self.call("paidservices.%s" % mod.get("kind"))
        if srv:
            # searching the closes match to old period
            best_offer = None
            offers = self.offers(srv)
            # searching for exact period match
            for offer in offers:
                if offer.get("period") == mod.get("period"):
                    best_offer = offer
                    break
            # searching for the greatest period less than previous one
            if not best_offer:
                for offer in offers:
                    if offer.get("period") < mod.get("period"):
                        if best_offer is None or offer.get("period") > best_offer:
                            best_offer = offer
            # searching for the least period greater than previous one
            if not best_offer:
                for offer in offers:
                    if offer.get("period") > mod.get("period"):
                        if best_offer is None or offer.get("period") < best_offer:
                            best_offer = offer
            if best_offer:
                auto_prolong = best_offer.get("period") >= min_auto_prolong
                if self.call("paidservices.prolong", mods, mod.get("kind"), best_offer.get("period"), best_offer.get("price"), best_offer.get("currency"), auto_prolong=auto_prolong, pack=mod.get("pack")):
                    return
        # paid service was not prolonged
        mods.destroy(mod.get("kind"), expiration=True)

    def paidservices_prolong(self):
        req = self.req()
        mods = self.call("modifiers.obj", "user", req.user())
        with self.lock([mods.lock_key]):
            mods.load()
            mod = mods.get(req.args)
            if mod:
                auto_prolong = True if req.hook == "prolong-enable" else False
                for m in mod["mods"]:
                    if not auto_prolong or m.get("period") and m.get("period") >= min_auto_prolong:
                        m["auto_prolong"] = auto_prolong
                        mods.touch()
            mods.store(remove_expired=True)
        mods.notify()
        self.call("web.redirect", req.param("redirect") or "/paidservices")

    def available(self, services):
        services.extend(self.conf("paidservices.manual-packs", []))

    def manual_info(self, srv_id):
        srv = self.conf("paidservices.info-%s" % srv_id, {})
        return {
            "id": srv_id,
            "name": srv.get("name"),
            "description": srv.get("description"),
            "subscription": True,
            "type": srv.get("type"),
            "pack": srv.get("pack"),
            "manual": True,
        }

    def manual_money_description(self, srv_id):
        srv = self.conf("paidservices.info-%s" % srv_id, {})
        return {
            "args": ["period", "period_a"],
            "text": self._("paidservice///{name} for {{period}}").format(name=srv.get("name")),
        }

    def ext_paid_service(self):
        req = self.req()
        pinfo = self.call("paidservices.%s" % req.args)
        if not pinfo:
            self.call("web.not_found")
        vars = {
            "menu_left": [
                {
                    "href": "/paidservices",
                    "html": self._("Paid services"),
                }, {
                    "html": pinfo["name"],
                    "lst": True
                }
            ]
        }
        form = self.call("web.form")
        offer = intz(req.param("offer"))
        mods = self.call("modifiers.obj", "user", req.user())
        mod = mods.get(pinfo["id"])
        if mod:
            btn_title = self._("Prolong")
            if mod["maxtill"] is None:
                self.call("main-frame.info", self._("This paid service is bought already"), vars)
        else:
            btn_title = self._("Buy")
        form.add_message_top(pinfo["description"])
        offers = self.call("paidservices.offers", pinfo["id"])
        if req.ok():
            if offer < 0 or offer >= len(offers):
                form.error("offer", self._("Select an offer"))
            if not form.errors:
                o = offers[offer]
                mods = self.call("modifiers.obj", "user", req.user())
                auto_prolong = o["period"] is not None and o["period"] >= min_auto_prolong
                if o["period"] is None:
                    btn_title = self._("Buy")
                if self.call("paidservices.prolong", mods, pinfo["id"], o["period"], o["price"], o["currency"], auto_prolong=auto_prolong, pack=pinfo.get("pack")):
                    self.call("web.redirect", "/paidservices")
                else:
                    form.error("offer", self.call("money.not-enough-funds", o["currency"]))
        for i in xrange(0, len(offers)):
            o = offers[i]
            form.radio(o["html"], "offer", i, offer)
        form.submit(None, None, btn_title)
        self.call("game.internal_form", form, vars)

class PaidServicesAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-economy.index", self.menu_economy_index)
        self.rhook("ext-admin-paidservices.editor", self.admin_paidservices_editor, priv="paidservices.editor")
        self.rhook("headmenu-admin-paidservices.editor", self.headmenu_paidservices_editor)
        self.rhook("advice-admin-game.dashboard", self.advice_game_dashboard)
        self.rhook("admin-modifiers.descriptions", self.mod_descriptions)
        self.rhook("admin-gameinterface.design-files", self.gameinterface_design_files)
        self.rhook("admin-sociointerface.design-files", self.sociointerface_design_files)

    def sociointerface_design_files(self, files):
        files.append({"filename": "paid-services.html", "description": self._("Paid services interface"), "doc": "/doc/design/paid-services"})

    def gameinterface_design_files(self, files):
        files.append({"filename": "paid-services.html", "description": self._("Paid services interface"), "doc": "/doc/design/paid-services"})

    def mod_descriptions(self, modifiers, mods):
        for key, mod in mods.iteritems():
            srv = self.call("paidservices.%s" % key)
            if srv:
                mod["description"] = htmlescape(srv.get("name"))

    def advice_game_dashboard(self, args, advice):
        if args == "" and self.app().project.get("published"):
            advice.append({"title": self._("Paid services"), "content": self._('To raise your income you can offer some subscription-based <hook:admin.link href="paidservices/editor" title="paid services" /> to your players'), "order": 10})
        
    def permissions_list(self, perms):
        perms.append({"id": "paidservices.editor", "name": self._("Paid services editor")})

    def menu_economy_index(self, menu):
        req = self.req()
        if req.has_access("paidservices.editor"):
            menu.append({"id": "paidservices/editor", "text": self._("Paid services"), "icon": "/st-mg/menu/coin.gif", "leaf": True})

    def headmenu_paidservices_editor(self, args):
        m = re_cmd_pack.match(args)
        if m:
            uuid = m.group(1)
            if uuid == "new":
                return [self._("New packet"), "paidservices/editor"]
            else:
                return [self._("Packet properties"), "paidservices/editor"]
        elif args:
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
        else:
            return self._("Paid services")

    def admin_paidservices_editor(self):
        req = self.req()
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('You can find information on setting up paid services in your game in the <a href="//www.%s/doc/paid-services" target="_blank">paid services manual</a>.') % self.main_host})
        m = re_cmd_pack.match(req.args)
        if m:
            uuid = m.group(1)
            if False:
                # We may not destroy the pack completely - money-descriptions must remain untouched
                m = re_del.match(uuid)
                if m:
                    uuid = m.group(1)
                    packs = self.conf("paidservices.manual-packs", [])
                    packs = [p for p in packs if p["id"] != uuid]
                    config = self.app().config_updater()
                    config.set("paidservices.manual-packs", packs)
                    config.delete("paidservices.info-%s" % uuid)
                    config.store()
                    self.call("admin.redirect", "paidservices/editor")
            # loading available packet components
            service_ids = []
            self.call("paidservices.available", service_ids)
            valid_components = set()
            if uuid != "new":
                info = self.conf("paidservices.info-%s" % uuid)
                if info is None:
                    srv = self.call("paidservices.%s" % uuid)
                    if not srv:
                        self.call("admin.redirect", "paidservices/editor")
                    info = {
                        "name": srv["name"],
                        "description": srv["description"],
                        "order": srv.get("order", 0),
                    }
            else:
                components = []
                for srv_id in service_ids:
                    srv = self.call("paidservices.%s" % srv_id["id"])
                    if not srv or srv.get("pack") or not srv.get("subscription"):
                        continue
                    valid_components.add(srv_id["id"])
                    components.append({"id": srv_id["id"], "name": srv["name"], "type": srv["type"]})
            if req.ok():
                # processing form
                errors = {}
                tp = None
                packs = self.conf("paidservices.manual-packs", [])
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                description = req.param("description").strip()
                if not description:
                    errors["description"] = self._("This field is mandatory")
                if uuid == "new":
                    for c in components:
                        if req.param("cmp-%s" % c["id"]):
                            if tp is None:
                                tp = c.get("type")
                    new_uuid = req.param("uuid")
                    if not new_uuid:
                        errors["uuid"] = self._("This field is mandatory")
                    elif not re_valid_identifier.match(new_uuid):
                        errors["uuid"] = self._("Identifier must start with 'u_'. Other symbols may be latin letters, digits or '_'")
                    elif self.call("paidservices.%s" % new_uuid):
                        errors["uuid"] = self._("You already have paid service with same ID")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                # storing
                config = self.app().config_updater()
                if uuid == "new":
                    config.set("paidservices.manual-packs", packs)
                    uuid = new_uuid
                    pack = []
                    for c in components:
                        if req.param("cmp-%s" % c["id"]):
                            pack.append(c["id"])
                    info = {
                        "id": uuid,
                        "pack": pack,
                        "type": tp
                    }
                    packs.append(info)
                info["name"] = name
                info["description"] = description
                info["order"] = floatz(req.param("order"))
                config.set("paidservices.info-%s" % uuid, info)
                config.store()
                self.call("admin.redirect", "paidservices/editor")
            elif uuid == "new":
                name = ""
                description = ""
                order = ""
            else:
                name = info.get("name")
                description = info.get("description")
                order = info.get("order")
            fields = [
                {"name": "name", "value": name, "label": self._("Packet name")},
                {"name": "order", "value": order, "label": self._("Sorting order"), "inline": True},
                {"name": "description", "value": description, "label": self._("Packet description")},
            ]
            if uuid == "new":
                fields.insert(0, {"name": "uuid", "label": self._("Packet identifier (for usage in scripting)"), "value": "u_"})
                first = True
                for c in components:
                    fields.append({"name": "cmp-%s" % c["id"], "label": c["name"], "type": "checkbox"})
                    if first:
                        first = False
                        fields[-1]["desc"] = self._("Select paid services to include in the pack")
            self.call("admin.form", fields=fields)
        m = re_cmd.match(req.args)
        if m:
            cmd, srv_id = m.group(1, 2)
            config = self.app().config_updater()
            config.set("paidservices.enabled-%s" % srv_id, True if cmd == "enable" else False)
            config.store()
            self.call("admin.redirect", "paidservices/editor")
        elif req.args:
            m = re_cmd_del.match(req.args)
            if m:
                srv_id, offer_id = m.group(1, 2)
                offer_id = int(offer_id)
                offers = self.call("paidservices.offers", srv_id)
                if offers and offer_id < len(offers):
                    del offers[offer_id:offer_id + 1]
                    config = self.app().config_updater()
                    config.set("paidservices.offers-%s" % srv_id, offers)
                    config.store()
                self.call("admin.redirect", "paidservices/editor/%s" % srv_id)
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
        service_info = {}
        for srv_id in service_ids:
            srv = self.call("paidservices.%s" % srv_id["id"])
            if not srv:
                continue
            service_info[srv_id["id"]] = srv
        rows = []
        for srv_id in service_ids:
            srv = service_info.get(srv_id["id"])
            if not srv:
                continue
            info = self.conf("paidservices.info-%s" % srv_id["id"])
            # current status
            status = self.conf("paidservices.enabled-%s" % srv_id["id"], srv.get("default_enabled"))
            if status:
                status = '%s<br /><hook:admin.link href="paidservices/editor/disable/%s" title="%s" />' % (self._("service///enabled"), srv_id["id"], self._("disable"))
            else:
                status = '%s<br /><hook:admin.link href="paidservices/editor/enable/%s" title="%s" />' % (self._("service///disabled"), srv_id["id"], self._("enable"))
            # offers list
            offers = self.call("paidservices.offers", srv)
            offers = ['<div>%s</div>' % off["html"] for off in offers]
            offers.append('<hook:admin.link href="paidservices/editor/%s" title="%s" />' % (srv_id["id"], self._("edit")))
            offers = ''.join(offers)
            name = '<strong>%s</strong><br />char.mod.%s' % (info.get("name") if info else srv.get("name"), srv_id["id"])
            if srv.get("pack"):
                name += '<ul>'
                for s in srv.get("pack"):
                    s_info = service_info.get(s)
                    name += '<li>%s</li>' % (s_info.get("name") if s_info else self._("Unknown service %s") % s)
                name += '</ul>'
            control = '<hook:admin.link href="paidservices/editor/pack/%s" title="%s" />' % (srv_id["id"], self._("edit"))
            #if srv.get("manual"):
            #    control = '<hook:admin.link href="paidservices/editor/pack/%s" title="%s" />' % (srv_id["id"], self._("edit"))
            #else:
            #    control = None
            rows.append(([
                name,
                status,
                offers,
                control,
            ], info.get("order", 0) if info else srv.get("order", 0)))
        rows.sort(cmp=lambda x, y: cmp(x[1], y[1]) or cmp(x[0][0], y[0][0]))
        rows = [row for row, order in rows]
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "paidservices/editor/pack/new", "text": self._("New paid services packet"), "lst": True},
                    ],
                    "header": [
                        self._("Paid service"),
                        self._("Status"),
                        self._("Prices"),
                        self._("Control"),
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
                    offer.get("period") or self._("Forever"),
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
            period = req.param("period").strip()
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
            if period == "":
                period = None
            elif not valid_nonnegative_int(period):
                errors["period"] = self._("Invalid number format")
            else:
                period = int(period)
                if period > 315360000:
                    errors["period"] = self._("Max period is %d sec") % 315360000
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            offers = self.conf("paidservices.offers-%s" % srv["id"], [])
            if offer_id == "new":
                offers.append({
                    "period": period,
                    "price": float(price),
                    "currency": currency,
                })
            else:
                offer_id = int(offer_id)
                if offer_id < len(offers):
                    offers[offer_id]["period"] = int(period) if period is not None else None
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
            {"name": "period", "label": self._("Period (in seconds; empty field means forever)"), "value": period},
            {"name": "price", "label": self._("Price"), "value": price},
            {"name": "currency", "label": self._("Currency"), "value": currency, "type": "combo", "values": [(code, info["name_plural"]) for code, info in currencies.iteritems()], "inline": True},
        ]
        self.call("admin.form", fields=fields)
