from mg.constructor.params import *
from mg.constructor.player_classes import *

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

    def menu_characters_index(self, menu):
        req = self.req()
        if req.has_access("characters.params"):
            menu.append({"id": "characters/params", "text": self.title, "leaf": True, "order": 25})

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("characters.params-view"):
            character = self.character(user.uuid)
            if character.valid:
                params = []
                self.admin_view_params(character, params)
                tbl = {
                    "type": "params",
                    "title": self._("Parameters"),
                    "order": 50,
                    "header": [self._("Code"), self._("parameter///Name"), self._("Value"), "HTML"],
                    "rows": params,
                }
            tables.append(tbl)

class CharacterParams(Params):
    def __init__(self, app, fqn):
        Params.__init__(self, app, fqn)
        self.kind = "characters"

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
