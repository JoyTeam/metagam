from mg.constructor import *
import mg
from uuid import uuid4
from PIL import Image
import cStringIO

re_del = re.compile(r'^del/(.+)$')
re_recipes_cmd = re.compile(r'^(view|ingredients|production)/([0-9a-f]+)(?:|/(.+))$')
re_truncate = re.compile(r'^(.{17}).{3}.+$', re.DOTALL)

class Crafting(ConstructorModule):
    def register(self):
        self.rhook("crafting.categories", self.categories)
        self.rhook("crafting.recipes", self.recipes)
        self.rhook("interfaces.list", self.interfaces_list)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("interface-crafting.action-default", self.interface_crafting, priv="logged")

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

    def interfaces_list(self, types):
        types.append(("crafting", self._("Crafting")))

    def gameinterface_buttons(self, buttons):
        funcs = self.call("globfunc.functions")
        for func in funcs:
            if func["tp"] == "crafting":
                buttons.append({
                    "id": func["id"],
                    "href": "/globfunc/%s" % func["id"],
                    "target": "main",
                    "icon": "crafting.png",
                    "title": self._("Crafting"),
                    "block": "left-menu",
                    "order": 4,
                })

    def interface_crafting(self, func_id, base_url, func, args, vars):
        req = self.req()
        if req.ok():
            lock_objects = []
            if req.ok():
                lock_objects.append(character.lock)
                lock_objects.append(character.inventory.lock_key)
            with self.lock(lock_objects):
                character.inventory.load()
                pass
        categories = self.call("crafting.categories")
        recipes = self.call("crafting.recipes")
        rcategories = []
        for cat in categories:
            rrecipes = []
            for rcp in recipes:
                if rcp["category"] == cat["id"]:
                    rrecipe = {
                        "id": rcp["id"],
                        "name": htmlescape(rcp.get("name")),
                        "image": None,
                        "params": None,
                        "description": rcp.get("description"),
                    }
                    rrecipes.append(rrecipe)
            if rrecipes:
                rcategories.append({
                    "id": cat["id"],
                    "name_html_js": jsencode(htmlescape(cat.get("name"))),
                    "visible": func.get("default_category") == cat["id"],
                    "recipes": rrecipes,
                })
        vars["categories"] = rcategories
        content = self.call("game.parse_internal", func.get("shop_template", "crafting-recipes-layout.html"), vars)
        content = self.call("game.parse_internal", "crafting-recipes.html", vars, content)
        self.call("game.response_internal", "crafting-global.html", vars, content)

class CraftingAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-peaceful.index", self.menu_peaceful_index)
        self.rhook("menu-admin-crafting.index", self.menu_crafting_index)
        self.rhook("ext-admin-crafting.categories", self.admin_categories, priv="peaceful.crafting")
        self.rhook("headmenu-admin-crafting.categories", self.headmenu_categories)
        self.rhook("ext-admin-crafting.recipes", self.admin_recipes, priv="peaceful.crafting")
        self.rhook("headmenu-admin-crafting.recipes", self.headmenu_recipes)
        self.rhook("admin-globfunc.predefined", self.globfuncs)
        self.rhook("admin-interfaces.form", self.form_render)
        self.rhook("admin-interface-crafting.store", self.form_store)

    def globfuncs(self, funcs):
        funcs.append({
            "id": "u_crafting",
            "type": "crafting",
            "title": self._("Crafting"),
            "tp": "crafting",
        })

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
        m = re_recipes_cmd.match(args)
        if m:
            cmd, recipe_id, args = m.group(1, 2, 3)
            for rcp in self.call("crafting.recipes"):
                if rcp["id"] == recipe_id:
                    if cmd == "view":
                        return [htmlescape(rcp.get("name")), "crafting/recipes"]
                    elif cmd == "ingredients":
                        if args == "new":
                            return [self._("New ingredient"), "crafting/recipes/view/%s" % recipe_id]
                        elif args:
                            for ing in rcp.get("ingredients", []):
                                if ing["id"] == args:
                                    item_type = self.item_type(ing["item_type"])
                                    return [self._("Ingredient '%s'") % htmlescape(item_type.name), "crafting/recipes/view/%s" % recipe_id]
                    elif cmd == "production":
                        if args == "new":
                            return [self._("New product"), "crafting/recipes/view/%s" % recipe_id]
                        elif args:
                            for ing in rcp.get("production", []):
                                if ing["id"] == args:
                                    item_type = self.item_type(ing["item_type"])
                                    return [self._("Product '%s'") % htmlescape(item_type.name), "crafting/recipes/view/%s" % recipe_id]
        elif args == "new":
            return [self._("New recipe"), "crafting/recipes"]
        elif args:
            for rcp in self.call("crafting.recipes"):
                if rcp["id"] == args:
                    return [self._("Editing"), "crafting/recipes/view/%s" % args]
        return self._("Crafting recipes")

    def admin_recipes(self):
        categories = self.call("crafting.categories")
        recipes = self.call("crafting.recipes")
        req = self.req()
        m = re_recipes_cmd.match(req.args)
        if m:
            cmd, recipe_id, args = m.group(1, 2, 3)
            for recipe in recipes:
                if recipe["id"] == recipe_id:
                    if cmd == "view":
                        return self.admin_recipe_view(recipe, args)
                    if cmd == "ingredients":
                        return self.admin_recipe_ingredients(recipes, recipe, args)
                    if cmd == "production":
                        return self.admin_recipe_production(recipes, recipe, args)
            self.call("web.not_found")
        m = re_del.match(req.args)
        if m:
            rcpid = m.group(1)
            for rcp in recipes:
                if rcp["id"] == rcpid and rcp.get("image"):
                    self.call("cluster.static_delete", rcp["image"])
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
                self.call("web.upload_handler")
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
                # image
                old_image = rcp.get("image")
                image_data = req.param_raw("image")
                if image_data:
                    try:
                        image = Image.open(cStringIO.StringIO(image_data))
                        if image.load() is None:
                            raise IOError
                    except IOError:
                        errors["image"] = self._("Image format not recognized")
                    else:
                        ext, content_type = self.image_format(image)
                        form = image.format
                        if ext is None:
                            errors["image"] = self._("Valid formats are: PNG, GIF, JPEG")
                        else:
                            w, h = image.size
                            if h != 100:
                                w = w * 100 / h
                                h = 100
                            if w < 100:
                                h = h * 100 / w
                                w = 100
                            left = (w - 100) / 2
                            top = (h - 100) / 2
                            image = image.resize((w, h), Image.ANTIALIAS).crop((left, top, left + 100, top + 100))
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # upload image
                data = cStringIO.StringIO()
                if form == "JPEG":
                    image.save(data, form, quality=95)
                else:
                    image.save(data, form)
                rcp["image"] = self.call("cluster.static_upload", "recipe", ext, content_type, data.getvalue())
                # save
                recipes = [c for c in recipes if c["id"] != rcp["id"]]
                recipes.append(rcp)
                recipes.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["name"], y["name"]))
                config = self.app().config_updater()
                config.set("crafting.recipes", recipes)
                config.store()
                # delete old image
                if image_data and old_image:
                    self.call("cluster.static_delete", old_image)
                self.call("admin.redirect", "crafting/recipes/view/%s" % rcp["id"])
            fields = [
                {"name": "name", "label": self._("Recipe name"), "value": rcp.get("name")},
                {"name": "order", "label": self._("Sorting order"), "value": rcp.get("order"), "inline": True},
                {"name": "category", "label": self._("Category"), "type": "combo", "value": rcp.get("category"), "values": categories_values},
                {"name": "image", "type": "fileuploadfield", "label": self._("Recipe image")},
            ]
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
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
                        u'<hook:admin.link href="crafting/recipes/view/%s" title="%s" />' % (rcp["id"], self._("open")),
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
                    u'<hook:admin.link href="crafting/recipes/view/%s" title="%s" />' % (rcp["id"], self._("open")),
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

    def form_render(self, fields, func):
        categories = self.call("crafting.categories")
        recipes = self.call("crafting.recipes")
        fields.append({
            "name": "default_category",
            "type": "combo",
            "label": self._("Open this category by default"),
            "value": func.get("default_category"),
            "values": [(cat["id"], cat["name"]) for cat in categories],
        })
        for cat in categories:
            first_recipe = True
            col = 0
            cols = 3
            for rcp in recipes:
                if rcp["category"] == cat["id"]:
                    if first_recipe:
                        fields.append({
                            "type": "header",
                            "html": self._("Available recipes: %s") % htmlescape(cat["name"]),
                            "condition": "[tp] == 'crafting'",
                        })
                        first_recipe = False
                    key = "crafting_%s" % rcp["id"]
                    fields.append({
                        "type": "checkbox",
                        "name": key,
                        "checked": func.get(key),
                        "label": htmlescape(rcp.get("name")),
                        "condition": "[tp] == 'crafting'",
                        "inline": col != 0,
                    })
                    col = (col + 1) % cols
            while col:
                fields.append({
                    "type": "empty",
                    "condition": "[tp] == 'crafting'",
                    "inline": col != 0,
                })
                col = (col + 1) % cols

    def form_store(self, func, errors):
        req = self.req()
        categories = self.call("crafting.categories")
        recipes = self.call("crafting.recipes")
        used_categories = set()
        for cat in categories:
            for rcp in recipes:
                if rcp["category"] == cat["id"]:
                    key = "crafting_%s" % rcp["id"]
                    if req.param(key):
                        func[key] = True
                        used_categories.add(cat["id"])
                    elif func.get(key):
                        del func[key]
        default_category = req.param("v_default_category")
        if not used_categories:
            self.call("web.response_json", {"success": False, "errormsg": self._("No recipes selected")})
        elif default_category not in used_categories:
            errors["v_default_category"] = self._("Select a category which contains at least 1 enabled recipe")
        else:
            func["default_category"] = default_category

    def admin_recipe_view(self, recipe, args):
        ingredients = []
        for ing in recipe.get("ingredients", []):
            item_type = self.item_type(ing.get("item_type"))
            quantity = self.call("script.unparse-expression", ing.get("quantity"))
            quantity = re_truncate.sub(r'\1...', quantity)
            requirements = []
            if ing.get("equipped"):
                requirements.append(self._("item///must be equipped"))
            ingredients.append([
                htmlescape(item_type.name),
                htmlescape(quantity),
                '<div class="nowrap">%s</div>' % ('<br />'.join(requirements)),
                ing.get("order"),
                u'<hook:admin.link href="crafting/recipes/ingredients/%s/%s" title="%s" />' % (recipe["id"], ing["id"], self._("edit")),
                u'<hook:admin.link href="crafting/recipes/ingredients/%s/del/%s" title="%s" confirm="%s" />' % (recipe["id"], ing["id"], self._("delete"), self._("Are you sure want to delete this ingredient?")),
            ])
        production = []
        for prod in recipe.get("production", []):
            item_type = self.item_type(prod.get("item_type"))
            quantity = self.call("script.unparse-expression", prod.get("quantity"))
            quantity = re_truncate.sub(r'\1...', quantity)
            mods = []
            for key in sorted(prod.get("mods", {}).keys()):
                line = u"%s = %s" % (key, self.call("script.unparse-expression", prod["mods"][key]))
                line = re_truncate.sub(r'\1...', line)
                mods.append(line)
            production.append([
                htmlescape(item_type.name),
                htmlescape(quantity),
                '<div class="nowrap">%s</div>' % ('<br />'.join(mods)),
                prod.get("order"),
                u'<hook:admin.link href="crafting/recipes/production/%s/%s" title="%s" />' % (recipe["id"], prod["id"], self._("edit")),
                u'<hook:admin.link href="crafting/recipes/production/%s/del/%s" title="%s" confirm="%s" />' % (recipe["id"], prod["id"], self._("delete"), self._("Are you sure want to delete this product?")),
            ])
        params = [
            [self._("recipe///Name"), htmlescape(recipe["name"])],
            [self._("Sorting order"), recipe["order"]],
        ]
        if recipe.get("image"):
            params.append([self._("Recipe image"), '<img src="%s" alt="" />' % recipe["image"]])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "crafting/recipes/%s" % recipe["id"],
                            "text": self._("Edit recipe parameters"),
                            "lst": True,
                        },
                    ],
                    "rows": params,
                },
                {
                    "title": self._("Ingredients"),
                    "links": [
                        {
                            "hook": "crafting/recipes/ingredients/%s/new" % recipe["id"],
                            "text": self._("New ingredient"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Item name"),
                        self._("Quantity (in fractions of items)"),
                        self._("Special requirements"),
                        self._("Sorting order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": ingredients,
                },
                {
                    "title": self._("Production"),
                    "links": [
                        {
                            "hook": "crafting/recipes/production/%s/new" % recipe["id"],
                            "text": self._("New product"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Item name"),
                        self._("Quantity (in whole items)"),
                        self._("Modifications"),
                        self._("Sorting order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": production,
                },
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def load_item_types(self):
        categories = self.call("item-types.categories", "admin")
        item_types = self.call("item-types.list")
        valid_item_types = set()
        item_type_values = []
        item_type_values.append((None, None))
        for cat in categories:
            first_item_type = True
            for item_type in item_types:
                if item_type.get("cat-admin") == cat["id"]:
                    if first_item_type:
                        item_type_values.append((None, cat["name"]))
                        first_item_type = False
                    item_type_values.append((item_type.uuid, u"----- %s" % item_type.get("name")))
                    valid_item_types.add(item_type.uuid)
        return item_type_values, valid_item_types

    def admin_recipe_ingredients(self, recipes, recipe, args):
        req = self.req()
        item_type_values, valid_item_types = self.load_item_types()
        ingredients = recipe.get("ingredients", [])
        m = re_del.match(args)
        if m:
            uuid = m.group(1)
            ingredients = [i for i in ingredients if i["id"] != uuid]
            recipe["ingredients"] = ingredients
            config = self.app().config_updater()
            config.set("crafting.recipes", recipes)
            config.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe["id"])
        if args == "new":
            ing = {
                "id": uuid4().hex,
                "order": ingredients[-1]["order"] + 10.0 if ingredients else 0.0,
            }
        else:
            for i in ingredients:
                if i["id"] == args:
                    ing = i.copy()
                    break
            if ing is None:
                self.call("admin.redirect", "crafting/recipes/view/%s" % recipe["id"])
        if req.ok():
            errors = {}
            # item_type
            item_type = req.param("v_item_type")
            if not item_type:
                errors["v_item_type"] = self._("This field is mandatory")
            elif item_type not in valid_item_types:
                errors["v_item_type"] = self._("Make a valid selection")
            else:
                ing["item_type"] = item_type
            # order
            ing["order"] = floatz(req.param("order"))
            # quantity
            char = self.character(req.user())
            ing["quantity"] = self.call("script.admin-expression", "quantity", errors, globs={"char": char})
            # equipped
            ing["equipped"] = True if req.param("equipped") else False
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save
            ingredients = [i for i in ingredients if i["id"] != ing["id"]]
            ingredients.append(ing)
            ingredients.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            recipe["ingredients"] = ingredients
            config = self.app().config_updater()
            config.set("crafting.recipes", recipes)
            config.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe["id"])
        fields = [
            {"name": "item_type", "label": self._("Item type"), "type": "combo", "values": item_type_values, "value": ing.get("item_type")},
            {"name": "order", "label": self._("Sorting order"), "value": ing.get("order"), "inline": True},
            {"name": "quantity", "label": self._("Quantity of fractions to take") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", ing.get("quantity", 1))},
            {"name": "equipped", "label": self._("Item must be equipped"), "type": "checkbox", "checked": ing.get("equipped")},
        ]
        self.call("admin.form", fields=fields)

    def admin_recipe_production(self, recipes, recipe, args):
        req = self.req()
        item_type_values, valid_item_types = self.load_item_types()
        params = self.call("item-types.params")
        production = recipe.get("production", [])
        m = re_del.match(args)
        if m:
            uuid = m.group(1)
            production = [p for p in production if p["id"] != uuid]
            recipe["production"] = production
            config = self.app().config_updater()
            config.set("crafting.recipes", recipes)
            config.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe["id"])
        if args == "new":
            prod = {
                "id": uuid4().hex,
                "order": production[-1]["order"] + 10.0 if production else 0.0,
            }
        else:
            for p in production:
                if p["id"] == args:
                    prod = p.copy()
                    break
            if prod is None:
                self.call("admin.redirect", "crafting/recipes/view/%s" % recipe["id"])
        if req.ok():
            errors = {}
            # item_type
            item_type = req.param("v_item_type")
            if not item_type:
                errors["v_item_type"] = self._("This field is mandatory")
            elif item_type not in valid_item_types:
                errors["v_item_type"] = self._("Make a valid selection")
            else:
                prod["item_type"] = item_type
            # order
            prod["order"] = floatz(req.param("order"))
            # quantity
            char = self.character(req.user())
            prod["quantity"] = self.call("script.admin-expression", "quantity", errors, globs={"char": char})
            # mods
            mods = {}
            for param in params:
                val = req.param("p_%s" % param["code"]).strip()
                if val == "":
                    continue
                mods[param["code"]] = self.call("script.admin-expression", "p_%s" % param["code"], errors, globs={"char": char})
            prod["mods"] = mods
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save
            production = [p for p in production if p["id"] != prod["id"]]
            production.append(prod)
            production.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            recipe["production"] = production
            config = self.app().config_updater()
            config.set("crafting.recipes", recipes)
            config.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe["id"])
        fields = [
            {"name": "item_type", "label": self._("Item type"), "type": "combo", "values": item_type_values, "value": prod.get("item_type")},
            {"name": "order", "label": self._("Sorting order"), "value": prod.get("order"), "inline": True},
            {"name": "quantity", "label": self._("Quantity of items to give") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", prod.get("quantity", 1))},
        ]
        if params:
            fields.append({"type": "header", "html": self._("Override parameters")})
            fields.append({"type": "html", "html": self._("If you remain a field empty its value will be taken from the item type parameters")})
            mods = prod.get("mods", {})
            grp = None
            for param in params:
                if param["grp"] != grp and param["grp"] != "":
                    fields.append({"type": "header", "html": param["grp"]})
                    grp = param["grp"]
                fields.append({"name": "p_%s" % param["code"], "label": u"%s%s" % (param["name"], self.call("script.help-icon-expressions")), "value": mods.get(param["code"]), "value": req.param("p_%s" % param["code"])})
        self.call("admin.form", fields=fields)
