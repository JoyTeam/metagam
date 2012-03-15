from mg.constructor import *

class StartLoc(ConstructorModule):
    def register(self):
        self.rhook("charclass.selected", self.charclass_selected)

    def child_modules(self):
        return ["mg.mmorpg.startloc.StartLocAdmin"]

    def charclass_selected(self, character, param, cls_id):
        loc_uuid = self.conf("startloc.%s-%s" % (param["code"], cls_id))
        if loc_uuid:
            loc = self.call("location.info", loc_uuid)
            if loc:
                character.teleport(loc, character.instance, [self.now(), self.now()])

class StartLocAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-locations.index", self.menu_locations_index)
        self.rhook("ext-admin-locations.start", self.admin_locations_start, priv="locations.start")
        self.rhook("headmenu-admin-locations.start", self.headmenu_locations_start)
        self.rhook("advice-admin-locations.start", self.advice_locations_start)

    def advice_locations_start(self, args, advice):
        advice.append({"title": self._("Starting locations documentation"), "content": self._('You can find detailed information on the starting locations system in the <a href="//www.%s/doc/startloc" target="_blank">starting locations page</a> in the reference manual.') % self.app().inst.config["main_host"], "order": 10})

    def permissions_list(self, perms):
        perms.append({"id": "locations.start", "name": self._("Starting locations")})

    def menu_locations_index(self, menu):
        req = self.req()
        if req.has_access("locations.start"):
            menu.append({"id": "locations/start", "text": self._("Starting locations"), "order": 50, "leaf": True})

    def headmenu_locations_start(self, args):
        return self._("Starting locations configuration")

    def admin_locations_start(self):
        req = self.req()
        # list of class groups
        params = []
        for param in self.call("characters.params"):
            if param.get("charclass"):
                params.append(param)
        if not params:
            self.call("admin.response", u'<div class="admin-alert">%s</div>' % (self._("This interface allows you to configure starting location of a character depending of his race or class. To create races and classes system go to the '{href}' page first").format(href=u'<hook:admin.link href="characters/classes" title="%s" />' % self._("Races and classes"))), {})
        # list of locations
        locations = self.call("admin-locations.all")
        locations_ok = set([loc_id for loc_id, loc in locations])
        # processing request
        if req.ok():
            config = self.app().config_updater()
            for param in params:
                classes = self.conf("charclasses.%s" % param["code"], {}).items()
                for cls_id, cls in classes:
                    loc_uuid = req.param("v_loc-%s-%s" % (param["code"], cls_id))
                    key = "startloc.%s-%s" % (param["code"], cls_id)
                    if loc_uuid in locations_ok:
                        config.set(key, loc_uuid)
                    else:
                        config.delete(key)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        # rendering form
        locations.insert(0, (None, "---"))
        fields = []
        for param in params:
            fields.append({"type": "header", "html": htmlescape(param.get("name"))})
            classes = self.conf("charclasses.%s" % param["code"], {}).items()
            classes.sort(cmp=lambda x, y: cmp(x[1].get("order"), y[1].get("order")) or cmp(x[0], y[0]))
            for cls_id, cls in classes:
                fields.append({"type": "combo", "name": "loc-%s-%s" % (param["code"], cls_id), "label": htmlescape(cls.get("name")), "value": self.conf("startloc.%s-%s" % (param["code"], cls_id)), "values": locations})
        self.call("admin.form", fields=fields)
