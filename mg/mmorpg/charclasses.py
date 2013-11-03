from mg.constructor import *
import re

re_param_edit = re.compile(r'^([a-z_][a-z0-9_]*)(?:|/(.+))$', re.IGNORECASE)

class CharClassesAdmin(ConstructorModule):
    def __init__(self, *args, **kwargs):
        ConstructorModule.__init__(self, *args, **kwargs)
        self.hide_params = set(["visual_mode", "visual_template", "visual_table"])

    def register(self):
        self.rhook("admin-characters.params-form-render", self.params_form_render)
        self.rhook("admin-characters.params-form-save", self.params_form_save)
        self.rhook("admin-characters.params-stored", self.params_stored)
        self.rhook("menu-admin-characters.index", self.menu_characters_index)
        self.rhook("ext-admin-characters.classes", self.admin_characters_classes, priv="characters.params")
        self.rhook("headmenu-admin-characters.classes", self.headmenu_characters_classes)
        self.rhook("advice-admin-characters.classes", self.advice_charclasses)
        self.rhook("admin-gameinterface.design-files", self.design_files)

    def design_files(self, files):
        files.append({"filename": "charclass-select.html", "description": self._("Character class selector"), "doc": "/doc/design/character-classes"})
        files.append({"filename": "charclass-select-layout.html", "description": self._("Character class selector layout"), "doc": "/doc/design/character-classes"})

    def advice_charclasses(self, args, advice):
        advice.append({"title": self._("Character classes documentation"), "content": self._('You can find detailed information on the character classes system in the <a href="//www.%s/doc/character-classes" target="_blank">character classes page</a> in the reference manual.') % self.main_host})

    def params_form_render(self, param, fields):
        i = 0
        while i < len(fields):
            field = fields[i]
            name = field.get("name")
            if name in self.hide_params:
                if field.get("condition"):
                    field["condition"] = "(%s) && ![charclass]" % field["condition"]
                else:
                    field["condition"] = "![charclass]"
            if name == "owner_visible":
                fields.insert(i + 1, {"name": "charclass", "type": "checkbox", "checked": param.get("charclass"), "label": self._("This parameter is a character class (race, profession, etc)")})
                fields.insert(i + 2, {"name": "require", "value": self.call("script.unparse-expression", param.get("require", 0)), "label": self._("Whether selection of this class is required for the character (0 - never require, 1 - require for everybody)") + self.call("script.help-icon-expressions"), "condition": "[charclass]"})
                i += 2
            i += 1

    def params_form_save(self, param, new_param, errors):
        req = self.req()
        if req.param("charclass"):
            new_param["charclass"] = True
            for key in self.hide_params:
                if key in new_param:
                    del new_param[key]
                if key in errors:
                    del errors[key]
                v_key = "v_%s" % key
                if v_key in errors:
                    del errors[v_key]
            new_param["require"] = self.call("script.admin-expression", "require", errors, globs=self.call("characters.script-globs"))
            if new_param.get("type") != 0:
                errors["v_type"] = self._("Character class must be stored in DB")

    def menu_characters_index(self, menu):
        req = self.req()
        if req.has_access("characters.params"):
            menu.append({"id": "characters/classes", "text": self._("Races and classes"), "leaf": True, "order": 26})

    def headmenu_characters_classes(self, args):
        m = re_param_edit.match(args)
        if m:
            param_id, cmd = m.group(1, 2)
            if cmd == "new":
                return [self._("New variant"), "characters/classes/%s" % param_id]
            elif cmd is None:
                param = self.call("characters.param", param_id)
                if param:
                    return [htmlescape(param.get("name")), "characters/classes"]
            else:
                classes = self.conf("charclasses.%s" % param_id, {})
                cls = classes.get(cmd) or classes.get(intz(cmd))
                if cls:
                    return [htmlescape(cls.get("name")), "characters/classes/%s" % param_id]
        return self._("Races and classes")

    def admin_characters_classes(self):
        req = self.req()
        m = re_param_edit.match(req.args)
        if m:
            param_id, cmd = m.group(1, 2)
            param = self.call("characters.param", param_id)
            if not param or not param.get("charclass"):
                self.call("admin.redirect", "characters/classes")
            classes = self.conf("charclasses.%s" % param["code"], {})
            if cmd is None:
                # list of class variants
                rows = []
                cls_list = classes.items()
                cls_list.sort(cmp=lambda x, y: cmp(x[1].get("order"), y[1].get("order")) or cmp(x[0], y[0]))
                for cls_id, cls in cls_list:
                    rows.append([
                        cls_id,
                        htmlescape(cls["name"]),
                        cls["order"],
                        u'<hook:admin.link href="characters/classes/%s/%s" title="%s" />' % (param["code"], cls_id, self._("edit")),
                    ])
                vars = {
                    "tables": [
                        {
                            "links": [
                                {"hook": "characters/classes/%s/new" % param["code"], "text": self._("New variant for this class"), "lst": True},
                            ],
                            "header": [
                                self._("Value"),
                                self._("Name"),
                                self._("Order"),
                                self._("Editing"),
                            ],
                            "rows": rows,
                        }
                    ]
                }
            else:
                # class editor
                classes = classes.copy()
                # Converting integer hash keys (old format) to strings (new format)
                for cls_id, cls in classes.items():
                    if type(cls_id) == int:
                        del classes[cls_id]
                        if str(cls_id) not in classes:
                            classes[str(cls_id)] = cls
                if cmd == "new":
                    cls = {}
                    max_id = None
                    max_order = None
                    for c_id, c in classes.iteritems():
                        if max_id is None or intz(c_id) > max_id:
                            max_id = intz(c_id)
                        if max_order is None or c["order"] > max_order:
                            max_order = c["order"]
                    cls_id = str(max_id + 1 if max_id is not None else 1)
                    cls["order"] = max_order + 10 if max_order is not None else 0.0
                    classes[cls_id] = cls
                else:
                    cls_id = cmd
                    cls = classes.get(cls_id)
                    if not cls:
                        self.call("admin.redirect", "characters/classes/%s" % param_id)
                    cls = cls.copy()
                    classes[cls_id] = cls
                if req.ok():
                    errors = {}
                    name = req.param("name").strip()
                    if not name:
                        errors["name"] = self._("This field is mandatory")
                    else:
                        cls["name"] = name
                    cls["order"] = floatz(req.param("order"))
                    cls["description"] = req.param("description").strip()
                    cls["available"] = self.call("script.admin-expression", "available", errors, globs=self.call("characters.script-globs"))
                    cls["library_visible"] = True if req.param("library_visible") else False
                    cls["api_visible"] = True if req.param("api_visible") else False
                    if errors:
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # storing 
                    config = self.app().config_updater()
                    config.set("charclasses.%s" % param_id, classes)
                    config.store()
                    self.call("admin.redirect", "characters/classes/%s" % param_id)
                fields = [
                    {"name": "name", "label": self._("Class variant name"), "value": cls.get("name")},
                    {"name": "order", "label": self._("Sorting order"), "value": cls.get("order"), "inline": True},
                    {"name": "description", "label": self._("Class variant description for players (HTML allowed)"), "value": cls.get("description"), "type": "textarea"},
                    {"name": "available", "label": self._("Whether this class variant is available for player") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", cls.get("available", 1))},
                    {"type": "header", "html": self._("Library settings")},
                    {"name": "library_visible", "label": self._("Publish this class variant in the library"), "checked": cls.get("library_visible", True), "type": "checkbox"},
                    {"type": "header", "html": self._("API settings (API is not implemented yet)")},
                    {"name": "api_visible", "label": self._("This class variant is visible in the API"), "checked": cls.get("api_visible", True), "type": "checkbox"},
                ]
                self.call("admin.form", fields=fields)
            self.call("admin.response_template", "admin/common/tables.html", vars)
        # list of class groups
        rows = []
        for param in self.call("characters.params"):
            if param.get("charclass"):
                rows.append([
                    htmlescape(param["name"]),
                    u'<hook:admin.link href="characters/classes/%s" title="%s" />' % (param["code"], self._("open")),
                ])
        if not rows:
            self.call("admin.response", u'<div class="admin-alert">%s</div>' % (self._("To create races and classes system go to the '{href}' page first and create one or more parameters with 'character class' option").format(href=u'<hook:admin.link href="characters/params" title="%s" />' % self._("Characters parameters"))), {})
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Type"),
                        self._("List of classes"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def params_stored(self, params, config):
        classes = []
        for param in params:
            if param.get("charclass"):
                classes.append({
                    "code": param.get("code"),
                    "require": param.get("require"),
                })
        config.set("reqcache.charclasses", classes)

class CharClasses(ConstructorModule):
    def register(self):
        self.rhook("characters.param-html", self.html, priority=10)
        self.rhook("quest.check-dialogs", self.check_dialogs, priority=-10)
        self.rhook("ext-charclass.select", self.charclass_select, priv="logged")
        self.rhook("modules.list", self.modules_list)

    def html(self, param, value):
        if param.get("charclass"):
            value_i = intz(value)
            if value_i > 0:
                variants = self.conf("charclasses.%s" % param["code"], {})
                cls = variants.get(str(value)) or variants.get(value_i)
                if cls:
                    raise Hooks.Return(htmlescape(cls["name"]))
                raise Hooks.Return(htmlescape(unicode(value)))
            raise Hooks.Return("")

    def child_modules(self):
        mods = ["mg.mmorpg.charclasses.CharClassesAdmin", "mg.mmorpg.charclasses.CharClassesLibrary"]
        if self.conf("module.startloc"):
            mods.append("mg.mmorpg.startloc.StartLoc")
        return mods

    def modules_list(self, modules):
        modules.append({
            "id": "startloc",
            "name": self._("Starting location"),
            "description": self._("Ability to select character starting location depending on his class"),
            "parent": "charclasses",
        })

    def check_dialogs(self):
        req = self.req()
        character = self.character(req.user())
        for param in self.conf("reqcache.charclasses", []):
            # First check is very fast (without loading param descriptions)
            val = character.db_params.get(param["code"])
            if val is None:
                # Loading parameter description and trying to get default value for the parameter
                val = character.param(param["code"])
            if (type(val) == str or type(val) == unicode) and valid_nonnegative_int(val):
                val = int(val)
            elif type(val) == float:
                val = int(val)
            if type(val) != int or val < 1:
                if self.call("script.evaluate-expression", param["require"], globs={"char": character}, description=self._("Whether class '%s' is required") % param["code"]):
                    self.call("web.redirect", "charclass/select")

    def charclass_select(self):
        req = self.req()
        character = self.character(req.user())
        for param in self.conf("reqcache.charclasses", []):
            val = character.param(param["code"])
            if (type(val) == str or type(val) == unicode) and valid_nonnegative_int(val):
                val = int(val)
            elif type(val) == float:
                val = int(val)
            if type(val) != int or val < 1:
                if self.call("script.evaluate-expression", param["require"], globs={"char": character}, description=self._("Whether class '%s' is required") % param["code"]):
                    # Found required parameter. Loading list of classes
                    classes = self.conf("charclasses.%s" % param["code"], {}).items()
                    classes = [(str(cls_id), cls) for cls_id, cls in classes if self.call("script.evaluate-expression", cls["available"], globs={"char": character}, description=self._("Availability of class variant '{variant}' in class '{cls}'").format(variant=cls_id, cls=param["code"]))]
                    if not classes:
                        param_info = self.call("characters.param", param["code"])
                        self.call("game.internal-error", self._("You have no available variants of '%s' to select from") % (htmlescape(param_info["name"]) if param_info else param["code"]))
                    classes.sort(cmp=lambda x, y: cmp(x[1].get("order"), y[1].get("order")) or cmp(x[0], y[0]))
                    if req.ok():
                        cls_selected = req.param("class")
                        for cls_id, cls in classes:
                            if cls_id == cls_selected:
                                # Storing new character class
                                old_val = character.param(param["code"])
                                try:
                                    character.set_param(param["code"], intz(cls_id))
                                except AttributeError:
                                    pass
                                else:
                                    character.store()
                                    self.call("charclass.selected", character, param, cls_id)
                                    self.qevent("charclass-selected", char=character, cls=param["code"], oldval=old_val, newval=cls_id)
                                self.call("quest.check-redirects")
                                self.call("web.redirect", "/charclass/select")
                    vars = {
                        "Select": self._("charclass///Select"),
                    }
                    layout = self.call("game.parse_internal", "charclass-select-layout.html", vars)
                    vars["classes"] = []
                    vars["layout"] = layout
                    param_info = self.call("characters.param", param["code"])
                    for cls_id, cls in classes:
                        vars["classes"].append({
                            "id": cls_id,
                            "name": jsencode(htmlescape(cls["name"])),
                            "description": jsencode(cls["description"]),
                        })
                    self.call("game.response_internal", "charclass-select.html", vars)
        self.call("web.redirect", self.call("game-interface.default-location") or "/location")

class CharClassesLibrary(ConstructorModule):
    def register(self):
        self.rdep(["mg.mmorpg.charparams.CharacterParams"])
        for param in self.call("characters.params", load_handlers=False):
            if param.get("library_visible") and param.get("charclass"):
                self.rhook("library-page-charparam/%s.content" % param["code"], curry(self.library_page_charclass, param), priority=10)
        self.rhook("characters.param-library", self.param_library, priority=10)

    def param_library(self, param):
        if param.get("charclass"):
            raise Hooks.Return("/library/charparam/%s" % param["code"])

    def library_page_charclass(self, param, render_content):
        name = htmlescape(param["name"])
        res = {
            "code": "charparam/%s" % param["code"],
            "title": name,
            "keywords": '%s, %s' % (self._("class"), name),
            "description": self._("This page describes class %s") % name,
            "parent": "charparams",
        }
        if render_content:
            vars = {
                "name": name,
                "classdesc": htmlescape(param["description"]),
            }
            rows = []
            classes = self.conf("charclasses.%s" % param["code"], {})
            cls_list = [(cls_id, cls) for cls_id, cls in classes.iteritems() if cls.get("library_visible")]
            cls_list.sort(cmp=lambda x, y: cmp(x[1].get("order"), y[1].get("order")) or cmp(x[0], y[0]))
            for ent_id, ent in cls_list:
                rows.append({
                    "name": htmlescape(ent["name"]),
                    "description": ent["description"],
                })
            if rows:
                rows[-1]["lst"] = True
            vars["variants"] = rows
            res["content"] = self.call("socio.parse", "library-charclass.html", vars)
        return res
