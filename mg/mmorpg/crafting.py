from mg.constructor import *
import mg
from uuid import uuid4

re_del = re.compile(r'^del/(.+)$')

class Crafting(ConstructorModule):
    def register(self):
        self.rhook("crafting.categories", self.categories)
        self.rhook("crafting.recipes", self.recipes)

    def child_modules(self):
        return ["mg.mmorpg.crafting.CraftingAdmin"]

    def categories(self):
        categories = self.conf("crafting.categories")
        if categories is not None:
            return categories
        return [
            {
                "id": "potions",
                "name": self._("Potions"),
                "order": 10.0,
            },
            {
                "id": "elixirs",
                "name": self._("Elixirs"),
                "order": 20.0,
            },
        ]

    def recipes(self):
        recipes = self.conf("crafting.recipes")
        if recipes is not None:
            return recipes
        return []

class CraftingAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-peaceful.index", self.menu_peaceful_index)
        self.rhook("menu-admin-crafting.index", self.menu_crafting_index)
        self.rhook("ext-admin-crafting.categories", self.admin_categories, priv="peaceful.crafting")
        self.rhook("headmenu-admin-crafting.categories", self.headmenu_categories)
        self.rhook("ext-admin-crafting.recipes", self.admin_recipes, priv="peaceful.crafting")
        self.rhook("headmenu-admin-crafting.recipes", self.headmenu_recipes)

    def permissions_list(self, perms):
        perms.append({"id": "peaceful.crafting", "name": self._("Peaceful activities: crafting")})

    def menu_peaceful_index(self, menu):
        menu.append({"id": "crafting.index", "text": self._("Crafting"), "order": 10})

    def menu_crafting_index(self, menu):
        req = self.req()
        if req.has_access("peaceful.crafting"):
            menu.append({"id": "crafting/categories", "text": self._("Recipes categories"), "order": 0, "leaf": True})
            menu.append({"id": "crafting/recipes", "text": self._("Recipes"), "order": 10, "leaf": True})

    def headmenu_categories(self, args):
        if args == "new":
            return [self._("New category"), "crafting/categories"]
        elif args:
            for cat in self.call("crafting.categories"):
                if cat["id"] == args:
                    return [htmlescape(cat.get("name")), "crafting/categories"]
        return self._("Crafting recipes categories")

    def admin_categories(self):
        categories = self.call("crafting.categories")
        req = self.req()
        m = re_del.match(req.args)
        if m:
            catid = m.group(1)
            categories = [cat for cat in categories if cat["id"] != catid]
            config = self.app().config_updater()
            config.set("crafting.categories", categories)
            config.store()
            self.call("admin.redirect", "crafting/categories")
        if req.args:
            if req.args == "new":
                cat = {
                    "id": uuid4().hex
                }
                order = None
                for c in categories:
                    if order is None or c["order"] > order:
                        order = c["order"]
                if order is None:
                    cat["order"] = 0.0
                else:
                    cat["order"] = order + 10.0
            else:
                cat = None
                for c in categories:
                    if c["id"] == req.args:
                        cat = c
                        break
                if cat is None:
                    self.call("admin.redirect", "crafting/categories")
            if req.ok():
                cat = cat.copy()
                errors = {}
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    cat["name"] = name
                # order
                cat["order"] = floatz(req.param("order"))
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # save
                categories = [c for c in categories if c["id"] != cat["id"]]
                categories.append(cat)
                categories.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["name"], y["name"]))
                config = self.app().config_updater()
                config.set("crafting.categories", categories)
                config.store()
                self.call("admin.redirect", "crafting/categories")
            fields = [
                {"name": "name", "label": self._("Category name"), "value": cat.get("name")},
                {"name": "order", "label": self._("Sorting order"), "value": cat.get("order"), "inline": True},
            ]
            self.call("admin.form", fields=fields)
        rows = []
        for cat in categories:
            rows.append([
                htmlescape(cat.get("name")),
                cat.get("order"),
                u'<hook:admin.link href="crafting/categories/%s" title="%s" />' % (cat["id"], self._("edit")),
                u'<hook:admin.link href="crafting/categories/del/%s" title="%s" confirm="%s" />' % (cat["id"], self._("delete"), self._("Are you sure want to delete this category?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "crafting/categories/new",
                            "text": self._("New category"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Category name"),
                        self._("Sorting order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                },
            ],
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_recipes(self, args):
        if args == "new":
            return [self._("New recipe"), "crafting/recipes"]
        elif args:
            for rcp in self.call("crafting.recipes"):
                if rcp["id"] == args:
                    return [htmlescape(rcp.get("name")), "crafting/recipes"]
        return self._("Crafting recipes")

    def admin_recipes(self):
        categories = self.call("crafting.categories")
        recipes = self.call("crafting.recipes")
        req = self.req()
        m = re_del.match(req.args)
        if m:
            rcpid = m.group(1)
            recipes = [rcp for rcp in recipes if rcp["id"] != rcpid]
            config = self.app().config_updater()
            config.set("crafting.recipes", recipes)
            config.store()
            self.call("admin.redirect", "crafting/recipes")
        if req.args:
            if req.args == "new":
                rcp = {
                    "id": uuid4().hex
                }
                order = None
                for c in recipes:
                    if order is None or c["order"] > order:
                        order = c["order"]
                if order is None:
                    rcp["order"] = 0.0
                else:
                    rcp["order"] = order + 10.0
            else:
                rcp = None
                for c in recipes:
                    if c["id"] == req.args:
                        rcp = c
                        break
                if rcp is None:
                    self.call("admin.redirect", "crafting/recipes")
            # prepare list of categories
            valid_categories = set()
            categories_values = [(None, self._("Select a category"))]
            for cat in categories:
                valid_categories.add(cat["id"])
                categories_values.append((cat["id"], cat["name"]))
            if req.ok():
                rcp = rcp.copy()
                errors = {}
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    rcp["name"] = name
                # order
                rcp["order"] = floatz(req.param("order"))
                # category
                category = req.param("v_category")
                if category not in valid_categories:
                    errors["v_category"] = self._("Select valid category")
                else:
                    rcp["category"] = category
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # save
                recipes = [c for c in recipes if c["id"] != rcp["id"]]
                recipes.append(rcp)
                recipes.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["name"], y["name"]))
                config = self.app().config_updater()
                config.set("crafting.recipes", recipes)
                config.store()
                self.call("admin.redirect", "crafting/recipes")
            fields = [
                {"name": "name", "label": self._("Recipe name"), "value": rcp.get("name")},
                {"name": "order", "label": self._("Sorting order"), "value": rcp.get("order"), "inline": True},
                {"name": "category", "label": self._("Category"), "type": "combo", "value": rcp.get("category"), "values": categories_values},
            ]
            self.call("admin.form", fields=fields)
        if not categories:
            self.call("admin.response", u'<div class="admin-alert">%s</div>' % (self._("Before creating recipes go to the '{href}' page first and create one or more categories").format(href=u'<hook:admin.link href="crafting/categories" title="%s" />' % self._("Recipes categories"))), {})
        tables = [
            {
                "links": [
                    {
                        "hook": "crafting/recipes/new",
                        "text": self._("New recipe"),
                        "lst": True,
                    },
                ],
            }
        ]
        displayed_recipes = set()
        header = [
            self._("Recipe name"),
            self._("Sorting order"),
            self._("Editing"),
            self._("Deletion"),
        ]
        for cat in categories:
            rows = []
            for rcp in recipes:
                if rcp["category"] == cat["id"]:
                    rows.append([
                        htmlescape(rcp.get("name")),
                        rcp.get("order"),
                        u'<hook:admin.link href="crafting/recipes/%s" title="%s" />' % (rcp["id"], self._("edit")),
                        u'<hook:admin.link href="crafting/recipes/del/%s" title="%s" confirm="%s" />' % (rcp["id"], self._("delete"), self._("Are you sure want to delete this recipe?")),
                    ])
                    displayed_recipes.add(rcp["id"])
            if rows:
                tables.append({
                    "title": htmlescape(cat["name"]),
                    "header": header,
                    "rows": rows,
                })
        rows = []
        for rcp in recipes:
            if rcp["id"] not in displayed_recipes:
                rows.append([
                    htmlescape(rcp.get("name")),
                    rcp.get("order"),
                    u'<hook:admin.link href="crafting/recipes/%s" title="%s" />' % (rcp["id"], self._("edit")),
                    u'<hook:admin.link href="crafting/recipes/del/%s" title="%s" confirm="%s" />' % (rcp["id"], self._("delete"), self._("Are you sure want to delete this recipe?")),
                ])
        if rows:
            tables.append({
                "title": self._("Uncategorized"),
                "header": header,
                "rows": rows,
            })
        vars = {
            "tables": tables
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
