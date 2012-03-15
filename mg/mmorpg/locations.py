from mg import *
from mg.constructor import *
from mg.mmorpg.locations_classes import *
import cStringIO
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageFilter
import re
import hashlib
from uuid import uuid4

re_polygon_param = re.compile(r'^polygon-(\d+)$')
re_multiimage_map = re.compile(r'^([a-f0-9]+)/([a-f0-9]+)$')
re_multiimage_map_del = re.compile(r'^([a-f0-9]+)/del/([a-f0-9]+)$')

class LocationsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-locations.index", self.menu_locations_index)
        self.rhook("ext-admin-locations.editor", self.admin_locations_editor, priv="locations.editor")
        self.rhook("headmenu-admin-locations.editor", self.headmenu_locations_editor)
        self.rhook("ext-admin-locations.config", self.admin_locations_config, priv="locations.config")
        self.rhook("headmenu-admin-locations.config", self.headmenu_locations_config)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("admin-interface.progress-bars", self.progress_bars)
        self.rhook("admin-locations.valid-transitions", self.valid_transitions)
        self.rhook("admin-locations.update-transitions", self.update_transitions)
        self.rhook("advice-admin-locations.index", self.advice_locations)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-locations.teleport", self.admin_locations_teleport, priv="locations.teleport")
        self.rhook("headmenu-admin-locations.teleport", self.headmenu_locations_teleport)
        self.rhook("admin-locations.links", self.links)
        self.rhook("admin-locations.render-links", self.render_links)
        self.rhook("admin-locations.all", self.locations_all)
        self.rhook("admin-gameinterface.design-files", self.design_files)

    def design_files(self, files):
        files.append({"filename": "location-layout.html", "description": self._("Location page layout"), "doc": "/doc/locations"})
        files.append({"filename": "location-arrows.html", "description": self._("Left/right/up/down arrows for the location"), "doc": "/doc/locations"})
        files.append({"filename": "location-static.html", "description": self._("Static image location interface"), "doc": "/doc/locations"})
        files.append({"filename": "location-multistatic.html", "description": self._("Multiple static images location interface"), "doc": "/doc/locations"})
        files.append({"filename": "location-transitions.html", "description": self._("List of transitions in the location"), "doc": "/doc/locations"})

    def links(self, location, links):
        req = self.req()
        if req.has_access("locations.editor"):
            links.append({"hook": "locations/editor/%s" % location.uuid, "text": self._("Location"), "order": -10})

    def render_links(self, location, links):
        self.call("admin-locations.links", location, links)
        if links:
            req = self.req()
            uri = req.group
            if req.hook != "index":
                uri = "%s/%s" % (uri, req.hook)
            if req.args:
                uri = "%s/%s" % (uri, req.args)
            for l in links:
                if "admin-%s" % l.get("hook") == uri:
                    del l["hook"]
            links.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x.get("text"), y.get("text")))
            links[-1]["lst"] = True

    def headmenu_locations_teleport(self, args):
        return [self._("Service teleport"), "auth/user-dashboard/%s?active_tab=location" % htmlescape(args)]

    def admin_locations_teleport(self):
        req = self.req()
        character = self.character(req.args)
        if not character.valid:
            self.call("web.not_found")
        # list of locations
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        locations = [(loc.uuid, loc.get("name")) for loc in lst]
        valid_locations = set([loc.uuid for loc in lst])
        # processing request
        if req.ok():
            errors = {}
            # loc
            loc = req.param("v_loc")
            if not loc:
                errors["v_loc"] = self._("This field is mandatory")
            elif not loc in valid_locations:
                errors["v_loc"] = self._("Select a valid location")
            # errors
            if errors:
                self.call("web.response_json_html", {"success": False, "errors": errors})
            # teleporting
            self.call("teleport.character", character, self.location(loc))
            character.main_open("/location")
            self.call("admin.redirect", "auth/user-dashboard/%s?active_tab=location" % character.uuid)
        # rendering form
        fields = [
            {"name": "loc", "label": self._("Target location"), "type": "combo", "values": locations, "value": character.location.uuid if character.location else None},
        ]
        self.call("admin.form", fields=fields)

    def advice_locations(self, hook, args, advice):
        advice.append({"title": self._("Locations documentation"), "content": self._('You can find detailed information on the location system in the <a href="//www.%s/doc/locations" target="_blank">locations page</a> in the reference manual.') % self.app().inst.config["main_host"]})

    def objclasses_list(self, objclasses):
        objclasses["CharacterLocation"] = (DBCharacterLocation, DBCharacterLocationList)
        objclasses["Location"] = (DBLocation, DBLocationList)
        objclasses["LocParams"] = (DBLocParams, DBLocParamsList)

    def child_modules(self):
        lst = [
            "mg.mmorpg.locations.LocationsStaticImages", "mg.mmorpg.locations.LocationsStaticImagesAdmin",
            "mg.mmorpg.locations.LocationsMultiStaticImages", "mg.mmorpg.locations.LocationsMultiStaticImagesAdmin",
            "mg.mmorpg.locparams.LocationParams", "mg.mmorpg.locfunctions.LocationFunctions"]
        return lst

    def menu_root_index(self, menu):
        menu.append({"id": "locations.index", "text": self._("Locations"), "order": 20})

    def menu_locations_index(self, menu):
        req = self.req()
        if req.has_access("locations.config"):
            menu.append({"id": "locations/config", "text": self._("Locations configuration"), "order": 0, "leaf": True})
            menu.append({"id": "locations/editor", "text": self._("Locations editor"), "order": 1, "leaf": True})

    def permissions_list(self, perms):
        perms.append({"id": "locations.editor", "name": self._("Locations editor")})
        perms.append({"id": "locations.config", "name": self._("Locations configuration")})
        perms.append({"id": "locations.users", "name": self._("Viewing characters locations")})
        perms.append({"id": "locations.teleport", "name": self._("Service teleport")})

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("locations.users"):
            character = self.character(user.uuid)
            if character.valid:
                if character.location:
                    location = htmlescape(character.location.name)
                    if req.has_access("locations.editor"):
                        location = u'<hook:admin.link href="locations/editor/%s" title="%s" />' % (character.location.uuid, location)
                else:
                    location = self._("none")
                loc_row = [self._("Location"), location]
                if req.has_access("locations.teleport"):
                    loc_row.append(u'<hook:admin.link href="locations/teleport/%s" title="%s" />' % (character.uuid, self._("teleport the character")))
                table = {
                    "type": "location",
                    "title": self._("Location"),
                    "order": 30,
                    "rows": [
                        loc_row,
                    ]
                }
                tables.append(table)

    def headmenu_locations_editor(self, args):
        if args == "new":
            return [self._("New location"), "locations/editor"]
        elif args:
            location = self.location(args)
            if location.valid():
                return [location.name, "locations/editor"]
            else:
                return [self._("Editor"), "locations/editor"]
        return self._("Locations")

    def admin_locations_editor(self):
        req = self.req()
        if req.args:
            if req.args != "new":
                location = self.location(req.args)
                if not location.valid():
                    self.call("web.response_json", {"success": True, "redirect": "locations/editor"})
                db_loc = location.db_location
            else:
                db_loc = self.obj(DBLocation)
            lang = self.call("l10n.lang")
            if req.ok():
                self.call("web.upload_handler")
                errors = {}
                name = req.param("name")
                if not name:
                    errors["name"] = self._("Name is mandatory")
                elif name != htmlescape(name) or name != jsencode(name):
                    errors["name"] = self._("Name contains forbidden symbols")
                else:
                    db_loc.set("name", name)
                if lang == "ru":
                    if req.param("name_g"):
                        db_loc.set("name_g", req.param("name_g"))
                    else:
                        db_loc.delkey("name_g")
                    if req.param("name_a"):
                        db_loc.set("name_a", req.param("name_a"))
                    else:
                        db_loc.delkey("name_a")
                    if req.param("name_w"):
                        db_loc.set("name_w", req.param("name_w"))
                    else:
                        db_loc.delkey("name_w")
                    if req.param("name_t"):
                        db_loc.set("name_t", req.param("name_t"))
                    else:
                        db_loc.delkey("name_t")
                    if req.param("name_f"):
                        db_loc.set("name_f", req.param("name_f"))
                    else:
                        db_loc.delkey("name_f")
                val = req.param("delay")
                if not valid_nonnegative_int(val):
                    errors["delay"] = self._("Delay must be a non-negative integer value")
                else:
                    db_loc.set("delay", intz(val))
                for dest in ["up", "left", "right", "down", "exit"]:
                    loc = req.param("v_loc_%s" % dest)
                    if loc:
                        loc = self.location(loc)
                        if not loc.valid():
                            errors["v_loc_%s" % dest] = self._("Invalid location selected")
                        elif loc.uuid == db_loc.uuid:
                            errors["v_loc_%s" % dest] = self._("Link to the same location")
                        else:
                            db_loc.set("loc_%s" % dest, loc.uuid)
                    else:
                        db_loc.delkey("loc_%s" % dest)
                image_type = req.param("v_image_type")
                db_loc.set("image_type", image_type)
                flags = {}
                if image_type == "none":
                    flags["image_type_valid"] = True
                self.call("admin-locations.editor-form-validate", db_loc, flags, errors)
                if not flags.get("image_type_valid"):
                    errors["v_image_type"] = self._("Select valid image type")
                # errors
                if len(errors):
                    self.call("web.response_json_html", {"success": False, "errors": errors})
                # storing
                self.call("admin-locations.editor-form-store", db_loc, flags)
                self.call("admin-locations.update-transitions", db_loc)
                transitions = db_loc.get("transitions", {})
                char = self.character(req.user())
                for loc_id, info in transitions.iteritems():
                    info["hint"] = req.param("tr-%s-hint" % loc_id).strip()
                    val = req.param("tr-%s-delay" % loc_id).strip()
                    info["delay"] = intz(val) if val != "" else None
                    info["available"] = self.call("script.admin-expression", "tr-%s-available" % loc_id, errors, globs={"char": char}) if req.param("tr-%s-available" % loc_id) != "" else 1
                    info["error"] = self.call("script.admin-text", "tr-%s-error" % loc_id, errors, globs={"char": char})
                db_loc.store()
                self.call("admin-locations.editor-form-cleanup", db_loc, flags)
                self.call("web.response_json_html", {"success": True, "redirect": "locations/editor/%s" % db_loc.uuid, "parameters": {"saved": 1}})
            # rendering form
            fields = []
            fields.append({"name": "name", "value": db_loc.get("name"), "label": self._("Location name")})
            if lang == "ru":
                fields.append({"name": "name_g", "value": db_loc.get("name_g"), "label": self._("Location name in genitive")})
                fields.append({"name": "name_a", "value": db_loc.get("name_a"), "label": self._("Location name in accusative"), "inline": True})
                fields.append({"name": "name_w", "value": db_loc.get("name_w"), "label": self._("Location name (where?) - 'in the Some Location'")})
                fields.append({"name": "name_t", "value": db_loc.get("name_t"), "label": self._("Location name (to where?) - 'to the Some Location'"), "inline": True})
                fields.append({"name": "name_f", "value": db_loc.get("name_f"), "label": self._("Location name (from where?) - 'from the Some Location'"), "inline": True})
            # timing
            fields.append({"name": "delay", "label": self._("Delay when moving to this location and from it"), "value": db_loc.get("delay", default_location_delay)})
            # left/right/up/down navigation
            lst = self.objlist(DBLocationList, query_index="all")
            lst.load()
            locations = [(loc.uuid, loc.get("name")) for loc in lst if loc.uuid != db_loc.uuid]
            locations.insert(0, ("", "---------------"))
            fields.append({"name": "loc_up", "label": self._("Location to the up"), "type": "combo", "values": locations, "value": db_loc.get("loc_up", "")})
            fields.append({"name": "loc_left", "label": self._("Location to the left"), "type": "combo", "values": locations, "value": db_loc.get("loc_left", "")})
            fields.append({"name": "loc_right", "label": self._("Location to the right"), "type": "combo", "values": locations, "value": db_loc.get("loc_right", ""), "inline": True})
            fields.append({"name": "loc_down", "label": self._("Location to the down"), "type": "combo", "values": locations, "value": db_loc.get("loc_down", "")})
            fields.append({"name": "loc_exit", "label": self._("This location has 'Exit' direction pointing to this location"), "type": "combo", "values": locations, "value": db_loc.get("loc_exit", "")})
            # image type
            image_types = []
            image_types.append(("none", self._("No image")))
            image_type = {"name": "image_type", "type": "combo", "value": db_loc.get("image_type", "none"), "label": self._("Image type"), "values": image_types}
            fields.append(image_type)
            self.call("admin-locations.editor-form-render", db_loc, fields)
            if not db_loc.get("image_type") and image_type["values"] and not image_type["value"]:
                image_type["value"] = image_type["values"][0][0]
            menu = None
            # rendering location preview
            if req.args != "new":
                menu = []
                self.call("admin-locations.render-links", location, menu)
                # location preview
                self.call("admin-locations.render", location, fields)
            # transitions
            for loc_id, info in db_loc.get("transitions", {}).iteritems():
                loc = self.location(loc_id)
                if not loc.valid():
                    continue
                fields.append({"type": "header", "html": '%s: %s' % (self._("Transition"), loc.name_t)})
                fields.append({"name": "tr-%s-hint" % loc_id, "label": self._("Hint when mouse over the link"), "value": info.get("hint")})
                fields.append({"name": "tr-%s-available" % loc_id, "label": self._("Transition is available for the character") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", info.get("available", 1))})
                fields.append({"name": "tr-%s-error" % loc_id, "label": self._("Error message when transition is unavailable") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", info.get("error", "")), "inline": True})
                fields.append({"name": "tr-%s-delay" % loc_id, "label": self._("Delay when moving to this location (if not specified delay will be calculated as sum of delays on both locations)"), "value": info.get("delay")})
            self.call("admin.form", fields=fields, modules=["FileUploadField"], menu=menu)
        rows = []
        locations = []
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        for db_loc in lst:
            row = [
                u'<strong>%s</strong><br />%s' % (htmlescape(db_loc.get("name")), db_loc.uuid),
                None,
                '<hook:admin.link href="locations/editor/%s" title="%s" />' % (db_loc.uuid, self._("edit")),
            ]
            rows.append(row)
            locations.append({
                "db_loc": db_loc,
                "row": row
            })
        table = {
            "links": [
                {
                    "hook": "locations/editor/new",
                    "text": self._("New location"),
                    "lst": True,
                }
            ],
            "header": [
                self._("Location"),
                self._("Functions"),
                self._("Editing"),
            ],
            "rows": rows,
        }
        self.call("admin-locations.format-list", locations, table)
        vars = {
            "tables": [table]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def locations_all(self):
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        return [(db_loc.uuid, db_loc.get("name")) for db_loc in lst]

    def headmenu_locations_config(self, args):
        return self._("Locations configuration")

    def admin_locations_config(self):
        req = self.req()
        if req.ok():
            errors = {}
            config = self.app().config_updater()
            start_location = req.param("v_start_location")
            movement_delay = req.param("movement_delay")
            if start_location:
                loc = self.location(start_location)
                if not loc.valid():
                    errors["v_start_location"] = self._("Invalid starting location")
                config.set("locations.startloc", start_location)
            char = self.character(req.user())
            config.set("locations.movement-delay", self.call("script.admin-expression", "movement_delay", errors, globs={"char": char, "base_delay": 1}, require_glob=["base_delay"]))
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        locations = self.call("admin-locations.all")
        fields = [
            {"name": "start_location", "label": self._("Starting location for the new character"), "type": "combo", "value": self.conf("locations.startloc"), "values": locations},
            {"name": "movement_delay", "label": '%s%s' % (self._("Location movement delay expression"), self.call("script.help-icon-expressions")), "value": self.call("script.unparse-expression", self.call("locations.movement_delay"))},
        ]
        self.call("admin.form", fields=fields)

    def progress_bars(self, bars):
        bars.append({"code": "location-movement", "description": self._("Delay when moving between locations")})

    def valid_transitions(self, db_loc, valid_transitions):
        for dest in ["up", "left", "right", "down", "exit"]:
            loc = db_loc.get("loc_%s" % dest)
            if loc:
                valid_transitions.add(loc)

    def update_transitions(self, db_loc):
        transitions = db_loc.get("transitions", {})
        db_loc.set("transitions", transitions)
        valid_transitions = set()
        self.call("admin-locations.valid-transitions", db_loc, valid_transitions)
        for loc in transitions.keys():
            if loc not in valid_transitions:
                del transitions[loc]
        for loc in valid_transitions:
            if loc not in transitions:
                transitions[loc] = {}
        db_loc.touch()

class Locations(ConstructorModule):
    def register(self):
        self.rhook("locations.character_get", self.get)
        self.rhook("locations.character_before_set", self.before_set)
        self.rhook("locations.character_set", self.lset)
        self.rhook("locations.character_after_set", self.after_set)
        self.rhook("locfunctions.list", self.locfunctions_list)
        self.rhook("ext-location.show", self.ext_location_show, priv="logged")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("ext-location.move", self.ext_move, priv="logged")
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("hook-location.arrows", self.hook_arrows)
        self.rhook("hook-location.transitions", self.hook_transitions)
        self.rhook("hook-location.name", self.hook_name)
        self.rhook("paidservices.available", self.paid_services_available)
        self.rhook("paidservices.fastmove", self.srv_fastmove)
        self.rhook("money-description.fastmove", self.money_description_fastmove)
        self.rhook("locations.movement_delay", self.movement_delay)
        self.rhook("location.info", self.location_info)
        self.rhook("teleport.character", self.teleport_character)
        self.rhook("hook-location.image", self.hook_image)

    def hook_image(self, vars):
        if not vars.get("load_extjs"):
            vars["load_extjs"] = {}
        vars["load_extjs"]["qtips"] = True
        try:
            location = self.location(vars["location"]["id"])
        except KeyError:
            pass
        else:
            return self.call("locations.render", location, vars)

    def location_info(self, loc_id):
        location = self.location(loc_id)
        if location.valid():
            return location
        else:
            return None

    def get(self, character):
        try:
            info = self.obj(DBCharacterLocation, character.uuid)
        except ObjectNotFoundException:
            start_location = self.conf("locations.startloc")
            if start_location:
                info = self.obj(DBCharacterLocation, character.uuid, data={})
                info.set("location", start_location)
                info.store()
                loc = self.location(start_location)
                self.after_set(character, loc, None)
                delay = None
                instance = None
            else:
                loc = None
                instance = None
                delay = None
        else:
            loc = self.location(info.get("location"))
            instance = info.get("instance")
            delay = info.get("delay")
        return [loc, instance, delay]

    def before_set(self, character, new_location, instance):
        self.call("chat.channel-unjoin", character, self.call("chat.channel-info", "loc"))

    def lset(self, character, new_location, instance, delay):
        info = self.obj(DBCharacterLocation, character.uuid)
        info.set("location", new_location.uuid)
        if instance is None:
            info.delkey("instance")
        else:
            info.set("instance", instance)
        if delay is None:
            info.delkey("delay")
        else:
            info.set("delay", delay)
        info.store()

    def after_set(self, character, old_location, instance):
        self.call("chat.channel-join", character, self.call("chat.channel-info", "loc"))

    def locfunctions_list(self, location, funcs):
        loc_exit = location.db_location.get("loc_exit")
        if loc_exit:
            funcs.append({
                "id": "exit",
                "order": -20,
                "title": self._("Exit"),
                "available": 1,
                "onclick": "parent.Locations.move('%s')" % loc_exit,
            })
        funcs.append({
            "id": "show",
            "order": -10,
            "title": self._("Location"),
            "available": 1,
        })

    def ext_location_show(self):
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        location = character.location
        if location is None:
            self.call("game.internal-error", self._("Character is outside of any locations"))
        vars = {
            "loc": ScriptTemplateObject(location),
            "location": {
                "id": location.uuid,
            },
            "update_script": None if req.param("noupdate") else self.update_js(character),
            "debug_ext": self.conf("debug.ext"),
        }
        transitions = []
        for loc_id, info in location.transitions.iteritems():
            transitions.append({
                "loc": loc_id,
                "hint": jsencode(info.get("hint"))
            })
        vars["transitions"] = transitions
        design = self.design("gameinterface")
        self.call("locfunctions.menu", character, vars)
        html = self.call("design.parse", design, "location-layout.html", None, vars)
        self.call("game.response_internal", "location.html", vars, html)

    def update_js(self, character):
        now = self.now()
        commands = []
        # updating location movement progress bar
        if character.location_delay is None or now >= character.location_delay[1]:
            commands.append("Game.progress_set('location-movement', 1);")
        else:
            now = unix_timestamp(now)
            start = unix_timestamp(character.location_delay[0])
            end = unix_timestamp(character.location_delay[1])
            current_ratio = (now - start) * 1.0 / (end - start)
            time_till_end = (end - now) * 1000
            commands.append("Game.progress_run('location-movement', %s, 1, %s);" % (current_ratio, time_till_end))
        # updating location names
        if character.location:
            commands.append(u"Locations.update('{name}', '{name_w}');".format(
                name=jsencode(character.location.name),
                name_w=jsencode(character.location.name_w)
            ))
        return ''.join(commands)

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("locations")
        vars["js_init"].append(self.update_js(character))

    def ext_move(self):
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        with self.lock([character.lock, "session.%s" % req.session().uuid]):
            if not character.tech_online:
                self.call("web.response_json", {"ok": False, "error": self._("Character offline")})
            if character.location_delay and character.location_delay[1] > self.now():
                self.call("web.response_json", {"ok": False, "error": self._("You are busy"), "hide_title": True})
            old_location = character.location
            new_location_id = req.param("location")
            # validating transition
            trans = old_location.transitions.get(new_location_id)
            if trans is None:
                self.call("web.response_json", {"ok": False, "error": self._("No way")})
            new_location = self.location(new_location_id)
            if not new_location.valid():
                self.call("web.response_json", {"ok": False, "error": self._("No such location")})
            delay = trans.get("delay")
            if delay is None:
                delay = old_location.delay + new_location.delay
            # evaluating availability
            available = self.call("script.evaluate-expression", trans.get("available", 1), globs={"char": character}, description=self._("Availability of transition between locations"))
            if not available:
                error = self.call("script.evaluate-text", trans.get("error", ""), globs={"char": character}, description=self._("Transition error message"))
                self.call("web.response_json", {"ok": False, "error": error, "hide_title": True})
            # evaluating delay
            delay = self.call("script.evaluate-expression", self.movement_delay(), {"char": character, "base_delay": delay}, description=self._("Location movement delay"))
            character.set_location(new_location, character.instance, [self.now(), self.now(delay)])
            self.call("web.response_json", {
                "ok": True,
                "id": character.location.uuid,
                "update_script": self.update_js(character),
            })

    def teleport_character(self, character, location, instance=None, delay=None):
        character.set_location(location=location, instance=instance, delay=delay)
        character.javascript(self.update_js(character))

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "location",
            "href": "/location",
            "target": "main",
            "icon": "location.png",
            "title": self._("Location"),
            "block": "left-menu",
            "order": 3,
        })

    def hook_arrows(self, vars):
        req = self.req()
        character = self.character(req.user())
        location = character.location
        design = self.design("gameinterface")
        arrows = {}
        for dest in ["up", "down", "left", "right", "exit"]:
            loc_id = location.db_location.get("loc_%s" % dest)
            if loc_id:
                arrows["img_%s" % dest] = "%s/location-%s.png" % (design.get("uri"), dest) if design and design.get("files").get("location-%s.png" % dest) else "/st/game/default-interface/%s.png" % dest
                arrows["loc_%s" % dest] = loc_id
        vars["location_arrows"] = arrows
        raise Hooks.Return(self.call("design.parse", design, "location-arrows.html", None, vars))

    def hook_transitions(self, vars):
        req = self.req()
        character = self.character(req.user())
        location = character.location
        design = self.design("gameinterface")
        transitions = []
        for loc_id, info in location.transitions.iteritems():
            loc = self.location(loc_id)
            if not loc.valid():
                continue
            transitions.append({
                "loc": loc_id,
                "name": loc.name,
            })
        if transitions:
            transitions.sort(cmp=lambda x, y: cmp(x["name"], y["name"]))
            transitions[-1]["lst"] = True
            vars["location_transitions"] = transitions
        raise Hooks.Return(self.call("design.parse", design, "location-transitions.html", None, vars))

    def hook_name(self, vars, declension=None):
        req = self.req()
        character = self.character(req.user())
        location = character.location
        if location is None:
            if declension == "w":
                name = self._("in the undefined location")
            else:
                name = self._("No location")
        elif declension == "w":
            name = location.name_w
        else:
            name = location.name
            declension = None
        raise Hooks.Return('<span class="location-name%s">%s</span>' % (('-%s' % declension) if declension else "", name))

    def paid_services_available(self, services):
        services.append({"id": "fastmove", "type": "main"})

    def money_description_fastmove(self):
        return {
            "args": ["period", "period_a"],
            "text": self._("Fast movement across the locations for {period}"),
        }

    def srv_fastmove(self):
        cur = self.call("money.real-currency")
        if not cur:
            return None
        cinfo = self.call("money.currency-info", cur)
        req = self.req()
        return {
            "id": "fastmove",
            "name": self._("Fast movement across the locations"),
            "description": self._("If you want to move across locations faster you may use this service"),
            "subscription": True,
            "type": "main",
            "default_period": 5 * 86400,
            "default_price": self.call("money.format-price", 30 / cinfo.get("real_roubles", 1), cur),
            "default_currency": cur,
            "default_enabled": True,
        }

    def movement_delay(self):
        delay = self.conf("locations.movement-delay")
        if delay is None:
            delay = ['/', ['glob', 'base_delay'], ['+', 1, ['.', ['.', ['glob', 'char'], 'mod'], 'fastmove']]]
        return delay

class LocationsStaticImages(ConstructorModule):
    def register(self):
        self.rhook("locations.render", self.render)

    def render(self, location, vars):
        if location.image_type == "static":
            zones = []
            if location.db_location.get("static_zones"):
                zone_id = 0
                for zone in location.db_location.get("static_zones"):
                    zone_id += 1
                    rzone = {
                        "polygon": zone.get("polygon"),
                        "action": zone.get("action", "none"),
                        "loc": zone.get("loc"),
                        "class": "loc-tr-%s" % zone.get("loc") if zone.get("action") == "move" else "loc-zone-%d" % zone_id,
                        "hint": htmlescape(jsencode(zone.get("hint"))),
                    }
                    if zone.get("url"):
                        rzone["url"] = htmlescape(jsencode(zone.get("url")))
                        m = hashlib.md5()
                        m.update(utf2str(zone.get("url")))
                        rzone["urlhash"] = m.hexdigest()
                    self.call("locations.map-zone-%s-render" % rzone["action"], zone, rzone)
                    zones.append(rzone)
            vars["loc"] = {
                "id": location.uuid,
                "image": location.db_location.get("image_static"),
            }
            vars["zones"] = zones
            design = self.design("gameinterface")
            raise Hooks.Return(self.call("design.parse", design, "location-static.html", None, vars))

class ImageMapEditor(ConstructorModule):
    def __init__(self, app, location, fqn="mg.mmorpg.locations.ImageMapEditor"):
        ConstructorModule.__init__(self, app, fqn)
        self._location = location

    def submit(self, zones):
        req = self.req()
        errors = {}
        for key in req.param_dict().keys():
            m = re_polygon_param.match(key)
            if m:
                zone_id = int(m.group(1))
                zone = {}
                zones[zone_id] = zone
                # polygon data
                zone["polygon"] = req.param("polygon-%d" % zone_id)
                poly = zone["polygon"].split(",")
                if len(poly) == 0:
                    errors["polygon-%d" % zone_id] = self._("Polygon may not be empty")
                elif len(poly) % 2:
                    errors["polygon-%d" % zone_id] = self._("Odd number of coordinates")
                elif len(poly) < 6:
                    errors["polygon-%d" % zone_id] = self._("Minimal number of points is 3")
                else:
                    for coo in poly:
                        if not valid_int(coo):
                            errors["polygon-%d" % zone_id] = self._("Invalid non-integer coordinate encountered")
                            break
                # action
                action = req.param("v_action-%d" % zone_id)
                zone["action"] = action
                if action == "move":
                    loc = req.param("v_location-%d" % zone_id)
                    if not loc:
                        errors["v_location-%d" % zone_id] = self._("Location not specified")
                    else:
                        loc_obj = self.location(loc)
                        if not loc_obj.valid():
                            errors["v_location-%d" % zone_id] = self._("Invalid location specified")
                        elif loc_obj.uuid == self._location.uuid:
                            errors["v_location-%d" % zone_id] = self._("Link to the same location")
                        else:
                            zone["loc"] = loc
                elif action == "open":
                    url = req.param("url-%d" % zone_id)
                    if not url:
                        errors["url-%d" % zone_id] = self._("This field is mandatory")
                    elif not url.startswith("/"):
                        errors["url-%d" % zone_id] = self._("URL must start with '/'")
                    else:
                        zone["url"] = url
                elif not self.call("admin-locations.map-zone-action-%s" % action, zone_id, zone, errors):
                    if "action" in zone:
                        del zone["action"]
                # hint
                hint = req.param("hint-%d" % zone_id)
                zone["hint"] = hint
        if len(errors):
            self.call("web.response_json", {"success": False, "errors": errors})

    def render_form(self, static_zones, image, width, height):
        req = self.req()
        # Loading zones
        zones = []
        if static_zones:
            for zone in static_zones:
                rzone = {
                    "polygon": zone.get("polygon"),
                    "action": zone.get("action", "none"),
                    "loc": zone.get("loc"),
                    "url": jsencode(zone.get("url")),
                    "hint": jsencode(zone.get("hint")),
                }
                self.call("admin-locations.map-zone-%s-render" % rzone["action"], zone, rzone)
                zones.append(rzone)
        # Loading locations
        locations = []
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        for db_loc in lst:
            if db_loc.uuid != self._location.uuid:
                locations.append({
                    "id": db_loc.uuid,
                    "name": jsencode(db_loc.get("name"))
                })
        actions = [("none", self._("No action")), ("move", self._("Move to another location")), ("open", self._("Open URL"))]
        self.call("admin-locations.map-zone-actions", self._location, actions)
        links = []
        self.call("admin-locations.render-links", self._location, links)
        vars = {
            "image": image,
            "width": width,
            "height": height,
            "ie_warning": self._("Warning! Internet Explorer browser is not supported. Location editor may work slowly and unstable. Mozilla Firefox, Google Chrome and Opera are fully supported"),
            "submit_url": "/%s/%s/%s" % (req.group, req.hook, req.args),
            "zones": zones,
            "actions": actions,
            "locations": locations,
            "links": links,
        }
        if req.param("saved"):
            vars["saved"] = {"text": self._("Location saved successfully")}
        self.call("admin-locations.render-imagemap-editor", self._location, vars)
        self.call("admin.response_template", "admin/locations/imagemap.html", vars)

class LocationsStaticImagesAdmin(ConstructorModule):
    def register(self):
        self.rhook("admin-locations.editor-form-render", self.form_render)
        self.rhook("admin-locations.editor-form-validate", self.form_validate)
        self.rhook("admin-locations.editor-form-store", self.form_store)
        self.rhook("admin-locations.editor-form-cleanup", self.form_cleanup)
        self.rhook("admin-locations.render", self.render)
        self.rhook("admin-locations.valid-transitions", self.valid_transitions)
        self.rhook("admin-locations.links", self.links)
        self.rhook("ext-admin-locations.image-map", self.admin_image_map, priv="locations.editor")
        self.rhook("headmenu-admin-locations.image-map", self.headmenu_image_map)

    def form_render(self, db_loc, fields):
        for fld in fields:
            if fld["name"] == "image_type":
                fld["values"].append(("static", self._("Static image")))
        fields.append({"name": "image_static", "type": "fileuploadfield", "label": self._("Replace location image (if necessary)") if db_loc.get("image_static") else self._("Upload location image"), "condition": "[image_type]=='static'"})

    def form_validate(self, db_loc, flags, errors):
        req = self.req()
        if db_loc.get("image_static"):
            flags["old_image_static"] = db_loc.get("image_static")
        if req.param("v_image_type") == "static":
            flags["image_type_valid"] = True
            image_data = req.param_raw("image_static")
            if image_data:
                try:
                    image_obj = Image.open(cStringIO.StringIO(image_data))
                    if image_obj.load() is None:
                        raise IOError
                except IOError:
                    errors["image_static"] = self._("Image format not recognized")
                except OverflowError:
                    errors["image_static"] = self._("Image format not recognized")
                else:
                    width, height = image_obj.size
                    flags["image_static"] = image_data
                    flags["image_static_w"] = width
                    flags["image_static_h"] = height
                    if image_obj.format == "GIF":
                        flags["image_static_ext"] = "gif"
                        flags["image_static_content_type"] = "image/gif"
                    elif image_obj.format == "PNG":
                        flags["image_static_ext"] = "png"
                        flags["image_static_content_type"] = "image/png"
                    elif image_obj.format == "JPEG":
                        flags["image_static_ext"] = "jpg"
                        flags["image_static_content_type"] = "image/jpeg"
                    else:
                        del flags["image_static"]
                        del flags["image_static_w"]
                        del flags["image_static_h"]
                        errors["image_static"] = self._("Image format must be GIF, JPEG or PNG")
            else:
                if db_loc.get("image_static"):
                    flags["old_image_static"] = db_loc.get("image_static")
                else:
                    errors["image_static"] = self._("Upload an image")
        else:
            db_loc.delkey("image_static")
            db_loc.delkey("image_static_w")
            db_loc.delkey("image_static_h")

    def form_store(self, db_loc, flags):
        if flags.get("image_static"):
            uri = self.call("cluster.static_upload", "locations", flags["image_static_ext"], flags["image_static_content_type"], flags["image_static"])
            db_loc.set("image_static", uri)
            db_loc.set("image_static_w", flags["image_static_w"])
            db_loc.set("image_static_h", flags["image_static_h"])

    def form_cleanup(self, db_loc, flags):
        if flags.get("old_image_static") and db_loc.get("image_static") != flags["old_image_static"]:
            self.call("cluster.static_delete", flags["old_image_static"])

    def headmenu_image_map(self, args):
        return [self._("Map"), "locations/editor/%s" % args]

    def admin_image_map(self):
        req = self.req()
        location = self.location(req.args)
        if not location.valid() or location.image_type != "static":
            self.call("admin.redirect", "locations/editor")
        imagemap_editor = ImageMapEditor(self.app(), location)
        if req.ok():
            zones = {}
            imagemap_editor.submit(zones)
            location.db_location.set("static_zones", [zones[zone_id] for zone_id in sorted(zones.keys())])
            self.call("admin-locations.update-transitions", location.db_location)
            location.db_location.store()
            self.call("web.response_json", {"success": True, "redirect": "locations/image-map/%s" % location.uuid, "parameters": {"saved": 1}})
        static_zones = location.db_location.get("static_zones")
        image = location.db_location.get("image_static")
        width = location.db_location.get("image_static_w")
        height = location.db_location.get("image_static_h")
        imagemap_editor.render_form(static_zones, image, width, height)

    def links(self, location, links):
        req = self.req()
        if req.has_access("locations.editor"):
            if location.image_type == "static":
                links.append({"hook": "locations/image-map/%s" % location.uuid, "text": self._("imagemap///Map")})

    def render(self, location, fields):
        if location.image_type == "static":
            zones = []
            if location.db_location.get("static_zones"):
                for zone in location.db_location.get("static_zones"):
                    zones.append({
                        "polygon": zone.get("polygon"),
                        "action": zone.get("action"),
                        "loc": zone.get("loc"),
                    })
            vars = {
                "loc": {
                    "id": location.uuid,
                    "image": location.db_location.get("image_static"),
                },
                "zones": zones,
            }
            req = self.req()
            if req.param("saved"):
                vars["saved"] = {"text": self._("Location data saved successfully")}
            fields.insert(0, {"type": "html", "html": self.call("web.parse_layout", "admin/locations/imagemap-render.html", vars)})

    def valid_transitions(self, db_loc, valid_transitions):
        if db_loc.get("image_type") == "static":
            if db_loc.get("static_zones"):
                for zone in db_loc.get("static_zones"):
                    if zone.get("action") == "move" and zone.get("loc"):
                        valid_transitions.add(zone.get("loc"))

# Multiple static images for different resolutions

class LocationsMultiStaticImages(ConstructorModule):
    def register(self):
        self.rhook("locations.render", self.render)

    def render(self, location, vars):
        if location.image_type == "multistatic":
            # initialization script
            loc_init = vars.get("loc_init", [])
            vars["loc_init"] = loc_init
            # images
            images = []
            for img in location.db_location.get("images_multistatic", []):
                zones = []
                zone_id = 0
                for zone in img.get("zones", []):
                    zone_id += 1
                    rzone = {
                        "polygon": zone.get("polygon"),
                        "action": zone.get("action", "none"),
                        "loc": zone.get("loc"),
                        "class": "loc-tr-%s" % zone.get("loc") if zone.get("action") == "move" else "loc-zone-%d" % zone_id,
                        "hint": htmlescape(jsencode(zone.get("hint"))),
                    }
                    if zone.get("url"):
                        rzone["url"] = htmlescape(jsencode(zone.get("url")))
                        m = hashlib.md5()
                        m.update(utf2str(zone.get("url")))
                        rzone["urlhash"] = m.hexdigest()
                    self.call("locations.map-zone-%s-render" % rzone["action"], zone, rzone)
                    zones.append(rzone)
                rimage = {
                    "id": img["uuid"],
                    "zones": zones,
                    "image": img.get("uri"),
                }
                images.append(rimage)
                loc_init.append("Loc.multiimage({width: %d, height: %s, id: '%s'});" % (img["width"], img["height"], img["uuid"]))
            vars["loc"] = {
                "id": location.uuid,
                "image": location.db_location.get("image_static"),
            }
            vars["images"] = images
            design = self.design("gameinterface")
            raise Hooks.Return(self.call("design.parse", design, "location-multistatic.html", None, vars))

class LocationsMultiStaticImagesAdmin(ConstructorModule):
    def register(self):
        self.rhook("admin-locations.editor-form-render", self.form_render)
        self.rhook("admin-locations.editor-form-validate", self.form_validate)
        self.rhook("admin-locations.editor-form-store", self.form_store)
        self.rhook("admin-locations.editor-form-cleanup", self.form_cleanup)
        self.rhook("admin-locations.render", self.render)
        self.rhook("admin-locations.valid-transitions", self.valid_transitions)
        self.rhook("admin-locations.links", self.links)
        self.rhook("ext-admin-locations.multiimage-map", self.admin_multiimage_map, priv="locations.editor")
        self.rhook("headmenu-admin-locations.multiimage-map", self.headmenu_multiimage_map)

    def form_render(self, db_loc, fields):
        for fld in fields:
            if fld["name"] == "image_type":
                fld["values"].append(("multistatic", self._("Multiple static images with different dimensions")))
        fields.append({"name": "image_multistatic", "type": "fileuploadfield", "label": self._("Add location image with different dimension") if db_loc.get("images_multistatic") else self._("Upload first location image"), "condition": "[image_type]=='multistatic'"})

    def form_validate(self, db_loc, flags, errors):
        req = self.req()
        if req.param("v_image_type") == "multistatic":
            flags["image_type_valid"] = True
            image_data = req.param_raw("image_multistatic")
            if image_data:
                try:
                    image_obj = Image.open(cStringIO.StringIO(image_data))
                    if image_obj.load() is None:
                        raise IOError
                except IOError:
                    errors["image_multistatic"] = self._("Image format not recognized")
                except OverflowError:
                    errors["image_multistatic"] = self._("Image format not recognized")
                else:
                    width, height = image_obj.size
                    flags["image_multistatic"] = image_data
                    flags["image_multistatic_w"] = width
                    flags["image_multistatic_h"] = height
                    if image_obj.format == "GIF":
                        flags["image_multistatic_ext"] = "gif"
                        flags["image_multistatic_content_type"] = "image/gif"
                    elif image_obj.format == "PNG":
                        flags["image_multistatic_ext"] = "png"
                        flags["image_multistatic_content_type"] = "image/png"
                    elif image_obj.format == "JPEG":
                        flags["image_multistatic_ext"] = "jpg"
                        flags["image_multistatic_content_type"] = "image/jpeg"
                    else:
                        del flags["image_multistatic"]
                        del flags["image_multistatic_w"]
                        del flags["image_multistatic_h"]
                        errors["image_multistatic"] = self._("Image format must be GIF, JPEG or PNG")
            else:
                if not db_loc.get("images_multistatic"):
                    errors["image_multistatic"] = self._("Upload an image")
        else:
            images = db_loc.get("images_multistatic")
            if images:
                flags["old_images_multistatic"] = images
                db_loc.delkey("images_multistatic")

    def form_store(self, db_loc, flags):
        if flags.get("image_multistatic"):
            uri = self.call("cluster.static_upload", "locations", flags["image_multistatic_ext"], flags["image_multistatic_content_type"], flags["image_multistatic"])
            images = db_loc.get("images_multistatic", [])
            images.append({
                "uuid": uuid4().hex,
                "uri": uri,
                "width": flags["image_multistatic_w"],
                "height": flags["image_multistatic_h"],
            })
            images.sort(cmp=lambda x, y: cmp(x["width"] + x["height"], y["width"] + y["height"]))
            db_loc.set("images_multistatic", images)
            db_loc.touch()

    def form_cleanup(self, db_loc, flags):
        old_images = flags.get("old_images_multistatic")
        if old_images:
            for img in old_images:
                self.call("cluster.static_delete", img["uri"])

    def links(self, location, links):
        req = self.req()
        order = 0
        if req.has_access("locations.editor"):
            if location.image_type == "multistatic":
                for img in location.db_location.get("images_multistatic", []):
                    links.append({"hook": "locations/multiimage-map/%s/%s" % (location.uuid, img["uuid"]), "text": self._("imagemap///Map {width}x{height}").format(width=img["width"], height=img["height"]), "order": order})
                    order += 0.001

    def render(self, location, fields):
        if location.image_type == "multistatic":
            images = []
            for img in location.db_location.get("images_multistatic", []):
                zones = []
                if img.get("zones"):
                    for zone in img.get("zones"):
                        zones.append({
                            "polygon": zone.get("polygon"),
                            "action": zone.get("action"),
                            "loc": zone.get("loc"),
                        })
                images.append({
                    "uuid": img["uuid"],
                    "uri": img["uri"],
                    "width": img["width"],
                    "height": img["height"],
                    "zones": zones
                })
            if images:
                images[-1]["lst"] = True
            vars = {
                "loc": {
                    "id": location.uuid,
                    "images": images,
                },
            }
            req = self.req()
            if req.param("saved"):
                vars["saved"] = {"text": self._("Location data saved successfully")}
            fields.insert(0, {"type": "html", "html": self.call("web.parse_layout", "admin/locations/multiimagemap-render.html", vars)})
            tabs = []
            active_tab = None
            for img in images:
                tab_id = "locimg-%s" % img["uuid"]
                if active_tab is None:
                    active_tab = 0
                delete = "locations/multiimage-map/%s/del/%s" % (location.uuid, img["uuid"])
                tabs.append({
                    "title": "%dx%d" % (img["width"], img["height"]),
                    "bodyStyle": "padding: 10px",
                    "tabId": tab_id,
                    "autoScroll": True,
                    "autoHeight": True,
                    "items": [{
                        "xtype": "box",
                        "cls": "admin-submenu",
                        "html": u'<a href="/admin#%s" onclick="if (confirm(\'%s\')) { adm(\'%s\'); } return false">%s</a>' % (delete, jsencode(self._("Are you sure want do delete this image?")), delete, self._("Delete this image")),
                    }, {
                        "xtype": "box",
                        "html": u'<img src="%s" alt="" usemap="#locmap-%s-%s" style="width: %dpx; height: %dpx;" />' % (img["uri"], location.uuid, img["uuid"], img["width"], img["height"]),
                    }]
                })
            fields.insert(1, {"type": "component", "component": {
                "xtype": "tabpanel",
                "id": "multiimages-panel",
                "items": tabs,
                "activeTab": active_tab,
                "autoHeight": True,
            }})

    def valid_transitions(self, db_loc, valid_transitions):
        if db_loc.get("image_type") == "multistatic":
            for img in db_loc.get("images_multistatic", []):
                for zone in img.get("zones", []):
                    if zone.get("action") == "move" and zone.get("loc"):
                        valid_transitions.add(zone.get("loc"))

    def headmenu_multiimage_map(self, args):
        m = re_multiimage_map.match(args)
        if m:
            loc_uuid, img_uuid = m.group(1, 2)
            location = self.location(loc_uuid)
            if location.valid and location.image_type == "multistatic":
                for img in location.db_location.get("images_multistatic", []):
                    if img["uuid"] == img_uuid:
                        return [self._("imagemap///Map {width}x{height}").format(width=img["width"], height=img["height"]), "locations/editor/%s" % loc_uuid]

    def admin_multiimage_map(self):
        req = self.req()
        m = re_multiimage_map_del.match(req.args)
        if m:
            loc_uuid, img_uuid = m.group(1, 2)
            location = self.location(loc_uuid)
            if not location.valid() or location.image_type != "multistatic":
                self.call("admin.redirect", "locations/editor")
            images = location.db_location.get("images_multistatic", [])
            for img in images:
                if img["uuid"] == img_uuid:
                    images = [i for i in images if i["uuid"] != img_uuid]
                    location.db_location.set("images_multistatic", images)
                    self.call("admin-locations.update-transitions", location.db_location)
                    location.db_location.store()
                    self.call("cluster.static_delete", img["uri"])
                    break
            self.call("admin.redirect", "locations/editor/%s" % loc_uuid)
        m = re_multiimage_map.match(req.args)
        if not m:
            self.call("admin.redirect", "locations/editor")
        loc_uuid, img_uuid = m.group(1, 2)
        location = self.location(loc_uuid)
        if not location.valid() or location.image_type != "multistatic":
            self.call("admin.redirect", "locations/editor")
        img = None
        for i in location.db_location.get("images_multistatic", []):
            if i["uuid"] == img_uuid:
                img = i
                break
        if not img:
            self.call("admin.redirect", "locations/editor/%s" % loc_uuid)
        imagemap_editor = ImageMapEditor(self.app(), location)
        if req.ok():
            zones = {}
            imagemap_editor.submit(zones)
            img["zones"] = [zones[zone_id] for zone_id in sorted(zones.keys())]
            self.call("admin-locations.update-transitions", location.db_location)
            location.db_location.touch()
            location.db_location.store()
            self.call("web.response_json", {"success": True, "redirect": "locations/multiimage-map/%s/%s" % (location.uuid, img_uuid), "parameters": {"saved": 1}})
        static_zones = img.get("zones")
        image = img.get("uri")
        width = img.get("width")
        height = img.get("height")
        imagemap_editor.render_form(static_zones, image, width, height)
