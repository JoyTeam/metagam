from mg import *
import re
import copy

re_delete_recover = re.compile(r'^(delete|recover)/(\S+)$')
re_combo_value = re.compile(r'\s*(\S+)\s*:\s*(.*?)\s*$')

class Auth(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-users.index", self.menu_users_index)
        self.rhook("ext-admin-players.auth", self.admin_players_auth)
        self.rhook("headmenu-admin-players.auth", self.headmenu_players_auth)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-characters.form", self.admin_characters_form)
        self.rhook("headmenu-admin-characters.form", self.headmenu_characters_form)
        self.rhook("indexpage.render", self.indexpage_render)

    def permissions_list(self, perms):
        perms.append({"id": "players.auth", "name": self._("Players authentication settings")})

    def menu_users_index(self, menu):
        req = self.req()
        if req.has_access("players.auth"):
            menu.append({"id": "players/auth", "text": self._("Players authentication"), "leaf": True, "order": 10})
            menu.append({"id": "characters/form", "text": self._("Character form"), "leaf": True, "order": 20})

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

    def admin_characters_form(self):
        self.call("session.require_permission", "players.auth")
        req = self.req()
        character_form = self.character_form()
        m = re_delete_recover.match(req.args)
        if m:
            op, code = m.group(1, 2)
            for fld in character_form:
                if fld["code"] == code:
                    if op == "delete":
                        fld["deleted"] = True
                    else:
                        try:
                            del fld["deleted"]
                        except KeyError:
                            pass
                    config = self.app().config
                    config.set("auth.char_form", character_form)
                    config.store()
                    self.call("auth.char-form-changed")
                    break
            self.call("admin.redirect", "characters/form")
        if req.args:
            # Loading data
            std_values = [(0, self._("Custom field")), (1, self._("Character name")), (2, self._("Character sex"))]
            used_std_values = dict([(fld["std"], fld["code"]) for fld in character_form if fld.get("std")])
            if req.args == "new":
                show_std = True
                std = 0
                code = ""
                name = ""
                description = ""
                prompt = ""
                field_type = 0
                values = ""
                order = character_form[-1]["order"] + 10 if len(character_form) else 10
                reg = False
                mandatory_level = 0
                std_values = [val for val in std_values if not used_std_values.get(val[0])]
            else:
                ok = False
                for fld in character_form:
                    if fld["code"] == req.args:
                        std = intz(fld.get("std"))
                        code = fld.get("code")
                        name = fld.get("name")
                        field_type = intz(fld.get("type"))
                        values = fld.get("values")
                        if values:
                            values = "|".join([":".join(val) for val in values])
                        description = fld.get("description")
                        prompt = fld.get("prompt")
                        order = fld.get("order")
                        reg = fld.get("reg")
                        mandatory_level = fld.get("mandatory_level")
                        show_std = std != 1 and std != 2
                        ok = True
                        break
                if not ok:
                    self.call("admin.redirect", "characters/form")
                std_values = [val for val in std_values if not used_std_values.get(val[0]) or used_std_values[val[0]] == code]
            valid_std_values = dict([(val[0], True) for val in std_values])
            if req.ok():
                # Validating data
                if show_std:
                    std = intz(req.param("v_std"))
                name = req.param("name")
                field_type = intz(req.param("v_type"))
                values = req.param("values")
                description = req.param("description")
                prompt = req.param("prompt")
                order = floatz(req.param("order"))
                reg = req.param("reg")
                mandatory_level = req.param("mandatory_level")
                errors = {}
                if show_std and not std in valid_std_values:
                    errors["std"] = self._("Invalid selection")
                if not name:
                    errors["name"] = self._("Name may not be empty")
                if not description:
                    errors["description"] = self._("Description may not be empty")
                if not prompt:
                    errors["prompt"] = self._("Prompt may not be empty")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                # Storing data
                val = {
                    "name": name,
                    "description": description,
                    "prompt": prompt,
                    "order": order,
                    "std": std
                }
                if req.args == "new":
                    val["code"] = uuid4().hex
                else:
                    val["code"] = req.args
                if std == 1 or std == 2:
                    val["reg"] = True
                else:
                    val["reg"] = reg
                    if not valid_nonnegative_int(mandatory_level):
                        errors["mandatory_level"] = self._("Number expected")
                    val["mandatory_level"] = intz(mandatory_level)
                if std == 1:
                    val["type"] = 0
                elif std == 2:
                    val["type"] = 1
                else:
                    val["type"] = field_type
                if val["type"] == 1:
                    if not values:
                        errors["values"] = self._("Specify list of values")
                    else:
                        values = values.split("|")
                        val["values"] = []
                        for v in values:
                            m = re_combo_value.match(v)
                            if not m:
                                errors["values"] = self._("Invalid format")
                            vl, desc = m.group(1, 2)
                            val["values"].append([vl, desc])
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                character_form = [fld for fld in character_form if fld["code"] != val["code"]]
                character_form.append(val)
                character_form.sort(cmp=lambda x, y: cmp(x.get("order"), y.get("order")) or cmp(x.get("name"), y.get("name")))
                config = self.app().config
                config.set("auth.char_form", character_form)
                config.store()
                self.call("auth.char-form-changed")
                self.call("admin.redirect", "characters/form")
            fields = [
                {"name": "name", "label": self._("Short description for administrators"), "value": name },
                {"name": "type", "label": self._("Form control type"), "value": field_type, "type": "combo", "values": [(0, self._("text input")), (1, self._("combo box")), (2, self._("text area"))], "condition": "![std]"},
                {"name": "values", "label": self._("Possible options. Format: 0:first value|1:second value|2:third value"), "value": values, "condition": "[type]==1 || [std]==2"},
                {"name": "order", "label": self._("Sort order"), "value": order },
                {"name": "description", "label": self._("Description for players"), "value": description },
                {"name": "prompt", "label": self._("Input prompt for players"), "value": prompt },
                {"name": "reg", "type": "checkbox", "label": self._("Show on registration"), "checked": reg, "condition": "[std]!=1 && [std]!=2"},
                {"name": "mandatory_level", "label": self._("The field is mandatory after this character level ('0' if not mandatory)"), "value": mandatory_level, "condition": "[std]!=1 && [std]!=2"},
            ]
            if show_std:
                fields.insert(0, {"name": "std", "type": "combo", "label": self._("Field type"), "value": std, "values": std_values})
            else:
                fields.insert(0, {"name": "std", "type": "hidden", "value": std})
            self.call("admin.form", fields=fields)
        self.call("admin.response_template", "admin/auth/character-form.html", {
            "fields": character_form,
            "NewField": self._("Create new field"),
            "Code": self._("Code"),
            "Name": self._("Name"),
            "Order": self._("Order"),
            "Editing": self._("Editing"),
            "Deletion": self._("Deletion"),
            "edit": self._("edit"),
            "delete": self._("delete"),
            "recover": self._("recover"),
            "Description": self._("Here you can customize parameters entered by player in the character form. These are not game parameters like strength and agility. Character form is a simple text fields like 'Legend', 'Motto' etc."),
        })

    def headmenu_characters_form(self, args):
        if args == "new":
            return [self._("New field"), "characters/form"]
        elif args:
            return [htmlescape(args), "characters/form"]
        return self._("Character form")

    def jsencode_character_form(self, lst):
        for fld in lst:
            fld["name"] = jsencode(fld.get("name"))
            fld["description"] = jsencode(fld.get("description"))
            fld["prompt"] = jsencode(fld.get("prompt"))
            if fld.get("values"):
                fld["values"] = [[jsencode(val[0]), jsencode(val[1])] for val in fld["values"]]
                fld["values"][-1].append(True)

    def character_form(self):
        fields = self.conf("auth.char_form", default=[])
        if not len(fields):
            fields.append({"std": 1, "code": "name", "name": self._("Character name"), "order": 10.0, "reg": True})
            fields.append({"std": 2, "code": "sex", "name": self._("Character sex"), "type": "combo", "values": [[0, self._("Male")], [1, self._("Female")]], "order": 20.0, "reg": True})
        return copy.deepcopy(fields)

    def indexpage_render(self, vars):
        character_form = self.character_form()
        character_form = [fld for fld in character_form if not fld.get("deleted") and fld.get("reg")]
        self.jsencode_character_form(character_form)
        vars["register_fields"] = character_form
