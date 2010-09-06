from mg.core import Module
from operator import itemgetter
from uuid import uuid4
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from mg.core.tools import *
import re
import cgi

class ForumTopic(CassandraObject):
    _indexes = {
        "category-created": [["category"], "pinned-created"],
        "category-updated": [["category"], "pinned-updated"],
        "author": [["author"], "created"],
        "tag": [["tag"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "ForumTopic-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return ForumTopic._indexes

    def sync(self):
        pinned = "1" if self.get("pinned") else "0"
        self.set("pinned", pinned)
        self.set("pinned-created", pinned + self.get("created"))
        self.set("pinned-updated", pinned + self.get("updated"))

class ForumTopicList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "ForumTopic-"
        kwargs["cls"] = ForumTopic
        CassandraObjectList.__init__(self, *args, **kwargs)

class ForumPost(CassandraObject):
    _indexes = {
        "topic-created": [["topic"], "created"],
        "author": [["author"], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "ForumPost-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return ForumPost._indexes

class ForumPostList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "ForumPost-"
        kwargs["cls"] = ForumPost
        CassandraObjectList.__init__(self, *args, **kwargs)

class Socio(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)

    def menu_root_index(self, menu):
        menu.append({ "id": "socio.index", "text": self._("Socio") })

class ForumAdmin(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.socio.Forum"])
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("menu-admin-forum.index", self.menu_forum_index)
        self.rhook("headmenu-admin-forum.categories", self.headmenu_forum_categories)
        self.rhook("headmenu-admin-forum.category", self.headmenu_forum_category)
        self.rhook("ext-admin-forum.categories", self.admin_categories)
        self.rhook("ext-admin-forum.category", self.admin_category)

    def menu_socio_index(self, menu):
        menu.append({ "id": "forum.index", "text": self._("Forum") })

    def menu_forum_index(self, menu):
        menu.append({ "id": "forum/categories", "text": self._("Forum categories"), "leaf": True })

    def headmenu_forum_categories(self, args):
        return self._("Forum categories")

    def headmenu_forum_category(self, args):
        cat = self.call("forum.category", args)
        if cat is None:
            return [self._("No such category"), "forum/categories"]
        return [self._("Category %s").decode("utf-8") % cat["title"], "forum/categories"]

    def admin_categories(self):
        categories = []
        topcat = None
        for cat in self.call("forum.categories"):
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
        cat = self.call("forum.category", req.args)
        if cat is None:
            return req.not_found()
        if req.param("ok"):
            errors = {}
            title = req.param("title")
            topcat = req.param("topcat")
            description = req.param("description")
            order = req.param("order")
            if title is None or title == "":
                errors["title"] = self._("Enter category title")
            if topcat is None or topcat == "":
                errors["topcat"] = self._("Enter top category title")
            if order is None or order == "":
                errors["order"] = self._("Enter category order")
            elif not re.match(r'^-?(?:\d+|\d+\.\d+)$', order):
                errors["order"] = self._("Invalid numeric format")
            if len(errors):
                return req.jresponse({"success": False, "errors": errors})
            cat["title"] = title
            cat["topcat"] = topcat
            cat["description"] = description
            cat["order"] = float(order)
            conf = self.app().config
            conf.set("forum.categories", self.call("forum.categories"))
            conf.store()
            return req.jresponse({"success": True, "redirect": "forum/categories"})

        fields = [
            {
                "name": "topcat",
                "label": self._("Top category title"),
                "value": cat["topcat"],
            },
            {
                "name": "title",
                "label": self._("Category title"),
                "value": cat["title"]
            },
            {
                "name": "description",
                "label": self._("Category description"),
                "value": cat["description"]
            },
            {
                "name": "order",
                "label": self._("Sort order"),
                "value": cat["order"],
                "type": "numberfield"
            }
        ]
        return self.call("admin.form", fields=fields)

class Forum(Module):
    def register(self):
        Module.register(self)
        self.rhook("hook-forum.categories", self.hook_forum_categories)
        self.rhook("hook-forum.topics", self.hook_forum_topics)
        self.rhook("hook-forum.topic", self.hook_forum_topic)
        self.rhook("forum.category", self.category)
        self.rhook("forum.categories", self.categories)
        self.rhook("ext-forum.index", self.ext_index)
        self.rhook("ext-forum.cat", self.ext_category)
        self.rhook("ext-forum.newtopic", self.ext_newtopic)
        self.rhook("forum.newtopic", self.newtopic)
        self.rhook("ext-forum.topic", self.ext_topic)

    def ext_index(self):
        return self.call("web.response_layout", "socio/layout_categories.html", {})

    def category(self, id):
        for cat in self.categories():
            if cat["id"] == id:
                return cat

    def hook_forum_categories(self, vars):
        categories = [cat for cat in self.categories() if self.may_read(cat)]
        self.categories_htmlencode(categories)
        entries = []
        topcat = None
        for cat in categories:
            if cat["topcat"] != topcat:
                topcat = cat["topcat"]
                entries.append({"header": topcat})
            entries.append({"category": cat})
        vars["title"] = self._("Forum categories")
        vars["categories"] = entries
        vars["topics"] = self._("Topics")
        vars["replies"] = self._("Replies")
        vars["unread"] = self._("Unread")
        vars["last_message"] = self._("Last message")
        return self.call("web.parse_template", "socio/categories.html", vars)

    def categories_htmlencode(self, categories):
        pass

    def categories(self):
        cats = self.conf("forum.categories")
        if cats is None:
            cats = [
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("News"),
                    "description": self._("Game news published by the administrators"),
                    "order": 10.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("Game"),
                    "description": self._("Talks about game activities: gameplay, news, wars, politics etc."),
                    "order": 20.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("Newbies"),
                    "description": self._("Dear newbies, if you have any questions about the game, feel free to ask"),
                    "order": 30.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Game"),
                    "title": self._("Diplomacy"),
                    "description": self._("Authorized guild members can talk to each other about diplomacy and politics issues here"),
                    "order": 40.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Admin"),
                    "title": self._("Admin talks"),
                    "description": self._("Discussions with the game administrators. Here you can discuss any issues related to the game itself."),
                    "order": 50.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Admin"),
                    "title": self._("Reference manuals"),
                    "description": self._("Actual reference documents about the game are placed here."),
                    "order": 60.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Admin"),
                    "title": self._("Bug reports"),
                    "description": self._("Report any problems in the game here"),
                    "order": 70.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Reallife"),
                    "title": self._("Smoking room"),
                    "description": self._("Everything not related to the game: humor, forum games, hobbies, sport etc."),
                    "order": 80.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Reallife"),
                    "title": self._("Art"),
                    "description": self._("Poems, prose, pictures, photos, music about the game"),
                    "order": 90.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Trading"),
                    "title": self._("Services"),
                    "description": self._("Any game services: mercenaries, guardians, builders etc."),
                    "order": 100.0
                },
                {
                    "id": uuid4().hex,
                    "topcat": self._("Trading"),
                    "title": self._("Market"),
                    "description": self._("Market place to sell and by any item"),
                    "order": 110.0
                }
            ]
            conf = self.app().config
            conf.set("forum.categories", cats)
            conf.store()
        cats.sort(key=itemgetter("order"))
        return cats

    def may_read(self, cat):
        return True

    def may_write(self, cat):
        return True

    def topics(self, cat, start=None):
        topics_per_page = 5
        if start is None:
            start = ""
        topics = self.objlist(ForumTopicList, query_index="category-updated", query_equal=cat["id"], query_start="", query_finish="", query_limit=topics_per_page, query_reversed=True)
        topics.load()
        return topics

    def ext_category(self):
        req = self.req()
        cat = self.call("forum.category", req.args)
        if cat is None:
            return req.not_found()
        if not self.may_read(cat):
            return req.forbidden()
        return self.call("web.response_layout", "socio/layout_topics.html", {
            "title": cat["title"],
            "categories_list": self._("Categories"),
            "category": cat,
            "new_topic": self._("New topic"),
        })

    def topics_htmlencode(self, topics):
        for topic in topics:
            topic["subject_html"] = cgi.escape(topic.get("subject"))
            topic["member_html"] = "Author-name"
            topic["comments"] = intz(topic.get("comments"))
            topic["content_html"] = cgi.escape(topic.get("content"))

    def hook_forum_topics(self, vars):
        cat = vars["category"]
        topics = self.topics(cat).data()
        self.topics_htmlencode(topics)
        vars["title"] = cat["title"]
        vars["topics"] = topics
        vars["author"] = self._("Author")
        vars["replies"] = self._("Replies")
        vars["last_reply"] = self._("Last reply")
        vars["by"] = self._("by")
        vars["to_page"] = self._("Pages")
        return self.call("web.parse_template", "socio/topics.html", vars)

    def ext_newtopic(self):
        req = self.req()
        cat = self.call("forum.category", req.args)
        if cat is None:
            return req.not_found()
        if not self.may_write(cat):
            return req.forbidden()
        subject = req.param("subject")
        content = req.param("content")
        form = self.call("web.form", "socio/form.html")
        if req.ok():
            if not subject:
                form.error("subject", self._("Enter topic subject"))
            if not content:
                form.error("content", self._("Enter topic content"))
            if not form.errors:
                topic = self.call("forum.newtopic", cat, None, subject, content)
                return req.redirect("/forum/topic/%s" % topic.uuid)
        form.input(self._("Subject"), "subject", subject)
        form.texteditor(self._("Content"), "content", content)
        return self.call("web.response_layout", "socio/layout_form.html", {
            "form": form.html()
        })

    def newtopic(self, cat, author, subject, content):
        topic = ForumTopic(self.db())
        print "topic.uuid=%s creating in category=%s" % (topic.uuid, cat["id"])
        now = self.now()
        topic.set("category", cat["id"])
        topic.set("created", now)
        topic.set("updated", now)
        topic.set("author", author)
        topic.set("subject", subject)
        topic.set("content", content)
        topic.sync()
        topic.store()
        return topic

    def ext_topic(self):
        req = self.req()
        try:
            topic = self.obj(ForumTopic, req.args)
        except ObjectNotFoundException:
            return req.not_found()
        cat = self.call("forum.category", topic.get("category"))
        if cat is None:
            return req.not_found()
        if not self.may_read(cat):
            return req.forbidden()
        topic = topic.data
        self.topics_htmlencode([topic])
        return self.call("web.response_layout", "socio/layout_topic.html", {
            "categories_list": self._("Categories"),
            "topic": topic,
            "category": cat,
            "title": topic["subject_html"]
        })

    def hook_forum_topic(self, vars):
        vars["to_page"] = self._("Pages")
        vars["show_topic"] = True
        vars["topic_started"] = self._("topic started")
        vars["all_posts"] = self._("All posts")
        vars["search_all_posts"] = self._("Search for all posts of this member")
        vars["to_the_top"] = self._("to the top")
        vars["written_at"] = self._("written at")
        return self.call("web.parse_template", "socio/topic.html", vars)

