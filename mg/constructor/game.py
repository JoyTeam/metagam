from mg import *

class Game(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-game.index", self.menu_game_index)
        self.rhook("ext-admin-game.profile", self.ext_profile)
        self.rhook("headmenu-admin-game.profile", self.headmenu_profile)
        self.rhook("permissions.list", self.permissions_list)

    def menu_root_index(self, menu):
        menu.append({"id": "game.index", "text": self._("Game"), "order": 10})

    def permissions_list(self, perms):
        perms.append({"id": "game.profile", "name": self._("Game profile editor")})

    def menu_game_index(self, menu):
        req = self.req()
        if req.has_access("game.profile"):
            menu.append({"id": "game/profile", "text": self._("Game profile editor"), "leaf": True})

    def headmenu_profile(self, args):
        return self._("Game profile")

    def ext_profile(self):
        self.call("session.require_permission", "game.profile")
        req = self.req()
        config = self.app().config
        author_name = req.param("author_name")
        description = req.param("description")
        indexpage_description = req.param("indexpage_description")
        indexpage_keywords = req.param("indexpage_keywords")
        if req.param("ok"):
            config.set("gameprofile.author_name", author_name)
            config.set("gameprofile.description", description)
            config.set("gameprofile.indexpage_description", indexpage_description)
            config.set("gameprofile.indexpage_keywords", indexpage_keywords)
            config.store()
            self.call("admin.response", self._("Game profile stored"), {})
        else:
            author_name = config.get("gameprofile.author_name")
            description = config.get("gameprofile.description")
            indexpage_description = config.get("gameprofile.indexpage_description")
            indexpage_keywords = config.get("gameprofile.indexpage_keywords")
        fields = [
            {"name": "author_name", "label": self._("Game author name"), "value": author_name},
            {"type": "textarea", "name": "description", "label": self._("Game description"), "value": description},
            {"name": "indexpage_description", "label": self._("SEO HTML description for the index page"), "value": indexpage_description},
            {"name": "indexpage_keywords", "label": self._("SEO HELP keywords for the index page"), "value": indexpage_keywords},
        ]
        self.call("admin.form", fields=fields)
