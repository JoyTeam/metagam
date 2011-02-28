from mg import *

class Auth(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-users.index", self.menu_users_index)
        self.rhook("ext-admin-players.auth", self.admin_players_auth)
        self.rhook("headmenu-admin-players.auth", self.headmenu_players_auth)
        self.rhook("permissions.list", self.permissions_list)

    def permissions_list(self, perms):
        perms.append({"id": "players.auth", "name": self._("Players authentication settings")})

    def menu_users_index(self, menu):
        req = self.req()
        if req.has_access("players.auth"):
            menu.append({"id": "players/auth", "text": self._("Players authentication"), "leaf": True})

    def headmenu_players_auth(self, args):
        return self._("Players authentication settings")

    def admin_players_auth(self):
        self.call("session.require_permission", "players.auth")
        req = self.req()
        config = self.app().config
        if req.param("ok"):
            multicharing = intz(req.param("v_multicharing"))
            free_chars = intz(req.param("free_chars"))
            max_chars = intz(req.param("max_chars"))
            config.set("auth.multicharing", multicharing)
            config.set("auth.free_chars", free_chars)
            config.set("auth.max_chars", max_chars)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            multicharing = config.get("auth.multicharing", 0)
            free_chars = config.get("auth.free_chars", 1)
            max_chars = config.get("auth.max_chars", 5)
        fields = [
            {"name": "multicharing", "type": "combo", "label": self._("Are players allowed to play more than 1 character"), "value": multicharing, "values": [(0, self._("No")), (1, self._("Yes, but play them by turn")), (2, self._("Yes, play them simultaneously"))] },
            {"name": "free_chars", "label": self._("Number of characters per player allowed for free"), "value": free_chars, "condition": "[multicharing]>0" },
            {"name": "max_chars", "label": self._("Maximal number of characters per player allowed"), "value": max_chars, "inline": True, "condition": "[multicharing]>0" },
        ]
        self.call("admin.form", fields=fields)
