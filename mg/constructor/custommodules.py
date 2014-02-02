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

import mg.constructor
from mg.core.tools import *

class CustomModulesModule(mg.constructor.Module):
    def register(self):
        self.rhook("constructor.project-options-main", self.project_options)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-constructor.custom-modules", self.custom_modules, priv="constructor.custom-modules")
        self.rhook("headmenu-admin-constructor.custom-modules", self.headmenu_custom_modules)

    def permissions_list(self, perms):
        perms.append({"id": "constructor.custom-modules", "name": self._("Constructor: custom modules injection")})

    def project_options(self, project, options):
        if self.req().has_access("constructor.custom-modules"):
            options.append({"title": self._("Custom modules injection"), "value": '<hook:admin.link href="constructor/custom-modules/%s" title="%s" />' % (project.uuid, self._("open list"))})

    def headmenu_custom_modules(self, args):
        tokens = args.split("/")
        app_id = tokens[0]
        if len(tokens) == 2 and tokens[1] == "new":
            return [self._("New module"), "constructor/custom-modules/%s" % app_id]
        return [self._("Custom modules"), "constructor/project-dashboard/%s" % app_id]

    def custom_modules(self):
        req = self.req()
        tokens = req.args.split("/")
        app_id = tokens[0]
        app = self.app().inst.appfactory.get_by_tag(app_id)
        if app is None:
            self.call("web.not_found")
        modules = app.config.get("modules.custom", [])
        modules = sorted(modules)
        # parse command line
        if len(tokens) == 3 and tokens[1] == "del":
            mod = tokens[2]
            modules = [m for m in modules if m != mod]
            config = app.config_updater()
            config.set("modules.custom", modules)
            config.store()
            self.call("admin.redirect", "constructor/custom-modules/%s" % app_id)
        if len(tokens) == 2 and tokens[1] == "new":
            if req.ok():
                errors = {}
                # mod
                mod = req.param("mod").strip()
                if not mod:
                    errors["mod"] = self._("This field is mandatory")
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # save settings
                modules = [m for m in modules if m != mod]
                modules.append(mod)
                config = app.config_updater()
                config.set("modules.custom", modules)
                config.store()
                self.call("admin.redirect", "constructor/custom-modules/%s" % app_id)
            fields = [
                {"label": self._("Module name"), "name": "mod" }
            ]
            self.call("admin.form", fields=fields)
        # render list
        rows = []
        for module in modules:
            rows.append([
                htmlescape(module),
                u'<hook:admin.link href="constructor/custom-modules/%s/del/%s" title="%s" confirm="%s" />' % (
                    app_id,
                    htmlescape(module),
                    self._("delete"),
                    self._("Are you sure want to delete this module?")
                )
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "constructor/custom-modules/%s/new" % app_id,
                            "text": self._("New module"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Module name"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                },
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
