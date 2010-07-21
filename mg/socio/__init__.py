from mg.core import Module
from operator import itemgetter
from uuid import uuid4

class Forum(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-forum.index", self.index)
        self.rhook("forum.index", self.forum_index)
        self.rhook("forum.categories", self.forum_categories)
        self.rhook("admin.menu-root", self.menu_root)
        self.rhook("admin.menu-forum", self.menu_forum)
        self.rhook("ext-admin.forum.categories", self.admin_categories)
        self.rhook("ext-admin.forum.category", self.admin_category)

    def index(self):
        return self.call("web.response_hook_layout", "forum.index", {})

    def forum_index(self, vars):
        return "socio/layout_categories.html"

    def forum_categories(self, vars):
        request = self.req()
        categories = [cat for cat in self.categories() if self.may_read(cat)]
        self.categories_htmlencode(categories)
        entries = []
        for cat in categories:
            entries.append({"category": cat})
        vars["title"] = self._("Forum categories")
        vars["categories"] = entries
        return self.call("web.parse_template", "socio/categories.html", vars)

    def categories_htmlencode(self, categories):
        pass

    def categories(self):
        cats = self.conf("forum.categories-2")
        if cats is None:
            cats = [
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("News"),
                    "description": self._("Game news published by the administrators"),
                    "order": 10
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("Game"),
                    "description": self._("Talks about game activities: gameplay, news, wars, politics etc."),
                    "order": 20
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("Newbies"),
                    "description": self._("Dear newbies, if you have any questions about the game, feel free to ask"),
                    "order": 30
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("Diplomacy"),
                    "description": self._("Authorized guild members can talk to each other about diplomacy and politics issues here"),
                    "order": 40
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Admin"),
                    "title": self._("Admin talks"),
                    "description": self._("Discussions with the game administrators. Here you can discuss any issues related to the game itself."),
                    "order": 50
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Admin"),
                    "title": self._("Reference manuals"),
                    "description": self._("Actual reference documents about the game are placed here."),
                    "order": 60
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Admin"),
                    "title": self._("Bug reports"),
                    "description": self._("Report any problems in the game here"),
                    "order": 70
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Reallife"),
                    "title": self._("Smoking room"),
                    "description": self._("Everything not related to the game: humor, forum games, hobbies, sport etc."),
                    "order": 80
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Reallife"),
                    "title": self._("Art"),
                    "description": self._("Poems, prose, pictures, photos, music about the game"),
                    "order": 90
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Trading"),
                    "title": self._("Services"),
                    "description": self._("Any game services: mercenaries, guardians, builders etc."),
                    "order": 100
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Trading"),
                    "title": self._("Market"),
                    "description": self._("Market place to sell and by any item"),
                    "order": 110
                }
            ]
            conf = self.app().config
            conf.set("forum.categories-2", cats)
            conf.store()
        cats.sort(key=itemgetter("order"))
        return cats

    def may_read(self, cat):
        return True

    def menu_root(self, menu):
        menu.append({ "id": "forum", "text": self._("Forum") })

    def menu_forum(self, menu):
        menu.append({ "id": "forum.categories", "text": self._("Forum categories"), "leaf": True })

    def admin_categories(self):
        categories = []
        topcat = None
        for cat in self.categories():
            if cat["topcat"] != topcat:
                topcat = cat["topcat"]
                categories.append({"header": topcat})
            categories.append({"cat": cat})
        return self.call("admin.response_template", "admin/forum/categories.html", {
            "code": self._("Code"),
            "title": self._("Title"),
            "order": self._("Order"),
            "editing": self._("Editing"),
            "edit": self._("edit"),
            "categories": categories
        })

    def admin_category(self):
        req = self.req()
        categories = self.categories()
        for cat in categories:
            if cat["id"] == req.args:
                fields = [
                    {
                        "name": "title",
                        "label": self._("Category title"),
                        "value": "name-name-name"
                    },
                    {
                        "name": "description",
                        "label": self._("Category description"),
                        "value": "desc-desc-desc"
                    },
                    {
                        "name": "order",
                        "label": self._("Sort order"),
                        "value": 123,
                        "type": "numberfield"
                    }
                ]
                return self.call("admin.form", fields=fields)
        return req.not_found()
