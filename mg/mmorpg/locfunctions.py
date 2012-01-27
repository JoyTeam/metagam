from mg.constructor import *
from mg.mmorpg.locations_classes import *
import re

re_valid_identifier = re.compile(r'^u_[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_specfunc_arg = re.compile(r'^([0-9a-f]+)(?:|/(.+))$')
re_del = re.compile(r'del/(.+)')

class LocationFunctions(ConstructorModule):
    def register(self):
        self.rhook("ext-location.index", self.ext_location_index, priv="logged")
        self.rhook("locfunctions.menu", self.menu)
        self.rhook("locfunctions.functions", self.functions)
        self.rhook("ext-location.handler", self.ext_location_handler, priv="logged", priority=-10)

    def child_modules(self):
        return ["mg.mmorpg.locfunctions.LocationFunctionsAdmin"]

    def functions(self, char, loc):
        # Cache read
        if char:
            try:
                cache = char._locfunctions
            except AttributeError:
                cache = {}
                char._locfunctions = cache
            try:
                return cache[loc.uuid]
            except KeyError:
                pass
        # Cache miss
        funcs = []
        for fn_id in self.conf("locfunc-%s.list" % loc.uuid, []):
            funcs.append({
                "id": fn_id
            })
        self.call("locfunctions.list", loc, funcs)
        for func in funcs:
            conf = self.conf("locfunc-%s.%s" % (loc.uuid, func["id"]))
            if conf:
                for k, v in conf.iteritems():
                    func[k] = v
        if char:
            globs = {"char": char}
            description = self._("Availability of location special function '%s'")
            funcs = [func for func in funcs if self.call("script.evaluate-expression", func.get("available"), globs=globs, description=description % func["id"])]
        funcs.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x["title"], y["title"]))
        # Cache store
        if char:
            cache[loc.uuid] = funcs
        return funcs

    def ext_location_index(self):
        req = self.req()
        char = self.character(req.user())
        location = char.location
        if location is None:
            lst = self.objlist(DBLocationList, query_index="all", query_limit=1)
            if len(lst):
                self.call("main-frame.error", '%s <a href="/admin#locations/config" target="_blank">%s</a>' % (self._("Starting location not configured."), self._("Open locations configuration")))
            else:
                self.call("main-frame.error", '%s <a href="/admin#locations/editor" target="_blank">%s</a>' % (self._("No locations defined."), self._("Open locations editor")))
        # Extracting available functions
        funcs = self.functions(char, location)
        if not funcs:
            self.call("game.internal-error", self._("No functions in the location"))
        # Selecting default function
        for func in funcs:
            if func.get("default"):
                req.hook = func["id"]
                self.call("ext-location.%s" % req.hook)
                req.hook = "handler"
                req.args = func["id"]
                self.call("ext-location.handler")
        # If no default function show the first
        req.hook = funcs[0]["id"]
        self.call("ext-location.%s" % req.hook)
        req.hook = "handler"
        req.args = funcs[0]["id"]
        self.call("ext-location.handler")

    def menu(self, char, vars, selected=None):
        if selected is None:
            req = self.req()
            selected = req.hook
        funcs = self.functions(char, char.location)
        if len(funcs) >= 2:
            menu_left = []
            for func in funcs:
                menu_left.append({
                    "html": func["title"],
                    "href": None if selected == func["id"] else "/location/%s" % func["id"],
                    "selected": selected == func["id"],
                })
            menu_left[-1]["lst"] = True
            vars["menu_left"] = menu_left

    def ext_location_handler(self):
        req = self.req()
        char = self.character(req.user())
        location = char.location
        if location is None:
            self.call("web.redirect", "/location")
        funcs = self.functions(char, location)
        for func in funcs:
            if func["id"] == req.args:
                req.hook = func["id"]
                req.args = ""
                vars = {}
                self.call("locfunctions.menu", char, vars)
                self.call("main-frame.info", self._("Function %s implementation") % func["id"], vars)
        self.call("game.error", self._("Function {func} is not implemented in location {loc}").format(func=func["id"], loc=htmlescape(location.name)))

class LocationFunctionsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("admin-locations.render-links", self.render_links)
        self.rhook("ext-admin-locations.specfunc", self.admin_specfunc, priv="locations.specfunc")
        self.rhook("headmenu-admin-locations.specfunc", self.headmenu_specfunc)
        
    def permissions_list(self, perms):
        perms.append({"id": "locations.specfunc", "name": self._("Locations special functions")})

    def render_links(self, loc, fields):
        req = self.req()
        if req.has_access("locations.specfunc"):
            fields.insert(0, {"type": "html", "html": self.call("web.parse_layout", "admin/locations/specfunc.html", {
                "loc": loc.uuid,
                "LocationSpecFuncs": self._("View location special functions"),
            })})

    def headmenu_specfunc(self, args):
        m = re_specfunc_arg.match(args)
        if m:
            loc_id, cmd = m.group(1, 2)
            if cmd == "new":
                return [self._("New function"), "locations/specfunc/%s" % loc_id]
            elif cmd:
                loc = self.location(loc_id)
                for func in self.call("locfunctions.functions", None, loc):
                    if func["id"] == cmd:
                        return [htmlescape(func["title"]), "locations/specfunc/%s" % loc_id]
        return [self._("Special functions"), "locations/editor/%s" % htmlescape(args)]

    def admin_specfunc(self):
        req = self.req()
        m = re_specfunc_arg.match(req.args)
        if not m:
            self.call("web.not_found")
        loc_id, cmd = m.group(1, 2)
        loc = self.location(loc_id)
        if not loc.valid:
            self.call("web.not_found")
        # Loading special functions
        funcs = self.call("locfunctions.functions", None, loc)
        default = funcs[0]["id"] if funcs else None
        for func in funcs:
            if func.get("default"):
                default = func["id"]
                break
        # Processing command
        if cmd:
            m = re_del.match(cmd)
            if m:
                fn_id = m.group(1)
                lst = self.conf("locfunc-%s.list" % loc.uuid, [])
                lst = [ent for ent in lst if ent != fn_id]
                config = self.app().config_updater()
                config.set("locfunc-%s.list" % loc.uuid, lst)
                config.store()
                self.call("admin.redirect", "locations/specfunc/%s" % loc.uuid)
            if cmd == "new":
                func = {
                    "id": "u_",
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
            if req.ok():
                errors = {}
                # id
                if cmd == "new":
                    ident = req.param("ident").strip()
                    if not ident:
                        errors["ident"] = self._("This field is mandatory")
                    elif not re_valid_identifier.match(ident):
                        errors["ident"] = self._("Special function identifier must start with 'u_' and contain latin letters, digits and underscores only")
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
                # default
                func["default"] = True if req.param("default") else False
                # handling errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                config = self.app().config_updater()
                if cmd == "new":
                    lst = self.conf("locfunc-%s.list" % loc.uuid, [])
                    lst.append(fn_id)
                    config.set("locfunc-%s.list" % loc.uuid, lst)
                config.set("locfunc-%s.%s" % (loc.uuid, fn_id), func)
                if func.get("default"):
                    for fn in funcs:
                        if fn["id"] != fn_id and fn.get("default"):
                            del fn["default"]
                            config.set("locfunc-%s.%s" % (loc.uuid, fn["id"]), fn)
                config.store()
                self.call("admin.redirect", "locations/specfunc/%s" % loc.uuid)
            fields = []
            if cmd == "new":
                fields.append({"name": "ident", "label": self._("Identifier"), "value": func.get("id")})
            fields.append({"name": "order", "label": self._("Sorting order"), "value": func.get("order")})
            fields.append({"name": "title", "label": self._("Menu title"), "value": func.get("title")})
            fields.append({"name": "available", "label": self._("Availability of the function for the character") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", fn.get("available"))})
            fields.append({"name": "default", "label": self._("Default special function"), "type": "checkbox", "checked": func.get("default")})
            self.call("admin.form", fields=fields)
        rows = []
        for func in funcs:
            rows.append([
                func["id"],
                htmlescape(func["title"]) + (u" (%s)" % self._("default") if func.get("default") else u""),
                func.get("order", 0),
                u'<hook:admin.link href="locations/specfunc/%s/%s" title="%s" />' % (loc.uuid, func["id"], self._("edit")),
                u'<hook:admin.link href="locations/specfunc/%s/del/%s" title="%s" confirm="%s" />' % (loc.uuid, func["id"], self._("delete"), self._("Are you sure want to delete this special function?")) if func.get("deletable") else None,
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "locations/specfunc/%s/new" % loc.uuid, "text": self._("New function"), "lst": True},
                    ],
                    "header": [
                        self._("Code"),
                        self._("Title"),
                        self._("Order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
