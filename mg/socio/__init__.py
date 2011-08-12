# -*- coding: utf-8 -*-

from mg import *
from operator import itemgetter
from uuid import uuid4
from mg.core.cluster import StaticUploadError
from concurrence.http import HTTPError
from concurrence import Timeout, TimeoutError
from PIL import Image, ImageEnhance
from mg.core.auth import PermissionsEditor
from itertools import *
import re
import cgi
import cStringIO
import urlparse
import time

posts_per_page = 20
topics_per_page = 20
max_word_len = 30
max_tag_len = 30
search_results_per_page = 20

re_trim = re.compile(r'^\s*(.*?)\s*$', re.DOTALL)
re_r = re.compile(r'\r')
re_emptylines = re.compile(r'(\s*\n)+\s*')
re_trimlines = re.compile(r'^\s*(.*?)\s*$', re.DOTALL | re.MULTILINE)
re_images = re.compile(r'\[img:([0-9a-f]+)\]')
re_tag = re.compile(r'^(.*?)\[(b|s|i|u|color|quote|code|url)(?:=([^\[\]]+)|)\](.*?)\[/\2\](.*)$', re.DOTALL)
re_color = re.compile(r'^#[0-9a-f]{6}$')
re_color_present = re.compile(r'\[color')
re_url = re.compile(r'^((http|https|ftp):/|)/\S+$')
re_cut = re.compile(r'\s*\[cut\]')
re_softhyphen = re.compile(r'(\S{110})', re.DOTALL)
re_mdash = re.compile(r' +-( +|$)', re.MULTILINE)
re_bull = re.compile(r'^\*( +|$)', re.MULTILINE)
re_parbreak = re.compile(r'(\n\s*){2,}')
re_linebreak = re.compile(r'\n')
re_img = re.compile(r'^(.*?)\[img:([a-f0-9]+)\](.*)$', re.DOTALL)
valid = r'\/\w\/\+\%\#\$\&=\?#'
re_urls = re.compile(r'(.*?)(((?:http|ftp|https):\/\/|(?=(?:[a-z][\-a-z0-9]{,30}\.)+[a-z]{2,5}))[\-\.\w]+(?::\d+|)(?:[\/#][' + valid + r'\-;:\.\(\)!,]*[' + valid + r']|[\/#]|))(.*)', re.IGNORECASE | re.DOTALL | re.UNICODE)
re_email = re.compile(r'(.*?)(\w[\w\-\.]*\@[a-z0-9][a-z0-9_\-]*(?:\.[a-z0-9][a-z0-9_\-]*)*)(.*)', re.IGNORECASE | re.DOTALL)
re_split_tags = re.compile(r'\s*(,\s*)+')
re_text_chunks = re.compile(r'.{1000,}?\S*|.+', re.DOTALL)
delimiters = r'\s\.,\-\!\&\(\)\'"\:;\<\>\/\?\`\|»\—«\r\n'
re_word_symbol = re.compile(r'[^%s]' % delimiters)
re_not_word_symbol = re.compile(r'[%s]' % delimiters)
re_remove_word = re.compile(r'^.*\/\/')
re_format_date = re.compile(r'^(\d\d\d\d)-(\d\d)-(\d\d) \d\d:\d\d:\d\d$')
re_valid_date = re.compile(r'^(\d\d\.\d\d\.\d\d\d\d|\d\d\.\d\d\.\d\d\d\d \d\d:\d\d:\d\d)$')
re_valid_tag = re.compile(r'^[\w\- ]+$', re.UNICODE)
re_whitespace = re.compile(r'\s+')

class UserForumSettings(CassandraObject):
    _indexes = {
        "notify-any": [["notify_any"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserForumSettings-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return UserForumSettings._indexes

class UserForumSettingsList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "UserForumSettings-"
        kwargs["cls"] = UserForumSettings
        CassandraObjectList.__init__(self, *args, **kwargs)

class ForumCategoryStat(CassandraObject):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumCategoryStat-"
        CassandraObject.__init__(self, *args, **kwargs)

class ForumCategoryStatList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumCategoryStat-"
        kwargs["cls"] = ForumCategoryStat
        CassandraObjectList.__init__(self, *args, **kwargs)

class ForumTopic(CassandraObject):
    _indexes = {
        "category-created": [["category"], "pinned-created"],
        "category-updated": [["category"], "pinned-updated"],
        "updated-category": [[], "updated", "category"],
        "category-list": [["category"], "created"],
        "author": [["author"], "created"],
        "tag": [["tag"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumTopic-"
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
        kwargs["clsprefix"] = "ForumTopic-"
        kwargs["cls"] = ForumTopic
        CassandraObjectList.__init__(self, *args, **kwargs)

class ForumTopicContent(CassandraObject):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumTopicContent-"
        CassandraObject.__init__(self, *args, **kwargs)

class ForumTopicContentList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumTopicContent-"
        kwargs["cls"] = ForumTopicContent
        CassandraObjectList.__init__(self, *args, **kwargs)

class ForumPost(CassandraObject):
    _indexes = {
        "topic": [["topic"], "created"],
        "category": [["category"], "created"],
        "author": [["author"], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumPost-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return ForumPost._indexes

class ForumPostList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumPost-"
        kwargs["cls"] = ForumPost
        CassandraObjectList.__init__(self, *args, **kwargs)

class SocioImage(CassandraObject):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "SocioImage-"
        CassandraObject.__init__(self, *args, **kwargs)

class ForumLastRead(CassandraObject):
    _indexes = {
        "category": [["category"]],
        "topic-user": [["topic", "user"]],
        "user-subscribed": [["user", "subscribed"]],
        "topic-subscribed": [["topic", "subscribed"]],
        "topic": [["topic"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumLastRead-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return ForumLastRead._indexes

class ForumLastReadList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumLastRead-"
        kwargs["cls"] = ForumLastRead
        CassandraObjectList.__init__(self, *args, **kwargs)

class ForumPermissions(CassandraObject):
    _indexes = {
        "member": [["member"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumPermissions-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return ForumPermissions._indexes

class ForumPermissionsList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "ForumPermissions-"
        kwargs["cls"] = ForumPermissions
        CassandraObjectList.__init__(self, *args, **kwargs)

class ForumAdmin(Module):
    def register(self):
        self.rdep(["mg.socio.Forum"])
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("menu-admin-forum.index", self.menu_forum_index)
        self.rhook("ext-admin-forum.categories", self.admin_categories, priv="forum.categories")
        self.rhook("headmenu-admin-forum.categories", self.headmenu_forum_categories)
        self.rhook("ext-admin-forum.category", self.admin_category, priv="forum.categories")
        self.rhook("headmenu-admin-forum.category", self.headmenu_forum_category)
        self.rhook("ext-admin-forum.access", self.admin_access, priv="forum.categories")
        self.rhook("headmenu-admin-forum.access", self.headmenu_forum_access)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("forum-admin.default_rules", self.default_rules)
        self.rhook("ext-admin-forum.delete", self.admin_delete, priv="forum.categories")
        self.rhook("advice-admin-forum.categories", self.advice_forum_categories)
        self.rhook("advice-admin-forum.category", self.advice_forum_categories)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("headmenu-admin-socio.user", self.headmenu_user)
        self.rhook("ext-admin-socio.user", self.user, priv="public")

    def advice_forum_categories(self, args, advice):
        advice.append({"title": self._("Defining categories"), "content": self._("Think over forum categories carefully. Try to create minimal quantity of categories. Keep in mind that users will spend just few seconds to choose a category to write. Descriptions should be short and simple. Titles should be short and self explanatory. Don't create many categories for future reference. It's better to create several more common categories and split them later.")})

    def permissions_list(self, perms):
        perms.append({"id": "forum.categories", "name": self._("Forum categories editor")})
        perms.append({"id": "forum.moderation", "name": self._("Forum moderation")})
        self.call("permissions.forum", perms)

    def menu_socio_index(self, menu):
        menu.append({"id": "forum.index", "text": self._("Forum"), "order": 10})

    def menu_forum_index(self, menu):
        req = self.req()
        if req.has_access("forum.categories"):
            menu.append({ "id": "forum/categories", "text": self._("Forum categories"), "leaf": True, "order": 20})

    def admin_categories(self):
        categories = []
        topcat = None
        for cat in self.call("forum.categories"):
            if cat["topcat"] != topcat:
                topcat = cat["topcat"]
                categories.append({"header": topcat})
            categories.append({"cat": cat})
        self.call("admin.response_template", "admin/forum/categories.html", {
            "code": self._("Code"),
            "title": self._("Title"),
            "order": self._("Order"),
            "editing": self._("Editing"),
            "edit": self._("edit"),
            "Access": self._("Access"),
            "access": self._("access"),
            "Deletion": self._("Deletion"),
            "delete": self._("delete"),
            "NewCategory": self._("Create new category"),
            "categories": categories
        })

    def headmenu_forum_categories(self, args):
        return self._("Forum categories")

    def admin_category(self):
        req = self.req()
        if req.args == "new":
            cat = {}
        else:
            cat = self.call("forum.category", req.args)
            if cat is None:
                self.call("web.not_found")
        if req.param("ok"):
            errors = {}
            title = req.param("title")
            topcat = req.param("topcat")
            description = req.param("description")
            tag = req.param("tag")
            order = req.param("order")
            default_subscribe = req.param("default_subscribe")
            manual_date = True if req.param("manual_date") else False
            allow_skip_notify = True if req.param("allow_skip_notify") else False
            if title is None or title == "":
                errors["title"] = self._("Enter category title")
            if topcat is None or topcat == "":
                errors["topcat"] = self._("Enter top category title")
            if order is None or order == "":
                errors["order"] = self._("Enter category order")
            elif not re.match(r'^-?(?:\d+|\d+\.\d+)$', order):
                errors["order"] = self._("Invalid numeric format")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            categories = self.call("forum.categories")
            if not cat.get("id"):
                cat = {"id": uuid4().hex}
                categories.append(cat)
            cat["title"] = title
            cat["topcat"] = topcat
            cat["description"] = description
            cat["tag"] = tag
            cat["order"] = float(order)
            cat["default_subscribe"] = True if default_subscribe else False
            cat["manual_date"] = manual_date
            cat["allow_skip_notify"] = allow_skip_notify
            conf = self.app().config_updater()
            conf.set("forum.categories", categories)
            conf.store()
            self.call("admin.redirect", "forum/categories")
        fields = [
            {
                "name": "title",
                "label": self._("Category title"),
                "value": cat.get("title"),
            },
            {
                "name": "topcat",
                "label": self._("Top category title"),
                "value": cat.get("topcat"),
                "inline": True,
            },
            {
                "name": "order",
                "label": self._("Sort order"),
                "value": cat.get("order"),
                "type": "numberfield",
                "inline": True,
            },
            {
                "name": "description",
                "label": self._("Category description"),
                "value": cat.get("description"),
                "flex": 2,
            },
            {
                "name": "tag",
                "label": self._("Category tag"),
                "value": cat.get("tag"),
                "inline": True,
                "flex": 1,
            },
            {
                "name": "default_subscribe",
                "label": self._("Notify users about new topics in this category by default"),
                "checked": cat.get("default_subscribe"),
                "type": "checkbox",
            },
            {
                "name": "manual_date",
                "label": self._("Allow users to enter topic dates manually"),
                "checked": cat.get("manual_date"),
                "type": "checkbox",
            },
            {
                "name": "allow_skip_notify",
                "label": self._("Allow users to inhibit notifications about new topic"),
                "checked": cat.get("allow_skip_notify"),
                "type": "checkbox",
            },
        ]
        self.call("admin.form", fields=fields)

    def headmenu_forum_category(self, args):
        if args == "new":
            return [self._("New category"), "forum/categories"]
        cat = self.call("forum.category", args)
        if cat is None:
            return [self._("No such category"), "forum/categories"]
        return [self._("Category %s") % cat["title"], "forum/categories"]

    def admin_access(self):
        permissions = []
        permissions.append(("-R", self._("Deny everything")))
        permissions.append(("+R", self._("Allow reading")))
        permissions.append(("-C", self._("Deny creating topics")))
        permissions.append(("+C", self._("Allow creating topics")))
        permissions.append(("-W", self._("Deny replying")))
        permissions.append(("+W", self._("Allow reading and replying")))
        permissions.append(("+M", self._("Allow moderation")))
        permissions.append(("-M", self._("Deny moderation")))
        PermissionsEditor(self.app(), ForumPermissions, permissions, "forum-admin.default_rules").request()

    def default_rules(self, perms):
        perms.append(("logged", "+W"))
        perms.append(("logged", "+C"))
        perms.append(("all", "+R"))
        perms.append(("perm:forum.moderation", "+M"))

    def headmenu_forum_access(self, args):
        return [self._("Access"), "forum/category/" + re.sub(r'/.*', '', args)]

    def admin_delete(self):
        cat = self.call("forum.category", self.req().args)
        if cat is None:
            self.call("admin.redirect", "forum/categories")
        categories = [c for c in self.call("forum.categories") if c["id"] != cat["id"]]
        conf = self.app().config_updater()
        conf.set("forum.categories", categories)
        conf.store()
        list = self.objlist(ForumTopicList, query_index="category-created", query_equal=cat["id"])
        list.remove()
        list = self.objlist(ForumPostList, query_index="category", query_equal=cat["id"])
        list.remove()
        list = self.objlist(ForumLastReadList, query_index="category", query_equal=cat["id"])
        list.remove()
        obj = self.obj(ForumPermissions, cat["id"], silent=True)
        obj.remove()
        self.call("admin.redirect", "forum/categories")

    def user_tables(self, user, tables):
        settings = self.obj(UserForumSettings, user.uuid, silent=True)
        params = []
        params.append((self._("Status"), htmlescape(settings.get("status"))))
        params.append((self._("Signature"), self.call("socio.format_text", settings.get("signature"))))
        avatar = settings.get("avatar")
        if avatar:
            params.append((self._("Avatar"), '<img src="%s" alt="" />' % avatar))
        if len(params):
            tables.append({
                "type": "socio",
                "title": self._("Socio"),
                "order": 20,
                "links": [{"hook": "socio/user/%s" % user.uuid, "text": self._("edit"), "lst": True}],
                "rows": params,
            })

    def user(self):
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        settings = self.obj(UserForumSettings, user.uuid, silent=True)
        if req.param("ok"):
            settings.set("signature", req.param("signature"))
            settings.set("status", req.param("status"))
            settings.store()
            self.call("admin.redirect", "auth/user-dashboard/%s" % user.uuid, {"active_tab": "socio"})
        fields = [
            {
                "name": "status",
                "label": self._("Status"),
                "value": settings.get("status"),
            },
            {
                "type": "textarea",
                "name": "signature",
                "label": self._("Signature"),
                "value": settings.get("signature"),
            },
        ]
        self.call("admin.form", fields=fields)

    def headmenu_user(self, args):
        return [self._("Socio settings"), "auth/user-dashboard/%s?active_tab=socio" % args]

class Socio(Module):
    def register(self):
        self.rhook("socio.format_text", self.format_text)
        self.rhook("ext-socio.image", self.ext_image, priv="logged")
        self.rhook("ext-socio.user", self.ext_user, priv="public")
        self.rhook("socio.template", self.template)
        self.rhook("socio.word_extractor", self.word_extractor)
        self.rhook("socio.fulltext_store", self.fulltext_store)
        self.rhook("socio.fulltext_remove", self.fulltext_remove)
        self.rhook("socio.fulltext_search", self.fulltext_search)
        self.rhook("socio.user", self.socio_user)
        self.rhook("socio.semi_user", self.socio_semi_user)
        self.rhook("socio.response", self.response)
        self.rhook("socio.response_template", self.response_template)
        self.rhook("socio.response_simple", self.response_simple)
        self.rhook("socio.response_simple_template", self.response_simple_template)
        self.rhook("socio.button-blocks", self.button_blocks)
        self.rhook("sociointerface.buttons", self.buttons)
        self.rhook("modules.list", self.modules_list)

    def child_modules(self):
        lst = ["mg.socio.SocioAdmin"]
        if self.conf("module.forum"):
            lst.extend(["mg.socio.Forum", "mg.socio.ForumAdmin", "mg.socio.paidservices.PaidServices"])
        if self.conf("module.smiles"):
            lst.extend(["mg.socio.smiles.Smiles", "mg.socio.smiles.SmilesAdmin"])
        if self.conf("module.library"):
            lst.extend(["mg.constructor.library.Library"])
        return lst

    def modules_list(self, modules):
        modules.extend([
            {
                "id": "forum",
                "name": self._("Forum"),
                "description": self._("Game forum"),
                "parent": "socio",
            }, {
                "id": "smiles",
                "name": self._("Smiles"),
                "description": self._("Smiles support"),
                "parent": "socio",
            }, {
                "id": "library",
                "name": self._("Library"),
                "description": self._("Game-related documentation for players"),
                "parent": "socio",
            }
        ])

    def button_blocks(self, blocks):
        blocks.append({"id": "forum", "title": self._("Forum"), "class": "forum"})

    def buttons(self, buttons):
        buttons.append({
            "id": "forum-settings",
            "href": "/forum/settings",
            "title": self._("Settings"),
            "condition": ['glob', 'char'],
            "target": "_self",
            "block": "forum",
            "order": 5,
        })
        buttons.append({
            "id": "library-forum",
            "href": "/forum",
            "title": self._("Forum"),
            "target": "_self",
            "block": "library",
            "order": 10,
            "left": True,
        })

    def socio_user(self):
        req = self.req()
        try:
            return req._socio_user
        except AttributeError:
            pass
        req._socio_user = req.user()
        return req._socio_user

    def socio_semi_user(self):
        req = self.req()
        try:
            return req._socio_semi_user
        except AttributeError:
            pass
        sess = req.session()
        if sess is None:
            req._socio_semi_user = None
        else:
            req._socio_semi_user = sess.semi_user()
        return req._socio_semi_user

    def word_extractor(self, text):
        for chunk in re_text_chunks.finditer(text):
            text = chunk.group()
            while True:
                m = re_word_symbol.search(text)
                if not m:
                    break
                start = m.start()
                m = re_not_word_symbol.search(text, start)
                if m:
                    end = m.end()
                    if end - start > 3:
                        w = self.stem(text[start:end-1].lower())
                        if len(w) >= 3:
                            yield w
                    text = text[end:]
                else:
                    text = text[start:]
                    if len(text) >= 3:
                        w = self.stem(text.lower())
                        if len(w) >= 3:
                            yield w
                    break

    def fulltext_store(self, group, uuid, words):
        timestamp = time.time() * 1000
        app_tag = str(self.app().tag)
        cnt = dict()
        for word in words:
            if len(word) > max_word_len:
                word = word[0:max_word_len]
            try:
                cnt[word] += 1
            except KeyError:
                cnt[word] = 1
        mutations_search = []
        mutations_list = []
        mutations = {
            "%s-%s" % (app_tag, group): {"Indexes": mutations_search},
            "%s-%s-%s" % (app_tag, group, uuid): {"Indexes": mutations_list},
        }
        for word, count in cnt.iteritems():
            mutations_search.append(Mutation(ColumnOrSuperColumn(Column(name=(u"%s//%s" % (word, uuid)).encode("utf-8"), value=str(count), timestamp=timestamp))))
            mutations_list.append(Mutation(ColumnOrSuperColumn(Column(name=word.encode("utf-8"), value=str(count), timestamp=timestamp))))
            if len(mutations_search) >= 1000:
                self.app().db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
                mutations_search = []
                mutations_list = []
        if len(mutations_search):
            self.app().db.batch_mutate(mutations, ConsistencyLevel.QUORUM)

    def fulltext_remove(self, group, uuid):
        timestamp = time.time() * 1000
        app_tag = str(self.app().tag)
        words = self.app().db.get_slice("%s-%s-%s" % (app_tag, group, uuid), ColumnParent("Indexes"), SlicePredicate(slice_range=SliceRange("", "", count=10000000)), ConsistencyLevel.QUORUM)
        mutations = []
        for word in words:
            mutations.append(Mutation(deletion=Deletion(predicate=SlicePredicate(["%s//%s" % (word.column.name, str(uuid))]), timestamp=timestamp)))
        if len(mutations):
            self.db().batch_mutate({"%s-%s" % (app_tag, group): {"Indexes": mutations}}, ConsistencyLevel.QUORUM)
            self.db().remove("%s-%s-%s" % (app_tag, group, uuid), ColumnPath("Indexes"), timestamp, ConsistencyLevel.QUORUM)

    def fulltext_search(self, group, words):
        app_tag = str(self.app().tag)
        render_objects = None
        for word in words:
            query_search = word
            if len(query_search) > max_word_len:
                query_search = query_search[0:max_word_len]
            start = (query_search + "//").encode("utf-8")
            finish = (query_search + "/=").encode("utf-8")
            objs = dict([(re_remove_word.sub('', obj.column.name), int(obj.column.value)) for obj in self.app().db.get_slice("%s-%s" % (app_tag, group), ColumnParent("Indexes"), SlicePredicate(slice_range=SliceRange(start, finish, count=10000000)), ConsistencyLevel.QUORUM)])
            if render_objects is None:
                render_objects = objs
            else:
                for k, v in render_objects.items():
                    try:
                        render_objects[k] += objs[k]
                    except KeyError:
                        del render_objects[k]
        # loading and rendering posts and topics
        if render_objects is None:
            render_objects = []
        else:
            render_objects = [(v, k) for k, v in render_objects.iteritems()]
            render_objects.sort(reverse=True)
        return render_objects

    def response(self, content, vars):
        vars["global_html"] = "constructor/socio_global.html"
        self.call("socio.setup-interface", vars)
        self.call("web.response_global", content, vars)

    def response_template(self, template, vars):
        vars["global_html"] = "constructor/socio_global.html"
        self.call("socio.setup-interface", vars)
        self.call("web.response_template", 'socio/%s' % template, vars)

    def response_simple(self, content, vars):
        vars["global_html"] = "constructor/socio_simple_global.html"
        self.call("socio.setup-interface", vars)
        self.call("web.response_global", content, vars)

    def response_simple_template(self, template, vars):
        vars["global_html"] = "constructor/socio_simple_global.html"
        self.call("socio.setup-interface", vars)
        self.call("web.response_template", 'socio/%s' % template, vars)

    def template(self, name, default=None):
        templates = {}
        self.call("socio.design", templates)
        return templates.get(name, default)

    def format_text(self, html, options={}):
        if html is None:
            return None
        m = re_tag.match(html)
        if m:
            before, tag, arg, inner, after = m.group(1, 2, 3, 4, 5)
            if tag == "color":
                if re_color.match(arg) and not options.get("no_colours"):
                    return self.format_text(before, options) + ('<span style="color: %s">' % arg) + self.format_text(inner, options) + '</span>' + self.format_text(after, options)
            elif tag == "url":
                if re_url.match(arg):
                    arg = htmlescape(arg)
                    return self.format_text(before, options) + ('<a href="%s" target="_blank">' % arg) + self.format_text(inner, options) + '</a>' + self.format_text(after, options)
            elif tag == "code":
                    return self.format_text(before.rstrip(), options) + '<pre class="code">' + htmlescape(inner).strip() + '</pre>' + self.format_text(after.lstrip(), options)
            elif tag == "quote":
                before = self.format_text(re_trim.sub(r'\1', before), options)
                inner = self.format_text(re_trim.sub(r'\1', inner), options)
                after = self.format_text(re_trim.sub(r'\1', after), options)
                if arg is not None:
                    inner = '<div class="author">%s</div>%s' % (htmlescape(arg), inner)
                return '%s<div class="quote">%s</div>%s' % (before, inner, after)
            else:
                if tag == "s":
                    tag = "strike"
                return self.format_text(before, options) + ('<%s>' % tag) + self.format_text(inner, options) + ('</%s>' % tag) + self.format_text(after, options)
            return self.format_text(before, options) + self.format_text(inner, options) + self.format_text(after, options)
        m = re_img.match(html)
        if m:
            before, id, after = m.group(1, 2, 3)
            if options.get("no_images"):
                return self.format_text(before, options) + self.format_text(after, options)
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
        m = re_email.match(html)
        if m:
            before, email, after = m.group(1, 2, 3)
            inner_show = htmlescape(re_softhyphen.sub(r'\1' + u"\u200b", email))
            email = htmlescape(email)
            return '%s<a href="mailto:%s">%s</a>%s' % (self.format_text(before, options), email, email, self.format_text(after, options))
        m = re_urls.match(html)
        if m:
            before, inner, protocol, after = m.group(1, 2, 3, 4)
            inner_show = htmlescape(re_softhyphen.sub(r'\1' + u"\u200b", inner))
            inner = htmlescape(inner)
            if protocol == "":
                inner = "http://%s" % inner
            return '%s<a href="%s" target="_blank">%s</a>%s' % (self.format_text(before, options), inner, inner_show, self.format_text(after, options))
        html = re_cut.sub("\n", html)
        # smiles
        smiles = self.call("smiles.dict")
        tokens = self.call("smiles.split", html)
        smiles_cnt = 0
        max_smiles = options.get("max_smiles")
        if tokens and len(tokens) > 1:
            result = u""
            for token in tokens:
                info = smiles.get(token)
                if info:
                    if not options.get("no_smiles"):
                        smiles_cnt += 1
                        if max_smiles is None or smiles_cnt <= max_smiles:
                            result += '<img src="%s" alt="" class="socio-smile" />' % info["image"]
                else:
                    result += self.format_text(token, options)
            return result
        html = re_softhyphen.sub(r'\1' + u"\u200b", html)
        html = htmlescape(html)
        html = re_mdash.sub("&nbsp;&mdash; ", html)
        html = re_bull.sub("&bull;&nbsp;", html)
        html = re_parbreak.sub("\n\n", html)
        html = re_linebreak.sub("<br />", html)
        return html

    def ext_image(self):
        req = self.req()
        if not re.match(r'^[a-z0-9_]+$', req.args):
            self.call("web.not_found")
        form = self.call("web.form")
        url = req.param("url")
        image_field = "image"
        if req.ok():
            image = req.param_raw("image")
            if not image and url:
                url_obj = urlparse.urlparse(url.encode("utf-8"), "http", False)
                if url_obj.scheme != "http":
                    form.error("url", self._("Scheme '%s' is not supported") % htmlescape(url_obj.scheme))
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
                                    form.error("url", self._("Download error: %s") % htmlescape(response.status))
                            else:
                                image = response.body
                                image_field = "url"
                    except TimeoutError as e:
                        form.error("url", self._("Timeout on downloading image. Time limit - 30 sec"))
                    except Exception as e:
                        form.error("url", self._("Download error: %s") % htmlescape(str(e)))
                    finally:
                        try:
                            cnn.close()
                        except Exception:
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
                    if width <= 800 and height <= 800 and format == target_format:
                        th_data = None
                    else:
                        th = image_obj.convert("RGB")
                        th.thumbnail((800, 800), Image.ANTIALIAS)
                        th_data = cStringIO.StringIO()
                        th.save(th_data, "JPEG", quality=98)
                        th_data = th_data.getvalue()
                        th_ext = "jpg"
                        th_content_type = "image/jpeg"
                    if target_format != format:
                        im_data = cStringIO.StringIO()
                        kwargs = {}
                        if target_format == "JPEG":
                            kwargs["quality"] = 95
                        image_obj.save(im_data, target_format, **kwargs)
                        im_data = im_data.getvalue()
                    else:
                        im_data = image
                    # storing
                    socio_image = self.obj(SocioImage)
                    if not form.errors:
                        try:
                            uri = self.call("cluster.static_upload", "socio", ext, content_type, im_data)
                            socio_image.set("image", uri)
                        except StaticUploadError as e:
                            form.error(image_field, unicode(e))
                    if not form.errors and th_data is not None:
                        try:
                            uri = self.call("cluster.static_upload", "thumb", th_ext, th_content_type, th_data)
                            socio_image.set("thumbnail", uri)
                        except StaticUploadError as e:
                            form.error(image_field, unicode(e))
                    if not form.errors:
                        socio_image.store()
                        vars = {
                            "image": socio_image.uuid,
                            "id": req.args,
                        }
                        self.call("socio.response_simple_template", "uploaded.html", vars)
            elif not form.errors:
                form.error("image", self._("Upload an image"))
            
        form.file(self._("Image"), "image")
        form.input(self._("Or Internet address"), "url", url)
        form.submit(None, None, self._("Upload"))
        vars = {
            "title": self._("Upload image")
        }
        self.call("socio.response_simple", form.html(), vars)

    def ext_user(self):
        req = self.req()
        try:
            user = self.obj(User, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        settings = self.obj(UserForumSettings, user.uuid, silent=True)
        name = htmlescape(user.get("name"))
        params = []
        params.append({"name": self._("user///Registered"), "value": self.call("l10n.date_local", from_unixtime(user.get("created")))})
        status = settings.get("status")
        if status:
            params.append({"name": self._("Status"), "value": htmlescape(status)})
        vars = {
            "title": self._("User %s") % name,
            "name": name,
            "params": params,
            "User": self._("User"),
        }
        self.call("socio.response_template", self.call("socio.template", "user", "user.html"), vars)

class Forum(Module):
    def register(self):
        self.rdep(["mg.socio.Socio"])
        self.rhook("forum.category", self.category)                     # get forum category by id
        self.rhook("forum.category-by-tag", self.category_by_tag)       # get forum category by tag
        self.rhook("forum.categories", self.categories)                 # get list of forum categories
        self.rhook("forum.newtopic", self.newtopic)                     # create new topic
        self.rhook("forum.reply", self.reply)                           # reply in the topic
        self.rhook("forum.notify-newtopic", self.notify_newtopic)
        self.rhook("forum.notify-reply", self.notify_reply)
        self.rhook("socio.setup-interface", self.setup_interface)
        self.rhook("forum.sync", self.sync)
        self.rhook("ext-forum.index", self.ext_index, priv="public")
        self.rhook("ext-forum.cat", self.ext_category, priv="public")
        self.rhook("ext-forum.newtopic", self.ext_newtopic, priv="public")
        self.rhook("ext-forum.topic", self.ext_topic, priv="public")
        self.rhook("ext-forum.reply", self.ext_reply, priv="public")
        self.rhook("ext-forum.delete", self.ext_delete, priv="public")
        self.rhook("ext-forum.edit", self.ext_edit, priv="public")
        self.rhook("ext-forum.settings", self.ext_settings, priv="logged")
        self.rhook("ext-forum.subscribe", self.ext_subscribe, priv="logged")
        self.rhook("ext-forum.unsubscribe", self.ext_unsubscribe, priv="logged")
        self.rhook("ext-forum.pin", self.ext_pin, priv="logged")
        self.rhook("ext-forum.unpin", self.ext_unpin, priv="logged")
        self.rhook("ext-forum.move", self.ext_move, priv="logged")
        self.rhook("ext-forum.tag", self.ext_tag, priv="public")
        self.rhook("ext-forum.tags", self.ext_tags, priv="public")
        self.rhook("ext-forum.search", self.ext_search, priv="public")
        self.rhook("ext-forum.subscribed", self.ext_subscribed, priv="logged")
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("auth.registered", self.auth_registered)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("hook-forum.news", self.news)
        self.rhook("forum.may_read", self.may_read)
        self.rhook("forum.may_write", self.may_write)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "forum",
            "href": "/forum",
            "target": "_blank",
            "icon": "forum.png",
            "title": self._("Game forum"),
            "block": "top-menu",
            "order": 5,
        })

    def objclasses_list(self, objclasses):
        objclasses["UserForumSettings"] = (UserForumSettings, UserForumSettingsList)
        objclasses["ForumTopic"] = (ForumTopic, ForumTopicList)
        objclasses["ForumTopicContent"] = (ForumTopicContent, ForumTopicContentList)
        objclasses["ForumLastRead"] = (ForumLastRead, ForumLastReadList)
        objclasses["ForumPost"] = (ForumPost, ForumPostList)
        objclasses["SocioImage"] = (SocioImage, None)
        objclasses["ForumPermissions"] = (ForumPermissions, ForumPermissionsList)
        objclasses["ForumCategoryStat"] = (ForumCategoryStat, ForumCategoryStatList)

    def setup_interface(self, vars):
        req = self.req()
        if vars.get("menu") and len(vars["menu"]):
            menu_left = []
            menu_right = []
            for ent in vars["menu"]:
                if ent.get("right"):
                    menu_right.append(ent)
                else:
                    menu_left.append(ent)
            if len(menu_left):
                menu_left[-1]["lst"] = True
                vars["menu_left"] = menu_left
            if len(menu_right):
                menu_right[-1]["lst"] = True
                vars["menu_right"] = menu_right
        silence = self.silence(self.call("socio.user"))
        if silence:
            vars["socio_message_top"] = self.call("socio-admin.message-silence").format(till=self.call("l10n.time_local", silence.get("till")))
        else:
            vars["socio_message_top"] = self.conf("socio.message-top")

    def ext_index(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        categories = self.categories()
        rules = self.load_rules([cat["id"] for cat in categories])
        if user_uuid is None:
            roles = ["notlogged", "all"]
        else:
            roles = {}
            self.call("security.users-roles", [user_uuid], roles)
            roles = roles.get(user_uuid, [])
        categories = [cat for cat in categories if self.may_read(user_uuid, cat, rules=rules[cat["id"]], roles=roles)]
        # category counters
        stat = self.objlist(ForumCategoryStatList, [cat["id"] for cat in categories])
        stat.load(silent=True)
        stat = dict([(s.uuid, s) for s in stat])
        # unread topics
        unread = {}
        semi_user_uuid = self.call("socio.semi_user")
        if semi_user_uuid:
            topics = self.objlist(ForumTopicList, query_index="updated-category", query_start=self.now(-31 * 86400))
            re_updated = re.compile(r'^(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)-([a-f0-9]+)-[a-f0-9]+$')
            top_updated = {}
            for top in topics.index_data:
                m = re_updated.match(top[0])
                if m:
                    upd, cat = m.group(1, 2)
                    top_updated[top[1]] = (upd, cat)
            lastread_list = self.objlist(ForumLastReadList, query_index="topic-user", query_equal=["%s-%s" % (topic, semi_user_uuid) for topic in top_updated.iterkeys()])
            lastread_list.load()
            lastread = dict([(lr.get("topic"), lr) for lr in lastread_list])
            for top, info in top_updated.iteritems():
                upd, cat = info
                if not unread.get(cat):
                    lr = lastread.get(top)
                    if lr is None or lr.get("last_post") < upd:
                        unread[cat] = True
        # generating template
        entries = []
        topcat = None
        odd = None
        for cat in categories:
            cat = cat.copy()
            if cat["topcat"] != topcat:
                topcat = cat["topcat"]
                entries.append({"header": topcat})
                odd = None
            st = stat.get(cat["id"])
            if st:
                topics = st.get_int("topics")
                replies = st.get_int("replies")
                if topics:
                    cat["topics"] = topics
                if replies:
                    cat["replies"] = replies
                cat["lastinfo"] = st.get("last")
            if unread.get(cat["id"]):
                cat["unread"] = True
            odd = 0 if odd else 1
            entries.append({"category": cat, "odd": odd})
        vars = {
            "categories": entries,
            "menu": [
                { "html": self._("Forum categories") },
                { "href": "/forum/subscribed", "html": self._("Subscribed topics") },
            ],
        }
        self.call("forum.vars-index", vars)
        self.call("socio.response_template", "index.html", vars)

    def category(self, id):
        for cat in self.categories():
            if cat["id"] == id:
                return cat

    def category_by_tag(self, tag):
        if not tag:
            return None
        for cat in self.categories():
            if cat.get("tag") == tag:
                return cat

    def categories(self):
        cats = self.conf("forum.categories")
        if cats is None:
            cats = []
            self.call("forum-admin.init-categories", cats)
            conf = self.app().config_updater()
            conf.set("forum.categories", cats)
            conf.store()
        cats.sort(key=itemgetter("order"))
        return cats

    def load_rules(self, cat_ids):
        lst = self.objlist(ForumPermissionsList, cat_ids)
        lst.load(silent=True)
        rules = dict([(ent.uuid, ent.get("rules")) for ent in lst])
        for cat in cat_ids:
            if not rules.get(cat):
                lst = []
                self.call("forum-admin.default_rules", lst)
                rules[cat] = lst
        return rules

    def load_rules_roles(self, user_uuid, cat, rules=None, roles=None):
        if rules is None:
            rules = self.load_rules([cat["id"]])[cat["id"]]
        if roles is None:
            if user_uuid is None:
                roles = ["notlogged", "all"]
            else:
                roles = {}
                self.call("security.users-roles", [user_uuid], roles)
                roles = roles[user_uuid]
        return (rules, roles)

    def may_read(self, user_uuid, cat, rules=None, roles=None):
        rules, roles = self.load_rules_roles(user_uuid, cat, rules, roles)
        if rules is None:
            return False
        for ent in rules:
            role = ent[0]
            perm = ent[1]
            if (perm == "+R" or perm == "+W") and role in roles:
                return True
            if perm == "-R" and role in roles:
                return False
        return False

    def silence(self, user):
        if user is None:
            return None
        restraints = {}
        self.call("restraints.check", user, restraints)
        return restraints.get("forum-silence")

    def may_write(self, cat, topic=None, rules=None, roles=None, errors=None):
        req = self.req()
        user = self.call("socio.user")
        if user is None:
            if errors is not None:
                errors["may_write"] = self._("You are not logged in")
            return False
        if self.silence(user):
            if errors is not None:
                errors["may_write"] = self._("Silence restraint")
            return False
        rules, roles = self.load_rules_roles(user, cat, rules, roles)
        if rules is None:
            return False
        for ent in rules:
            role = ent[0]
            perm = ent[1]
            if perm == "+W" and role in roles:
                return True
            if (perm == "-W" or perm == "-R") and role in roles:
                if errors is not None and len(ent) >= 3 and ent[2]:
                    errors["may_write"] = ent[2]
                return False
        return False

    def may_create_topic(self, cat, topic=None, rules=None, roles=None, errors=None):
        req = self.req()
        user = self.call("socio.user")
        if user is None:
            if errors is not None:
                errors["may_create_topic"] = self._("You are not logged on")
            return False
        if self.silence(user):
            if errors is not None:
                errors["may_create_topic"] = self._("Silence restraint")
            return False
        rules, roles = self.load_rules_roles(user, cat, rules, roles)
        if rules is None:
            return False
        for ent in rules:
            role = ent[0]
            perm = ent[1]
            if (perm == "+C") and role in roles:
                return True
            if (perm == "-C" or perm == "-R") and role in roles:
                if errors is not None and len(ent) >= 3 and ent[2]:
                    errors["may_create_topic"] = ent[2]
                return False
        return False

    def may_edit(self, cat, topic=None, post=None, rules=None, roles=None):
        req = self.req()
        user = self.call("socio.user")
        if user is None:
            return False
        if self.silence(user):
            return False
        rules, roles = self.load_rules_roles(user, cat, rules, roles)
        if rules is None:
            return False
        for ent in rules:
            role = ent[0]
            perm = ent[1]
            if (perm == "-W" or perm == "-R") and role in roles:
                return False
        for ent in rules:
            role = ent[0]
            perm = ent[1]
            if perm == "-M" and role in roles:
                break
            if perm == "+M" and role in roles:
                return True
        if post is None:
            if topic.get("author") == user and topic.get("created") > self.now(-900):
                return True
        else:
            if post.get("author") == user and post.get("created") > self.now(-900):
                return True
        return False

    def may_moderate(self, cat, topic=None, rules=None, roles=None):
        req = self.req()
        user = self.call("socio.user")
        if user is None:
            return False
        if self.silence(user):
            return False
        rules, roles = self.load_rules_roles(user, cat, rules, roles)
        if rules is None:
            return False
        for ent in rules:
            role = ent[0]
            perm = ent[1]
            if (perm == "-W" or perm == "-R") and role in roles:
                return False
        for ent in rules:
            role = ent[0]
            perm = ent[1]
            if perm == "-M" and role in roles:
                return False
            if perm == "+M" and role in roles:
                return True
        return False

    def may_pin(self, cat, topic=None, rules=None, roles=None):
        return self.may_moderate(cat, topic, rules, roles)

    def may_move(self, cat, topic=None, rules=None, roles=None):
        return self.may_moderate(cat, topic, rules, roles)

    def may_delete(self, cat, topic=None, post=None, rules=None, roles=None):
        return self.may_moderate(cat, topic, rules, roles)

    def topics(self, cat, page=1, tpp=topics_per_page):
        topics = self.objlist(ForumTopicList, query_index="category-updated", query_equal=cat["id"], query_reversed=True)
        pages = (len(topics) - 1) / tpp + 1
        if pages < 1:
            pages = 1
        if page < 1:
            page = 1
        elif page > pages:
            page = pages
        del topics[page * tpp:]
        del topics[0:(page - 1) * tpp]
        topics.load()
        return topics, page, pages

    def ext_category(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        cat = self.call("forum.category", req.args)
        if cat is None:
            self.call("web.not_found")
        # permissions
        rules, roles = self.load_rules_roles(user_uuid, cat)
        if not self.may_read(user_uuid, cat, rules=rules, roles=roles):
            self.call("web.forbidden")
        # getting list of topics
        page = intz(req.param("page"))
        topics, page, pages = self.topics(cat, page)
        topics = topics.data()
        self.topics_htmlencode(topics)
        if len(topics):
            topics[-1]["lst"] = True
        menu = [
            { "href": "/forum", "html": self._("Forum categories") },
            { "html": cat["title"] },
        ]
        errors = {}
        if self.may_create_topic(user_uuid, cat, rules=rules, roles=roles, errors=errors):
            menu.append({"href": "/forum/newtopic/%s" % cat["id"], "html": self._("New topic"), "right": True})
        elif errors.get("may_create_topic"):
            menu.append({"html": errors["may_create_topic"], "right": True})
        vars = {
            "title": cat["title"],
            "category": cat,
            "topics": topics if len(topics) else None,
            "menu": menu,
        }
        if pages > 1:
            pages_list = []
            last_show = None
            for i in range(1, pages + 1):
                show = (i <= 5) or (i >= pages - 5) or (abs(i - page) < 5)
                if show:
                    pages_list.append({"entry": {"text": i, "a": None if i == page else {"href": "/forum/cat/%s?page=%d" % (cat["id"], i)}}})
                elif last_show:
                    pages_list.append({"entry": {"text": "..."}})
                last_show = show
            pages_list[-1]["lst"] = True
            vars["pages"] = pages_list
        self.call("forum.vars-category", vars)
        self.call("socio.response_template", "category.html", vars)

    def load_settings(self, list, signatures, avatars, statuses):
        authors = dict([(ent.get("author"), True) for ent in list if ent.get("author")]).keys()
        if len(authors):
            grayscale_support = self.call("paidservices.socio_coloured_avatar")
            if grayscale_support:
                grayscale_support = self.conf("paidservices.enabled-socio_coloured_avatar", grayscale_support["default_enabled"])
            paid_images_support = self.call("paidservices.socio_signature_images")
            if paid_images_support:
                paid_images_support = self.conf("paidservices.enabled-socio_signature_images", paid_images_support["default_enabled"])
            paid_smiles_support = self.call("paidservices.socio_signature_smiles")
            if paid_smiles_support:
                paid_smiles_support = self.conf("paidservices.enabled-socio_signature_smiles", paid_smiles_support["default_enabled"])
            paid_colours_support = self.call("paidservices.socio_signature_colours")
            if paid_colours_support:
                paid_colours_support = self.conf("paidservices.enabled-socio_signature_colours", paid_colours_support["default_enabled"])
            # loading settings
            authors_list = self.objlist(UserForumSettingsList, authors)
            authors_list.load(silent=True)
            for obj in authors_list:
                grayscale = grayscale_support and not self.call("modifiers.kind", obj.uuid, "socio_coloured_avatar")
                signatures[obj.uuid] = self.call("socio.format_text", obj.get("signature"), {
                    "no_images": not self.conf("socio.signature-images", True) or (paid_images_support and not self.call("modifiers.kind", obj.uuid, "socio_signature_images")),
                    "no_smiles": not self.conf("socio.signature-smiles", False) or (paid_smiles_support and not self.call("modifiers.kind", obj.uuid, "socio_signature_smiles")),
                    "no_colours": not self.conf("socio.signature-colours", True) or (paid_colours_support and not self.call("modifiers.kind", obj.uuid, "socio_signature_colours")),
                    "max_smiles": self.conf("socio.signature-max-smiles", 3),
                })
                avatars[obj.uuid] = obj.get("avatar_gray" if grayscale else "avatar")
                statuses[obj.uuid] = htmlescape(obj.get("status"))
        for ent in list:
            author = ent.get("author")
            ent["avatar"] = avatars.get(author)
            ent["signature"] = signatures.get(author)
            ent["status"] = statuses.get(author)

    def topics_htmlencode(self, topics, load_settings=False):
        signatures = {}
        avatars = {}
        statuses = {}
        if load_settings:
            self.load_settings(topics, signatures, avatars, statuses)
        for topic in topics:
            topic["subject_html"] = htmlescape(topic.get("subject"))
            topic["author_html"] = topic.get("author_html")
            topic["posts"] = intz(topic.get("posts"))
            topic["literal_created"] = self.call("l10n.time_local", topic.get("created"))
            topic["literal_created_date"] = self.call("l10n.date_local", topic.get("created"))
            topic["created_date"] = re_format_date.sub(r'\3.\2.\1', topic.get("created"))
            if topic.get("last_post_created"):
                topic["last_post_created"] = self.call("l10n.time_local", topic["last_post_created"])
            menu = []
            menu.append({"title": self._("Profile"), "href": "/socio/user/%s" % topic.get("author")})
            self.call("socio.author_menu", topic.get("author"), topic.get("author_html"), menu)
            topic["author_menu"] = menu
            pages = (topic["posts"] - 1) / posts_per_page + 1
            if pages > 1:
                pages_list = []
                for i in range(1, pages + 1):
                    pages_list.append({"entry": {"text": i, "a": {"href": "/forum/topic/%s?page=%d" % (topic["uuid"], i)}}})
                pages_list[-1]["lst"] = True
                topic["pages"] = pages_list
        req = self.req()
        user_uuid = self.call("socio.semi_user")
        if user_uuid is not None:
            lastread_list = self.objlist(ForumLastReadList, query_index="topic-user", query_equal=["%s-%s" % (topic["uuid"], user_uuid) for topic in topics])
            lastread_list.load()
            lastread = dict([(lr.get("topic"), lr) for lr in lastread_list])
            for topic in topics:
                lr = lastread.get(topic["uuid"])
                if lr is None:
                    topic["unread"] = True
                else:
                    topic["subscribed"] = lr.get("subscribed")
                    topic["unread"] = topic["updated"] > lr.get("last_post")
        self.call("forum.topics_htmlencode", topics)

    def posts_htmlencode(self, posts):
        signatures = {}
        avatars = {}
        statuses = {}
        self.load_settings(posts, signatures, avatars, statuses)
        for post in posts:
            post["author_html"] = post.get("author_html")
            post["posts"] = intz(post.get("posts"))
            if post.get("content_html") is None:
                post["content_html"] = self.call("socio.format_text", post.get("content"))
            post["literal_created"] = self.call("l10n.time_local", post.get("created"))
            menu = []
            menu.append({"title": self._("Profile"), "href": "/socio/user/%s" % post.get("author")})
            self.call("socio.author_menu", post.get("author"), post.get("author_html"), menu)
            post["author_menu"] = menu
        self.call("forum.posts_htmlencode", posts)

    def ext_newtopic(self):
        req = self.req()
        cat = self.call("forum.category", req.args)
        if cat is None:
            self.call("web.not_found")
        if not self.may_create_topic(cat):
            self.call("web.forbidden")
        subject = req.param("subject")
        content = req.param("content")
        if cat.get("manual_date"):
            created = req.param("created")
        else:
            created = None
        if cat.get("allow_skip_notify"):
            notify = True if req.param("notify") else False
        else:
            notify = True
        params = {}
        self.call("forum.params", params)
        tags = req.param("tags")
        form = self.call("web.form")
        if req.ok():
            if not subject:
                form.error("subject", self._("Enter topic subject"))
            if not content:
                form.error("content", self._("Enter topic content"))
            if cat.get("manual_date") and created:
                if created == "":
                    created = None
                elif not re_valid_date.match(created):
                    form.error("created", self._("Invalid datetime format"))
            self.call("forum.topic-form", None, form, "validate")
            if not form.errors:
                if req.param("publish"):
                    user = self.obj(User, self.call("socio.user"))
                    topic = self.call("forum.newtopic", cat, user, subject, content, tags, date_from_human(created) if created else None, notify=notify)
                    self.call("forum.topic-form", topic, form, "store")
                    self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
                else:
                    form.add_message_top('<div class="socio-preview">%s</div>' % self.call("socio.format_text", content))
        if cat.get("manual_date"):
            form.input(self._("Topic date (dd.mm.yyyy or dd.mm.yyyy hh:mm:ss)"), "created", created)
        if cat.get("allow_skip_notify"):
            form.checkbox(self._("Notify other users about this topic"), "notify", notify)
        form.input(self._("Subject"), "subject", subject)
        form.texteditor(self._("Content"), "content", content)
        if params.get("show_tags", True):
            form.input(self._("Tags (delimited with commas)"), "tags", tags)
        form.submit(None, None, self._("Preview"))
        form.submit(None, "publish", self._("Publish"), inline=True)
        self.call("forum.topic-form", None, form, "form")
        vars = {
            "category": cat,
            "title": u"%s: %s" % (self._("New topic"), cat["title"]),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
                { "html": self._("New topic") },
            ],
        }
        self.call("socio.response", form.html(), vars)

    def newtopic(self, cat, author, subject, content, tags="", created=None, notify=True):
        topic = self.obj(ForumTopic)
        topic_content = self.obj(ForumTopicContent, topic.uuid, {})
        if created is None:
            created = self.now()
        topic.set("category", cat["id"])
        topic.set("created", created)
        topic.set("updated", created)
        catstat = self.catstat(cat["id"])
        catstat.set("updated", time.time())
        catstat.incr("topics")
        last = {
            "topic": topic.uuid,
        }
        if author is not None:
            author_name = author.get("name")
            author_html = htmlescape(author_name.encode("utf-8"))
            topic.set("author", author.uuid)
            topic.set("author_name", author_name)
            topic.set("author_html", author_html)
            last["author_html"] = author_html
            last["subject_html"] = htmlescape(subject)
            last["updated"] = self.call("l10n.time_local", created)
        catstat.set("last", last)
        topic.set("subject", subject)
        topic.sync()
        topic_content.set("content", content)
        topic_content.set("content_html", self.call("socio.format_text", content))
        # tags index
        tags = self.tags_store(topic.uuid, tags)
        # fulltext index
        words = list(chain(self.call("socio.word_extractor", subject), self.call("socio.word_extractor", content)))
        self.call("socio.fulltext_store", "ForumSearch", topic.uuid, words)
        # storing objects
        topic_content.set("tags", tags)
        topic.store()
        topic_content.store()
        if author is not None:
            self.subscribe(author.uuid, topic.uuid, cat["id"], created)
        catstat.store()
        if notify:
            self.call("queue.add", "forum.notify-newtopic", {"topic_uuid": topic.uuid}, retry_on_fail=True)
        return topic

    def tags_parse(self, tags_str):
        raw_tags = re_split_tags.split(tags_str) if tags_str != None and len(tags_str) else []
        tags = set()
        for i in range(0, len(raw_tags)):
            if i % 2 == 0:
                tag = raw_tags[i].strip()
                if len(tag):
                    tags.add(tag.lower())
        return [re_whitespace.sub(' ', tag) for tag in tags]

    def tags_store(self, uuid, tags_str):
        if tags_str is None:
            return
        tags = self.tags_parse(tags_str)
        mutations = {}
        mutations_tags = []
        timestamp = time.time() * 1000
        app_tag = str(self.app().tag)
        for tag in tags:
            tag_short = tag
            if len(tag_short) > max_tag_len:
                tag_short = tag_short[0:max_tag_len]
            tag = tag.encode("utf-8")
            tag_short = tag_short.encode("utf-8")
            mutations_tags.append(Mutation(ColumnOrSuperColumn(Column(name=tag_short, value=tag, timestamp=timestamp))))
            mutations["%s-ForumTaggedTopics-%s" % (app_tag, tag_short)] = {"Indexes": [Mutation(ColumnOrSuperColumn(Column(name=str(uuid), value="1", timestamp=timestamp)))]}
        if len(mutations):
            mutations["%s-ForumTags" % app_tag] = {"Indexes": mutations_tags}
            self.app().db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
        return tags

    def tags_remove(self, uuid, tags_str):
        if type(tags_str) == list:
            tags = tags_str
        else:
            tags = self.tags_parse(tags_str)
        mutations = {}
        timestamp = time.time() * 1000
        app_tag = str(self.app().tag)
        short_tags = []
        for tag in tags:
            tag_short = tag
            if len(tag_short) > max_tag_len:
                tag_short = tag_short[0:max_tag_len]
            tag = tag.encode("utf-8")
            tag_short = tag_short.encode("utf-8")
            short_tags.append(tag_short)
            mutations["%s-ForumTaggedTopics-%s" % (app_tag, tag_short)] = {"Indexes": [Mutation(deletion=Deletion(predicate=SlicePredicate([str(uuid)]), timestamp=timestamp))]}
        if len(mutations):
            self.app().db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
            mutations = []
            for tag_utf8 in short_tags:
                topics = self.app().db.get_slice("%s-ForumTaggedTopics-%s" % (app_tag, tag_utf8), ColumnParent("Indexes"), SlicePredicate(slice_range=SliceRange("", "", count=1)), ConsistencyLevel.QUORUM)
                if not topics:
                    mutations.append(Mutation(deletion=Deletion(predicate=SlicePredicate([tag_utf8]), timestamp=timestamp)))
            if len(mutations):
                self.db().batch_mutate({"%s-ForumTags" % app_tag: {"Indexes": mutations}}, ConsistencyLevel.QUORUM)
        return tags

    def reply(self, cat, topic, author, content):
        with self.lock(["ForumTopic-" + topic.uuid]):
            post = self.obj(ForumPost)
            now = self.now()
            post.set("category", cat["id"])
            post.set("topic", topic.uuid)
            post.set("created", now)
            catstat = self.catstat(cat["id"])
            catstat.set("updated", time.time())
            catstat.incr("replies")
            last = {
                "topic": topic.uuid,
                "post": post.uuid,
            }
            if author is not None:
                author_name = author.get("name")
                author_html = htmlescape(author_name.encode("utf-8"))
                post.set("author", author.uuid)
                post.set("author_name", author_name)
                post.set("author_html", author_html)
                last["author_html"] = author_html
                last["subject_html"] = htmlescape(topic.get("subject"))
                last["updated"] = self.call("l10n.time_local", now)
            catstat.set("last", last)
            post.set("content", content)
            post.set("content_html", self.call("socio.format_text", content))
            post.store()
            if author is not None:
                self.subscribe(author.uuid, topic.uuid, cat["id"], now)
            posts = len(self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid))
            page = (posts - 1) / posts_per_page + 1
            catstat.store()
            self.call("queue.add", "forum.notify-reply", {"topic_uuid": topic.uuid, "page": page, "post_uuid": post.uuid}, retry_on_fail=True)
            self.call("socio.fulltext_store", "ForumSearch", post.uuid, self.call("socio.word_extractor", content))
            raise Hooks.Return((post, page))

    def ext_topic(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        try:
            topic = self.obj(ForumTopic, req.args)
            topic_content = self.obj(ForumTopicContent, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        cat = self.call("forum.category", topic.get("category"))
        if cat is None:
            self.call("web.not_found")
        # permissions
        rules, roles = self.load_rules_roles(user_uuid, cat)
        if not self.may_read(user_uuid, cat, rules=rules, roles=roles):
            self.call("web.forbidden")
        # find a post
        if req.param("post"):
            uuid = req.param("post")
            posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
            for i in range(0, len(posts)):
                if posts[i].uuid == uuid:
                    self.call("web.redirect", "/forum/topic/%s?page=%d#%s" % (topic.uuid, (i / posts_per_page + 1), uuid))
            if len(posts):
                self.call("web.redirect", "/forum/topic/%s?page=%s" % (topic.uuid, uuid))
            else:
                self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
        # topic contents
        may_write = self.may_write(cat, topic, rules=rules, roles=roles)
        topic_data = topic.data_copy()
        topic_data["content"] = topic_content.get("content")
        topic_data["content_html"] = topic_content.get("content_html")
        if topic_content.get("tags"):
            topic_data["tags_html"] = ", ".join(['<a href="/forum/tag/%s">%s</a>' % (tag, tag) for tag in [htmlescape(tag) for tag in topic_content.get("tags")]])
        self.topics_htmlencode([topic_data], load_settings=True)
        # preparing menu
        menu = [
            { "href": "/forum", "html": self._("Forum categories") },
            { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
            { "html": self._("Topic") },
        ]
        actions = []
        if self.may_delete(cat, topic, rules=rules, roles=roles):
            menu.append({"href": "/forum/delete/%s" % topic.uuid, "html": self._("delete"), "right": True})
        if self.may_edit(cat, topic, rules=rules, roles=roles):
            actions.append('<a href="/forum/edit/' + topic.uuid + '">' + self._("edit") + '</a>')
        if may_write:
            actions.append('<a href="/forum/reply/' + topic.uuid + '">' + self._("reply") + '</a>')
        if len(actions):
            topic_data["topic_actions"] = " / ".join(actions)
        # getting list of posts
        page = intz(req.param("page"))
        posts, page, pages, last_post = self.posts(topic, page)
        # updating lastread
        user_uuid = self.call("socio.semi_user")
        if user_uuid is not None:
            lastread = self.lastread(user_uuid, topic.uuid, cat["id"])
            if last_post is not None:
                created = last_post.get("created")
            else:
                created = topic.get("created")
            if lastread.get("last_post", "") < created:
                lastread.set("last_post", created)
            lastread.delkey("email_notified")
            lastread.store()
            if self.call("socio.user"):
                redirect = urlencode(req.uri())
                if lastread.get("subscribed"):
                    menu.append({"href": "/forum/unsubscribe/%s?redirect=%s" % (topic.uuid, redirect), "html": self._("unsubscribe"), "right": True})
                else:
                    menu.append({"href": "/forum/subscribe/%s?redirect=%s" % (topic.uuid, redirect), "html": self._("subscribe"), "right": True})
                if self.may_pin(cat, topic, rules=rules, roles=roles):
                    if topic.get("pinned"):
                        menu.append({"href": "/forum/unpin/%s?redirect=%s" % (topic.uuid, redirect), "html": self._("unpin"), "right": True})
                    else:
                        menu.append({"href": "/forum/pin/%s?redirect=%s" % (topic.uuid, redirect), "html": self._("pin"), "right": True})
                if self.may_move(cat, topic, rules=rules, roles=roles):
                    menu.append({"href": "/forum/move/%s?redirect=%s" % (topic.uuid, redirect), "html": self._("move"), "right": True})
        self.call("forum.topic-menu", topic, menu)
        # preparing posts to rendering
        posts = posts.data()
        self.posts_htmlencode(posts)
        for post in posts:
            actions = []
            if self.may_delete(cat, topic, post, rules=rules, roles=roles):
                actions.append('<a href="/forum/delete/' + topic.uuid + '/' + post["uuid"] + '">' + self._("delete") + '</a>')
            if self.may_edit(cat, topic, post, rules=rules, roles=roles):
                actions.append('<a href="/forum/edit/' + topic.uuid + '/' + post["uuid"] + '">' + self._("edit") + '</a>')
            if may_write:
                actions.append('<a href="/forum/reply/' + topic.uuid + '/' + post["uuid"] + '">' + self._("reply") + '</a>')
            if len(actions):
                post["post_actions"] = " / ".join(actions)
        # reply form
        content = req.param("content")
        form = self.call("web.form", action="/forum/topic/" + topic.uuid + "#post-form")
        if req.ok():
            errors = {}
            if not content:
                form.error("content", self._("Enter post content"))
            elif not self.may_write(cat, rules=rules, roles=roles, errors=errors):
                form.error("content", errors.get("may_write", self._("Access denied")))
            if not form.errors:
                if req.param("save"):
                    print "posting reply"
                    user = self.obj(User, self.call("socio.user"))
                    post, page = self.call("forum.reply", cat, topic, user, content)
                    self.call("web.redirect", "/forum/topic/%s?page=%d#%s" % (topic.uuid, page, post.uuid))
                else:
                    form.add_message_top('<div class="socio-preview">%s</div>' % self.call("socio.format_text", content))
        # making web response
        vars = {
            "topic": topic_data,
            "category": cat,
            "title": topic_data.get("subject_html"),
            "show_topic": page <= 1,
            "posts": posts,
            "menu": menu,
        }
        errors = {}
        if req.ok() or (self.may_write(cat, rules=rules, roles=roles, errors=errors) and (page == pages)):
            if errors.get("may_write"):
                form.error("content", errors["may_write"])
            form.texteditor(None, "content", content)
            form.submit(None, "preview", self._("Preview"))
            form.submit(None, "save", self._("Post reply"), inline=True)
            if req.ok():
                self.call("socio.response", form.html(), vars)
            vars["new_post_form"] = form.html()
        else:
            if errors.get("may_write"):
                vars["new_post_form"] = u'<div class="socio-access-error">%s</div>' % errors["may_write"]
        if pages > 1:
            pages_list = []
            last_show = None
            for i in range(1, pages + 1):
                show = (i <= 5) or (i >= pages - 5) or (abs(i - page) < 5)
                if show:
                    pages_list.append({"entry": {"text": i, "a": None if i == page else {"href": "/forum/topic/%s?page=%d" % (topic.uuid, i)}}})
                elif last_show:
                    pages_list.append({"entry": {"text": "..."}})
                last_show = show
            pages_list[-1]["lst"] = True
            vars["pages"] = pages_list
        vars["share_url"] = htmlescape("http://%s%s" % (getattr(self.app(), "canonical_domain", "www.%s" % self.app().domain), req.uri()))
        self.call("forum.vars-topic", vars)
        self.call("socio.response_template", "topic.html", vars)

    def lastread(self, user_uuid, topic_uuid, category_uuid):
        if user_uuid is None:
            return None
        list = self.objlist(ForumLastReadList, query_index="topic-user", query_equal="%s-%s" % (topic_uuid, user_uuid))
        if len(list):
            list.load()
            return list[0]
        else:
            return self.obj(ForumLastRead, data={"topic": topic_uuid, "user": user_uuid, "category": category_uuid})

    def subscribe(self, user_uuid, topic_uuid, category_uuid, now):
        lastread = self.lastread(user_uuid, topic_uuid, category_uuid)
        lastread.set("last_post", now)
        lastread.set("subscribed", 1)
        lastread.store()

    def unsubscribe(self, user_uuid, topic_uuid, category_uuid, now):
        lastread = self.lastread(user_uuid, topic_uuid, category_uuid)
        lastread.set("last_post", now)
        lastread.delkey("subscribed")
        lastread.store()

    def posts(self, topic, page=1):
        posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
        pages = (len(posts) - 1) / posts_per_page + 1
        if pages < 1:
            pages = 1
        lock = self.lock(["ForumTopic-" + topic.uuid])
        if len(posts):
            last_post = posts[-1]
            last_post.load()
            if topic.get("last_post") != last_post.uuid:
                if not lock.locked:
                    lock.__enter__()
                    topic.load()
                topic.set("last_post", last_post.uuid)
                topic.set("last_post_page", pages)
                topic.set("last_post_created", last_post.get("created"))
                topic.set("last_post_author", last_post.get("author"))
                topic.set("last_post_author_name", last_post.get("author_name"))
                topic.set("last_post_author_html", htmlescape(last_post.get("author_name")))
            updated = last_post.get("created")
        else:
            last_post = None
            if topic.get("last_post"):
                if not lock.locked:
                    lock.__enter__()
                    topic.load()
                topic.delkey("last_post")
                topic.delkey("last_post_page")
                topic.delkey("last_post_created")
                topic.delkey("last_post_author")
                topic.delkey("last_post_author_name")
                topic.delkey("last_post_author_html")
            updated = topic.get("created")
        if topic.get("updated") != updated:
            if not lock.locked:
                lock.__enter__()
                topic.load()
            topic.set("updated", updated)
        if topic.get("posts") != len(posts):
            if not lock.locked:
                lock.__enter__()
                topic.load()
            topic.set("posts", len(posts))
        if lock.locked:
            topic.sync()
            topic.store()
            lock.__exit__(None, None, None)
        if page < 1:
            page = 1
        elif page > pages:
            page = page
        del posts[page * posts_per_page:]
        del posts[0:(page - 1) * posts_per_page]
        posts.load()
        return posts, page, pages, last_post

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
            topic_content = self.obj(ForumTopicContent, topic.uuid)
            old_content = topic_content.get("content")
        topic_data = topic.data_copy()
        self.topics_htmlencode([topic_data])
        req = self.req()
        content = req.param("content")
        form = self.call("web.form")
        if req.ok():
            if not content:
                form.error("content", self._("Enter post content"))
            if not form.errors:
                user = self.obj(User, self.call("socio.user"))
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
        self.call("socio.response", form.html(), vars)

    def update_last(self, cat, stat):
        topics = self.objlist(ForumTopicList, query_index="category-list", query_equal=cat["id"], query_reversed=True, query_limit=1)
        topics.load(silent=True)
        posts = self.objlist(ForumPostList, query_index="category", query_equal=cat["id"], query_reversed=True, query_limit=1)
        posts.load(silent=True)
        last_topic = topics[0] if len(topics) else None
        last_post = posts[0] if len(posts) else None
        if last_topic is None:
            stat.delkey("last")
        elif last_post is not None and last_post.get("created") > last_topic.get("created"):
            topic = self.obj(ForumTopic, last_post.get("topic"))
            stat.set("last", {
                "topic": topic.uuid,
                "post": last_post.uuid,
                "author_html": last_post.get("author_html"),
                "subject_html": htmlescape(topic.get("subject")),
                "updated": self.call("l10n.time_local", last_post.get("created")),
            })
        else:
            stat.set("last", {
                "topic": last_topic.uuid,
                "author_html": last_topic.get("author_html"),
                "subject_html": htmlescape(last_topic.get("subject")),
                "updated": self.call("l10n.time_local", last_topic.get("created")),
            })

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
                    if i < len(posts) - 1:
                        prev = "#%s" % posts[i + 1].uuid
                        page = i / posts_per_page + 1
                    elif i > 0:
                        prev = "#%s" % posts[i - 1].uuid
                        page = (i - 1) / posts_per_page + 1
                    else:
                        page = 1
                    break
            post.remove()
            catstat = self.catstat(cat["id"])
            catstat.decr("replies")
            if catstat.get("last") and catstat.get("last").get("post") == post.uuid:
                self.update_last(cat, catstat)
            catstat.store()
            self.call("web.redirect", "/forum/topic/%s?page=%d%s" % (topic.uuid, page, prev))
        else:
            posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
            posts.remove()
            lastread = self.objlist(ForumLastReadList, query_index="topic", query_equal=topic.uuid)
            lastread.remove()
            topic.remove()
            topic_content = self.obj(ForumTopicContent, topic.uuid, {})
            topic_content.remove()
            self.call("forum.topic-form", topic, None, "delete")
            catstat = self.catstat(cat["id"])
            catstat.decr("topics")
            catstat.decr("replies", len(posts))
            if catstat.get("last") and catstat.get("last").get("topic") == topic.uuid:
                self.update_last(cat, catstat)
            catstat.store()
            self.call("web.redirect", "/forum/cat/%s" % cat["id"])

    def ext_edit(self):
        cat, topic, post = self.category_or_topic_args()
        if not self.may_edit(cat, topic, post):
            self.call("web.forbidden")
        req = self.req()
        form = self.call("web.form")
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
                    self.call("socio.fulltext_remove", "ForumSearch", post.uuid)
                    self.call("socio.fulltext_store", "ForumSearch", post.uuid, self.call("socio.word_extractor", content))
                    posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
                    for i in range(0, len(posts)):
                        if posts[i].uuid == post.uuid:
                            page = i / posts_per_page + 1
                            self.call("web.redirect", "/forum/topic/%s?page=%d#%s" % (topic.uuid, page, post.uuid))
                    self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
            else:
                content = post.get("content")
            form.texteditor(None, "content", content)
        else:
            topic_content = self.obj(ForumTopicContent, topic.uuid)
            vars["title"] = self._("Edit topic")
            subject = req.param("subject")
            content = req.param("content")
            tags = req.param("tags")
            params = {}
            self.call("forum.params", params)
            if req.ok():
                if not subject:
                    form.error("subject", self._("Enter topic subject"))
                if not content:
                    form.error("content", self._("Enter topic content"))
                for tag in self.tags_parse(tags):
                    errors = []
                    if not re_valid_tag.match(tag):
                        errors.append(self._("Tag '%s' is invalid - only letters, digits, spaces, underscore and minus are allowed") % htmlescape(tag))
                    if len(errors):
                        form.error("tags", "<br />".join(errors))
                self.call("forum.topic-form", topic, form, "validate")
                if not form.errors:
                    with self.lock(["ForumTopic-" + topic.uuid]):
                        topic.set("subject", subject)
                        topic_content.set("content", content)
                        topic_content.set("content_html", self.call("socio.format_text", content))
                        self.tags_remove(topic.uuid, topic_content.get("tags"))
                        tags = self.tags_store(topic.uuid, tags)
                        topic_content.set("tags", tags)
                        topic.store()
                        topic_content.store()
                        self.call("forum.topic-form", topic, form, "store")
                        self.call("socio.fulltext_remove", "ForumSearch", topic.uuid)
                        self.call("socio.fulltext_store", "ForumSearch", topic.uuid, list(chain(self.call("socio.word_extractor", subject), self.call("socio.word_extractor", content))))
                    self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
            else:
                subject = topic.get("subject")
                content = topic_content.get("content")
                tags = ", ".join(topic_content.get("tags")) if topic_content.get("tags") else ""
            form.input(self._("Subject"), "subject", subject)
            form.texteditor(self._("Content"), "content", content)
            if params.get("show_tags", True):
                form.input(self._("Tags (delimited with commas)"), "tags", tags)
            self.call("forum.topic-form", topic, form, "form")
        form.submit(None, None, self._("Save"))
        self.call("socio.response", form.html(), vars)

    def ext_settings(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        try:
            settings = self.obj(UserForumSettings, user_uuid)
        except ObjectNotFoundException:
            settings = self.obj(UserForumSettings, user_uuid, {})
        vars = {
            "title": self._("Forum settings"),
        }
        # categories list
        categories = self.categories()
        rules = self.load_rules([cat["id"] for cat in categories])
        roles = {}
        self.call("security.users-roles", [user_uuid], roles)
        roles = roles.get(user_uuid, [])
        categories = [cat for cat in categories if self.may_read(user_uuid, cat, rules[cat["id"]], roles)]
        # settings form
        form = self.call("web.form")
        form.textarea_rows = 4
        signature = req.param("signature")
        avatar = req.param_raw("avatar")
        redirect = req.param("redirect")
        if redirect is None or redirect == "":
            redirect = "/forum"
        notify_replies = req.param("notify_replies")
        notify = {}
        for cat in categories:
            notify[cat["id"]] = req.param("notify_%s" % cat["id"])
        # paid services
        grayscale_support = self.call("paidservices.socio_coloured_avatar")
        if grayscale_support:
            grayscale_support = self.conf("paidservices.enabled-socio_coloured_avatar", grayscale_support["default_enabled"])
        grayscale = grayscale_support and not self.call("modifiers.kind", user_uuid, "socio_coloured_avatar")
        paid_images_support = self.call("paidservices.socio_signature_images")
        if paid_images_support:
            paid_images_support = self.conf("paidservices.enabled-socio_signature_images", paid_images_support["default_enabled"])
        paid_smiles_support = self.call("paidservices.socio_signature_smiles")
        if paid_smiles_support:
            paid_smiles_support = self.conf("paidservices.enabled-socio_signature_smiles", paid_smiles_support["default_enabled"])
        paid_colours_support = self.call("paidservices.socio_signature_colours")
        if paid_colours_support:
            paid_colours_support = self.conf("paidservices.enabled-socio_signature_colours", paid_colours_support["default_enabled"])
        if req.ok():
            signature = re_trim.sub(r'\1', signature)
            signature = re_r.sub('', signature)
            signature = re_emptylines.sub('\n', signature)
            signature = re_trimlines.sub(r'\1', signature)
            lines = signature.split('\n')
            if len(lines) > 4:
                form.error("signature", self._("Signature can't contain more than 4 lines"))
            else:
                smiles = self.call("smiles.dict")
                total_w = 0
                total_h = 0
                smiles_present = 0
                colours_present = False
                for line in lines:
                    if len(line) > 80:
                        form.error("signature", self._("Signature line couldn't be longer than 80 symbols"))
                    else:
                        images = re_images.findall(line)
                        if images:
                            if not self.conf("socio.signature-images", True):
                                form.error("signature", self._("Signature can't contain images"))
                                break
                            else:
                                if paid_images_support and not self.call("modifiers.kind", user_uuid, "socio_signature_images"):
                                    form.error("signature", self._('To use images in the signature <a href="/socio/paid-services">subscribe to the corresponding service</a>'))
                                    break
                                else:
                                    for img_id in images:
                                        try:
                                            img = self.obj(SocioImage, img_id)
                                        except ObjectNotFoundException:
                                            form.error("signature", self._("Invalid image: [img:%s]") % img_id)
                                            break
                                        img_uri = img.get("thumbnail") or img.get("image")
                                        try:
                                            img_data = self.download(img_uri)
                                        except DownloadError:
                                            form.error("signature", self._("Error downloading [img:%s]") % img_id)
                                            break
                                        try:
                                            img_obj = Image.open(cStringIO.StringIO(img_data))
                                            if img_obj.load() is None:
                                                form.error("signature", self._("Image [img:%s] format error") % img_id)
                                                break
                                        except IOError:
                                            form.error("signature", self._("Image [img:%s] IO error") % img_id)
                                            break
                                        except OverflowError:
                                            form.error("signature", self._("Image [img:%s] overflow error") % img_id)
                                            break
                                        img_w, img_h = img_obj.size
                                        total_w += img_w
                                        total_h += img_h
                        tokens = self.call("smiles.split", line)
                        if tokens and len(tokens) > 1:
                            for token in tokens:
                                if smiles.get(token):
                                    smiles_present += 1
                        if re_color_present.search(line):
                            colours_present = True
                max_w = self.conf("socio.signature-images-width", 800)
                max_h = self.conf("socio.signature-images-height", 60)
                if total_w > max_w or total_h > max_h:
                    form.error("signature", self._("Total dimensions of images in your signature are {img_w}x{img_h}. Max permitted are {max_w}x{max_h}. Resize your images to meet this condition").format(img_w=total_w, img_h=total_h, max_w=max_w, max_h=max_h))
                if smiles_present > 0:
                    if not self.conf("socio.signature-smiles", False):
                        form.error("signature", self._("Signature can't contain smiles"))
                    else:
                        if paid_smiles_support and not self.call("modifiers.kind", user_uuid, "socio_signature_smiles"):
                            form.error("signature", self._('To use smiles in the signature <a href="/socio/paid-services">subscribe to the corresponding service</a>'))
                        else:
                            max_s = self.conf("socio.signature-max-smiles", 3)
                            if smiles_present > max_s:
                                form.error("signature", self._("Signature can contain at most {max} {smiles}").format(max=max_s, smiles=self.call("l10n.literal_value", max_s, self._("smile/smiles"))))
                if colours_present:
                    if not self.conf("socio.signature-colours", True):
                        form.error("signature", self._("Signature can't contain colours"))
                    else:
                        if paid_colours_support and not self.call("modifiers.kind", user_uuid, "socio_signature_colours"):
                            form.error("signature", self._('To use colours in the signature <a href="/socio/paid-services">subscribe to the corresponding service</a>'))
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
                            image_obj = image_obj.crop((left, top, left + 100, top + 100))
                        elif height > 100:
                            left = 0
                            top = (height - 100) / 2
                            image_obj = image_obj.crop((left, top, left + 100, top + 100))
            if not form.errors:
                old_uri = []
                if image_obj:
                    # storing
                    im_data = cStringIO.StringIO()
                    image_obj.save(im_data, target_format)
                    im_data = im_data.getvalue()
                    if grayscale_support:
                        gray_data = cStringIO.StringIO()
                        ImageEnhance.Brightness(image_obj.convert("L")).enhance(1.5).save(gray_data, target_format)
                        #image_obj.convert("L").save(gray_data, target_format)
                        gray_data = gray_data.getvalue()
                    try:
                        old_uri.append(settings.get("avatar"))
                        old_uri.append(settings.get("avatar_gray"))
                        settings.set("avatar", self.call("cluster.static_upload", "avatars", ext, content_type, im_data))
                        if grayscale_support:
                            settings.set("avatar_gray", self.call("cluster.static_upload", "avatars", ext, content_type, gray_data))
                        else:
                            settings.delkey("avatar_gray")
                    except StaticUploadError as e:
                        form.error("avatar", unicode(e))
                settings.set("signature", signature)
                settings.delkey("signature_html")
                notify_any = False
                for cat in categories:
                    settings.set("notify_%s" % cat["id"], True if notify[cat["id"]] else False)
                    if notify[cat["id"]]:
                        notify_any = True
                if notify_any:
                    settings.set("notify_any", 1)
                else:
                    settings.delkey("notify_any")
                settings.set("notify_replies", True if notify_replies else False)
                settings.store()
                for uri in old_uri:
                    if uri:
                        self.call("cluster.static_delete", uri)
                self.call("web.redirect", redirect)
        else:
            signature = settings.get("signature")
            notify_replies = settings.get("notify_replies", True)
            for cat in categories:
                notify[cat["id"]] = settings.get("notify_%s" % cat["id"], cat.get("default_subscribe"))
        form.hidden("redirect", redirect)
        form.file(self._("Change avatar") if avatar else self._("Your avatar"), "avatar")
        form.texteditor(self._("Your forum signature"), "signature", signature)
        form.checkbox(self._("Replies in subscribed topics"), "notify_replies", notify_replies, description=self._("E-mail notifications"))
        for cat in categories:
            form.checkbox(self._("New topics in '{topcat} / {cat}'").format(topcat=cat["topcat"], cat=cat["title"]), "notify_%s" % cat["id"], notify.get(cat["id"]))
        form.add_message_top('<a href="%s">%s</a>' % (redirect, self._("Return")))
        avatar = settings.get("avatar_gray" if grayscale else "avatar")
        if avatar:
            form.add_message_top('<div class="form-avatar-demo"><img src="%s" alt="" /></div>' % avatar)
        if grayscale:
            form.add_message_top(self._('You can use grayscale avatars only. To get an ability to upload coloured avatars <a href="/socio/paid-services">please subscribe</a>'))
        self.call("socio.response", form.html(), vars)

    def ext_subscribe(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        try:
            topic = self.obj(ForumTopic, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        cat = self.call("forum.category", topic.get("category"))
        if cat is None:
            self.call("web.not_found")
        if not self.may_read(user_uuid, cat):
            self.call("web.forbidden")
        self.subscribe(user_uuid, topic.uuid, cat["id"], self.now())
        redirect = req.param("redirect")
        if redirect is not None and redirect != "":
            self.call("web.redirect", redirect)
        self.call("web.redirect", "/forum/topic/%s" % topic.uuid)

    def ext_unsubscribe(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        try:
            topic = self.obj(ForumTopic, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        cat = self.call("forum.category", topic.get("category"))
        if cat is None:
            self.call("web.not_found")
        if not self.may_read(user_uuid, cat):
            self.call("web.forbidden")
        self.unsubscribe(user_uuid, topic.uuid, cat["id"], self.now())
        redirect = req.param("redirect")
        if redirect is not None and redirect != "":
            self.call("web.redirect", redirect)
        self.call("web.redirect", "/forum/topic/%s" % topic.uuid)

    def ext_pin(self):
        req = self.req()
        with self.lock(["ForumTopic-" + req.args]):
            try:
                topic = self.obj(ForumTopic, req.args)
            except ObjectNotFoundException:
                self.call("web.not_found")
            cat = self.call("forum.category", topic.get("category"))
            if cat is None:
                self.call("web.not_found")
            if not self.may_pin(cat, topic):
                self.call("web.forbidden")
            topic.set("pinned", 1)
            topic.sync()
            topic.store()
        redirect = req.param("redirect")
        if redirect is not None and redirect != "":
            self.call("web.redirect", redirect)
        self.call("web.redirect", "/forum/topic/%s" % topic.uuid)

    def ext_unpin(self):
        req = self.req()
        with self.lock(["ForumTopic-" + req.args]):
            try:
                topic = self.obj(ForumTopic, req.args)
            except ObjectNotFoundException:
                self.call("web.not_found")
            cat = self.call("forum.category", topic.get("category"))
            if cat is None:
                self.call("web.not_found")
            if not self.may_pin(cat, topic):
                self.call("web.forbidden")
            topic.delkey("pinned")
            topic.sync()
            topic.store()
        redirect = req.param("redirect")
        if redirect is not None and redirect != "":
            self.call("web.redirect", redirect)
        self.call("web.redirect", "/forum/topic/%s" % topic.uuid)

    def ext_move(self):
        req = self.req()
        with self.lock(["ForumTopic-" + req.args]):
            try:
                topic = self.obj(ForumTopic, req.args)
            except ObjectNotFoundException:
                self.call("web.not_found")
            cat = self.call("forum.category", topic.get("category"))
            if cat is None:
                self.call("web.not_found")
            # permissions
            user_uuid = self.call("socio.user")
            categories = self.categories()
            rules = self.load_rules([c["id"] for c in categories])
            roles = {}
            self.call("security.users-roles", [user_uuid], roles)
            roles = roles.get(user_uuid, [])
            categories = [c for c in categories if c["id"] != cat["id"] and self.may_write(user_uuid, c, rules=rules[c["id"]], roles=roles)]
            if not self.may_create_topic(cat, topic, rules=rules[cat["id"]], roles=roles):
                self.call("web.forbidden")
            form = self.call("web.form")
            newcat = req.param("newcat")
            allowed = dict([(c["id"], True) for c in categories])
            if req.ok():
                if not allowed.get(newcat):
                    form.error("newcat", self._("Select category"))
                if not form.errors:
                    topic.set("category", newcat)
                    topic.sync()
                    topic.store()
                    posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
                    posts.load(silent=True)
                    for post in posts:
                        post.set("category", newcat)
                    posts.store()
                    self.call("forum.topic-form", topic, None, "update")
                    catstat = self.catstat(cat["id"])
                    catstat.decr("topics")
                    catstat.decr("replies", topic.get_int("posts"))
                    catstat.store()
                    catstat = self.catstat(newcat)
                    catstat.incr("topics")
                    catstat.incr("replies", topic.get_int("posts"))
                    catstat.store()
                    self.call("web.redirect", "/forum/cat/%s" % cat["id"])
        catlist = [{}]
        catlist.extend([{"value": c["id"], "description": c["title"]} for c in categories])
        form.select(self._("Category where to move"), "newcat", newcat, catlist)
        form.submit(None, None, self._("Move"))
        vars = {
            "title": self._("Move topic: %s") % topic.get("subject")
        }
        self.call("socio.response", form.html(), vars)

    def auth_registered(self, user):
        settings = self.obj(UserForumSettings, user.uuid, {})
        # categories list
        categories = self.categories()
        rules = self.load_rules([cat["id"] for cat in categories])
        roles = {}
        self.call("security.users-roles", [user.uuid], roles)
        roles = roles.get(user.uuid, [])
        categories = [cat for cat in categories if self.may_read(user.uuid, cat, rules[cat["id"]], roles)]
        for cat in categories:
            if cat.get("default_subscribe"):
                settings.set("notify_%s" % cat["id"], True)
                settings.set("notify_any", 1)
        settings.store()

    def notify_newtopic(self, topic_uuid):
        try:
            topic = self.obj(ForumTopic, topic_uuid)
        except ObjectNotFoundException:
            self.call("web.response_json", {"error": "Topic not found"})
        subscribers = self.objlist(UserForumSettingsList, query_index="notify-any", query_equal="1")
        subscribers.load()
        notify_str = "notify_%s" % topic.get("category")
        author = topic.get("author")
        users = []
        cat = self.call("forum.category", topic.get("category"))
        rules = self.load_rules([cat["id"]])
        for sub in subscribers:
            if sub.get(notify_str) and self.may_read(sub.uuid, cat, rules=rules[cat["id"]]) and sub.uuid != author:
                users.append(sub.uuid)
        if len(users):
            vars = {
                "author_name": topic.get("author_name"),
                "topic_subject": topic.get("subject"),
                "domain": self.app().domain,
                "topic_uuid": topic.uuid,
            }
            if author:
                author_obj = self.obj(User, author)
                sex = author_obj.get("sex", 0)
            else:
                sex = 0
            self.call("email.users", users, self._("New topic: %s") % topic.get("subject"), format_gender(sex, self._("{author_name} has started new topic: {topic_subject}\n\nhttp://www.{domain}/forum/topic/{topic_uuid}").format(**vars)), immediately=True)
        self.call("web.response_json", {"ok": 1})

    def notify_reply(self, topic_uuid, page, post_uuid):
        try:
            topic = self.obj(ForumTopic, topic_uuid)
        except ObjectNotFoundException:
            self.call("web.response_json", {"error": "Topic not found"})
        try:
            post = self.obj(ForumPost, post_uuid)
        except ObjectNotFoundException:
            self.call("web.response_json", {"error": "Post not found"})
        subscribers = self.objlist(ForumLastReadList, query_index="topic-subscribed", query_equal="%s-1" % topic.uuid)
        subscribers.load()
        author = post.get("author")
        users = []
        cat = self.call("forum.category", topic.get("category"))
        rules = self.load_rules([cat["id"]])
        now = time.time()
        for sub in subscribers:
            email_notified = sub.get("email_notified")
            if email_notified is None or float(email_notified) < now - 86400 * 3:
                user = sub.get("user")
                if user != author:
                    users.append(user)
                    sub.set("email_notified", now)
        subscribers.store()
        notify_users = []
        if len(users):
            settings = self.objlist(UserForumSettingsList, users)
            settings.load(silent=True)
            sets = dict([(set.uuid, set) for set in settings])
            for usr in users:
                set = sets.get(usr)
                if (set is None or set.get("notify_replies", True)) and self.may_read(usr, cat, rules=rules[cat["id"]]):
                    notify_users.append(usr)
        if len(notify_users):
            vars = {
                "author_name": post.get("author_name"),
                "topic_subject": topic.get("subject"),
                "domain": self.app().domain,
                "topic_uuid": topic.uuid,
                "post_uuid": post.uuid,
                "post_page": page,
            }
            if author:
                author_obj = self.obj(User, author)
                sex = author_obj.get("sex", 0)
            else:
                sex = 0
            self.call("email.users", notify_users, self._("New replies: %s") % topic.get("subject"), format_gender(sex, self._("{author_name} has replied in the topic: {topic_subject}\n\nhttp://www.{domain}/forum/topic/{topic_uuid}?page={post_page}#{post_uuid}").format(**vars)), immediately=True)
        self.call("web.response_json", {"ok": 1})

    def catstat(self, cat_id):
        return self.obj(ForumCategoryStat, cat_id, silent=True)

    def schedule(self, sched):
        sched.add("forum.sync", "0 1 * * *", priority=10)

    def sync(self):
        self.debug("Synchronizing forum")
        categories = self.categories()
        for cat in categories:
            topics = self.objlist(ForumTopicList, query_index="category-list", query_equal=cat["id"], query_reversed=True)
            for topic in topics:
                posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
                posts.load(silent=True)
                for post in posts:
                    post.set("category", cat["id"])
                posts.store()
            posts = self.objlist(ForumPostList, query_index="category", query_equal=cat["id"], query_reversed=True)
            stat = self.catstat(cat["id"])
            stat.set("topics", len(topics))
            stat.set("replies", len(posts))
            last_topic = self.obj(ForumTopic, topics[0].uuid) if len(topics) else None
            last_post = self.obj(ForumPost, posts[0].uuid) if len(posts) else None
            if last_topic is None:
                stat.delkey("last")
            elif last_post is not None and last_post.get("created") > last_topic.get("created"):
                topic = self.obj(ForumTopic, last_post.get("topic"))
                stat.set("last", {
                    "topic": topic.uuid,
                    "post": last_post.uuid,
                    "author_html": last_post.get("author_html"),
                    "subject_html": htmlescape(topic.get("subject")),
                    "updated": self.call("l10n.time_local", last_post.get("created")),
                })
            else:
                stat.set("last", {
                    "topic": last_topic.uuid,
                    "author_html": last_topic.get("author_html"),
                    "subject_html": htmlescape(last_topic.get("subject")),
                    "updated": self.call("l10n.time_local", last_topic.get("created")),
                })
            stat.store()
        # Updating tags
        app_tag = str(self.app().tag)
        tags = self.app().db.get_slice("%s-ForumTags" % app_tag, ColumnParent("Indexes"), SlicePredicate(slice_range=SliceRange("", "", count=10000000)), ConsistencyLevel.QUORUM)
        mutations = []
        timestamp = None
        for tag in tags:
            tag_utf8 = tag.column.name
            topics = self.app().db.get_slice("%s-ForumTaggedTopics-%s" % (app_tag, tag_utf8), ColumnParent("Indexes"), SlicePredicate(slice_range=SliceRange("", "", count=1)), ConsistencyLevel.QUORUM)
            if not topics:
                if timestamp is None:
                    timestamp = time.time() * 1000
                mutations.append(Mutation(deletion=Deletion(predicate=SlicePredicate([tag_utf8]), timestamp=timestamp)))
        if len(mutations):
            self.db().batch_mutate({"%s-ForumTags" % app_tag: {"Indexes": mutations}}, ConsistencyLevel.QUORUM)
        self.call("web.response_json", {"ok": 1})

    def ext_tag(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        categories = self.categories()
        rules = self.load_rules([cat["id"] for cat in categories])
        if user_uuid is None:
            roles = ["notlogged", "all"]
        else:
            roles = {}
            self.call("security.users-roles", [user_uuid], roles)
            roles = roles.get(user_uuid, [])
        may_read_category = set()
        for cat in categories:
            if self.may_read(user_uuid, cat, rules=rules[cat["id"]], roles=roles):
                may_read_category.add(cat["id"])
        # querying tag
        tag = req.args
        tag_utf8 = tag
        if len(tag_utf8) > max_tag_len:
            tag_utf8 = tag_utf8[0:max_tag_len]
        tag_utf8 = tag_utf8.encode("utf-8")
        app_tag = str(self.app().tag)
        topics = self.app().db.get_slice("%s-ForumTaggedTopics-%s" % (app_tag, tag_utf8), ColumnParent("Indexes"), SlicePredicate(slice_range=SliceRange("", "", count=10000000)), ConsistencyLevel.QUORUM)
        # loading topics
        render_topics = [topic.column.name for topic in topics]
        render_topics = self.objlist(ForumTopicList, render_topics)
        render_topics.load(silent=True)
        topics = [topic for topic in render_topics.data() if topic["category"] in may_read_category]
        self.topics_htmlencode(topics, load_settings=True)
        if len(topics):
            topics[-1]["lst"] = True
        vars = {
            "topics": topics if len(topics) else None,
            "author": self._("Author"),
            "replies": self._("Replies"),
            "last_reply": self._("Last reply"),
            "by": self._("by"),
            "title": htmlescape(tag),
            "message": "" if len(topics) else self._("Nothing found"),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "href": "/forum/tags", "html": self._("Tags") },
                { "html": htmlescape(tag) },
            ],
        }
        self.call("forum.vars-category", vars)
        self.call("socio.response_template", "category.html", vars)

    def ext_search(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        categories = self.categories()
        rules = self.load_rules([cat["id"] for cat in categories])
        if user_uuid is None:
            roles = ["notlogged", "all"]
        else:
            roles = {}
            self.call("security.users-roles", [user_uuid], roles)
            roles = roles.get(user_uuid, [])
        may_read_category = set()
        for cat in categories:
            if self.may_read(user_uuid, cat, rules=rules[cat["id"]], roles=roles):
                may_read_category.add(cat["id"])
        # querying
        query = req.args.lower().strip()
        words = list(self.call("socio.word_extractor", query))
        render_objects = self.call("socio.fulltext_search", "ForumSearch", words)
        if len(render_objects) > search_results_per_page:
            del render_objects[search_results_per_page:]
        posts = []
        while len(render_objects):
            get_cnt = 1000
            if get_cnt > len(render_objects):
                get_cnt = len(render_objects)
            bucket = [render_objects[i][1] for i in range(0, get_cnt)]
            del render_objects[0:get_cnt]
            loaded = dict()
            posts_list = self.objlist(ForumPostList, bucket)
            posts_list.load(silent=True)
            for post in posts_list:
                loaded[post.uuid] = post
            remain = [uuid for uuid in bucket if uuid not in loaded]
            if len(remain):
                topics_list = self.objlist(ForumTopicList, remain)
                topics_list.load(silent=True)
                topics_content_list = self.objlist(ForumTopicContentList, topics_list.uuids())
                topics_content_list.load(silent=True)
                topics_content = dict([(obj.uuid, obj.data) for obj in topics_content_list])
                for topic in topics_list:
                    loaded[topic.uuid] = topic
            bucket = [loaded.get(uuid) for uuid in bucket if loaded.get(uuid) and loaded.get(uuid).get("category") in may_read_category]
            for obj in bucket:
                data = obj.data_copy()
                if type(obj) == ForumTopic:
                    content = topics_content.get(obj.uuid)
                    if content is not None:
                        data["content_html"] = content.get("content_html")
                        self.topics_htmlencode([data], load_settings=True)
                        data["post_actions"] = '<a href="/forum/topic/%s">%s</a>' % (data.get("uuid"), self._("open"))
                        data["post_title"] = data.get("subject_html")
                        if content.get("tags"):
                            data["tags_html"] = ", ".join(['<a href="/forum/tag/%s">%s</a>' % (tag, tag) for tag in [htmlescape(tag) for tag in content.get("tags")]])
                        posts.append(data)
                else:
                    self.posts_htmlencode([data])
                    topic_posts = self.objlist(ForumPostList, query_index="topic", query_equal=data.get("topic"))
                    page = ""
                    for i in range(0, len(topic_posts)):
                        if topic_posts[i].uuid == data.get("uuid"):
                            page = "?page=%d" % (i / posts_per_page + 1)
                            break
                    data["post_actions"] = '<a href="/forum/topic/%s%s#%s">%s</a>' % (data.get("topic"), page, data.get("uuid"), self._("open"))
                    posts.append(data)
        if len(posts):
            posts[-1]["lst"] = True
        vars = {
            "search_query": htmlescape(query),
            "title": htmlescape(query),
            "posts": posts,
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "html": self._("results///Search") },
                { "html": htmlescape(query) },
            ],
            "Tags": self._("Tags"),
            "new_post_form": "" if len(posts) else self._("Nothing found")
        }
        self.call("socio.response_template", "topic.html", vars)

    def ext_subscribed(self):
        req = self.req()
        user_uuid = self.call("socio.user")
        categories = self.categories()
        rules = self.load_rules([cat["id"] for cat in categories])
        roles = {}
        self.call("security.users-roles", [user_uuid], roles)
        roles = roles.get(user_uuid, [])
        may_read_category = set()
        for cat in categories:
            if self.may_read(user_uuid, cat, rules=rules[cat["id"]], roles=roles):
                may_read_category.add(cat["id"])
        # querying
        lastreadlist = self.objlist(ForumLastReadList, query_index="user-subscribed", query_equal="%s-1" % user_uuid)
        lastreadlist.load(silent=True)
        topic_uuids = [lr.get("topic") for lr in lastreadlist if lr.get("category") in may_read_category]
        # loading topics
        topics = self.objlist(ForumTopicList, topic_uuids)
        topics.load(silent=True)
        topics = topics.data()
        self.topics_htmlencode(topics, load_settings=True)
        if len(topics):
            topics[-1]["lst"] = True
        vars = {
            "title": self._("Subscribed topics"),
            "topics": topics if len(topics) else None,
            "message": None if len(topics) else self._("You have not subscribed to any topic"),
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "html": self._("Subscribed topics") },
            ],
        }
        self.call("forum.vars-category", vars)
        self.call("socio.response_template", "category.html", vars)

    def ext_tags(self):
        app_tag = str(self.app().tag)
        tags = self.app().db.get_slice("%s-ForumTags" % app_tag, ColumnParent("Indexes"), SlicePredicate(slice_range=SliceRange("", "", count=10000000)), ConsistencyLevel.QUORUM)
        tags = [{"html": htmlescape(tag.column.value), "url": urlencode(tag.column.value)} for tag in tags]
        # It seems Cassandra always returns sorted results
        # tags.sort(cmp=lambda x, y: cmp(x["html"], y["html"]))
        if len(tags):
            tags[-1]["lst"] = True
        vars = {
            "tags": tags,
            "menu": [
                { "href": "/forum", "html": self._("Forum categories") },
                { "html": self._("Tags") },
            ],
        }
        self.call("forum.vars-tags", vars)
        self.call("socio.response_template", "tags.html", vars)

    def news(self, vars, category, limit=5, template=None):
        req = self.req()
        user_uuid = self.call("socio.user")
        cat = self.call("forum.category-by-tag", category)
        if not cat:
            return ""
        topics, page, pages = self.topics(cat, 1, limit)
        # loading content
        topics_content_list = self.objlist(ForumTopicContentList, topics.uuids())
        topics_content_list.load(silent=True)
        topics_content = dict([(obj.uuid, obj.data) for obj in topics_content_list])
        # preparing output
        topics = topics.data()
        self.topics_htmlencode(topics)
        if len(topics):
            topics[-1]["lst"] = True
        for topic in topics:
            content = topics_content.get(topic["uuid"])
            if content:
                content = content.get("content")
                if content:
                    m = re_cut.search(content)
                    if m:
                        topic["more"] = True
                        content = content[0:m.start()]
                topic["content"] = self.call("socio.format_text", content)
        vars["news"] = topics
        vars["ReadMore"] = self._("Read more")
        vars["Comment"] = self._("Comment")
        if template is None:
            template = self.call("socio.template", "news", "news.html")
        if template:
            return self.call("web.parse_template", 'socio/%s' % template, vars)

class SocioAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-forum.index", self.menu_forum_index)
        self.rhook("ext-admin-socio.messages", self.admin_socio_messages, priv="socio.messages")
        self.rhook("socio-admin.message-silence", self.message_silence)
        self.rhook("ext-admin-socio.config", self.admin_socio_config, priv="socio.config")
        self.rhook("menu-admin-root.index", self.menu_root_index)

    def menu_root_index(self, menu):
        menu.append({"id": "socio.index", "text": self._("Socio"), "order": 1000})

    def message_silence(self):
        return self.conf("socio.message-silence", self._("Your access to the forum is temporarily blocked till {till}"))

    def permissions_list(self, perms):
        perms.append({"id": "socio.messages", "name": self._("Socio interface message editor")})
        perms.append({"id": "socio.config", "name": self._("Socio configuration")})

    def menu_forum_index(self, menu):
        req = self.req()
        if req.has_access("socio.config"):
            menu.append({"id": "socio/config", "text": self._("Configuration"), "leaf": True, "order": 9})
        if req.has_access("socio.messages"):
            menu.append({"id": "socio/messages", "text": self._("Interface messages"), "leaf": True, "order": 10})

    def admin_socio_messages(self):
        req = self.req()
        if req.ok():
            config = self.app().config_updater()
            config.set("socio.message-top", req.param("message_top"))
            config.set("socio.message-silence", req.param("message_silence"))
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            message_top = self.conf("socio.message-top")
            message_silence = self.message_silence()
        fields = [
            {"type": "textarea", "name": "message_top", "label": self._("Top message"), "value": message_top},
            {"type": "textarea", "name": "message_silence", "label": self._("Silence message"), "value": message_silence},
        ]
        self.call("admin.form", fields=fields)

    def admin_socio_config(self):
        req = self.req()
        if req.ok():
            errors = {}
            config = self.app().config_updater()
            config.set("socio.signature-images", True if req.param("signature_images") else False)
            config.set("socio.signature-smiles", True if req.param("signature_smiles") else False)
            config.set("socio.signature-colours", True if req.param("signature_colours") else False)
            width = req.param("width")
            if not valid_nonnegative_int(width):
                errors["width"] = self._("Invalid number format")
            else:
                width = int(width)
                if width < 300:
                    errors["width"] = self._("Minimal value is %d") % 300
                else:
                    config.set("socio.signature-images-width", width)
            height = req.param("height")
            if not valid_nonnegative_int(height):
                errors["height"] = self._("Invalid number format")
            else:
                height = int(height)
                if height < 16:
                    errors["height"] = self._("Minimal value is %d") % 16
                else:
                    config.set("socio.signature-images-height", height)
            maxs = req.param("maxs")
            if not valid_nonnegative_int(maxs):
                errors["maxs"] = self._("Invalid number format")
            else:
                maxs = int(maxs)
                if maxs < 1:
                    errors["maxs"] = self._("Minimal value is %d") % 1
                else:
                    config.set("socio.signature-max-smiles", maxs)
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            signature_images = self.conf("socio.signature-images", True)
            width = self.conf("socio.signature-images-width", 800)
            height = self.conf("socio.signature-images-height", 60)
            signature_smiles = self.conf("socio.signature-smiles", False)
            maxs = self.conf("socio.signature-max-smiles", 3)
            signature_colours = self.conf("socio.signature-colours", True)
        fields = [
            {"type": "checkbox", "name": "signature_images", "label": self._("Allow images in signatures"), "checked": signature_images},
            {"name": "width", "label": self._("Limit for sum width of all images in the signature"), "value": width},
            {"name": "height", "label": self._("Limit for sum height of all images in the signature"), "value": height},
            {"type": "checkbox", "name": "signature_smiles", "label": self._("Allow smiles in signatures"), "checked": signature_smiles},
            {"name": "maxs", "label": self._("Maximal number of smiles in the signature"), "value": maxs},
            {"type": "checkbox", "name": "signature_colours", "label": self._("Allow colours in signatures"), "checked": signature_colours},
        ]
        self.call("admin.form", fields=fields)
