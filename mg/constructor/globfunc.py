from mg.constructor import *
from concurrence import Tasklet
import re

re_valid_identifier = re.compile(r'^u_[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_del = re.compile(r'del/(.+)')
re_action = re.compile(r'^(u_[a-z_][a-z0-9_]*)/action/([a-z0-9_]+)(?:|/(.+))$', re.IGNORECASE)

class GlobalFunctions(ConstructorModule):
    def register(self):
        self.rhook("globfunc.functions", self.functions)
        self.rhook("ext-globfunc.handler", self.globfunc_handler, priv="logged")
        self.rhook("locations.map-zone-globfunc-render", self.location_map_zone_globfunc_render)

    def child_modules(self):
        return ["mg.constructor.globfunc.GlobalFunctionsAdmin"]

    def functions(self):
        tasklet = Tasklet.current()
        try:
            return tasklet._globfunctions
        except AttributeError:
            pass
        # Cache miss
        funcs = []
        for fn_id in self.conf("globfunc.list", []):
            funcs.append({
                "id": fn_id,
            })
        for func in funcs:
            conf = self.conf("globfunc.%s" % func["id"])
            if conf:
                for k, v in conf.iteritems():
                    func[k] = v
        funcs.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x["title"], y["title"]))
        # Cache store
        tasklet._globfunctions = funcs
        return funcs

    def globfunc_handler(self):
        req = self.req()
        char = self.character(req.user())
        funcs = self.functions()
        # Parsing request
        m = re_action.match(req.args)
        if m:
            fn_id, action, args = m.group(1, 2, 3)
        else:
            m = re_valid_identifier.match(req.args)
            if m:
                fn_id = req.args
                action = None
                args = None
            else:
                char.error(self._("Invalid global interface request"))
                self.call("web.redirect", "/location")
        # Looking for the function requested
        for func in funcs:
            if func["id"] == fn_id:
                globs = {"char": char}
                description = self._("Availability of global interface '%s'") % fn_id
                if not self.call("script.evaluate-expression", func.get("available"), globs=globs, description=description):
                    char.error(self._("This function is not available at the moment"))
                    self.call("web.redirect", "/location")
                # Function is available
                if action is None:
                    action = func["default_action"]
                    args = ""
                req.hook = fn_id
                req.args = args
                vars = {}
                self.call("interface-%s.action-%s" % (func["tp"], action), "glob-%s" % fn_id, "/globfunc/%s/action" % fn_id, func, args, vars, check_priv=True)
                self.call("main-frame.info", self._("Implementation of action {type}.{action} ({id}) is missing").format(type=func["tp"], action=htmlescape(action), id=func["id"]), vars)
        self.call("game.error", self._("Global interface function {func} is not defined").format(func=htmlescape(fn_id)))

    def location_map_zone_globfunc_render(self, zone, rzone):
        rzone["globfunc"] = jsencode(zone.get("globfunc"))

class GlobalFunctionsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-gameinterface.index", self.menu_gameinterface_index)
        self.rhook("ext-admin-globfunc.editor", self.admin_globfunc_editor, priv="interface.globfunc")
        self.rhook("headmenu-admin-globfunc.editor", self.headmenu_globfunc_editor)
        self.rhook("admin-locations.map-zone-actions", self.location_map_zone_actions)
        self.rhook("admin-locations.map-zone-action-globfunc", self.location_map_zone_action_globfunc)
        self.rhook("admin-locations.map-zone-globfunc-render", self.location_map_zone_globfunc_render)
        self.rhook("admin-locations.render-imagemap-editor", self.render_imagemap_editor)

    def permissions_list(self, perms):
        perms.append({"id": "interface.globfunc", "name": self._("Global interfaces")})

    def menu_gameinterface_index(self, menu):
        req = self.req()
        if req.has_access("interface.globfunc"):
            menu.append({"id": "globfunc/editor", "text": self._("Global interfaces"), "leaf": True, "order": 60})

    def headmenu_globfunc_editor(self, args):
        cmd = args
        if cmd == "new":
            return [self._("New interface"), "globfunc/editor"]
        elif cmd:
            m = re_action.match(cmd)
            if m:
                fn_id, action, args = m.group(1, 2, 3)
                for func in self.call("globfunc.functions"):
                    if func["id"] == fn_id:
                        actions = []
                        self.call("admin-interface-%s.actions" % func["tp"], "glob-%s" % func["id"], func, actions)
                        for act in actions:
                            if action == act["id"]:
                                headmenu = self.call("admin-interface-%s.headmenu-%s" % (func["tp"], action), func, args)
                                if headmenu is None:
                                    return [self._("globfunc///{action_name} of {func_title}").format(action_name=action, func_title=htmlescape(func["title"])), "globfunc/editor"]
                                elif type(headmenu) == list:
                                    return [headmenu[0], "globfunc/editor/%s/action/%s" % (fn_id, headmenu[1])]
                                else:
                                    return [headmenu, "globfunc/editor"]
            else:
                for func in self.call("globfunc.functions"):
                    if func["id"] == cmd:
                        return [htmlescape(func["title"]), "globfunc/editor"]
        return [self._("Global interfaces")]

    def admin_globfunc_editor(self):
        req = self.req()
        # Loading global functions
        funcs = self.call("globfunc.functions")
        # Processing command
        cmd = req.args
        if cmd:
            m = re_del.match(cmd)
            if m:
                fn_id = m.group(1)
                lst = self.conf("globfunc.list", [])
                lst = [ent for ent in lst if ent != fn_id]
                config = self.app().config_updater()
                config.set("globfunc.list", lst)
                config.store()
                self.call("admin.redirect", "globfunc/editor")
            m = re_action.match(cmd)
            if m:
                fn_id, action, args = m.group(1, 2, 3)
                for fn in funcs:
                    if fn["id"] == fn_id:
                        return self.call("admin-interface-%s.action-%s" % (fn["tp"], action), "glob-%s" % fn_id, "globfunc/editor/%s/action" % fn_id, fn, args, check_priv=True)
                self.call("admin.redirect", "globfunc/editor")
            if cmd == "new":
                func = {
                    "id": "u_",
                    "custom": True,
                }
                max_order = None
                for fn in funcs:
                    if max_order is None or fn.get("order", 0) > max_order:
                        max_order = fn.get("order", 0)
                func["order"] = 0.0 if max_order is None else max_order + 10.0
            else:
                fn_id = cmd
                for fn in funcs:
                    if fn["id"] == fn_id:
                        func = fn.copy()
                        break
            # Available interfaces
            if func.get("custom"):
                function_types = []
                self.call("interfaces.list", function_types)
                valid_function_types = set([code for code, desc in function_types])
            # Processing POST
            if req.ok():
                errors = {}
                # id
                if cmd == "new":
                    ident = req.param("ident").strip()
                    if not ident:
                        errors["ident"] = self._("This field is mandatory")
                    elif not re_valid_identifier.match(ident):
                        errors["ident"] = self._("Global interface identifier must start with 'u_' and contain latin letters, digits and underscores only")
                    elif len(ident) > 32:
                        errors["ident"] = self._("Maximal identifier length is %d") % 32
                    else:
                        fn_id = ident
                        func["id"] = fn_id
                # title
                title = req.param("title").strip()
                if not title:
                    errors["title"] = self._("This field is mandatory")
                else:
                    func["title"] = title
                # order
                func["order"] = floatz(req.param("order"))
                # available
                char = self.character(req.user())
                func["available"] = self.call("script.admin-expression", "available", errors, globs={"char": char})
                # tp
                if func.get("custom"):
                    tp = req.param("v_tp")
                    if tp not in valid_function_types:
                        errors["v_tp"] = self._("This field is mandatory")
                    else:
                        func["tp"] = tp
                        self.call("admin-interface-%s.validate" % tp, func, errors)
                # handling errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                config = self.app().config_updater()
                if func.get("custom"):
                    self.call("admin-interface-%s.store" % tp, func, errors)
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                if cmd == "new":
                    lst = self.conf("globfunc.list", [])
                    lst.append(fn_id)
                    config.set("globfunc.list", lst)
                config.set("globfunc.%s" % fn_id, func)
                config.store()
                self.call("admin.redirect", "globfunc/editor")
            fields = []
            if cmd == "new":
                fields.append({"name": "ident", "label": self._("Identifier"), "value": func.get("id")})
            fields.append({"name": "order", "label": self._("Sorting order"), "value": func.get("order"), "inline": True})
            fields.append({"name": "title", "label": self._("Title"), "value": func.get("title")})
            fields.append({"name": "available", "label": self._("Availability of the function for the character") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("available", 1))})
            if func.get("custom"):
                fields.append({"type": "header", "html": self._("Global interface settings")})
                function_types.insert(0, ("", ""))
                fields.append({"name": "tp", "label": self._("Function"), "type": "combo", "values": function_types, "value": func.get("tp")})
                self.call("admin-interfaces.form", fields, func)
            self.call("admin.form", fields=fields)
        rows = []
        for func in funcs:
            actions = []
            if func.get("custom"):
                self.call("admin-interface-%s.actions" % func["tp"], "glob-%s" % func["id"], func, actions)
                for act in actions:
                    if "hook" not in act:
                        act["hook"] = "globfunc/editor/%s/action/%s" % (func["id"], act["id"])
            actions.insert(0, {
                "hook": "globfunc/editor/%s" % func["id"],
                "text": self._("edit"),
            })
            actions = [u'<hook:admin.link href="%s" title="%s" />' % (act["hook"], act["text"]) for act in actions]
            rows.append([
                func["id"],
                htmlescape(func["title"]) + (u" (%s)" % self._("default") if func.get("default") else u""),
                func.get("order", 0),
                '<br />'.join(actions),
                u'<hook:admin.link href="globfunc/editor/del/%s" title="%s" confirm="%s" />' % (func["id"], self._("delete"), self._("Are you sure want to delete this interface?")) if func.get("custom") else None,
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "globfunc/editor/new", "text": self._("New interface"), "lst": True},
                    ],
                    "header": [
                        self._("Code"),
                        self._("Title"),
                        self._("Order"),
                        self._("Actions"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def location_map_zone_actions(self, location, actions):
        actions.append(("globfunc", jsencode(self._("Open global interface"))))

    def location_map_zone_action_globfunc(self, zone_id, zone, errors):
        req = self.req()
        key = "v_globfunc-%d" % zone_id
        globfunc = req.param(key).strip()
        if not globfunc:
            errors[key] = self._("Global interface not specified")
        else:
            zone["globfunc"] = globfunc
        return True

    def location_map_zone_globfunc_render(self, zone, rzone):
        rzone["globfunc"] = jsencode(zone.get("globfunc"))

    def render_imagemap_editor(self, location, vars):
        lst = []
        funcs = self.call("globfunc.functions")
        for func in funcs:
            actions = []
            lst.append({"id": func["id"], "title": jsencode(func["title"])})
        vars["globfunc"] = lst
