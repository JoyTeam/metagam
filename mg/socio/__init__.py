from mg.core import Module

class Forum(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-forum.index", self.index)
        self.rhook("forum.index", self.forum_index)
        self.rhook("forum.categories", self.forum_categories)
        self.rhook("admin.menu-root", self.menu_root)
        self.rhook("admin.menu-forum", self.menu_forum)
        self.rhook("ext-admin.forum.categories", self.admin_categories)

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
        cats = self.conf("forum.categories")
        if cats is None:
            cats = [
                {
                    "name": "Test forum 1",
                    "description": "This is a primary place to talk to another buddies"
                },
                {
                    "name": "Test forum 2",
                    "description": "This is a secondary to talk about anything else"
                }
            ]
        return cats

    def may_read(self, cat):
        return True

    def menu_root(self, menu):
        menu.append({ "id": "forum", "text": self._("Forum") })

    def menu_forum(self, menu):
        menu.append({ "id": "forum.categories", "text": self._("Forum categories"), "leaf": True })

    def admin_categories(self):
        return self.call("admin.response", "admin/forum/categories.js", "ForumCategories", self.categories())
