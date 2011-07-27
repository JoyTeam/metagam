from mg.constructor import *
from uuid import uuid4
from mg.constructor.player_classes import *
import re

re_delete_recover = re.compile(r'^(delete|recover)/(\S+)$')
re_combo_value = re.compile(r'\s*(\S+)\s*:\s*(.*?)\s*$')
re_tokens = re.compile(r'{([^{}]+)}')

class CharactersMod(ConstructorModule):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-characters.index", self.menu_characters_index)
        self.rhook("ext-admin-characters.form", self.admin_characters_form, priv="players.auth")
        self.rhook("headmenu-admin-characters.form", self.headmenu_characters_form)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("dossier.record", self.dossier_record)
        self.rhook("dossier.before-display", self.dossier_before_display)
        self.rhook("dossier.after-display", self.dossier_after_display)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-characters.names", self.admin_characters_names, priv="characters.names")
        self.rhook("headmenu-admin-characters.names", self.headmenu_characters_names)
        self.rhook("characters.name-purposes", self.name_purposes)
        self.rhook("characters.name-purpose-default", self.name_purpose_default)
        self.rhook("characters.name-purpose-admin", self.name_purpose_admin)
        self.rhook("characters.name-sample-params", self.name_sample_params)
        self.rhook("characters.name-params", self.name_params)
        self.rhook("characters.name-tokens", self.name_tokens)
        self.rhook("characters.name-render", self.name_render)
        self.rhook("characters.name-fixup", self.name_fixup)

    def name_fixup(self, character, purpose, params):
        if purpose == "admin":
            params["NAME"] = u'<hook:admin.link href="auth/user-dashboard/%s" title="%s" />' % (character.uuid, htmlescape(params["NAME"]))

    def permissions_list(self, perms):
        perms.append({"id": "characters.names", "name": self._("Character names rendering editor")})

    def menu_root_index(self, menu):
        menu.append({"id": "characters.index", "text": self._("Characters"), "order": 20})

    def menu_characters_index(self, menu):
        req = self.req()
        if req.has_access("players.auth"):
            menu.append({"id": "characters/form", "text": self._("Character form"), "leaf": True, "order": 20})
        if req.has_access("characters.names"):
            menu.append({"id": "characters/names", "text": self._("Character names"), "leaf": True, "order": 25})

    def admin_characters_form(self):
        req = self.req()
        character_form = self.call("character.form")
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
                    config = self.app().config_updater()
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
                config = self.app().config_updater()
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

    def objclasses_list(self, objclasses):
        objclasses["Player"] = (DBPlayer, DBPlayerList)
        objclasses["Character"] = (DBCharacter, DBCharacterList)
        objclasses["CharacterForm"] = (DBCharacterForm, DBCharacterFormList)

    def dossier_record(self, rec):
        try:
            char = self.obj(DBCharacter, rec.get("user"))
        except ObjectNotFoundException:
            pass
        else:
            rec.set("character", char.uuid)
            rec.set("user", char.get("player"))

    def dossier_before_display(self, dossier_info, vars):
        try:
            char = self.obj(DBCharacter, dossier_info["user"])
        except ObjectNotFoundException:
            pass
        else:
            dossier_info["user"] = char.get("player")

    def dossier_after_display(self, records, users, table):
        table["header"].append(self._("Character"))
        load_users = {}
        for rec in records:
            char_uuid = rec.get("character")
            if char_uuid and not users.get(char_uuid):
                load_users[char_uuid] = None
        if load_users:
            ulst = self.objlist(UserList, uuids=load_users.keys())
            ulst.load(silent=True)
            for ent in ulst:
                users[ent.uuid] = ent
        i = 0
        for rec in records:
            char_uuid = rec.get("character")
            user = users.get(char_uuid) if char_uuid else None
            table["rows"][i].append(u'<hook:admin.link href="auth/user-dashboard/{0}" title="{1}" />'.format(user.uuid, htmlescape(user.get("name"))) if user else None)
            i += 1

    def name_purposes(self, purposes):
        purposes.append(self.name_purpose_default())
        purposes.append(self.name_purpose_admin())

    def name_purpose_default(self):
        return {"id": "default", "title": self._("Default"), "order": -1000, "default": "{NAME} {INFO}"}

    def name_purpose_admin(self):
        return {"id": "admin", "title": self._("Administration interface"), "order": 0, "default": "{NAME}"}

    def name_params(self, characters, params):
        design = self.design("gameinterface")
        for char in characters:
            ent = params[char.uuid]
            ent["NAME"] = u'<span class="char-name">%s</span>' % htmlescape(char.name)
            img = "char-female.gif" if char.sex else "char-male.gif"
            ent["INFO"] = '<a href="/character/info/%s" target="_blank"><img src="%s/%s" alt="" class="icon char-info-icon" /></a>' % (char.uuid, design.get("uri") if design and img in design.get("files") else "/st-mg/icons", img)

    def name_sample_params(self, params):
        params["NAME"] = self._("Character")
        design = self.design("gameinterface")
        params["INFO"] = '<img src="%s/char-male.gif" alt="" class="icon char-info-icon" />' % (design.get("uri") if design and "char-male.gif" in design.get("files") else "/st-mg/icons")

    def name_tokens(self, tokens):
        tokens.append({"id": "NAME", "description": self._("Character name")})
        tokens.append({"id": "INFO", "description": self._("Character info icon")})

    def headmenu_characters_names(self, args):
        if args:
            pinfo = self.call("characters.name-purpose-%s" % args)
            if pinfo:
                return [pinfo["title"], "characters/names"]
            else:
                return [htmlescape(args), "characters/names"]
        return self._("Character names")

    def name_render(self, template, params):
        if type(template) != unicode:
            template = unicode(template)
        watchdog = 0
        while True:
            watchdog += 1
            if watchdog >= 100:
                break
            try:
                return template.format(**params)
            except KeyError as e:
                params[e.args[0]] = '{?%s?}' % htmlescape(e.args[0])
        return template

    def admin_characters_names(self):
        req = self.req()
        if req.args:
            pinfo = self.call("characters.name-purpose-%s" % req.args)
            if not pinfo:
                self.call("admin.redirect", "characters/names")
            tokens = []
            self.call("characters.name-tokens", tokens)
            valid_tokens = set()
            for token in tokens:
                valid_tokens.add(token["id"])
            if req.ok():
                errors = {}
                template = req.param("template").strip()
                if not template:
                    errors["template"] = self._("This field is mandatory")
                else:
                    tokens = re_tokens.findall(template)
                    for token in tokens:
                        if token not in valid_tokens:
                            errors["template"] = self._("Unknown token {%s}") % htmlescape(token)
                            break
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                config = self.app().config_updater()
                config.set("character.name-template-%s" % req.args, template)
                config.store()
                self.app().mc.incr_ver("character-names")
                self.call("admin.redirect", "characters/names")
            else:
                template = self.conf("character.name-template-%s" % pinfo["id"], pinfo["default"])
            tokens_html = '<div class="admin-description">%s</div>' % ''.join(['<div><strong>{%s}</strong> &mdash; %s</div>' % (token["id"], token["description"]) for token in tokens])
            fields = [
                {"type": "html", "html": tokens_html},
                {"name": "template", "value": template, "label": self._("Name template (valid tags are shown above)")},
            ]
            self.call("admin.form", fields=fields)
        purposes = []
        self.call("characters.name-purposes", purposes)
        purposes.sort(cmp=lambda x, y: cmp(x.get("order"), y.get("order")))
        rows = []
        sample_params = {}
        self.call("characters.name-sample-params", sample_params)
        for purp in purposes:
            template = self.conf("character.name-template-%s" % purp["id"], purp["default"])
            rows.append([
                purp["title"],
                self.name_render(template, sample_params),
                '<hook:admin.link href="characters/names/%s" title="%s" />' % (purp["id"], self._("edit")),
            ])
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Purpose"),
                        self._("Format"),
                        self._("Editing"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
