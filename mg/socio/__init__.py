from mg.core import Module

class Forum(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-forum.index", self.index)

    def index(self, args, request):
        categories = [cat for cat in self.categories() if self.may_read(request, cat)]
        print "categories: %s" % categories
        return request.jresponse({"forum": True})

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

    def may_read(self, request, cat):
        return True
