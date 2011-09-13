from mg.constructor.params import *
from mg.mmorpg.locations_classes import *
import re

re_locparam = re.compile(r'^locparam/(.+)$')
re_loc_params = re.compile(r'loc\.p_([a-zA-Z_][a-zA-Z0-9_]*)')

class LocationParamsAdmin(ParamsAdmin):
    def __init__(self, app, fqn):
        ParamsAdmin.__init__(self, app, fqn)
        self.kind = "locations"

    @property
    def title(self):
        return self._("Locations parameters")

    def register(self):
        ParamsAdmin.register(self)
        self.rhook("menu-admin-locations.index", self.menu_locations_index)
        self.rhook("locations.params-url", self.params_url)
        self.rhook("locations.params-redirect", self.params_redirect)
        self.rhook("locations.params-obj", self.params_obj)
        self.rhook("locations.script-globs", self.script_globs)
        self.rhook("headmenu-admin-locations.paramview", self.headmenu_paramview)
        self.rhook("ext-admin-locations.paramview", self.admin_paramview, priv="locations.params-view")

    def script_globs(self):
        req = self.req()
        return {"loc": self.character(req.user()).location}

    def params_url(self, uuid):
        return "locations/paramview/%s" % uuid

    def params_redirect(self, uuid):
        self.call("admin.redirect", "locations/paramview/%s" % uuid)

    def params_obj(self, uuid):
        return self.location(uuid).db_params

    def menu_locations_index(self, menu):
        req = self.req()
        if req.has_access("locations.params"):
            menu.append({"id": "locations/params", "text": self.title, "leaf": True, "order": 25})

    def headmenu_paramview(self, args):
        return [self._("Parameters"), "locations/editor/%s" % args]

    def admin_paramview(self):
        req = self.req()
        loc = self.location(req.args)
        if not loc.valid:
            self.call("web.not_found")
        may_edit = req.has_access("locations.params-edit")
        header = [self._("Code"), self._("parameter///Name"), self._("Value"), "HTML"]
        if may_edit:
            header.append(self._("Changing"))
        params = []
        self.admin_view_params(loc, params, may_edit)
        vars = {
            "tables": [
                {
                    "header": header,
                    "rows": params,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

class LocationParams(Params):
    def __init__(self, app, fqn):
        Params.__init__(self, app, fqn)
        self.kind = "locations"

    def child_modules(self):
        return ["mg.mmorpg.locparams.LocationParamsAdmin"]

    def register(self):
        Params.register(self)

