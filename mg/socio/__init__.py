from mg.core import Module

class Forum(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-forum.index", self.index)
        self.rhook("forum.index", self.forum_index)
        self.rhook("forum.categories", self.forum_categories)

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
        return [
            {
                "id": 123,
                "name": "Game"
            },
            {
                "id": 124,
                "name": "Talks"
            },
            {
                "id": 125,
                "name": "Fuckoff"
            },
            {
                "id": 126,
                "name": "Some other forum"
            }
        ]

    def may_read(self, cat):
        return True
