from mg.core import Module, Hooks
from operator import itemgetter
from uuid import uuid4
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from mg.core.tools import *
from mg.core.cluster import StaticUploadError
from concurrence.http import HTTPError
from concurrence import Timeout, TimeoutError
from PIL import Image
from mg.core.auth import User, PermissionsEditor
import re
import cgi
import cStringIO
import urlparse
import time

posts_per_page = 20
topics_per_page = 20

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
        "category-list": [["category"], "updated"],
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
        Module.register(self)
        self.rdep(["mg.socio.Forum"])
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("menu-admin-forum.index", self.menu_forum_index)
        self.rhook("ext-admin-forum.categories", self.admin_categories)
        self.rhook("headmenu-admin-forum.categories", self.headmenu_forum_categories)
        self.rhook("ext-admin-forum.category", self.admin_category)
        self.rhook("headmenu-admin-forum.category", self.headmenu_forum_category)
        self.rhook("ext-admin-forum.access", self.admin_access)
        self.rhook("headmenu-admin-forum.access", self.headmenu_forum_access)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("forum-admin.default_rules", self.default_rules)
        self.rhook("ext-admin-forum.delete", self.admin_delete)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("advice-admin-forum.categories", self.advice_forum_categories)
        self.rhook("advice-admin-forum.category", self.advice_forum_categories)

    def advice_forum_categories(self, args, advice):
        advice.append({"title": self._("Defining categories"), "content": self._("Think over forum categories carefully. Try to create minimal quantity of categories. Keep in mind that users will spend just few seconds to choose a category to write. Descriptions should be short and simple. Titles should be short and self explanatory. Don't create many categories for future reference. It's better to create several more common categories and split them later.")})

    def menu_root_index(self, menu):
        menu.append({"id": "socio.index", "text": self._("Socio")})

    def permissions_list(self, perms):
        perms.append({"id": "forum.categories", "name": self._("Forum categories editor")})
        perms.append({"id": "forum.moderation", "name": self._("Forum moderation")})

    def menu_socio_index(self, menu):
        req = self.req()
        if req.has_access("forum.categories"):
            menu.append({ "id": "forum.index", "text": self._("Forum") })

    def menu_forum_index(self, menu):
        self.call("session.require_permission", "forum.categories")
        menu.append({ "id": "forum/categories", "text": self._("Forum categories"), "leaf": True })

    def admin_categories(self):
        self.call("session.require_permission", "forum.categories")
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
        self.call("session.require_permission", "forum.categories")
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
            order = req.param("order")
            default_subscribe = req.param("default_subscribe")
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
            cat["order"] = float(order)
            cat["default_subscribe"] = True if default_subscribe else False
            conf = self.app().config
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
            },
            {
                "name": "default_subscribe",
                "label": self._("Notify users about new topics in this category by default"),
                "checked": cat.get("default_subscribe"),
                "type": "checkbox",
            }
        ]
        self.call("admin.form", fields=fields)

    def headmenu_forum_category(self, args):
        cat = self.call("forum.category", args)
        if cat is None:
            return [self._("No such category"), "forum/categories"]
        return [self._("Category %s") % cat["title"], "forum/categories"]

    def admin_access(self):
        self.call("session.require_permission", "forum.categories")
        permissions = []
        permissions.append(("-R", self._("Deny reading, writing and moderation")))
        permissions.append(("+R", self._("Allow reading")))
        permissions.append(("-W", self._("Deny writing and moderation")))
        permissions.append(("+W", self._("Allow reading and writing")))
        permissions.append(("+M", self._("Allow moderation")))
        permissions.append(("-M", self._("Deny moderation")))
        PermissionsEditor(self.app(), ForumPermissions, permissions, "forum-admin.default_rules").request()

    def default_rules(self, perms):
        perms.append(("logged", "+W"))
        perms.append(("all", "+R"))
        perms.append(("perm:forum.moderation", "+M"))

    def headmenu_forum_access(self, args):
        return [self._("Access"), "forum/category/" + re.sub(r'/.*', '', args)]

    def admin_delete(self):
        self.call("session.require_permission", "forum.categories")
        cat = self.call("forum.category", self.req().args)
        if cat is None:
            self.call("admin.redirect", "forum/categories")
        categories = [c for c in self.call("forum.categories") if c["id"] != cat["id"]]
        conf = self.app().config
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

class Socio(Module):
    def register(self):
        Module.register(self)
        self.rhook("socio.format_text", self.format_text)
        self.rhook("ext-socio.image", self.ext_image)

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
        form = self.call("web.form", "common/form.html")
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
                    except (KeyboardInterrupt, SystemExit, TaskletExit):
                        raise
                    except BaseException as e:
                        form.error("url", self._("Download error: %s") % cgi.escape(str(e)))
                    finally:
                        try:
                            cnn.close()
                        except (KeyboardInterrupt, SystemExit, TaskletExit):
                            raise
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
        self.rhook("forum.notify-newtopic", self.notify_newtopic)
        self.rhook("forum.notify-reply", self.notify_reply)
        self.rhook("forum.response", self.response)
        self.rhook("forum.response_template", self.response_template)
        self.rhook("forum.sync", self.sync)
        self.rhook("ext-forum.index", self.ext_index)
        self.rhook("ext-forum.cat", self.ext_category)
        self.rhook("ext-forum.newtopic", self.ext_newtopic)
        self.rhook("ext-forum.topic", self.ext_topic)
        self.rhook("ext-forum.reply", self.ext_reply)
        self.rhook("ext-forum.delete", self.ext_delete)
        self.rhook("ext-forum.edit", self.ext_edit)
        self.rhook("ext-forum.settings", self.ext_settings)
        self.rhook("ext-forum.subscribe", self.ext_subscribe)
        self.rhook("ext-forum.unsubscribe", self.ext_unsubscribe)
        self.rhook("ext-forum.pin", self.ext_pin)
        self.rhook("ext-forum.unpin", self.ext_unpin)
        self.rhook("ext-forum.move", self.ext_move)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("auth.registered", self.auth_registered)
        self.rhook("all.schedule", self.schedule)

    def objclasses_list(self, objclasses):
        objclasses["UserForumSettings"] = (UserForumSettings, UserForumSettingsList)
        objclasses["ForumTopic"] = (ForumTopic, ForumTopicList)
        objclasses["ForumTopicContent"] = (ForumTopicContent, ForumTopicContentList)
        objclasses["ForumLastRead"] = (ForumLastRead, ForumLastReadList)
        objclasses["ForumPost"] = (ForumPost, ForumPostList)
        objclasses["SocioImage"] = (SocioImage, None)
        objclasses["ForumPermissions"] = (ForumPermissions, ForumPermissionsList)
        objclasses["ForumCategoryStat"] = (ForumCategoryStat, ForumCategoryStatList)

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
            menu_left = []
            menu_right = []
            first_left = True
            first_right = True
            for ent in vars["menu"]:
                if ent.get("right"):
                    if first_right:
                        first_right = False
                    else:
                        menu_right.append({"delim": True})
                    menu_right.append(ent)
                else:
                    if first_left:
                        first_left = False
                    else:
                        menu_left.append({"delim": True})
                    menu_left.append(ent)
            if len(menu_left):
                vars["menu_left"] = menu_left
            if len(menu_right):
                vars["menu_right"] = menu_right
        vars["forum_content"] = content
        self.call("web.response_layout", "socio/layout_forum.html", vars)

    def response_template(self, template, vars):
        self.call("forum.response", self.call("web.parse_template", template, vars), vars)

    def ext_index(self):
        req = self.req()
        user_uuid = req.user()
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
        semi_user_uuid = req.session().semi_user()
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
        for cat in categories:
            cat = cat.copy()
            if cat["topcat"] != topcat:
                topcat = cat["topcat"]
                entries.append({"header": topcat})
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
            entries.append({"category": cat})
        vars = {
            "title": self._("Forum categories"),
            "categories": entries,
            "topics": self._("Topics"),
            "replies": self._("Replies"),
            "unread": self._("Unread"),
            "last_message": self._("Last message"),
            "by": self._("by"),
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
            cats = []
            self.call("forum-admin.init-categories", cats)
            conf = self.app().config
            conf.set("forum.categories", cats)
            conf.store()
        cats.sort(key=itemgetter("order"))
        return cats

    def load_rules(self, cat_ids):
        list = self.objlist(ForumPermissionsList, cat_ids)
        list.load(silent=True)
        rules = dict([(perm.uuid, perm.get("rules")) for perm in list])
        for cat in cat_ids:
            if not rules.get(cat):
                list = []
                self.call("forum-admin.default_rules", list)
                rules[cat] = list
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
        for role, perm in rules:
            if (perm == "+R" or perm == "+W") and role in roles:
                return True
            if perm == "-R" and role in roles:
                return False
        return False

    def may_write(self, cat, topic=None, rules=None, roles=None):
        req = self.req()
        user = req.user()
        if user is None:
            return False
        rules, roles = self.load_rules_roles(user, cat, rules, roles)
        if rules is None:
            return False
        for role, perm in rules:
            if perm == "+W" and role in roles:
                return True
            if (perm == "-W" or perm == "-R") and role in roles:
                return False
        return False

    def may_edit(self, cat, topic=None, post=None, rules=None, roles=None):
        req = self.req()
        user = req.user()
        if user is None:
            return False
        rules, roles = self.load_rules_roles(user, cat, rules, roles)
        if rules is None:
            return False
        for role, perm in rules:
            if (perm == "-W" or perm == "-R") and role in roles:
                return False
        for role, perm in rules:
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
        user = req.user()
        if user is None:
            return False
        rules, roles = self.load_rules_roles(user, cat, rules, roles)
        if rules is None:
            return False
        for role, perm in rules:
            if (perm == "-W" or perm == "-R") and role in roles:
                return False
        for role, perm in rules:
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

    def topics(self, cat, page=1):
        topics = self.objlist(ForumTopicList, query_index="category-updated", query_equal=cat["id"], query_reversed=True)
        pages = (len(topics) - 1) / topics_per_page + 1
        if pages < 1:
            pages = 1
        if page < 1:
            page = 1
        elif page > pages:
            page = pages
        del topics[0:(page - 1) * topics_per_page]
        del topics[page * topics_per_page:]
        topics.load()
        return topics, page, pages

    def ext_category(self):
        req = self.req()
        user_uuid = req.user()
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
        if self.may_write(user_uuid, cat, rules=rules, roles=roles):
            menu.append({"href": "/forum/newtopic/%s" % cat["id"], "html": self._("New topic"), "right": True})
        vars = {
            "title": cat["title"],
            "category": cat,
            "new_topic": self._("New topic"),
            "topics": topics if len(topics) else None,
            "author": self._("Author"),
            "replies": self._("Replies"),
            "last_reply": self._("Last reply"),
            "by": self._("by"),
            "to_page": self._("Pages"),
            "menu": menu,
        }
        if pages > 1:
            pages_list = []
            last_show = None
            for i in range(1, pages + 1):
                show = (i <= 5) or (i >= pages - 5) or (abs(i - page) < 5)
                if show:
                    if len(pages_list):
                        pages_list.append({"delim": True})
                    pages_list.append({"entry": {"text": i, "a": None if i == page else {"href": "/forum/cat/%s?page=%d" % (cat["id"], i)}}})
                elif last_show:
                    if len(pages_list):
                        pages_list.append({"delim": True})
                    pages_list.append({"entry": {"text": "..."}})
                last_show = show
            vars["pages"] = pages_list
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
            topic["literal_created"] = self.call("l10n.timeencode2", topic.get("created"))
        req = self.req()
        user_uuid = req.session().semi_user()
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
        form = self.call("web.form", "common/form.html")
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
        topic_content = self.obj(ForumTopicContent, topic.uuid, {})
        now = self.now()
        topic.set("category", cat["id"])
        topic.set("created", now)
        topic.set("updated", now)
        catstat = self.catstat(cat["id"])
        catstat.set("updated", time.time())
        catstat.incr("topics")
        last = {
            "topic": topic.uuid,
        }
        if author is not None:
            author_name = author.get("name")
            author_html = cgi.escape(author_name.encode("utf-8"))
            topic.set("author", author.uuid)
            topic.set("author_name", author_name)
            topic.set("author_html", author_html)
            topic.set("author_icons", '<img src="/st/socio/test/blog.gif" alt="" />')
            last["author_html"] = author_html
            last["subject_html"] = cgi.escape(subject)
            last["updated"] = self.call("l10n.timeencode2", now)
        catstat.set("last", last)
        topic.set("subject", subject)
        topic.sync()
        topic_content.set("content", content)
        topic_content.set("content_html", self.call("socio.format_text", content))
        topic.store()
        topic_content.store()
        if author is not None:
            self.subscribe(author.uuid, topic.uuid, cat["id"], now)
        catstat.store()
        self.call("queue.add", "forum.notify-newtopic", {"topic_uuid": topic.uuid}, retry_on_fail=True)
        return topic

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
                author_html = cgi.escape(author_name.encode("utf-8"))
                post.set("author", author.uuid)
                post.set("author_name", author_name)
                post.set("author_html", author_html)
                post.set("author_icons", '<img src="/st/socio/test/blog.gif" alt="" />')
                last["author_html"] = author_html
                last["subject_html"] = cgi.escape(topic.get("subject"))
                last["updated"] = self.call("l10n.timeencode2", now)
            catstat.set("last", last)
            post.set("content", content)
            post.set("content_html", self.call("socio.format_text", content))
            post.store()
            if author is not None:
                self.subscribe(author.uuid, topic.uuid, cat["id"], now)
            posts = len(self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid))
            page = (posts - 1) / posts_per_page + 1
            last["page"] = page
            catstat.store()
            self.call("queue.add", "forum.notify-reply", {"topic_uuid": topic.uuid, "page": page, "post_uuid": post.uuid}, retry_on_fail=True)
            raise Hooks.Return((post, page))

    def ext_topic(self):
        req = self.req()
        user_uuid = req.user()
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
        may_write = self.may_write(cat, topic, rules=rules, roles=roles)
        topic_data = topic.data_copy()
        topic_data["content"] = topic_content.get("content")
        topic_data["content_html"] = topic_content.get("content_html")
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
        user_uuid = req.session().semi_user()
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
            if req.user():
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
        form = self.call("web.form", "common/form.html", "/forum/topic/" + topic.uuid + "#post_form")
        if req.ok():
            if not content:
                form.error("content", self._("Enter post content"))
            elif not self.may_write(cat, rules=rules, roles=roles):
                form.error("content", self._("Access denied"))
            if not form.errors:
                user = self.obj(User, req.user())
                post, page = self.call("forum.reply", cat, topic, user, content)
                self.call("web.redirect", "/forum/topic/%s?page=%d#%s" % (topic.uuid, page, post.uuid))
        # making web response
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
            "menu": menu,
        }
        if req.ok() or (self.may_write(cat, rules=rules, roles=roles) and (page == pages)):
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
                topic.set("last_post_author_html", cgi.escape(last_post.get("author_name")))
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
            page = pages
        del posts[0:(page - 1) * posts_per_page]
        del posts[page * posts_per_page:]
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
        form = self.call("web.form", "common/form.html")
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
            catstat = self.catstat(cat["id"])
            catstat.decr("replies")
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
            catstat = self.catstat(cat["id"])
            catstat.decr("topics")
            catstat.decr("replies", len(posts))
            catstat.store()
            self.call("web.redirect", "/forum/cat/%s" % cat["id"])

    def ext_edit(self):
        cat, topic, post = self.category_or_topic_args()
        if not self.may_edit(cat, topic, post):
            self.call("web.forbidden")
        req = self.req()
        form = self.call("web.form", "common/form.html")
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
            topic_content = self.obj(ForumTopicContent, topic.uuid)
            vars["title"] = self._("Edit topic")
            subject = req.param("subject")
            content = req.param("content")
            if req.ok():
                if not subject:
                    form.error("subject", self._("Enter topic subject"))
                if not content:
                    form.error("content", self._("Enter topic content"))
                if not form.errors:
                    with self.lock(["ForumTopic-" + topic.uuid]):
                        topic.set("subject", subject)
                        topic_content.set("content", content)
                        topic_content.set("content_html", self.call("socio.format_text", content))
                        topic.store()
                        topic_content.store()
                    self.call("web.redirect", "/forum/topic/%s" % topic.uuid)
            else:
                subject = topic.get("subject")
                content = topic_content.get("content")
            form.input(self._("Subject"), "subject", subject)
            form.texteditor(None, "content", content)
        form.submit(None, None, self._("Save"))
        self.call("forum.response", form.html(), vars)

    def ext_settings(self):
        self.call("session.require_login")
        req = self.req()
        user_uuid = req.user()
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
        form = self.call("web.form", "common/form.html")
        form.textarea_rows = 4
        signature = req.param("signature")
        avatar = req.param_raw("avatar")
        redirect = req.param("redirect")
        notify_replies = req.param("notify_replies")
        notify = {}
        for cat in categories:
            notify[cat["id"]] = req.param("notify_%s" % cat["id"])
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
                    try:
                        uri = self.call("cluster.static_upload", "avatars", ext, content_type, im_data)
                        settings.set("avatar", uri)
                    except StaticUploadError as e:
                        form.error("avatar", unicode(e))
                settings.set("signature", signature)
                settings.set("signature_html", self.call("socio.format_text", signature))
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
                if redirect is not None and redirect != "":
                    self.call("web.redirect", redirect)
                self.call("web.redirect", "/cabinet/settings")
        else:
            signature = settings.get("signature")
            notify_replies = settings.get("notify_replies", True)
            for cat in categories:
                notify[cat["id"]] = settings.get("notify_%s" % cat["id"], cat.get("default_subscribe"))
        form.hidden("redirect", redirect)
        form.texteditor(self._("Your forum signature"), "signature", signature)
        form.file(self._("Your avatar"), "avatar")
        form.checkbox(self._("Replies in subscribed topics"), "notify_replies", notify_replies, description=self._("E-mail notifications"))
        for cat in categories:
            form.checkbox(self._("New topics in '{topcat} / {cat}'").format(topcat=cat["topcat"], cat=cat["title"]), "notify_%s" % cat["id"], notify.get(cat["id"]))
        self.call("forum.response", form.html(), vars)

    def ext_subscribe(self):
        req = self.req()
        user_uuid = req.user()
        self.call("session.require_login")
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
        user_uuid = req.user()
        self.call("session.require_login")
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
        self.call("session.require_login")
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
        self.call("session.require_login")
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
        self.call("session.require_login")
        with self.lock(["ForumTopic-" + req.args]):
            try:
                topic = self.obj(ForumTopic, req.args)
            except ObjectNotFoundException:
                self.call("web.not_found")
            cat = self.call("forum.category", topic.get("category"))
            if cat is None:
                self.call("web.not_found")
            # permissions
            user_uuid = req.user()
            categories = self.categories()
            rules = self.load_rules([cat["id"] for cat in categories])
            roles = {}
            self.call("security.users-roles", [user_uuid], roles)
            roles = roles.get(user_uuid, [])
            categories = [c for c in categories if c["id"] != cat["id"] and self.may_write(user_uuid, c, rules=rules[c["id"]], roles=roles)]
            if not self.may_move(cat, topic, rules=rules[cat["id"]], roles=roles):
                self.call("web.forbidden")
            form = self.call("web.form", "common/form.html")
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
        catlist.extend([{"value": cat["id"], "description": cat["title"]} for cat in categories])
        form.select(self._("Category where to move"), "newcat", newcat, catlist)
        form.submit(None, None, self._("Move"))
        vars = {
            "title": self._("Move topic: %s" % topic.get("title"))
        }
        self.call("forum.response", form.html(), vars)

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
                posts = self.objlist(ForumPostList, query_index="topic", query_equal=topic.uuid)
                page = None
                for i in range(0, len(posts)):
                    if posts[i].uuid == last_post.uuid:
                        page = i / posts_per_page + 1
                        break
                stat.set("last", {
                    "topic": topic.uuid,
                    "post": last_post.uuid,
                    "page": page,
                    "author_html": last_post.get("author_html"),
                    "subject_html": cgi.escape(topic.get("subject")),
                    "updated": self.call("l10n.timeencode2", last_post.get("created")),
                })
            else:
                stat.set("last", {
                    "topic": last_topic.uuid,
                    "author_html": last_topic.get("author_html"),
                    "subject_html": cgi.escape(last_topic.get("subject")),
                    "updated": self.call("l10n.timeencode2", last_topic.get("created")),
                })
            stat.store()
        self.call("web.response_json", {"ok": 1})
