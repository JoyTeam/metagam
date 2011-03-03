from mg import *

class Auth(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-users.index", self.menu_users_index)
        self.rhook("ext-admin-players.auth", self.admin_players_auth)
        self.rhook("headmenu-admin-players.auth", self.headmenu_players_auth)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-players.form", self.admin_players_form)
        self.rhook("headmenu-admin-players.form", self.headmenu_players_form)

    def permissions_list(self, perms):
        perms.append({"id": "players.auth", "name": self._("Players authentication settings")})

    def menu_users_index(self, menu):
        req = self.req()
        if req.has_access("players.auth"):
            menu.append({"id": "players/auth", "text": self._("Players authentication"), "leaf": True})
            menu.append({"id": "players/form", "text": self._("Player form"), "leaf": True})

    def headmenu_players_auth(self, args):
        return self._("Players authentication settings")

    def admin_players_auth(self):
        self.call("session.require_permission", "players.auth")
        req = self.req()
        config = self.app().config
        currencies = {}
        self.call("currencies.list", currencies)
        if req.param("ok"):
            errors = {}
            # multicharing
            multicharing = req.param("v_multicharing")
            if multicharing != "0" and multicharing != "1" and multicharing != "2":
                errors["multicharing"] = self._("Make valid selection")
            else:
                multicharing = int(multicharing)
                config.set("auth.multicharing", multicharing)
                if multicharing:
                    # free and max chars
                    free_chars = req.param("free_chars")
                    if not valid_nonnegative_int(free_chars):
                        errors["free_chars"] = self._("Invalid number")
                    else:
                        free_chars = int(free_chars)
                        if free_chars < 1:
                            errors["free_chars"] = self._("Minimal value is 1")
                        config.set("auth.free_chars", free_chars)
                    max_chars = req.param("max_chars")
                    if not valid_nonnegative_int(max_chars):
                        errors["max_chars"] = self._("Invalid number")
                    else:
                        max_chars = int(max_chars)
                        if max_chars < 1:
                            errors["max_chars"] = self._("Minimal value is 1")
                        config.set("auth.max_chars", max_chars)
                    if not errors.get("max_chars") and not errors.get("free_chars"):
                        if max_chars < free_chars:
                            errors["free_chars"] = self._("Free characters can't be greater than max characters")
                        elif max_chars > free_chars:
                            # multichars price
                            multichar_price = req.param("multichar_price")
                            multichar_currency = req.param("v_multichar_currency")
                            if self.call("money.valid_amount", multichar_price, multichar_currency, errors, "multichar_price", "v_multichar_currency"):
                                multichar_price = float(multichar_price)
                                config.set("auth.multichar_price", multichar_price)
                                config.set("auth.multichar_currency", multichar_currency)
                # cabinet
                config.set("auth.cabinet", True if req.param("cabinet") else False)
            # email activation
            activate_email = True if req.param("activate_email") else False
            config.set("auth.activate_email", activate_email)
            if activate_email:
                activate_email_level = req.param("activate_email_level")
                if not valid_nonnegative_int(activate_email_level):
                    errors["activate_email_level"] = self._("Invalid number")
                else:
                    activate_email_level = int(activate_email_level)
                    config.set("auth.activate_email_level", activate_email_level)
                activate_email_days = req.param("activate_email_days")
                if not valid_nonnegative_int(activate_email_days):
                    errors["activate_email_days"] = self._("Invalid number")
                else:
                    activate_email_days = int(activate_email_days)
                    config.set("auth.activate_email_days", activate_email_days)
            # names validation
            validate_names = True if req.param("validate_names") else False
            config.set("auth.validate_names", validate_names)
            # processing
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            multicharing = config.get("auth.multicharing", 0)
            free_chars = config.get("auth.free_chars", 1)
            max_chars = config.get("auth.max_chars", 5)
            multichar_price = config.get("auth.multichar_price", 5)
            multichar_currency = config.get("auth.multichar_currency")
            cabinet = config.get("auth.cabinet", 0)
            activate_email = config.get("auth.activate_email", True)
            activate_email_level = config.get("auth.activate_email_level", 0)
            activate_email_days = config.get("auth.activate_email_days", 7)
            validate_names = config.get("auth.validate_names", False)
        fields = [
            {"name": "multicharing", "type": "combo", "label": self._("Are players allowed to play more than 1 character"), "value": multicharing, "values": [(0, self._("No")), (1, self._("Yes, but play them by turn")), (2, self._("Yes, play them simultaneously"))] },
            {"name": "free_chars", "label": self._("Number of characters per player allowed for free"), "value": free_chars, "condition": "[multicharing]>0" },
            {"name": "max_chars", "label": self._("Maximal number of characters per player allowed"), "value": max_chars, "inline": True, "condition": "[multicharing]>0" },
            {"name": "multichar_price", "label": self._("Price for one extra character over free limit"), "value": multichar_price, "condition": "[multicharing]>0 && [max_chars]>[free_chars]" },
            {"name": "multichar_currency", "label": self._("Currency"), "type": "combo", "value": multichar_currency, "values": [(code, info["description"]) for code, info in currencies.iteritems()], "allow_blank": True, "condition": "[multicharing]>0 && [max_chars]>[free_chars]", "inline": True},
            {"name": "cabinet", "type": "combo", "label": self._("Login sequence"), "value": cabinet, "condition": "![multicharing]", "values": [(0, self._("Enter the game immediately after login")), (1, self._("Open player cabinet after login"))]},
            {"name": "activate_email", "type": "checkbox", "label": self._("Require email activation"), "checked": activate_email},
            {"name": "activate_email_level", "label": self._("Activation is required after this character level ('0' if require on registration)"), "value": activate_email_level, "condition": "[activate_email]"},
            {"name": "activate_email_days", "label": self._("Activation is required after this number of days ('0' if require on registration)"), "value": activate_email_days, "inline": True, "condition": "[activate_email]"},
            {"name": "validate_names", "type": "checkbox", "label": self._("Manual validation of every character name"), "checked": validate_names},
        ]
        self.call("admin.form", fields=fields)

    def admin_players_form(self):
        self.call("session.require_permission", "players.auth")
        self.call("admin.response_template", "admin/auth/player-form.html", {
            "fields": self.conf("auth.player_form"),
            "NewField": self._("New field"),
        })
