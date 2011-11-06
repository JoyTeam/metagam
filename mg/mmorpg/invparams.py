from mg.constructor.params import *
from mg.mmorpg.inventory_classes import *
import re

re_itemparam = re.compile(r'^itemparam/(.+)$')
re_item_params = re.compile(r'item\.p_([a-zA-Z_][a-zA-Z0-9_]*)')

class ItemTypeParamsAdmin(ParamsAdmin):
    def __init__(self, app, fqn):
        ParamsAdmin.__init__(self, app, fqn)
        self.kind = "item-types"

    @property
    def title(self):
        return self._("Items parameters")

    def register(self):
        ParamsAdmin.register(self)
        self.rhook("menu-admin-inventory.index", self.menu_inventory_index)
        self.rhook("item-types.params-url", self.params_url)
        self.rhook("item-types.params-redirect", self.params_redirect)
        self.rhook("item-types.params-obj", self.params_obj)
        self.rhook("item-types.script-globs", self.script_globs)
        self.rhook("headmenu-admin-item-types.paramview", self.headmenu_paramview)
        self.rhook("ext-admin-item-types.paramview", self.admin_paramview, priv="inventory.params-view")

    def script_globs(self):
        req = self.req()
        item_type = ItemType(self.app(), "test")
        try:
            info = item_type.db_item_type
        except ObjectNotFoundException:
            info = self.obj(DBItemType, item_type.uuid, data={})
            info.set("test", 1)
            info.store()
        return {"item": item_type}

    def params_url(self, uuid):
        return "item-types/paramview/%s" % uuid

    def params_redirect(self, uuid):
        self.call("admin.redirect", "item-types/paramview/%s" % uuid)

    def params_obj(self, uuid):
        return self.item_type(uuid).db_params

    def menu_inventory_index(self, menu):
        req = self.req()
        if req.has_access("item-types.params"):
            menu.append({"id": "item-types/params", "text": self.title, "leaf": True, "order": 5})

    def headmenu_paramview(self, args):
        return [self._("Parameters"), "item-types/editor/%s" % args]

    def admin_paramview(self):
        req = self.req()
        item_type = self.item_type(req.args)
        if not item_type.valid:
            self.call("web.not_found")
        may_edit = req.has_access("item-types.params-edit")
        header = [self._("Code"), self._("parameter///Name"), self._("Value"), "HTML"]
        if may_edit:
            header.append(self._("Changing"))
        params = []
        self.admin_view_params(item_type, params, may_edit)
        vars = {
            "tables": [
                {
                    "header": header,
                    "rows": params,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

class ItemTypeParams(Params):
    def __init__(self, app, fqn):
        Params.__init__(self, app, fqn)
        self.kind = "item-types"

    def child_modules(self):
        return ["mg.mmorpg.invparams.ItemTypeParamsAdmin", "mg.mmorpg.invparams.ItemTypeParamsLibrary"]

    def register(self):
        Params.register(self)
        self.rhook("item-types.param-library", self.param_library)

    def param_library(self, param):
        return "/library/itemparams#%s" % param["code"]

class ItemTypeParamsLibrary(ParamsLibrary):
    def __init__(self, app, fqn):
        ParamsLibrary.__init__(self, app, fqn)
        self.kind = "item-types"

    def register(self):
        ParamsLibrary.register(self)
        self.rdep(["mg.mmorpg.invparams.ItemTypeParams"])
        self.rhook("library-grp-index.pages", self.library_index_pages)
        self.rhook("library-page-itemparams.content", self.library_page_itemparams)
        for param in self.call("item-types.params", load_handlers=False):
            if param.get("library_visible") and param.get("library_table"):
                self.rhook("library-page-itemparam/%s.content" % param["code"], self.library_page_itemparam)

    def library_index_pages(self, pages):
        pages.append({"page": "itemparams", "order": 50})

    def library_page_itemparams(self, render_content):
        pageinfo = {
            "code": "itemparams",
            "title": self._("Items parameters"),
            "keywords": self._("items parameters"),
            "description": self._("This page describes parameters of inventory items"),
            "parent": "index",
        }
        if render_content:
            params = []
            grp = None
            for param in self.call("item-types.params"):
                if param.get("library_visible") and not param.get("library_uri"):
                    if param["grp"] != "" and param["grp"] != grp:
                        params.append({"header": htmlescape(param["grp"])})
                        grp = param["grp"]
                    description = param.get("description")
                    if description is None:
                        if param["type"] == 0:
                            description = self._("Parameter stored in the database")
                        else:
                            description = self._("Derived (calculated) parameter")
                    rparam = {
                        "code": param["code"],
                        "name": htmlescape(param["name"]),
                        "description": htmlescape(description),
                    }
                    if param.get("library_table"):
                        rparam["tables"] = {
                            "uri": "/library/itemparam/%s" % param["code"],
                        }
                    params.append(rparam)
            vars = {
                "params": params,
                "OpenTable": self._("Open table"),
                "ItemsParams": self._("Items parameters"),
            }
            pageinfo["content"] = self.call("socio.parse", "library-itemparams.html", vars)
        return pageinfo

    def param_name(self, m):
        param = self.call("item-types.param", m.group(1))
        if param:
            return param["name"]
        else:
            return m.group(0)

    def library_page_itemparam(self, render_content):
        if render_content:
            req = self.req()
            m = re_itemparam.match(req.args)
            if not m:
                return None
            param = self.call("item-types.param", m.group(1))
            if not param or not param.get("library_table"):
                return None
            vars = {
                "name": htmlescape(param["name"]),
                "paramdesc": htmlescape(param["description"]),
            }
            # table rows
            levels = set()
            values = {}
            visuals = {}
            # table header
            header = []
            if param.get("values_table"):
                expr = re_item_params.sub(self.param_name, self.call("script.unparse-expression", param["expression"]))
                header.append(htmlescape(expr))
                for ent in param.get("values_table"):
                    levels.add(ent[1])
                    values[ent[1]] = ent[0]
            header.append(vars["name"])
            if param.get("visual_table"):
                header.append(self._("Description"))
                for ent in param.get("visual_table"):
                    levels.add(ent[0])
                    visuals[ent[0]] = ent[1]
            rows = []
            for level in sorted(levels):
                row = []
                if param.get("values_table"):
                    row.append(values.get(level))
                row.append(level)
                if param.get("visual_table"):
                    row.append(visuals.get(level))
                rows.append(row)
            vars["paramtable"] = {
                "header": header,
                "rows": rows,
            }
            return {
                "code": "itemparam/%s" % param["code"],
                "title": vars["name"],
                "keywords": '%s, %s' % (self._("parameter"), vars["name"]),
                "description": self._("This page describes parameter %s") % vars["name"],
                "content": self.call("socio.parse", "library-itemparam.html", vars),
                "parent": "itemparams",
            }
