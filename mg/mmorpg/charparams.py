from mg.constructor.params import *
from mg.constructor.player_classes import *
import re

re_charparam = re.compile(r'^charparam/(.+)$')
re_char_params = re.compile(r'char\.p_([a-zA-Z_][a-zA-Z0-9_]*)')

class CharacterParamsAdmin(ParamsAdmin):
    def __init__(self, app, fqn):
        ParamsAdmin.__init__(self, app, fqn)
        self.kind = "characters"

    @property
    def title(self):
        return self._("Characters parameters")

    def register(self):
        ParamsAdmin.register(self)
        self.rhook("menu-admin-characters.index", self.menu_characters_index)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("characters.params-url", self.params_url)
        self.rhook("characters.params-redirect", self.params_redirect)
        self.rhook("characters.params-obj", self.params_obj)
        self.rhook("characters.param-admin-changed", self.param_admin_changed)
        self.rhook("characters.script-globs", self.script_globs)
        self.rhook("characters.require-security-comment", self.require_security_comment)

    def require_security_comment(self):
        return True

    def script_globs(self):
        req = self.req()
        return {"char": self.character(req.user())}

    def params_url(self, uuid):
        return "auth/user-dashboard/%s" % uuid

    def params_redirect(self, uuid):
        self.call("admin.redirect", "auth/user-dashboard/%s" % uuid, parameters={"active_tab": "params"})

    def params_obj(self, uuid):
        return self.character(uuid).db_params

    def menu_characters_index(self, menu):
        req = self.req()
        if req.has_access("characters.params"):
            menu.append({"id": "characters/params", "text": self.title, "leaf": True, "order": 25})

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("characters.params-view"):
            character = self.character(user.uuid)
            if character.valid:
                may_edit = req.has_access("characters.params-edit")
                header = [self._("Code"), self._("parameter///Name"), self._("Value"), "HTML"]
                if may_edit:
                    header.append(self._("Changing"))
                params = []
                self.admin_view_params(character, params, may_edit)
                tbl = {
                    "type": "params",
                    "title": self._("Parameters"),
                    "order": 50,
                    "header": header,
                    "rows": params,
                }
                tables.append(tbl)

    def param_admin_changed(self, uuid, param, old_value, new_value, comment):
        req = self.req()
        self.call("security.suspicion", admin=req.user(), action="param.change", kind="characters", uuid=uuid, param=param["code"], old_value=old_value, new_value=new_value, comment=comment)
        self.call("dossier.write", user=uuid, admin=req.user(), content=self._("{param_name} ({param_code}) changed from {old_value} to {new_value}:\n{comment}").format(param_name=param["name"], param_code=param["code"], old_value=old_value, new_value=new_value, comment=comment))

class CharacterParams(Params):
    def __init__(self, app, fqn):
        Params.__init__(self, app, fqn)
        self.kind = "characters"

    def child_modules(self):
        return ["mg.mmorpg.charparams.CharacterParamsAdmin", "mg.mmorpg.charparams.CharacterParamsLibrary"]

    def register(self):
        Params.register(self)
        self.rhook("character-page.actions", self.charpage_actions)
        self.rhook("ext-character.params", self.charparams, priv="logged")

    def charpage_actions(self, character, actions):
        if self.notimportant_params_exist():
            actions.append({"href": "/character/params", "text": self._("Show parameters of the character"), "order": 15})

    def charparams(self):
        req = self.req()
        character = self.character(req.user())
        vars = {
            "character": {
            },
            "Ret": self._("Return"),
        }
        params = []
        self.call("characters.params-owner-all", character, params)
        if params:
            vars["character"]["params"] = params
        self.call("game.response_internal", "character-params.html", vars)

class CharacterParamsLibrary(ParamsLibrary):
    def __init__(self, app, fqn):
        ParamsLibrary.__init__(self, app, fqn)
        self.kind = "characters"

    def register(self):
        ParamsLibrary.register(self)
        self.rdep(["mg.mmorpg.charparams.CharacterParams"])
        self.rhook("library-grp-index.pages", self.library_index_pages)
        self.rhook("library-page-charparams.content", self.library_page_charparams)
        for param in self.call("characters.params", load_handlers=False):
            if param.get("library_visible") and param.get("library_table"):
                self.rhook("library-page-charparam/%s.content" % param["code"], self.library_page_charparam)

    def library_index_pages(self, pages):
        pages.append({"page": "charparams", "order": 40})

    def library_page_charparams(self):
        params = []
        grp = None
        for param in self.call("characters.params"):
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
                        "uri": "/library/charparam/%s" % param["code"],
                    }
                params.append(rparam)
        vars = {
            "params": params,
            "OpenTable": self._("Open table"),
        }
        return {
            "code": "charparams",
            "title": self._("Character parameters"),
            "keywords": self._("character parameters"),
            "description": self._("This page describes parameters of characters"),
            "content": self.call("socio.parse", "library-charparams.html", vars),
            "parent": "index",
        }

    def param_name(self, m):
        param = self.call("characters.param", m.group(1))
        if param:
            return param["name"]
        else:
            return m.group(0)

    def library_page_charparam(self):
        req = self.req()
        m = re_charparam.match(req.args) or self.call("web.not_found")
        param = self.call("characters.param", m.group(1)) or self.call("web.not_found")
        vars = {
            "name": htmlescape(param["name"]),
            "paramdesc": htmlescape(param["description"]),
        }
        if param.get("library_table"):
            # table rows
            levels = set()
            values = {}
            visuals = {}
            # table header
            header = []
            if param.get("values_table"):
                expr = re_char_params.sub(self.param_name, self.call("script.unparse-expression", param["expression"]))
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
        else:
            return None
        return {
            "code": "charparam/%s" % param["code"],
            "title": vars["name"],
            "keywords": '%s, %s' % (self._("parameter"), vars["name"]),
            "description": self._("This page describes parameter %s") % vars["name"],
            "content": self.call("socio.parse", "library-charparam.html", vars),
            "parent": "charparams",
        }
