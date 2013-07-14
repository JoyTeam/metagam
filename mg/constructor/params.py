from mg.constructor import *
import re

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_values_table = re.compile(r'^(-?(?:\d+|\d+\.\d+))\s*:\s*(-?(?:\d+|\d+\.\d+))$')
re_visual_table = re.compile(r'^(-?(?:\d+|\d+\.\d+))\s*:\s*(.+)$')
re_copy = re.compile(r'^copy/(.+)$')
re_del = re.compile(r'^del/(.+)$')
re_paramedit_args = re.compile(r'^([0-9a-f]+)/([a-zA-Z_][a-zA-Z0-9_]*)$')

class Fake(ConstructorModule):
    pass

class ParamsAdmin(ConstructorModule):
    def register(self):
        self.rdep(["mg.constructor.params.Fake"])
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-%s.params" % self.kind, self.admin_params, priv="%s.params" % self.kind)
        self.rhook("headmenu-admin-%s.params" % self.kind, self.headmenu_params)
        self.rhook("ext-admin-%s.paramedit" % self.kind, self.admin_paramedit, priv="%s.params-edit" % self.kind)
        self.rhook("headmenu-admin-%s.paramedit" % self.kind, self.headmenu_paramedit)

    def permissions_list(self, perms):
        perms.append({"id": "%s.params" % self.kind, "name": '%s: %s' % (self.title, self._("configuration"))})
        perms.append({"id": "%s.params-view" % self.kind, "name": '%s: %s' % (self.title, self._("viewing"))})
        perms.append({"id": "%s.params-edit" % self.kind, "name": '%s: %s' % (self.title, self._("editing"))})

    def headmenu_params(self, args):
        if args == "new":
            return [self._("New parameter"), "%s/params" % self.kind]
        elif args:
            m = re_copy.match(args)
            if m:
                uuid = m.group(1)
                param = self.call("%s.param" % self.kind, uuid)
                if param:
                    return [self._("Copy of %s") % htmlescape(param["name"]), "%s/params" % self.kind]
            else:
                param = self.call("%s.param" % self.kind, args)
                if param:
                    return [htmlescape(param["name"]), "%s/params" % self.kind]
        return self.title

    def admin_params(self):
        req = self.req()
        self.call("admin.advice", {"title": self._("Parameters documentation"), "content": self._('You can find detailed information on the parameters system in the <a href="//www.%s/doc/parameters" target="_blank">parameters page</a> in the reference manual.') % self.main_host, "order": 30})
        if req.args:
            m = re_del.match(req.args)
            if m:
                code = m.group(1)
                params = self.call("%s.params" % self.kind)
                new_params = [p for p in params if p["code"] != code]
                if len(params) != len(new_params):
                    config = self.app().config_updater()
                    config.set("%s.params" % self.kind, new_params)
                    self.call("admin-%s.params-stored" % self.kind, new_params, config)
                    config.store()
                self.call("admin.redirect", "%s/params" % self.kind)
            if req.args == "new":
                # new parameter
                param = {}
                params = self.call("%s.params" % self.kind)
                if params:
                    param["order"] = params[-1]["order"] + 10.0
                else:
                    param["order"] = 0.0
            else:
                m = re_copy.match(req.args)
                if m:
                    # copy parameter
                    uuid = m.group(1) 
                    param = self.call("%s.param" % self.kind, uuid)
                    if not param:
                        self.call("admin.redirect", "%s/params" % self.kind)
                    param = param.copy()
                    del param["code"]
                    params = self.call("%s.params" % self.kind)
                    if params:
                        param["order"] = params[-1]["order"] + 10.0
                    else:
                        param["order"] = 0.0
                else:
                    # edit parameter
                    param = self.call("%s.param" % self.kind, req.args)
                    if not param:
                        self.call("admin.redirect", "%s/params" % self.kind)
            lang = self.call("l10n.lang")
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
                if lang == "ru":
                    # name_g
                    name_g = req.param("name_g").strip()
                    if name_g:
                        new_param["name_g"] = name_g
                # visibility
                if req.param("owner_visible"):
                    new_param["owner_visible"] = True
                    if req.param("zero_visible"):
                        new_param["zero_visible"] = True
                    if req.param("important"):
                        new_param["important"] = True
                    if req.param("public"):
                        new_param["public"] = True
                    if req.param("condition").strip():
                        new_param["condition"] = self.call("script.admin-expression", "condition", errors, globs=self.call("%s.script-globs" % self.kind))
                # description
                new_param["description"] = req.param("description").strip()
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
                        default = req.param("default")
                        if not valid_number(default):
                            errors["default"] = self._("This doesn't look like a number")
                        else:
                            new_param["default"] = nn(default)
                    if tp > 0:
                        new_param["expression"] = self.call("script.admin-expression", "expression", errors, globs=self.call("%s.script-globs" % self.kind))
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
                    if mode == 0 or mode == 2:
                        new_param["visual_plus"] = True if req.param("visual_plus") else False
                        vis_round = req.param("visual_round").strip()
                        if vis_round != "":
                            if not valid_nonnegative_int(vis_round):
                                errors["visual_round"] = self._("This doesn't look like a number")
                            else:
                                vis_round = int(vis_round)
                                if vis_round > 5:
                                    errors["visual_round"] = self._("Maximal value is %d") % 5
                                else:
                                    new_param["visual_round"] = vis_round
                # library
                if req.param("library_visible"):
                    new_param["library_visible"] = True
                    if tp == 2 and req.param("library_table"):
                        new_param["library_table"] = True
                    if not req.param("library_auto"):
                        uri = req.param("library_uri").strip()
                        if not uri:
                            errors["library_uri"] = self._("This field is mandatory")
                        else:
                            new_param["library_uri"] = uri
                # API
                if req.param("api_values"):
                    new_param["api_values"] = True
                if tp > 0 and req.param("api_expression"):
                    new_param["api_expression"] = True
                if (tp == 2 or mode == 2) and req.param("api_table"):
                    new_param["api_table"] = True
                # extensions
                self.call("admin-%s.params-form-save" % self.kind, param, new_param, errors)
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                params = [p for p in self.call("%s.params" % self.kind) if p["code"] != new_param.get("code") and p["code"] != param.get("code")]
                params.append(new_param)
                params.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["code"], y["code"]))
                config = self.app().config_updater()
                config.set("%s.params" % self.kind, params)
                self.call("admin-%s.params-stored" % self.kind, params, config)
                config.store()
                self.call("admin.redirect", "%s/params" % self.kind)
            fields = [
                {"name": "code", "label": self._("Parameter code (used in scripting)"), "value": param.get("code")},
                {"name": "name", "label": self._("Parameter name"), "value": param.get("name")},
            ]
            if lang == "ru":
                fields.append({"name": "name_g", "label": self._("Parameter name in genitive"), "value": param.get("name_g"), "inline": True})
            fields.extend([
                {"name": "description", "label": self._("Parameter description (for players)"), "value": param.get("description")},
                {"name": "owner_visible", "label": self._("Parameter is visible to the owner"), "checked": param.get("owner_visible"), "type": "checkbox"},
                {"name": "zero_visible", "label": self._("Parameter is visible even if its value is zero"), "checked": param.get("zero_visible"), "type": "checkbox", "condition": "[owner_visible]"},
                {"name": "condition", "value": self.call("script.unparse-expression", param.get("condition")) if param.get("condition") else None, "label": "%s%s" % (self._("Visibility condition (empty field means 'always visible')"), self.call("script.help-icon-expressions")), "condition": "[owner_visible]"},
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
                {"type": "header", "html": self._("Parameter visualization"), "tag": "visualization"},
                {"type": "combo", "name": "visual_mode", "value": param.get("visual_mode", 0), "values": [
                    (0, self._("Simply show a number")),
                    (1, self._("Show abitrary HTML from the table of values")),
                    (2, self._("Complex template (with number and HTML from the table of values)")),
                ]},
                {"name": "visual_round", "value": param.get("visual_round"), "label": self._("Round value to this number of digits after decimal point (empty value means 'don't round')"), "condition": "[visual_mode] == 0 || [visual_mode] == 2"},
                {"name": "visual_plus", "type": "checkbox", "checked": param.get("visual_plus"), "label": self._("Show '+' sign before positive values"), "condition": "[visual_mode] == 0 || [visual_mode] == 2"},
                {"name": "visual_template", "value": param.get("visual_template"), "label": self._("Value template ({val} &mdash; number, {text} &mdash; text from the table)"), "condition": "[visual_mode]==2"},
                {"name": "visual_table", "value": "\n".join([u"%s: %s" % (ent[0], ent[1]) for ent in param.get("visual_table", [])]), "label": self._("Table of values (HTML allowed). Syntax:<br />1: recruit<br />2: sergeant<br />3: lieutenant<br />4: major"), "condition": "[visual_mode]>0", "type": "textarea", "remove_label_separator": True},
                {"type": "header", "html": self._("Library settings")},
                {"name": "library_visible", "label": self._("Publish parameter description in the library"), "checked": param.get("library_visible"), "type": "checkbox"},
                {"name": "library_auto", "label": self._("Generate library description automatically"), "checked": False if param.get("library_uri") else True, "condition": "[library_visible]", "type": "checkbox"},
                {"name": "library_uri", "label": self._("URI with the description of the parameter"), "value": param.get("library_uri"), "condition": "[library_visible] && ![library_auto]"},
                {"name": "library_table", "label": self._("Conversion table is published in the library"), "checked": param.get("library_table"), "type": "checkbox", "condition": "[type]==2 && [library_visible]"},
                {"type": "header", "html": self._("API settings (API is not implemented yet)")},
                {"name": "api_values", "label": self._("Parameter values are visible in the API"), "checked": param.get("api_values"), "type": "checkbox"},
                {"name": "api_expression", "label": self._("Parameter expression is visible in the API"), "checked": param.get("api_expression"), "type": "checkbox", "condition": "[type]>0"},
                {"name": "api_table", "label": self._("Parameter tables are visible in the API"), "checked": param.get("api_table"), "type": "checkbox", "condition": "[type]==2 || [visual_mode]>0"},
            ])
            self.call("admin-%s.params-form-render" % self.kind, param, fields)
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
                '<hook:admin.link href="%s/params/copy/%s" title="%s" />' % (self.kind, param["code"], self._("copy")),
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
                        self._("Copying"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def admin_view_params(self, obj, params, may_edit):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param["grp"] != "" and param["grp"] != grp:
                params.append(['<strong>%s</strong>' % htmlescape(param["grp"]), None, None, None])
                grp = param["grp"]
            rparam = [
                param["code"],
                htmlescape(param["name"]),
                htmlescape(obj.param(param["code"])) + ((u' <img src="/st/icons/dyn-script.gif" alt="" title="%s" />' % self._("Parameter changing with time")) if obj.param_dyn(param["code"]) else ''),
                htmlescape(obj.param_html(param["code"])),
            ]
            if may_edit and param["type"] == 0:
                rparam.append('<hook:admin.link href="%s/paramedit/%s/%s" title="%s" />' % (self.kind, obj.uuid, param["code"], self._("change")))
            params.append(rparam)

    def headmenu_paramedit(self, args):
        m = re_paramedit_args.match(args)
        if m:
            uuid = m.group(1)
            param = self.call("%s.param" % self.kind, m.group(2))
            if param:
                return [htmlescape(param["name"]), self.call("%s.params-url" % self.kind, uuid)]

    def admin_paramedit(self):
        req = self.req()
        m = re_paramedit_args.match(req.args)
        if not m:
            self.call("web.not_found")
        uuid = m.group(1)
        param = self.call("%s.param" % self.kind, m.group(2))
        if not param or param["type"] != 0:
            self.call("web.not_found")
        db_obj = self.call("%s.params-obj" % self.kind, uuid)
        if not db_obj:
            self.call("web.not_found")
        require_security_comment = self.call("%s.require-security-comment" % self.kind)
        if req.ok():
            with self.lock(["%s.params.%s" % (self.kind, uuid)]):
                try:
                    db_obj.load()
                except ObjectNotFoundException:
                    pass
                old_value = db_obj.get(param["code"], param.get("default", 0))
                errors = {}
                if req.param("dynamic"):
                    value = self.call("script.admin-expression", "dynamic_value", errors, keep_globs={"t": True})
                    till = None if req.param("infinite") else floatz(req.param("till"))
                    value = [till, value]
                else:
                    value = req.param("static_value").strip()
                    if not value:
                        errors["static_value"] = self._("This field is mandatory")
                    elif not valid_number(value):
                        errors["static_value"] = self._("This doesn't look like a number")
                    else:
                        value = nn(value)
                        if abs(value) > 1000000000:
                            errors["static_value"] = self._("Absolute values greater than 1 billion are not supported")
                if require_security_comment:
                    comment = req.param("comment").strip()
                    if not comment:
                        errors["comment"] = self._("This field is mandatory")
                else:
                    comment = None
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                if old_value != value:
                    db_obj.set(param["code"], value)
                    self.call("%s.param-changed" % self.kind, uuid=uuid, param=param, value=value)
                    self.call("%s.param-admin-changed" % self.kind, uuid=uuid, param=param, old_value=old_value, new_value=value, comment=comment)
                    db_obj.store()
                self.call("%s.params-redirect" % self.kind, uuid)
                self.call("admin.response", self._("Parameter value stored"), {})
        old_value = db_obj.get(param["code"], param.get("default", 0))
        fields = [
            {"name": "dynamic", "type": "checkbox", "checked": type(old_value) is list, "label": self._("Parameter changing with time")},
            {"name": "static_value", "value": "" if type(old_value) is list else old_value, "label": self._("Static value"), "condition": "![dynamic]"},
            {"name": "infinite", "type": "checkbox", "label": self._("Infinite duration"), "checked": (not old_value[0]) if type(old_value) is list else True, "condition": "[dynamic]"},
            {"name": "till", "label": self._("Stop at this time"), "value": old_value[0] if type(old_value) is list and old_value[0] else self.time(), "condition": "[dynamic] && ![infinite]"},
            {"name": "dynamic_value", "value": self.call("script.unparse-expression", old_value[1]) if type(old_value) is list else "", "label": self._("Dynamic value expression") + self.call("script.help-icon-expressions", "dyn"), "condition": "[dynamic]"},
        ]
        if require_security_comment:
            fields.append({"name": "comment", "label": '%s%s' % (self._("Reason why do you change this parameter. Provide the real reason. It will be inspected by the MMO Constructor Security Dept"), self.call("security.icon") or "")})
        self.call("admin.form", fields=fields)

class Params(ConstructorModule):
    def register(self):
        self.rdep(["mg.constructor.params.Fake"])
        self.rhook("%s.params" % self.kind, self.params)
        self.rhook("%s.param" % self.kind, self.param)
        self.rhook("%s.param-value" % self.kind, self.value)
        self.rhook("%s.param-value-rec" % self.kind, self.value_rec)
        self.rhook("%s.set-param" % self.kind, self.set_param)
        self.rhook("%s.param-html" % self.kind, self.html)
        self.rhook("%s.params-public" % self.kind, self.params_public)
        self.rhook("%s.params-owner-important" % self.kind, self.params_owner_important)
        self.rhook("%s.params-owner-all" % self.kind, self.params_owner_all)
        self.rhook("%s.library-icon" % self.kind, self.library_icon)
        self.rhook("%s.visibility-condition" % self.kind, self.visibility_condition)

    def params(self):
        return self.conf("%s.params" % self.kind, [])

    def param(self, param_code):
        for p in self.call("%s.params" % self.kind):
            if p["code"] == param_code:
                return p
        return None

    def set_param(self, obj, param_code, value):
        param = self.param(param_code)
        if not param or param["type"] != 0:
            raise AttributeError(param_code)
        old_value = obj.db_params.get(param["code"], param.get("default", 0))
        obj.db_params.set(param["code"], value)
        obj._param_cache = {}
        return old_value

    def value(self, obj, param_code, handle_exceptions=True):
        param = self.param(param_code)
        if not param:
            if handle_exceptions:
                return None
            else:
                raise AttributeError(param_code)
        return self.call("%s.param-value-rec" % self.kind, obj, param, handle_exceptions)

    def _evaluate(self, obj, param):
        value = self.call("script.evaluate-expression", param["expression"], obj.script_params(), description=self._("Evaluation of '{cls}.{uuid}.{param}'").format(cls=self.kind, param='p_%s' % param["code"], uuid=obj.uuid))
        if param["type"] == 2:
            res = None
            for ent in param["values_table"]:
                if ent[0] > value:
                    break
                res = ent[1]
            value = res
        return value

    def value_rec(self, obj, param, handle_exceptions=True):
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
        elif param["type"] == 1 or param["type"] == 2:
            if handle_exceptions:
                try:
                    value = self._evaluate(obj, param)
                except Exception as e:
                    self.exception(e, silent=True)
                    return None
            else:
                value = self._evaluate(obj, param)
        # storing in the cache
        cache[param["code"]] = value
        return value

    def html(self, param, value):
        visual_mode = param.get("visual_mode")
        if visual_mode == 0:
            visual_round = param.get("visual_round")
            if visual_round is not None:
                html = "%.{prec}f".format(prec=visual_round) % floatz(value)
            else:
                html = htmlescape(unicode(value))
            if param.get("visual_plus") and value > 0:
                html = u"+%s" % html
            return html
        elif visual_mode == 1 or visual_mode == 2:
            text = None
            for ent in param["visual_table"]:
                if ent[0] == value:
                    text = ent[1]
                    break
            if param.get("visual_plus") and value > 0:
                value = u"+%s" % value
            if text is None:
                return value
            if visual_mode == 1:
                return text
            else:
                return param["visual_template"].format(val=value, text=text)
        else:
            return htmlescape(unicode(value))

    def params_public(self, obj, params, **kwargs):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible") and param.get("public") and self.visibility_condition(param, obj):
                value = self.call("%s.param-value-rec" % self.kind, obj, param)
                value = self.call("script.evaluate-dynamic", value)
                if value or param.get("zero_visible"):
                    if param["grp"] != "" and param["grp"] != grp:
                        params.append({"header": htmlescape(param["grp"])})
                        grp = param["grp"]
                    value_html = self.call("%s.param-html" % self.kind, param, value)
                    params.append({
                        "param": param,
                        "value_raw": value,
                        "name": '<span class="%s-info-%s-name">%s</span>' % (self.kind, param["code"], htmlescape(param["name"])),
                        "value": '<span class="%s-info-%s-value">%s</span>' % (self.kind, param["code"], value_html),
                        "library_icon": self.library_icon(param),
                    })

    def params_owner_important(self, obj, params, **kwargs):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible") and param.get("important") and self.visibility_condition(param, obj):
                value = self.call("%s.param-value-rec" % self.kind, obj, param)
                value = self.call("script.evaluate-dynamic", value)
                if value or param.get("zero_visible"):
                    if param["grp"] != "" and param["grp"] != grp:
                        params.append({"header": htmlescape(param["grp"])})
                        grp = param["grp"]
                    value_html = self.call("%s.param-html" % self.kind, param, value)
                    params.append({
                        "param": param,
                        "value_raw": value,
                        "name": '<span class="%s-page-%s-name">%s</span>' % (self.kind, param["code"], htmlescape(param["name"])),
                        "value": '<span class="%s-page-%s-value">%s</span>' % (self.kind, param["code"], value_html),
                        "library_icon": self.library_icon(param),
                    })

    def params_owner_all(self, obj, params, **kwargs):
        grp = None
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible") and self.visibility_condition(param, obj):
                value = self.call("%s.param-value-rec" % self.kind, obj, param)
                value = self.call("script.evaluate-dynamic", value)
                if value or param.get("zero_visible"):
                    if param["grp"] != "" and param["grp"] != grp:
                        params.append({"header": htmlescape(param["grp"])})
                        grp = param["grp"]
                    value_html = self.call("%s.param-html" % self.kind, param, value)
                    params.append({
                        "param": param,
                        "value_raw": value,
                        "name": '<span class="%s-page-%s-name">%s</span>' % (self.kind, param["code"], htmlescape(param["name"])),
                        "value": '<span class="%s-page-%s-value">%s</span>' % (self.kind, param["code"], value_html),
                        "library_icon": self.library_icon(param),
                    })

    def notimportant_params_exist(self):
        for param in self.call("%s.params" % self.kind):
            if param.get("owner_visible") and not param.get("important"):
                return True
        return False

    def visibility_condition(self, param, obj):
        if not param.get("condition"):
            return True
        try:
            return self.call("script.evaluate-expression", param["condition"], obj.script_params(), description=self._("Evaluation of '{cls}.{uuid}.{param}' visibility condition").format(cls=self.kind, param=param["code"], uuid=obj.uuid))
        except Exception as e:
            self.exception(e)
            return False

    def library_icon(self, param):
        if not param.get("library_visible"):
            return None
        uri = param.get("library_uri") or self.call("%s.param-library" % self.kind, param)
        if not uri:
            return None
        return self.call("library.icon", uri)

class ParamsLibrary(ConstructorModule):
    def register(self):
        self.rdep(["mg.constructor.params.Fake"])
