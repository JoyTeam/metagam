from mg.constructor.params import *
from mg.constructor.player_classes import *
import re

re_charparam = re.compile(r'^charparam/(.+)$')
re_char_params = re.compile(r'char\.p_([a-zA-Z_][a-zA-Z0-9_]*)')
re_valid_parameter = re.compile('^p_[a-z0-9_]+$', re.IGNORECASE)
re_del = re.compile('^del/(.+)$')

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
        self.rhook("headmenu-admin-characters.params-delivery", self.headmenu_delivery)
        self.rhook("ext-admin-characters.params-delivery", self.admin_delivery, priv="characters.params")

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
            menu.append({"id": "characters/params-delivery", "text": self._("Delivery of parameters to the client"), "leaf": True, "order": 26})

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

    def headmenu_delivery(self, args):
        if args == "new":
            return [self._("New parameter"), "characters/params-delivery"]
        elif re_valid_parameter.match(args):
            return [self._("Parameter %s") % args, "characters/params-delivery"]
        else:
            return self._("Characters parameters delivered to the client")

    def admin_delivery(self):
        req = self.req()
        existing_params = self.conf("characters.params-delivery", {}).copy()
        if req.args:
            m = re_del.match(req.args)
            if m:
                paramid = m.group(1)
                if paramid in existing_params:
                    del existing_params[paramid]
                    config = self.app().config_updater()
                    config.set("characters.params-delivery", existing_params)
                    config.store()
                self.call("admin.redirect", "characters/params-delivery")
            paramid = req.args
            if req.ok():
                character = self.character(req.user())
                errors = {}
                # code
                pcode = req.param("code")
                if not re_valid_parameter.match(pcode):
                    errors["code"] = self._("Parameter code must start with p_ and contain only latin letters, digits and underscode characters")
                elif pcode in existing_params and pcode != paramid:
                    errors["code"] = self._("Parameter with this code is already delivered to client")
                # visible
                visible = self.call("script.admin-expression", "visible", errors, globs={"char": character, "viewer": character})
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # store configuration
                if paramid != "new":
                    del existing_params[paramid]
                existing_params[pcode] = {
                    "visible": visible
                }
                config = self.app().config_updater()
                config.set("characters.params-delivery", existing_params)
                config.store()
                self.call("admin.redirect", "characters/params-delivery")
            if paramid == "new":
                code = "p_"
                visible = 1
            else:
                code = paramid
                paraminfo = existing_params.get(code)
                if not paraminfo:
                    self.call("admin.redirect", "characters/params-delivery")
                visible = paraminfo.get("visible")
            fields = [
                {"name": "code", "label": self._("Character parameter"), "value": code},
                {"name": "visible", "label": self._("Whether parameter of character 'char' is visible to character 'viewer'") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", visible)},
            ]
            self.call("admin.form", fields=fields)
        rows = []
        for pcode in sorted(existing_params.keys()):
            param = existing_params[pcode]
            rows.append([
                pcode,
                self.call("script.unparse-expression", param["visible"]),
                u'<hook:admin.link href="characters/params-delivery/%s" title="%s" />' % (pcode, self._("edit")),
                u'<hook:admin.link href="characters/params-delivery/del/%s" title="%s" confirm="%s" />' % (pcode, self._("delete"), self._("Are you sure want to remove this parameter from the delivery")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "characters/params-delivery/new",
                            "text": self._("New parameter"),
                            "lst": True
                        }
                    ],
                    "header": [
                        self._("Parameter code"),
                        self._("Visibility"),
                        self._("Edit"),
                        self._("Delete"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars=vars)

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
        self.rhook("characters.param-library", self.param_library)

    def param_library(self, param):
        if param.get("library_table"):
            return "/library/charparam/%s" % param["code"]
        else:
            return "/library/charparams#%s" % param["code"]

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

    def library_page_charparams(self, render_content):
        pageinfo = {
            "code": "charparams",
            "title": self._("Character parameters"),
            "keywords": self._("character parameters"),
            "description": self._("This page describes parameters of characters"),
            "parent": "index",
        }
        if render_content:
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
                    if param.get("library_table") or param.get("charclass"):
                        rparam["tables"] = {
                            "uri": "/library/charparam/%s" % param["code"],
                        }
                    params.append(rparam)
            vars = {
                "params": params,
                "OpenTable": self._("Open table"),
                "CharsParams": self._("Characters parameters"),
            }
            pageinfo["content"] = self.call("socio.parse", "library-charparams.html", vars)
        return pageinfo

    def param_name(self, m):
        param = self.call("characters.param", m.group(1))
        if param:
            return param["name"]
        else:
            return m.group(0)

    def library_page_charparam(self, render_content):
        if render_content:
            req = self.req()
            m = re_charparam.match(req.args)
            if not m:
                return None
            param = self.call("characters.param", m.group(1))
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
            return {
                "code": "charparam/%s" % param["code"],
                "title": vars["name"],
                "keywords": '%s, %s' % (self._("parameter"), vars["name"]),
                "description": self._("This page describes parameter %s") % vars["name"],
                "parent": "charparams",
                "content": self.call("socio.parse", "library-charparam.html", vars),
            }
