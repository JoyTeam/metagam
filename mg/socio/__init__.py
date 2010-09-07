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
        "topic": [["topic"], "created"],
        "category": [["category"], "created"],
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
        self.call("admin.response_template", "admin/forum/index.html", {
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
            self.call("web.not_found")
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
        self.rhook("forum.category", self.category)         # get forum category by id
        self.rhook("forum.categories", self.categories)     # get list of forum categories
        self.rhook("forum.newtopic", self.newtopic)         # create new topic
        self.rhook("forum.reply", self.reply)               # reply in the topic
        self.rhook("forum.response", self.response)
        self.rhook("forum.response_template", self.response_template)
        self.rhook("ext-forum.index", self.ext_index)
        self.rhook("ext-forum.cat", self.ext_category)
        self.rhook("ext-forum.newtopic", self.ext_newtopic)
        self.rhook("ext-forum.topic", self.ext_topic)
        self.rhook("ext-forum.reply", self.ext_reply)

    def response(self, content, vars):
        if vars.get("menu") and len(vars["menu"]):
            menu = []
            first = True
            for ent in vars["menu"]:
                if first:
                    first = False
                else:
                    menu.append({"delim": True})
                menu.append(ent)
            vars["menu"] = menu
        vars["forum_content"] = content
        self.call("web.response_layout", "socio/layout_forum.html", vars)

    def response_template(self, template, vars):
        self.call("forum.response", self.call("web.parse_template", template, vars), vars)

    def ext_index(self):
        categories = [cat for cat in self.categories() if self.may_read(cat)]
        entries = []
        topcat = None
        for cat in categories:
            if cat["topcat"] != topcat:
                topcat = cat["topcat"]
                entries.append({"header": topcat})
            entries.append({"category": cat})
        vars = {
            "title": self._("Forum categories"),
            "categories": entries,
            "topics": self._("Topics"),
            "replies": self._("Replies"),
            "unread": self._("Unread"),
            "last_message": self._("Last message"),
            "menu": [
                { "html": self._("Forum categories") },
            ],
        }
        self.call("forum.response_template", "socio/index.html", vars)

    def category(self, id):
        for cat in self.categories():
            if cat["id"] == id:
                return cat

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
        topics = self.objlist(ForumTopicList, query_index="category-updated", query_equal=cat["id"], query_reversed=True)
        topics.load()
        return topics

    def ext_category(self):
        req = self.req()
        cat = self.call("forum.category", req.args)
        if cat is None:
            self.call("web.not_found")
        if not self.may_read(cat):
            self.call("web.forbidden")
        topics = self.topics(cat).data()
        self.topics_htmlencode(topics)
        vars = {
            "title": cat["title"],
            "category": cat,
            "new_topic": self._("New topic"),
            "topics": topics,
            "author": self._("Author"),
            "replies": self._("Replies"),
            "last_reply": self._("Last reply"),
            "by": self._("by"),
            "to_page": self._("Pages"),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "html": cat["title"] },
            ],
        }
        self.call("forum.response_template", "socio/category.html", vars)

    def topics_htmlencode(self, topics):
        for topic in topics:
            topic["subject_html"] = cgi.escape(topic.get("subject"))
            topic["avatar"] = "/st/socio/default_avatar.gif"
            topic["member_html"] = "Author-name"
            topic["member_html_no_icons"] = "Author-name"
            topic["comments"] = intz(topic.get("comments"))
            topic["content_html"] = cgi.escape(topic.get("content"))
            topic["literal_created"] = self.call("l10n.timeencode2", topic.get("created"))

    def posts_htmlencode(self, posts):
        for post in posts:
            post["avatar"] = "/st/socio/default_avatar.gif"
            post["member_html"] = "Author-name"
            post["member_html_no_icons"] = "Author-name"
            post["comments"] = intz(post.get("comments"))
            post["content_html"] = cgi.escape(post.get("content"))
            post["literal_created"] = self.call("l10n.timeencode2", post.get("created"))

    def ext_newtopic(self):
        req = self.req()
        cat = self.call("forum.category", req.args)
        if cat is None:
            self.call("web.not_found")
        if not self.may_write(cat):
            self.call("web.forbidden")
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
                self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
        form.input(self._("Subject"), "subject", subject)
        form.texteditor(self._("Content"), "content", content)
        vars = {
            "category": cat,
            "title": u"%s: %s" % (self._("New topic"), cat["title"]),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
                { "html": self._("New topic") },
            ],
        }
        self.call("forum.response", form.html(), vars)

    def newtopic(self, cat, author, subject, content):
        topic = ForumTopic(self.db())
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

    def reply(self, cat, topic, author, content):
        post = ForumPost(self.db())
        now = self.now()
        post.set("category", cat["id"])
        post.set("topic", topic.uuid)
        post.set("created", now)
        post.set("author", author)
        post.set("content", content)
        post.store()
        return post

    def ext_topic(self):
        req = self.req()
        try:
            topic = self.obj(ForumTopic, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        cat = self.call("forum.category", topic.get("category"))
        if cat is None:
            self.call("web.not_found")
        if not self.may_read(cat):
            self.call("web.forbidden")
        topic_data = topic.data
        topic_data["uuid"] = topic.uuid
        self.topics_htmlencode([topic_data])
        actions = []
        actions.append('<a href="/forum/reply/' + topic.uuid + '">' + self._("reply") + '</a>')
        if len(actions):
            topic_data["topic_actions"] = " &bull; ".join(actions)
        posts = self.posts(topic).data()
        self.posts_htmlencode(posts)
        for post in posts:
            actions = []
            actions.append('<a href="/forum/reply/' + topic.uuid + '/' + post["uuid"] + '">' + self._("reply") + '</a>')
            if len(actions):
                post["post_actions"] = " &bull; ".join(actions)
        req = self.req()
        content = req.param("content")
        form = self.call("web.form", "socio/form.html", "/forum/topic/" + topic.uuid + "#post_form")
        if req.ok():
            if not content:
                form.error("content", self._("Enter post content"))
            if not form.errors:
                post = self.call("forum.reply", cat, topic, None, content)
                self.call("web.redirect", "/forum/topic/%s#post_form" % topic.uuid)
        form.texteditor(None, "content", content)
        form.submit(None, None, self._("Reply"))
        vars = {
            "topic": topic_data,
            "category": cat,
            "title": topic_data.get("subject_html"),
            "to_page": self._("Pages"),
            "show_topic": True,
            "topic_started": self._("topic started"),
            "all_posts": self._("All posts"),
            "search_all_posts": self._("Search for all posts of this member"),
            "to_the_top": self._("to the top"),
            "written_at": self._("written at"),
            "posts": posts,
            "new_post_form": form.html(),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
                { "html": self._("Topic") },
            ],
        }
        self.call("forum.response_template", "socio/topic.html", vars)

    def posts(self, topic, start=None):
        posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
        posts.load()
        return posts

    def ext_reply(self):
        req = self.req()
        m = re.match(r'^([0-9a-f]+)/([0-9a-f]+)$', req.args)
        if m:
            topic_id, post_id = m.group(1, 2)
        else:
            m = re.match(r'^([0-9a-f]+)$', req.args)
            if m:
                topic_id = m.group(1)
                post_id = None
            else:
                self.call("web.not_found")
        try:
            topic = self.obj(ForumTopic, topic_id)
        except ObjectNotFoundException:
            print "topic %s not found" % topic_id
            self.call("web.not_found")
        if post_id is not None:
            try:
                post = self.obj(ForumPost, post_id)
            except ObjectNotFoundException:
                print "post %s not found" % post_id
                self.call("web.not_found")
            if post.get("topic") != topic_id:
                print "post %s doesn't match topic %s" % (post_id, topic_id)
                self.call("web.not_found")
            old_content = post.get("content")
        else:
            old_content = topic.get("content")
        cat = self.call("forum.category", topic.get("category"))
        if cat is None:
            self.call("web.not_found")
        if not self.may_write(cat):
            self.call("web.forbidden")
        topic_data = topic.data
        self.topics_htmlencode([topic_data])
        req = self.req()
        content = req.param("content")
        form = self.call("web.form", "socio/form.html")
        if req.ok():
            if not content:
                form.error("content", self._("Enter post content"))
            if not form.errors:
                post = self.call("forum.reply", cat, topic, None, content)
                self.call("web.redirect", "/forum/topic/%s#post_form" % topic.uuid)
        else:
            # TODO: clear old_content
            content = "[quote]\n%s\n[/quote]" % old_content
        form.texteditor(None, "content", content)
        form.submit(None, None, self._("Reply"))
        vars = {
            "topic": topic_data,
            "category": cat,
            "title": "%s: %s" % (self._("Reply"), topic_data.get("subject_html")),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
                { "href": "/forum/topic/%s" % topic.uuid, "html": self._("Topic") },
                { "html": self._("Reply") },
            ],
        }
        self.call("forum.response", form.html(), vars)
