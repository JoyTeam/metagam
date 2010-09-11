from mg.core import Module, Hooks
from operator import itemgetter
from uuid import uuid4
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from mg.core.tools import *
from mg.core.cluster import StaticUploadError
from concurrence import Timeout, TimeoutError
from PIL import Image
from mg.core.auth import User
import re
import cgi
import cStringIO
import urlparse

posts_per_page = 20

re_trim = re.compile(r'^\s*(.*?)\s*$', re.DOTALL)
re_r = re.compile(r'\r')
re_emptylines = re.compile(r'(\s*\n)+\s*')
re_trimlines = re.compile(r'^\s*(.*?)\s*$', re.DOTALL | re.MULTILINE)
re_images = re.compile(r'\[img:[0-9a-f]+\]')
re_tag = re.compile(r'^(.*?)\[(b|s|i|u|color|quote|url)(?:=([^\[\]]+)|)\](.*?)\[/\2\](.*)$', re.DOTALL)
re_color = re.compile(r'^#[0-9a-f]{6}$')
re_url = re.compile(r'^((http|https|ftp):/|)/\S+$')
re_cut = re.compile(r'\[cut\]')
re_softhyphen = re.compile(r'(\S{110})', re.DOTALL)
re_mdash = re.compile(r' +-( +|$)', re.MULTILINE)
re_bull = re.compile(r'^\*( +|$)', re.MULTILINE)
re_parbreak = re.compile(r'(\n\s*){2,}')
re_linebreak = re.compile(r'\n')
re_img = re.compile(r'^(.*?)\[img:([a-f0-9]+)\](.*)$', re.DOTALL)
valid = r'\/\w\/\+\%\#\$\&=\?#'
re_urls = re.compile(r'(.*?)((?:http|ftp|https):\/\/[\-\.\w]+(?::\d+|)(?:[\/#][' + valid + r'\-;:\.\(\)!,]*[' + valid + r']|[\/#]|))(.*)', re.IGNORECASE | re.DOTALL | re.UNICODE)

class UserForumSettings(CassandraObject):
    _indexes = {
    }

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "UserForumSettings-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return UserForumSettings._indexes

class UserForumSettingsList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "UserForumSettings-"
        kwargs["cls"] = UserForumSettings
        CassandraObjectList.__init__(self, *args, **kwargs)

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
        pinned = 1 if self.get("pinned") else 0
        self.set("pinned", pinned)
        self.set("pinned-created", str(pinned) + self.get("created"))
        self.set("pinned-updated", str(pinned) + self.get("updated"))

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

class SocioImage(CassandraObject):
    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "SocioImage-"
        CassandraObject.__init__(self, *args, **kwargs)

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

class Socio(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("socio.format_text", self.format_text)
        self.rhook("ext-socio.image", self.ext_image)

    def menu_root_index(self, menu):
        menu.append({ "id": "socio.index", "text": self._("Socio") })

    def format_text(self, html, options={}):
        m = re_tag.match(html)
        if m:
            before, tag, arg, inner, after = m.group(1, 2, 3, 4, 5)
            if tag == "color":
                if re_color.match(arg):
                    return self.format_text(before, options) + ('<span style="color: %s">' % arg) + self.format_text(inner, options) + '</span>' + self.format_text(after, options)
            elif tag == "url":
                if re_url.match(arg):
                    arg = cgi.escape(arg)
                    return self.format_text(before, options) + ('<a href="%s" target="_blank">' % arg) + self.format_text(inner, options) + '</a>' + self.format_text(after, options)
            elif tag == "quote":
                before = self.format_text(re_trim.sub(r'\1', before), options)
                inner = self.format_text(re_trim.sub(r'\1', inner), options)
                after = self.format_text(re_trim.sub(r'\1', after), options)
                if arg is not None:
                    inner = '<div class="author">%s</div>%s' % (cgi.escape(arg), inner)
                return '%s<div class="quote">%s</div>%s' % (before, inner, after)
            else:
                if tag == "s":
                    tag = "strike"
                return self.format_text(before, options) + ('<%s>' % tag) + self.format_text(inner, options) + ('</%s>' % tag) + self.format_text(after, options)
            return self.format_text(before, options) + self.format_text(inner, options) + self.format_text(after, options)
        m = re_img.match(html)
        if m:
            before, id, after = m.group(1, 2, 3)
            try:
                image = self.obj(SocioImage, id)
            except ObjectNotFoundException:
                return self.format_text(before, options) + self.format_text(after, options)
            thumbnail = image.get("thumbnail")
            image = image.get("image")
            if thumbnail is None:
                return '%s <img src="%s" alt="" /> %s' % (self.format_text(before, options), image, self.format_text(after, options))
            else:
                return '%s <a href="%s" target="_blank"><img src="%s" alt="" /></a> %s' % (self.format_text(before, options), image, thumbnail, self.format_text(after, options))
        m = re_urls.match(html)
        if m:
            before, inner, after = m.group(1, 2, 3)
            inner_show = cgi.escape(re_softhyphen.sub(r'\1' + u"\u200b", inner))
            inner = cgi.escape(inner)
            return '%s<a href="%s" target="_blank">%s</a>%s' % (self.format_text(before, options), inner, inner_show, self.format_text(after, options))
        html = re_cut.sub("\n", html)
        html = re_softhyphen.sub(r'\1' + u"\u200b", html)
        html = cgi.escape(html)
        html = re_mdash.sub("&nbsp;&mdash; ", html)
        html = re_bull.sub("&bull; ", html)
        html = re_parbreak.sub("\n\n", html)
        html = re_linebreak.sub("<br />", html)
        return html

    def ext_image(self):
        self.call("session.require_login")
        req = self.req()
        if not re.match(r'^[a-z0-9_]+$', req.args):
            self.call("web.not_found")
        form = self.call("web.form", "socio/form.html")
        url = req.param("url")
        image_field = "image"
        if req.ok():
            image = req.param_raw("image")
            if not image and url:
                url_obj = urlparse.urlparse(url.encode("utf-8"), "http", False)
                if url_obj.scheme != "http":
                    form.error("url", self._("Scheme '%s' is not supported") % cgi.escape(url_obj.scheme))
                elif url_obj.hostname is None:
                    form.error("url", self._("Enter correct URL"))
                else:
                    cnn = HTTPConnection()
                    try:
                        with Timeout.push(50):
                            cnn.set_limit(20000000)
                            port = url_obj.port
                            if port is None:
                                port = 80
                            cnn.connect((url_obj.hostname, port))
                            request = cnn.get(url_obj.path + url_obj.query)
                            response = cnn.perform(request)
                            if response.status_code != 200:
                                if response.status_code == 404:
                                    form.error("url", self._("Remote server response: Resource not found"))
                                elif response.status_code == 403:
                                    form.error("url", self._("Remote server response: Access denied"))
                                elif response.status_code == 500:
                                    form.error("url", self._("Remote server response: Internal server error"))
                                else:
                                    form.error("url", self._("Download error: %s") % cgi.escape(response.status))
                            else:
                                image = response.body
                                image_field = "url"
                    except TimeoutError as e:
                        form.error("url", self._("Timeout on downloading image. Time limit - 30 sec"))
                    except BaseException as e:
                        form.error("url", self._("Download error: %s") % cgi.escape(str(e)))
                    finally:
                        try:
                            cnn.close()
                        except:
                            pass
            if image:
                try:
                    image_obj = Image.open(cStringIO.StringIO(image))
                except IOError:
                    form.error(image_field, self._("Image format not recognized"))
                if not form.errors:
                    format = image_obj.format
                    if format == "GIF":
                        ext = "gif"
                        content_type = "image/gif"
                        target_format = "GIF"
                    elif format == "PNG":
                        ext = "png"
                        content_type = "image/png"
                        target_format = "PNG"
                    else:
                        target_format = "JPEG"
                        ext = "jpg"
                        content_type = "image/jpeg"
                    width, height = image_obj.size
                    if width <= 800 and height <= 600 and format == target_format:
                        th_data = None
                    else:
                        th = image_obj.convert("RGB")
                        th.thumbnail((800, 600), Image.ANTIALIAS)
                        th_data = cStringIO.StringIO()
                        th.save(th_data, "JPEG")
                        th_data = th_data.getvalue()
                        th_ext = "jpg"
                        th_content_type = "image/jpeg"
                    if target_format != format:
                        im_data = cStringIO.StringIO()
                        image_obj.save(im_data, target_format)
                        im_data = im_data.getvalue()
                    else:
                        im_data = image
                    # storing
                    socio_image = self.obj(SocioImage)
                    storage_server = self.call("cluster.storage_server")
                    image_url = "/%s.%s" % (socio_image.uuid, ext)
                    image_uri = "http://" + storage_server + image_url
                    socio_image.set("image", image_uri)
                    if th_data is not None:
                        thumbnail_url = "/%s-th.%s" % (socio_image.uuid, th_ext)
                        thumbnail_uri = "http://" + storage_server + thumbnail_url
                        socio_image.set("thumbnail", thumbnail_uri)
                    if not form.errors:
                        try:
                            self.call("cluster.static_upload", image_url, im_data, content_type)
                        except StaticUploadError as e:
                            form.error(image_field, unicode(e))
                    if not form.errors and th_data is not None:
                        try:
                            self.call("cluster.static_upload", thumbnail_url, th_data, th_content_type)
                        except StaticUploadError as e:
                            form.error(image_field, unicode(e))
                    if not form.errors:
                        socio_image.store()
                        vars = {
                            "image": socio_image.uuid,
                            "id": req.args,
                        }
                        self.call("web.response_template", "socio/uploaded.html", vars)
            elif not form.errors:
                form.error("image", self._("Upload an image"))
            
        form.file(self._("Image"), "image")
        form.input(self._("Or Internet address"), "url", url)
        form.submit(None, None, self._("Upload"))
        vars = {
            "title": self._("Upload image")
        }
        self.call("web.response_global", form.html(), vars)

class Forum(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.socio.Socio"])
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
        self.rhook("ext-forum.delete", self.ext_delete)
        self.rhook("ext-forum.edit", self.ext_edit)
        self.rhook("ext-forum.settings", self.ext_settings)

    def response(self, content, vars):
        topmenu = []
        self.call("forum.topmenu", topmenu)
        if len(topmenu):
            topmenu_left = []
            topmenu_right = []
            first_left = True
            first_right = True
            for ent in topmenu:
                if ent.get("left"):
                    if first_left:
                        first_left = False
                    else:
                        topmenu_left.append({"delim": True})
                    topmenu_left.append(ent)
                else:
                    if first_right:
                        first_right = False
                    else:
                        topmenu_right.append({"delim": True})
                    topmenu_right.append(ent)
            if len(topmenu_left):
                vars["topmenu_left"] = topmenu_left
            if len(topmenu_right):
                vars["topmenu_right"] = topmenu_right
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

    def may_write(self, cat, topic=None):
        req = self.req()
        user = req.user()
        if user is None:
            return False
        return True

    def may_edit(self, cat, topic=None, post=None):
        req = self.req()
        user = req.user()
        if user is None:
            return False
        if post is None:
            if topic.get("author") != user:
                return False
        else:
            if post.get("author") != user:
                return False
        return True

    def may_delete(self, cat, topic=None, post=None):
        req = self.req()
        user = req.user()
        if user is None:
            return False
        if post is None:
            if topic.get("author") != user:
                return False
        else:
            if post.get("author") != user:
                return False
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

    def load_settings(self, list, signatures, avatars):
        authors = dict([(ent.get("author"), True) for ent in list if ent.get("author")]).keys()
        if len(authors):
            authors_list = self.objlist(UserForumSettingsList, authors)
            authors_list.load(silent=True)
            for obj in authors_list:
                signatures[obj.uuid] = obj.get("signature_html")
                avatars[obj.uuid] = obj.get("avatar")
        for ent in list:
            author = ent.get("author")
            ent["avatar"] = avatars.get(author) if avatars.get(author) is not None else "/st/socio/default_avatar.gif"
            ent["signature"] = signatures.get(author)

    def topics_htmlencode(self, topics, load_settings=False):
        signatures = {}
        avatars = {}
        if load_settings:
            self.load_settings(topics, signatures, avatars)
        for topic in topics:
            topic["subject_html"] = cgi.escape(topic.get("subject"))
            topic["author_html"] = topic.get("author_html")
            topic["author_icons"] = topic.get("author_icons")
            topic["posts"] = intz(topic.get("posts"))
            if topic.get("content_html") is None:
                topic["content_html"] = self.call("socio.format_text", topic.get("content"))
            topic["literal_created"] = self.call("l10n.timeencode2", topic.get("created"))

    def posts_htmlencode(self, posts):
        signatures = {}
        avatars = {}
        self.load_settings(posts, signatures, avatars)
        for post in posts:
            post["author_html"] = post.get("author_html")
            post["author_icons"] = post.get("author_icons")
            post["posts"] = intz(post.get("posts"))
            if post.get("content_html") is None:
                post["content_html"] = self.call("socio.format_text", post.get("content"))
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
                user = self.obj(User, req.user())
                topic = self.call("forum.newtopic", cat, user, subject, content)
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
        topic = self.obj(ForumTopic)
        now = self.now()
        topic.set("category", cat["id"])
        topic.set("created", now)
        topic.set("updated", now)
        if author is not None:
            topic.set("author", author.uuid)
            topic.set("author_name", author.get("name"))
            topic.set("author_html", cgi.escape(author.get("name").encode("utf-8")))
            topic.set("author_icons", '<img src="/st/socio/test/blog.gif" alt="" />')
        topic.set("subject", subject)
        topic.set("content", content)
        topic.set("content_html", self.call("socio.format_text", content))
        topic.sync()
        topic.store()
        return topic

    def reply(self, cat, topic, author, content):
        with self.lock(["ForumTopic-" + topic.uuid]):
            post = self.obj(ForumPost)
            now = self.now()
            post.set("category", cat["id"])
            post.set("topic", topic.uuid)
            post.set("created", now)
            if author is not None:
                post.set("author", author.uuid)
                post.set("author_name", author.get("name"))
                post.set("author_html", cgi.escape(author.get("name").encode("utf-8")))
                post.set("author_icons", '<img src="/st/socio/test/blog.gif" alt="" />')
            post.set("content", content)
            post.set("content_html", self.call("socio.format_text", content))
            post.store()
            posts = len(self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid))
            topic.set("posts", posts)
            topic.sync()
            topic.store()
            page = (posts - 1) / posts_per_page + 1
            raise Hooks.Return((post, page))

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
        topic_data = topic.data.copy()
        topic_data["uuid"] = topic.uuid
        self.topics_htmlencode([topic_data], load_settings=True)
        may_write = self.may_write(cat, topic)
        actions = []
        if self.may_delete(cat, topic):
            actions.append('<a href="/forum/delete/' + topic.uuid + '">' + self._("delete") + '</a>')
        if self.may_edit(cat, topic):
            actions.append('<a href="/forum/edit/' + topic.uuid + '">' + self._("edit") + '</a>')
        if may_write:
            actions.append('<a href="/forum/reply/' + topic.uuid + '">' + self._("reply") + '</a>')
        if len(actions):
            topic_data["topic_actions"] = " &bull; ".join(actions)
        req = self.req()
        page = intz(req.param("page"))
        posts, page, pages = self.posts(topic, page)
        posts = posts.data()
        self.posts_htmlencode(posts)
        for post in posts:
            actions = []
            if self.may_delete(cat, topic, post):
                actions.append('<a href="/forum/delete/' + topic.uuid + '/' + post["uuid"] + '">' + self._("delete") + '</a>')
            if self.may_edit(cat, topic, post):
                actions.append('<a href="/forum/edit/' + topic.uuid + '/' + post["uuid"] + '">' + self._("edit") + '</a>')
            if may_write:
                actions.append('<a href="/forum/reply/' + topic.uuid + '/' + post["uuid"] + '">' + self._("reply") + '</a>')
            if len(actions):
                post["post_actions"] = " &bull; ".join(actions)
        content = req.param("content")
        form = self.call("web.form", "socio/form.html", "/forum/topic/" + topic.uuid + "#post_form")
        if req.ok():
            if not content:
                form.error("content", self._("Enter post content"))
            elif not self.may_write(cat):
                form.error("content", self._("Access denied"))
            if not form.errors:
                user = self.obj(User, req.user())
                post, page = self.call("forum.reply", cat, topic, user, content)
                self.call("web.redirect", "/forum/topic/%s?page=%d#%s" % (topic.uuid, page, post.uuid))
        vars = {
            "topic": topic_data,
            "category": cat,
            "title": topic_data.get("subject_html"),
            "to_page": self._("Pages"),
            "show_topic": page <= 1,
            "topic_started": self._("topic started"),
            "all_posts": self._("All posts"),
            "search_all_posts": self._("Search for all posts of this member"),
            "to_the_top": self._("to the top"),
            "written_at": self._("written at"),
            "posts": posts,
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
                { "html": self._("Topic") },
            ],
        }
        if req.ok() or self.may_write(cat):
            form.texteditor(None, "content", content)
            form.submit(None, None, self._("Reply"))
            vars["new_post_form"] = form.html()
        if pages > 1:
            pages_list = []
            last_show = None
            for i in range(1, pages + 1):
                show = (i <= 5) or (i >= pages - 5) or (abs(i - page) < 5)
                if show:
                    if len(pages_list):
                        pages_list.append({"delim": True})
                    pages_list.append({"entry": {"text": i, "a": None if i == page else {"href": "/forum/topic/%s?page=%d" % (topic.uuid, i)}}})
                elif last_show:
                    if len(pages_list):
                        pages_list.append({"delim": True})
                    pages_list.append({"entry": {"text": "..."}})
                last_show = show
            vars["pages"] = pages_list
        self.call("forum.response_template", "socio/topic.html", vars)

    def posts(self, topic, page=1):
        posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
        pages = (len(posts) - 1) / posts_per_page + 1
        if page < 1:
            page = 1
        elif page > pages:
            page = pages
        del posts[0:(page - 1) * posts_per_page]
        del posts[page * posts_per_page:]
        posts.load()
        return posts, page, pages

    def category_or_topic_args(self):
        req = self.req()
        m = re.match(r'^([0-9a-f]+)/([0-9a-f]+)$', req.args)
        post = None
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
            self.call("web.not_found")
        if post_id is not None:
            try:
                post = self.obj(ForumPost, post_id)
            except ObjectNotFoundException:
                self.call("web.not_found")
            if post.get("topic") != topic_id:
                self.call("web.not_found")
        cat = self.call("forum.category", topic.get("category"))
        if cat is None:
            self.call("web.not_found")
        return cat, topic, post

    def ext_reply(self):
        cat, topic, post = self.category_or_topic_args()
        if not self.may_write(cat):
            self.call("web.forbidden")
        if post is not None:
            old_content = post.get("content")
        else:
            old_content = topic.get("content")
        topic_data = topic.data.copy()
        self.topics_htmlencode([topic_data])
        req = self.req()
        content = req.param("content")
        form = self.call("web.form", "socio/form.html")
        if req.ok():
            if not content:
                form.error("content", self._("Enter post content"))
            if not form.errors:
                user = self.obj(User, req.user())
                post, page = self.call("forum.reply", cat, topic, user, content)
                self.call("web.redirect", "/forum/topic/%s?page=%d#%s" % (topic.uuid, page, post.uuid))
        else:
            old_content = re.sub(r'\[img:[0-9a-f]+\]', '', old_content)
            old_content = re.sub(re.compile(r'\[quote(|=[^\]]*)\].*?\[\/quote\]', re.DOTALL), '', old_content)
            old_content = re.sub(re.compile(r'^\s*(.*?)\s*$', re.MULTILINE), r'\1', old_content)
            old_content = re.sub(r'\r', '', old_content)
            old_content = re.sub(r'\n{3,}', '\n\n', old_content)
            old_content = re.sub(re.compile(r'^\s*(.*?)\s*$', re.DOTALL), r'\1', old_content)
            if old_content != "":
                content = "[quote=%s]\n%s\n[/quote]\n\n" % (post.get("author_name") if post else topic.get("author_name"), old_content)
            else:
                content = old_content
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

    def ext_delete(self):
        cat, topic, post = self.category_or_topic_args()
        if not self.may_delete(cat, topic, post):
            self.call("web.forbidden")
        if post is not None:
            posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
            page = 1
            prev = ""
            for i in range(0, len(posts)):
                if posts[i].uuid == post.uuid:
                    page = (i - 1) / posts_per_page + 1
                    if i < len(posts) - 1:
                        prev = "#%s" % posts[i + 1].uuid
                    elif i > 0:
                        prev = "#%s" % posts[i - 1].uuid
                    break
            post.remove()
            topic.set("posts", len(posts) - 1)
            topic.sync()
            topic.store()
            self.call("web.redirect", "/forum/topic/%s?page=%d%s" % (topic.uuid, page, prev))
        else:
            posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
            posts.remove()
            topic.remove()
            self.call("web.redirect", "/forum/cat/%s" % cat["id"])

    def ext_edit(self):
        cat, topic, post = self.category_or_topic_args()
        if not self.may_edit(cat, topic, post):
            self.call("web.forbidden")
        req = self.req()
        form = self.call("web.form", "socio/form.html")
        vars = {
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
                { "href": "/forum/topic/%s" % topic.uuid, "html": self._("Topic") },
                { "html": self._("Editing") },
            ]
        }
        if post is not None:
            vars["title"] = self._("Edit post")
            content = req.param("content")
            if req.ok():
                if not content:
                    form.error("content", self._("Enter post content"))
                if not form.errors:
                    post.set("content", content)
                    post.set("content_html", self.call("socio.format_text", content))
                    post.store()
                    posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
                    for i in range(0, len(posts)):
                        if posts[i].uuid == post.uuid:
                            page = (i - 1) / posts_per_page + 1
                            self.call("web.redirect", "/forum/topic/%s?page=%d#%s" % (topic.uuid, page, post.uuid))
                    self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
            else:
                content = post.get("content")
            form.texteditor(None, "content", content)
        else:
            vars["title"] = self._("Edit topic")
            subject = req.param("subject")
            content = req.param("content")
            if req.ok():
                if not subject:
                    form.error("subject", self._("Enter topic subject"))
                if not content:
                    form.error("content", self._("Enter topic content"))
                if not form.errors:
                    topic.set("subject", subject)
                    topic.set("content", content)
                    topic.set("content_html", self.call("socio.format_text", content))
                    topic.store()
                    self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
            else:
                content = topic.get("content")
                subject = topic.get("subject")
            form.input(self._("Subject"), "subject", subject)
            form.texteditor(None, "content", content)
        form.submit(None, None, self._("Save"))
        self.call("forum.response", form.html(), vars)

    def ext_settings(self):
        req = self.req()
        user_id = req.user()
        try:
            settings = self.obj(UserForumSettings, user_id)
        except ObjectNotFoundException:
            settings = self.obj(UserForumSettings, user_id, {})
        vars = {
            "title": self._("Forum settings"),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "html": self._("Forum settings") },
            ]
        }
        form = self.call("web.form", "socio/form.html")
        form.textarea_rows = 4
        signature = req.param("signature")
        avatar = req.param_raw("avatar")
        redirect = req.param("redirect")
        if req.ok():
            signature = re_trim.sub(r'\1', signature)
            signature = re_r.sub('', signature)
            signature = re_emptylines.sub('\n', signature)
            signature = re_trimlines.sub(r'\1', signature)
            lines = signature.split('\n')
            if len(lines) > 4:
                form.error("signature", self._("Signature can't contain more than 4 lines"))
            else:
                for line in lines:
                    if len(line) > 80:
                        form.error("signature", self._("Signature line couldn't be longer than 80 symbols"))
                    elif re_images.match(line):
                        form.error("signature", self._("Signature couldn't contain images"))
            image_obj = None
            if avatar:
                try:
                    image_obj = Image.open(cStringIO.StringIO(avatar))
                except IOError:
                    form.error("avatar", self._("Image format not recognized"))
                if image_obj:
                    format = image_obj.format
                    if format == "GIF":
                        ext = "gif"
                        content_type = "image/gif"
                        target_format = "GIF"
                    elif format == "PNG":
                        ext = "png"
                        content_type = "image/png"
                        target_format = "PNG"
                    else:
                        target_format = "JPEG"
                        ext = "jpg"
                        content_type = "image/jpeg"
                    width, height = image_obj.size
                    if width < 100 or height < 100:
                        form.error("avatar", self._("Avatar has to be at least 100x100 pixels"))
                    elif width != 100 or height != 100 or format != target_format:
                        image_obj = image_obj.convert("RGB")
                        if width > 100 and height > 100:
                            if width <= height:
                                height = height * 100 / width
                                width = 100
                            else:
                                width = width * 100 / height
                                height = 100
                            image_obj.thumbnail((width, height), Image.ANTIALIAS)
                        if width > 100:
                            left = (width - 100) / 2
                            top = 0
                            image_obj = image_obj.crop((left, top, left + 99, top + 99))
                        elif height > 100:
                            left = 0
                            top = (height - 100) / 2
                            image_obj = image_obj.crop((left, top, left + 99, top + 99))
            if not form.errors:
                if image_obj:
                    # storing
                    im_data = cStringIO.StringIO()
                    image_obj.save(im_data, target_format)
                    im_data = im_data.getvalue()
                    image_id = uuid4().hex
                    storage_server = self.call("cluster.storage_server")
                    image_url = "/%s.%s" % (image_id, ext)
                    image_uri = "http://" + storage_server + image_url
                    settings.set("avatar", image_uri)
                    try:
                        self.call("cluster.static_upload", image_url, im_data, content_type)
                    except StaticUploadError as e:
                        form.error("avatar", unicode(e))
                settings.set("signature", signature)
                settings.set("signature_html", self.call("socio.format_text", signature))
                settings.store()
                if redirect is not None and redirect != "":
                    self.call("web.redirect", redirect)
                self.call("web.redirect", "/cabinet/settings")
        else:
            signature = settings.get("signature")
        form.hidden("redirect", redirect)
        form.texteditor(self._("Your forum signature"), "signature", signature)
        form.file(self._("Your avatar"), "avatar")
        self.call("forum.response", form.html(), vars)
