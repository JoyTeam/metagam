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
from mg.mmorpg.locations_classes import *
import re

re_valid_identifier = re.compile(r'^u_[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_specfunc_arg = re.compile(r'^([0-9a-f]+)(?:|/(.+))$')
re_del = re.compile(r'del/(.+)')
re_action = re.compile(r'^(u_[a-z_][a-z0-9_]*)/action/([a-z0-9_]+)(?:|/(.+))$', re.IGNORECASE)

class LocationFunctions(ConstructorModule):
    def register(self):
        self.rhook("ext-location.index", self.ext_location_index, priv="logged")
        self.rhook("locfunctions.menu", self.menu)
        self.rhook("locfunctions.functions", self.functions)
        self.rhook("ext-location.handler", self.ext_location_handler, priv="logged", priority=-10)
        self.rhook("locations.map-zone-specfunc-render", self.location_map_zone_specfunc_render)

    def child_modules(self):
        return ["mg.mmorpg.locfunctions.LocationFunctionsAdmin"]

    def functions(self, loc, char=None):
        # Cache read
        if char:
            try:
                return char._specfunctions[loc.uuid]
            except AttributeError:
                pass
            except KeyError:
                pass
        else:
            try:
                return loc._specfunctions
            except AttributeError:
                pass
        # Cache miss
        funcs = []
        for fn_id in self.conf("locfunc-%s.list" % loc.uuid, []):
            funcs.append({
                "id": fn_id,
            })
        self.call("locfunctions.list", loc, funcs)
        nonvolatileKeys = set(["onclick"])
        for func in funcs:
            conf = self.conf("locfunc-%s.%s" % (loc.uuid, func["id"]))
            if conf:
                for k, v in conf.iteritems():
                    if k not in nonvolatileKeys:
                        func[k] = v
        if char:
            globs = {"char": char}
            description = self._("Availability of location special function '%s'")
            funcs = [func for func in funcs if self.call("script.evaluate-expression", func.get("available"), globs=globs, description=description % func["id"])]
        funcs.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x["title"], y["title"]))
        # Cache store
        if char:
            try:
                char._specfunctions[loc.uuid] = funcs
            except AttributeError:
                char._specfunctions = {loc.uuid: funcs}
        else:
            loc._specfunctions = funcs
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
        funcs = self.functions(location, char)
        if not funcs:
            self.call("game.internal-error", self._("No functions in the location"))
        # Selecting default function
        def func_execute(func):
            # /location/[func]/action/[default_action]
            action = func.get("default_action")
            if action:
                req.hook = func["id"]
                req.args = "action/%s" % action
                self.call("ext-location.%s" % req.hook)
                req.args = "%s/%s" % (req.hook, req.args)
                req.hook = "handler"
                self.call("ext-location.handler")
            # /location/[func_id]
            req.hook = func["id"]
            self.call("ext-location.%s" % req.hook)
            req.hook = "handler"
            req.args = func["id"]
            self.call("ext-location.handler")
        for func in funcs:
            if func.get("default"):
                func_execute(func)
        # If no default function show the first
        for func in funcs:
            if not func.get("onclick"):
                func_execute(func)

    def menu(self, char, vars, selected=None):
        if selected is None:
            req = self.req()
            selected = req.hook
        funcs = self.functions(char.location, char)
        trivial = True
        menu_left = []
        for func in funcs:
            if not func.get("menu_visible", 1):
                continue
            rfunc = {
                "html": func["title"],
            }
            if selected == func["id"]:
                rfunc["selected"] = True
            else:
                trivial = False
                if func.get("onclick"):
                    rfunc["onclick"] = "%s; return false" % func["onclick"]
                    rfunc["href"] = "javascript:void(0)"
                elif func.get("default_action"):
                    rfunc["href"] = "/location/%s/action/%s" % (func["id"], func.get("default_action"))
                else:
                    rfunc["href"] = "/location/%s" % func["id"]
            menu_left.append(rfunc)
        if not trivial:
            menu_left[-1]["lst"] = True
            vars["menu_left"] = menu_left

    def ext_location_handler(self):
        req = self.req()
        char = self.character(req.user())
        location = char.location
        if location is None:
            self.call("web.redirect", "/location")
        funcs = self.functions(location)
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
                char.error(self._("Invalid special function request"))
                self.call("web.redirect", "/location")
        # Looking for the function
        for func in funcs:
            if func["id"] == fn_id:
                globs = {"char": char}
                description = self._("Availability of location special function '%s'") % fn_id
                if not self.call("script.evaluate-expression", func.get("available"), globs=globs, description=description):
                    char.error(self._("This function is not available at the moment"))
                    self.call("web.redirect", "/location")
                req.hook = fn_id
                req.args = args
                if action is None:
                    action = func.get("default_action", "default")
                vars = {}
                self.call("locfunctions.menu", char, vars)
                self.call("interface-%s.action-%s" % (func["tp"], action), "loc-%s-%s" % (location.uuid, fn_id), "/location/%s/action" % fn_id, func, args, vars, check_priv=True)
                self.call("main-frame.info", self._("Implementation of action {type}.{action} ({id}) is missing").format(type=func["tp"], action=htmlescape(action), id=func["id"]), vars)
        self.call("game.error", self._("Function {func} is not defined in location {loc}").format(func=htmlescape(fn_id), loc=htmlescape(location.name)))

    def location_map_zone_specfunc_render(self, zone, rzone):
        rzone["specfunc"] = jsencode(zone.get("specfunc"))

class LocationFunctionsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-locations.specfunc", self.admin_specfunc, priv="locations.specfunc")
        self.rhook("headmenu-admin-locations.specfunc", self.headmenu_specfunc)
        self.rhook("admin-locations.links", self.links)
        self.rhook("admin-locations.map-zone-actions", self.location_map_zone_actions, priority=18)
        self.rhook("admin-locations.map-zone-action-specfunc", self.location_map_zone_action_specfunc)
        self.rhook("admin-locations.map-zone-specfunc-render", self.location_map_zone_specfunc_render)
        self.rhook("admin-locations.render-imagemap-editor", self.render_imagemap_editor)

    def links(self, location, links):
        req = self.req()
        if req.has_access("locations.specfunc"):
            links.append({"hook": "locations/specfunc/%s" % location.uuid, "text": self._("Special functions"), "order": 20})
        
    def permissions_list(self, perms):
        perms.append({"id": "locations.specfunc", "name": self._("Locations special functions")})

    def headmenu_specfunc(self, args):
        m = re_specfunc_arg.match(args)
        if m:
            loc_id, cmd = m.group(1, 2)
            if cmd == "new":
                return [self._("New function"), "locations/specfunc/%s" % loc_id]
            elif cmd:
                m = re_action.match(cmd)
                if m:
                    fn_id, action, args = m.group(1, 2, 3)
                    loc = self.location(loc_id)
                    for func in self.call("locfunctions.functions", loc):
                        if func["id"] == fn_id:
                            actions = []
                            self.call("admin-interface-%s.actions" % func["tp"], "loc-%s-%s" % (loc_id, func["id"]), func, actions)
                            for act in actions:
                                if action == act["id"]:
                                    headmenu = self.call("admin-interface-%s.headmenu-%s" % (func["tp"], action), func, args)
                                    if headmenu is None:
                                        return [self._("specfunc///{action_name} of {func_title}").format(action_name=action, func_title=htmlescape(func["title"])), "locations/specfunc/%s" % loc_id]
                                    elif type(headmenu) == list:
                                        return [headmenu[0], "locations/specfunc/%s/%s/action/%s" % (loc_id, fn_id, headmenu[1])]
                                    else:
                                        return [headmenu, "locations/specfunc/%s" % loc_id]
                else:
                    loc = self.location(loc_id)
                    for func in self.call("locfunctions.functions", loc):
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
        # Advice
        self.call("admin.advice", {"title": self._("Special functions documentation"), "content": self._('You can find detailed information on the location special functions system in the <a href="//www.%s/doc/locfunc" target="_blank">special functions page</a> in the reference manual.') % self.main_host, "order": 30})
        # Loading special functions
        funcs = self.call("locfunctions.functions", loc)
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
            m = re_action.match(cmd)
            if m:
                fn_id, action, args = m.group(1, 2, 3)
                for fn in funcs:
                    if fn["id"] == fn_id:
                        return self.call("admin-interface-%s.action-%s" % (fn["tp"], action), "loc-%s-%s" % (loc.uuid, fn_id), "locations/specfunc/%s/%s/action" % (loc.uuid, fn_id), fn, args, check_priv=True)
                self.call("admin.redirect", "locations/specfunc/%s" % loc.uuid)
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
            # Available special function types
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
                        errors["ident"] = self._("Special function identifier must start with 'u_' and contain latin letters, digits and underscores only")
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
                # menu_visible
                func["menu_visible"] = 1 if req.param("menu_visible") else 0
                # order
                func["order"] = floatz(req.param("order"))
                # available
                char = self.character(req.user())
                func["available"] = self.call("script.admin-expression", "available", errors, globs={"char": char})
                # default
                func["default"] = True if req.param("default") else False
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
            fields.append({"name": "order", "label": self._("Sorting order"), "value": func.get("order"), "inline": True})
            if not func.get("onclick"):
                fields.append({"name": "default", "label": self._("Default special function"), "type": "checkbox", "checked": func.get("default")})
            fields.append({"name": "title", "label": self._("Function title"), "value": func.get("title")})
            fields.append({"name": "menu_visible", "label": self._("Visible in the menu"), "type": "checkbox", "checked": func.get("menu_visible", 1)})
            fields.append({"name": "available", "label": self._("Availability of the function for the character") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("available", 1))})
            if func.get("custom"):
                fields.append({"type": "header", "html": self._("Special function settings")})
                function_types.insert(0, ("", ""))
                fields.append({"name": "tp", "label": self._("Function"), "type": "combo", "values": function_types, "value": func.get("tp")})
                self.call("admin-interfaces.form", fields, func)
            self.call("admin.form", fields=fields)
        rows = []
        for func in funcs:
            actions = []
            if func.get("custom"):
                self.call("admin-interface-%s.actions" % func["tp"], "loc-%s-%s" % (loc.uuid, func["id"]), func, actions)
                for act in actions:
                    if "hook" not in act:
                        act["hook"] = "locations/specfunc/%s/%s/action/%s" % (loc.uuid, func["id"], act["id"])
            actions.insert(0, {
                "hook": "locations/specfunc/%s/%s" % (loc.uuid, func["id"]),
                "text": self._("edit"),
            })
            actions = [u'<hook:admin.link href="%s" title="%s" />' % (act["hook"], act["text"]) for act in actions]
            rows.append([
                func["id"],
                htmlescape(func["title"]) + (u" (%s)" % self._("default") if func.get("default") else u""),
                func.get("order", 0),
                '<br />'.join(actions),
                u'<hook:admin.link href="locations/specfunc/%s/del/%s" title="%s" confirm="%s" />' % (loc.uuid, func["id"], self._("delete"), self._("Are you sure want to delete this special function?")) if func.get("custom") else None,
            ])
        links = []
        self.call("admin-locations.render-links", loc, links)
        vars = {
            "tables": [
                {
                    "links": links,
                },
                {
                    "links": [
                        {"hook": "locations/specfunc/%s/new" % loc.uuid, "text": self._("New function"), "lst": True},
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
        actions.append(("specfunc", jsencode(self._("Open special function"))))

    def location_map_zone_action_specfunc(self, zone_id, zone, errors):
        req = self.req()
        key = "v_specfunc-%d" % zone_id
        specfunc = req.param(key).strip()
        if not specfunc:
            errors[key] = self._("Special function not specified")
        else:
            zone["specfunc"] = specfunc
        return True

    def location_map_zone_specfunc_render(self, zone, rzone):
        rzone["specfunc"] = jsencode(zone.get("specfunc"))

    def render_imagemap_editor(self, location, vars):
        lst = []
        funcs = self.call("locfunctions.functions", location)
        for func in funcs:
            actions = []
            lst.append({"id": func["id"], "title": jsencode(func["title"])})
        vars["specfunc"] = lst
