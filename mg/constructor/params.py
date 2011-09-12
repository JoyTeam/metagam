from mg.constructor import *
import re

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_values_table = re.compile(r'^(-?(?:\d+|\d+\.\d+))\s*:\s*(-?(?:\d+|\d+\.\d+))$')
re_visual_table = re.compile(r'^(-?(?:\d+|\d+\.\d+))\s*:\s*(.+)$')
re_del = re.compile(r'^del/(.+)$')

class Fake(ConstructorModule):
    pass

class ParamsAdmin(ConstructorModule):
    def register(self):
        self.rdep(["mg.constructor.params.Fake"])
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-%s.params" % self.kind, self.admin_params, priv="%s.params" % self.kind)
        self.rhook("headmenu-admin-%s.params" % self.kind, self.headmenu_params)

    def permissions_list(self, perms):
        perms.append({"id": "%s.params" % self.kind, "name": '%s: %s' % (self.title, self._("editing"))})
        perms.append({"id": "%s.params-view" % self.kind, "name": '%s: %s' % (self.title, self._("viewing"))})

    def headmenu_params(self, args):
        if args == "new":
            return [self._("New parameter"), "%s/params" % self.kind]
        elif args:
            param = self.call("%s.param" % self.kind, args)
            if param:
                return [htmlescape(param["name"]), "%s/params" % self.kind]
        return self.title

    def admin_params(self):
        req = self.req()
        if req.args:
            m = re_del.match(req.args)
            if m:
                code = m.group(1)
                params = self.call("%s.params" % self.kind)
                new_params = [p for p in params if p["code"] != code]
                if len(params) != len(new_params):
                    config = self.app().config_updater()
                    config.set("%s.params" % self.kind, new_params)
                    config.store()
                self.call("admin.redirect", "%s/params" % self.kind)

            if req.args == "new":
                param = {}
                params = self.call("%s.params" % self.kind)
                if params:
                    param["order"] = params[-1]["order"] + 10.0
                else:
                    param["order"] = 0.0
            else:
                param = self.call("%s.param" % self.kind, req.args)
                if not param:
                    self.call("admin.redirect", "%s/params" % self.kind)
            if req.ok():
                new_param = {}
                errors = {}
                # code
                code = req.param("code")
                if not code:
                    errors["code"] = self._("This field is mandatory")
                elif not re_valid_identifier.match(code):
                    errors["code"] = self._("Parameter identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
                elif code != param.get("code") and self.call("%s.param" % self.kind, code):
                    errors["code"] = self._("Parameter with the same code already exists")
                else:
                    new_param["code"] = code
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    new_param["name"] = name
                # visibility
                if req.param("owner_visible"):
                    new_param["owner_visible"] = True
                    new_param["description"] = req.param("description").strip()
                    if req.param("important"):
                        new_param["important"] = True
                    if req.param("public"):
                        new_param["public"] = True
                # grouping
                new_param["grp"] = req.param("grp").strip()
                new_param["order"] = floatz(req.param("order"))
                # type
                tp = intz(req.param("v_type"))
                if tp < 0 or tp > 2:
                    errors["v_type"] = self._("This field is mandatory")
                else:
                    new_param["type"] = tp
                    if tp == 0:
                        new_param["default"] = nn(req.param("default"))
                    if tp > 0:
                        char = self.character(req.user())
                        new_param["expression"] = self.call("script.admin-expression", "expression", errors, globs={"char": char})
                    if tp == 2:
                        values_table = []
                        for line in req.param("values_table").strip().split("\n"):
                            l = line.strip()
                            if l != "":
                                m = re_values_table.match(l)
                                if not m:
                                    errors["values_table"] = self._("Invalid line format: '%s'") % l
                                    break
                                else:
                                    v1, v2 = m.group(1, 2)
                                    values_table.append([nn(v1), nn(v2)])
                        if "values_table" not in errors:
                            if not values_table:
                                errors["values_table"] = self._("This field is mandatory")
                            else:
                                new_param["values_table"] = values_table
                # visualization
                mode = intz(req.param("v_visual_mode"))
                if mode < 0 or mode > 2:
                    errors["v_visual_mode"] = self._("This field is mandatory")
                else:
                    new_param["visual_mode"] = mode
                    if mode == 2:
                        tpl = req.param("visual_template").strip()
                        if not tpl:
                            errors["visual_template"] = self._("This field is mandatory")
                        else:
                            try:
                                tpl.format(val=10, text="test")
                            except Exception:
                                errors["visual_template"] = self._("Invalid format of the template")
                            else:
                                new_param["visual_template"] = tpl
                    if mode > 0:
                        visual_table = []
                        for line in req.param("visual_table").strip().split("\n"):
                            l = line.strip()
                            if l != "":
                                m = re_visual_table.match(l)
                                if not m:
                                    errors["visual_table"] = self._("Invalid line format: '%s'") % l
                                    break
                                else:
                                    v1, v2 = m.group(1, 2)
                                    visual_table.append([nn(v1), v2])
                        if "visual_table" not in errors:
                            if not visual_table:
                                errors["visual_table"] = self._("This field is mandatory")
                            else:
                                new_param["visual_table"] = visual_table
                # library
                if req.param("library_visible"):
                    new_param["library_visible"] = True
                    if tp == 2 and req.param("library_table"):
                        new_param["library_table"] = True
                # API
                if req.param("api_values"):
                    new_param["api_values"] = True
                if tp > 0 and req.param("api_expression"):
                    new_param["api_expression"] = True
                if (tp == 2 or mode == 2) and req.param("api_table"):
                    new_param["api_table"] = True
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                params = [p for p in self.call("%s.params" % self.kind) if p["code"] != new_param.get("code") and p["code"] != param.get("code")]
                params.append(new_param)
                params.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["code"], y["code"]))
                config = self.app().config_updater()
                config.set("%s.params" % self.kind, params)
                config.store()
                self.call("admin.redirect", "%s/params" % self.kind)
            fields = [
                {"name": "code", "label": self._("Parameter code (used in scripting)"), "value": param.get("code")},
                {"name": "name", "label": self._("Parameter name"), "value": param.get("name")},
                {"name": "owner_visible", "label": self._("Parameter is visible to the owner"), "checked": param.get("owner_visible"), "type": "checkbox"},
                {"name": "description", "label": self._("Parameter description (for players)"), "value": param.get("description"), "condition": "[owner_visible]"},
                {"name": "important", "label": self._("Important parameter (show on the overview page)"), "checked": param.get("important"), "type": "checkbox", "condition": "[owner_visible]"},
                {"name": "public", "label": self._("Visible in public (show on the public information page)"), "checked": param.get("public"), "type": "checkbox", "condition": "[owner_visible]"},
                {"type": "header", "html": self._("Parameter grouping")},
                {"name": "grp", "label": self._("Parameter group name"), "value": param.get("grp")},
                {"name": "order", "label": self._("Sorting order"), "value": param.get("order")},
                {"type": "header", "html": self._("Parameter value")},
                {"type": "combo", "name": "type", "value": param.get("type", 0), "values": [
                    (0, self._("Stored in the database")),
                    (1, self._("Calculated using scripting expression")),
                    (2, self._("Calculated using expression and postprocessing table")),
                ]},
                {"name": "default", "value": param.get("default", 0), "label": self._("Default value"), "condition": "[type]==0"},
                {"name": "expression", "value": self.call("script.unparse-expression", param.get("expression")) if param.get("expression") else None, "label": "%s%s" % (self._("Expression"), self.call("script.help-icon-expressions")), "condition": "[type]>0"},
                {"name": "values_table", "value": "\n".join([u"%s: %s" % (ent[0], ent[1]) for ent in param.get("values_table", [])]), "label": self._("Conversion table (format: min_value - resulting_level). Sample 'experience to level' conversion:<br />0: 1<br />100: 2<br />500: 3<br />3000: 4"), "condition": "[type]==2", "type": "textarea", "remove_label_separator": True},
                {"type": "header", "html": self._("Parameter visualization")},
                {"type": "combo", "name": "visual_mode", "value": param.get("visual_mode", 0), "values": [
                    (0, self._("Simply show a number")),
                    (1, self._("Show abitrary HTML from the table of values")),
                    (2, self._("Complex template (with number and HTML from the table of values)")),
                ]},
                {"name": "visual_template", "value": param.get("visual_template"), "label": self._("Value template ({val} &mdash; number, {text} &mdash; text from the table)"), "condition": "[visual_mode]==2"},
                {"name": "visual_table", "value": "\n".join([u"%s: %s" % (ent[0], ent[1]) for ent in param.get("visual_table", [])]), "label": self._("Table of values (HTML allowed). Syntax:<br />1: recruit<br />2: sergeant<br />3: lieutenant<br />4: major"), "condition": "[visual_mode]>0", "type": "textarea", "remove_label_separator": True},
                {"type": "header", "html": self._("Library settings")},
                {"name": "library_visible", "label": self._("Publish parameter description in the library"), "checked": param.get("library_visible"), "type": "checkbox"},
                {"name": "library_table", "label": self._("Conversion table is published in the library"), "checked": param.get("library_table"), "type": "checkbox", "condition": "[type]==2 && [library_visible]"},
                {"type": "header", "html": self._("API settings (API is not implemented yet)")},
                {"name": "api_values", "label": self._("Parameter values are visible in the API"), "checked": param.get("api_values"), "type": "checkbox"},
                {"name": "api_expression", "label": self._("Parameter expression is visible in the API"), "checked": param.get("api_expression"), "type": "checkbox", "condition": "[type]>0"},
                {"name": "api_table", "label": self._("Parameter tables are visible in the API"), "checked": param.get("api_table"), "type": "checkbox", "condition": "[type]==2 || [visual_mode]>0"},
            ]
            self.call("admin.form", fields=fields)
        rows = []
        for param in self.call("%s.params" % self.kind):
            name = htmlescape(param["name"])
            if param["grp"]:
                name = '%s &middot; %s' % (htmlescape(param["grp"]), name)
            if param["type"] == 0:
                tp = self._("database///DB")
            elif param["type"] == 1:
                tp = self._("Expression")
            elif param["type"] == 2:
                tp = self._("Expression + table")
            else:
                tp = None
            rows.append([
                param["code"],
                name,
                tp,
                '<hook:admin.link href="%s/params/%s" title="%s" />' % (self.kind, param["code"], self._("edit")),
                '<hook:admin.link href="%s/params/del/%s" title="%s" confirm="%s" />' % (self.kind, param["code"], self._("delete"), self._("Are you sure want to delete this parameter?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "%s/params/new" % self.kind, "text": self._("New parameter"), "lst": True}
                    ],
                    "header": [
                        self._("Code"),
                        self._("Parameter name"),
                        self._("Type"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def admin_view_params(self, obj, params):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param["grp"] != "" and param["grp"] != grp:
                params.append(['<strong>%s</strong>' % htmlescape(param["grp"]), None, None, None])
                grp = param["grp"]
            value = self.call("%s.param-value-rec" % self.kind, obj, param)
            params.append([
                param["code"],
                htmlescape(param["name"]),
                htmlescape(value),
                self.call("%s.param-html" % self.kind, param, value),
            ])

class Params(ConstructorModule):
    def register(self):
        self.rdep(["mg.constructor.params.Fake"])
        self.rhook("%s.params" % self.kind, self.params)
        self.rhook("%s.param" % self.kind, self.param)
        self.rhook("%s.param-value" % self.kind, self.value)
        self.rhook("%s.param-value-rec" % self.kind, self.value_rec)
        self.rhook("%s.param-html" % self.kind, self.html)
        self.rhook("%s.params-public" % self.kind, self.params_public)
        self.rhook("%s.params-owner-important" % self.kind, self.params_owner_important)
        self.rhook("%s.params-owner-all" % self.kind, self.params_owner_all)

    def params(self):
        return self.conf("%s.params" % self.kind, [])

    def param(self, param_code):
        for p in self.call("%s.params" % self.kind):
            if p["code"] == param_code:
                return p
        return None

    def value(self, obj, param_code):
        param = self.param(param_code)
        if not param:
            return None
        return self.value_rec(obj, param)

    def value_rec(self, obj, param):
        # trying to return cached parameter value
        try:
            cache = obj._param_cache
        except AttributeError:
            cache = {}
            obj._param_cache = cache
        try:
            return cache[param["code"]]
        except KeyError:
            pass
        # cache miss. evaluating
        if param["type"] == 0:
            value = obj.db_params.get(param["code"], param.get("default", 0))
        else:
            try:
                value = self.call("script.evaluate-expression", param["expression"], obj.script_params(), description=self._("Evaluation of '{cls}.{uuid}.{param}'").format(cls=self.kind, param=param["code"], uuid=obj.uuid))
            except Exception as e:
                self.exception(e)
                value = None
            else:
                if param["type"] == 2:
                    res = None
                    for ent in param["values_table"]:
                        if ent[0] > value:
                            break
                        res = ent[1]
                    value = res
        # storing in the cache
        cache[param["code"]] = value
        return value

    def html(self, param, value):
        if param["visual_mode"] == 1 or param["visual_mode"] == 2:
            text = None
            for ent in param["visual_table"]:
                if ent[0] == value:
                    text = ent[1]
                    break
            if text is None:
                return value
            if param["visual_mode"] == 1:
                return text
            else:
                return param["visual_template"].format(val=value, text=text)
        else:
            return value

    def params_public(self, obj, params):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible") and param.get("public"):
                if param["grp"] != "" and param["grp"] != grp:
                    params.append({"header": htmlescape(param["grp"])})
                    grp = param["grp"]
                value = self.call("%s.param-value-rec" % self.kind, obj, param)
                value_html = self.call("%s.param-html" % self.kind, param, value)
                params.append({
                    "name": '<span class="%s-info-%s-name">%s</span>' % (self.kind, param["code"], htmlescape(param["name"])),
                    "value": '<span class="%s-info-%s-value">%s</span>' % (self.kind, param["code"], value_html),
                })

    def params_owner_important(self, obj, params):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible") and param.get("important"):
                if param["grp"] != "" and param["grp"] != grp:
                    params.append({"header": htmlescape(param["grp"])})
                    grp = param["grp"]
                value = self.call("%s.param-value-rec" % self.kind, obj, param)
                value_html = self.call("%s.param-html" % self.kind, param, value)
                params.append({
                    "name": '<span class="%s-page-%s-name">%s</span>' % (self.kind, param["code"], htmlescape(param["name"])),
                    "value": '<span class="%s-page-%s-value">%s</span>' % (self.kind, param["code"], value_html),
                })

    def params_owner_all(self, obj, params):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible"):
                if param["grp"] != "" and param["grp"] != grp:
                    params.append({"header": htmlescape(param["grp"])})
                    grp = param["grp"]
                value = self.call("%s.param-value-rec" % self.kind, obj, param)
                value_html = self.call("%s.param-html" % self.kind, param, value)
                params.append({
                    "name": '<span class="%s-page-%s-name">%s</span>' % (self.kind, param["code"], htmlescape(param["name"])),
                    "value": '<span class="%s-page-%s-value">%s</span>' % (self.kind, param["code"], value_html),
                })

    def notimportant_params_exist(self):
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible") and not param.get("important"):
                return True
        return False
