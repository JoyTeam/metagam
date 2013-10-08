from mg import *
import re

re_news = re.compile('^(\S+)\/(\S+)$')

news_categories_limit = 50
news_categories_title_limit = 100
news_per_page_admin = 30
news_per_page = 30
news_on_start_page = 10

class DBNewsEntry(CassandraObject):
    clsname = "NewsEntry"
    indexes = {
        "news": [["draft"], "publication_date"],
        "drafts": [["draft"], "modification_date"],
    }

class DBNewsEntryList(CassandraObjectList):
    objcls = DBNewsEntry

class DBNewsCategory(CassandraObject):
    clsname = "NewsCategory"
    indexes = {
        "all": [[], "order"],
    }

class DBNewsCategoryList(CassandraObjectList):
    objcls = DBNewsCategory

class NewsAdmin(Module):
    def register(self):
        self.rdep(["mg.socio.news.News"])
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("menu-admin-news.index", self.menu_news_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-news.config", self.news_config, priv="news.config")
        self.rhook("ext-admin-news.categories", self.news_categories, priv="news.categories")
        self.rhook("ext-admin-news.publish", self.news_publish, priv="news.publish")
        self.rhook("headmenu-admin-news.categories", self.headmenu_categories)
        self.rhook("headmenu-admin-news.config", self.headmenu_config)
        self.rhook("headmenu-admin-news.publish", self.headmenu_publish)
        self.rhook("news.categories", self.categories)
        self.rhook("news.create", self.create)
        self.rhook("news.publishing", self.news_publishing)
        self.rhook("news.delete", self.delete)
        self.rhook("news.removing", self.news_removing)
        self.rhook("news.updating", self.news_updating)
        self.rhook("news.category-by-uuid", self.category_by_uuid)
        
    def menu_socio_index(self, menu):
        menu.append({ "id": "news.index", "text": self._("News"), "order": 20 })
    
    def menu_news_index(self, menu):
        req = self.req()
        if req.has_access("news.config"):
            menu.append({ "id": "news/config", "text": self._("Configuration"), "leaf": True, "order": 0 })
        if req.has_access("news.categories"):
            menu.append({ "id": "news/categories", "text": self._("News categories"), "leaf": True, "order": 10 })
        if req.has_access("news.publish"):
            menu.append({ "id": "news/publish", "text": self._("Publishing"), "leaf": True, "order": 20 })

    def permissions_list(self, perms):
        perms.append({ "id": "news.config", "name": self._("News configuration") })
        perms.append({ "id": "news.categories", "name": self._("News categories") })
        perms.append({ "id": "news.publish", "name": self._("News publishing") })
    
    def news_config(self):
        req = self.req()
        
        if req.ok():
            errors = {}
            config = self.app().config_updater()
            config.set("socio.news.post_forum", True if req.param("post_forum") else False)
            config.set("socio.news.forum_category", req.param("v_forum_category") if req.param("post_forum") else None )
            if req.param("post_forum") and not req.param("v_forum_category"):
                errors["forum_category"] = self._("This field is mandatory")
            if not valid_nonnegative_int(req.param("on_start_page")) and req.param("startpage"):
                errors["on_start_page"] = self._("Invalid number")
            else:
                config.set("socio.news.on_start_page", int(req.param("on_start_page")) if req.param("startpage") else 0)
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Configuration stored"), {})
            
        post_forum = self.conf("socio.news.post_forum", False)
        forum_category = self.conf("socio.news.forum_category")
        on_start_page = self.conf("socio.news.on_start_page")
        
        forum_categories = self.call("forum.categories") or []
        available_categories = []
        for cat in forum_categories:
            available_categories.append((cat["id"], cat["title"]))
        if len(forum_categories) and not forum_category:
            forum_category = forum_categories[0]["id"]
        
        if on_start_page is None:
            on_start_page = news_on_start_page
        
        fields = [
            {"type": "checkbox", "name": "post_forum", "label": self._("Create forum topics"), "checked": post_forum},
            {"type": "combo", "name": "forum_category", "value": forum_category, "label": self._("Select forum category"), "condition": "[post_forum]", "values": available_categories },
            {"type": "checkbox", "name": "startpage", "checked": True if on_start_page > 0 else False, "label": self._("Show on the start page")},
            {"type": "numberfield", "name": "on_start_page", "label": self._("The number of news on the start page"), "value": on_start_page, "condition": "[startpage]" },
        ]
        self.call("admin.form", fields=fields)
        
    def news_categories(self):
        req = self.req()
        categories = self.call("news.categories")
        if req.ok():
            errors = {}
            uuid, title, order = (req.param(param).lstrip() for param in ("uuid", "title", "order"))
            if uuid == "":
                uuid = None
            
            if not uuid and len(categories) >= news_categories_limit:
                errors["title"] = self._("You can't create more categories. Limit is %d") % max_news_categories
            if order == "":
                errors["order"] = self._("This field is mandatory")
            elif not valid_int(order):
                errors["order"] = self._("Invalid number")

            try:
                cat = self.obj(DBNewsCategory, uuid)
            except ObjectNotFoundException:
                self.call("web.not_found")
            
            if len(title) > news_categories_title_limit:
                errors["title"] = self._("Maximal length of this field is %d characters") % news_categories_title_limit
            if not title:
                errors["title"] = self._("This field is mandatory")
                
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            
            cat.set("title", title)
            cat.set("order", int(order))
            cat.store()
            self.call("admin.redirect", "news/categories")
        
        if req.args == "new":
            return self.news_category_editor()
        
        m = re_news.match(req.args)
        if m:
            cmd, uuid = m.group(1, 2)
            try:
                obj = self.obj(DBNewsCategory, uuid)
            except ObjectNotFoundException:
                self.call("web.not_found")
            else:
                if cmd == "delete":
                    obj.remove()
                    self.call("admin.redirect", "news/categories")
                elif cmd == "edit":
                    return self.news_category_editor(obj)
        
        vars = {
            "categories": categories,
            "translation": {
                "news_categories": self._("News categories"),
                "new_category": self._("New category"),
                "title": self._("Title"),
                "order": self._("Order"),
                "editing": self._("Editing"),
                "deletion": self._("Deletion"),
                "edit": self._("edit"),
                "delete": self._("delete"),
                "confirm_delete": self._("Are you sure want to delete this category?"),
            },
        }
        
        self.call("admin.response_template", "admin/sociointerface/news/categories.html", vars)
    
    def categories(self):
        cat_lst = self.objlist(DBNewsCategoryList, query_index="all")
        cat_lst.load()
        return list({"id": cat.uuid, "title": cat.get("title"), "order": cat.get("order")} for cat in cat_lst)
    
    def news_category_editor(self, obj = None):
        title, order, uuid = (obj.get("title"), obj.get("order"), obj.uuid) if obj else (None, None, None)
        if order is None:
            categories = self.call("news.categories")
            order = 0
            for cat in categories:
                if cat["order"] > order:
                    order = cat["order"]
            if len(categories):
                order = order + 10
                
        fields = [
            { "name": "title", "label": self._("Category name"), "value": title },
            { "name": "order", "type": "numberfield", "label": self._("Sorting order"), "inline": True, "value": order },
            { "name": "uuid", "type": "hidden", "value": uuid},
        ]
        self.call("admin.form", fields=fields)
    
    def news_publish(self):
        req = self.req()
        drafts_lst = self.objlist(DBNewsEntryList, query_index="drafts", query_equal=1)
        news_lst = self.objlist(DBNewsEntryList, query_index="news", query_equal=0, query_reversed=True)
        if req.ok():
            title, category, content, uuid, announce = list(req.param(key) for key in ("title", "v_category", "content", "uuid", "announce"))
            if uuid == "":
                uuid = None
            if category == "":
                category = None
            errors = {}
            
            try:
                obj = self.obj(DBNewsEntry, uuid)
            except ObjectNotFoundException:
                self.call("web.not_found")
            if len(title) == 0:
                errors["title"] = self._("This field is mandatory")
                
            if category:
                try:
                    self.obj(DBNewsCategory, category)
                except ObjectNotFoundException:
                    errors["category"] = self._("Incorrect category")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            obj.set("title", title)
            obj.set("category", category)
            obj.set("announce", announce)
            obj.set("content", content)
            obj.set("modification_date", self.now())
            if not obj.get("publication_date"):
                obj.set("draft", 1)
            else:
                 self.call("news.updating", obj)
            obj.store()
            
            self.call("admin.redirect", "news/publish")
        
        if req.args == "new":
            return self.news_editor()
        
        m = re_news.match(req.args)
        if m:
            cmd, uuid = m.group(1, 2)
            try:
                obj = self.obj(DBNewsEntry, uuid)
            except ObjectNotFoundException:
                self.call("web.not_found")
            
            if cmd == "edit":
                return self.news_editor(obj)
            elif cmd == "preview":
                return self.preview(obj)
            elif cmd == "delete":
                self.delete(obj.uuid)
                self.call("admin.redirect", "news/publish")
            elif cmd == "publish":
                self.publish(obj)
                self.call("admin.redirect", "news/publish")
  
        page = int(req.param("page")) if req.param("page") else 1
        pages = self.call("news.paginate", news_lst, page, news_per_page_admin)
        if pages > 1:
            pages = range(1, pages + 1)
        else:
            pages = None
            
        news_lst.load()
        drafts_lst.load()
        
        news = list({
                        "id": entry.uuid,
                        "title": entry.get("title"),
                        "modification_date": self.call("l10n.time_local", entry.get("modification_date")),
                        "publication_date": self.call("l10n.time_local", entry.get("publication_date")),
                    } for entry in news_lst)
        drafts = list({
                        "id": entry.uuid,
                        "title": entry.get("title"),
                        "modification_date": self.call("l10n.time_local", entry.get("modification_date")),
                    } for entry in drafts_lst)
        
        vars = {
            "news": news if len(news) else None,
            "drafts": drafts if len(drafts) else None,
            "page": page,
            "pages": pages,
            "translation": {
                "drafts": self._("Drafts"),
                "published_news": self._("Published news"),
                "submit_news": self._("Submit news"),
                "modified": self._("Modification date"),
                "title": self._("Title"),
                "actions": self._("Actions"),
                "edit": self._("edit"),
                "delete": self._("delete"),
                "publish": self._("publish"),
                "preview": self._("preview"),
                "publication_date": self._("Publication date"),
                "confirm_delete": self._("Are you sure want to delete this news?"),
                "confirm_publish": self._("Are you sure want to publish this news?"),
            },
        }
        
        self.call("admin.response_template", "admin/sociointerface/news/news.html", vars)
    
    def news_editor(self, obj = None):
        title, category, uuid, content, announce = (obj.get("title"), obj.get("category"), obj.uuid, obj.get("content"), obj.get("announce")) if obj else (None, None, None, None, None)
        categories = list((cat["id"], cat["title"]) for cat in self.call("news.categories"))
        categories.append((None, self._("Uncategorized")))
        fields = [
            { "name": "title", "label": self._("News title"), "value": title },
            { "name": "category", "type": "combo", "label": self._("Category"), "value": category, "values": categories },
            { "name": "announce", "type": "textarea", "label": self._("News announce(shows on the start page)"), "value": announce },
            { "name": "content", "type": "textarea", "label": self._("News content"), "value": content },
            { "name": "uuid", "type": "hidden", "value": uuid },
        ]
        self.call("admin.form", fields=fields)
    
    def create(self, author, title, announce, content, category=None):
        obj = self.obj(DBNewsEntry)
        obj.set("title", title)
        obj.set("category", category)
        obj.set("announce", announce)
        obj.set("content", content)
        obj.set("modification_date", self.now())
        obj.set("draft", 1)
        if author is not None:
            obj.set("author", author.uuid)
        obj.store()
        self.call("news.publish", obj)
        
    
    def preview(self, obj):
        self.call("admin.response", self.call("socio.format_text", obj.get("content")) + u'<hr /><hook:admin.link href="news/publish" title="%s" />' % self._("Back"), {})
        
    def publish(self, obj):
        if not obj.get("draft"):
            self.call("admin.response", self._('This is not a draft'), {})
        obj.set("draft", 0)
        obj.set("publication_date", self.now())
        self.call("news.publishing", obj)
        obj.store()
        self.call("admin.redirect", "news/publish")
    
    def category_by_uuid(self, uuid):
        try:
            category = self.obj(DBNewsCategory, uuid)
        except ObjectNotFoundException:
            return None
        else:
            return category
        
    def news_publishing(self, obj):
        if self.conf("socio.news.post_forum"):
            forum_category = self.call("forum.category", self.conf("socio.news.forum_category"))
            if not forum_category:
                self.error("Forum category %s doesn't exist", self.conf("socio.news.forum_category"))
            title = obj.get("title")
            category = self.call("news.category-by-uuid", obj.get("category"))
            if category:
                category = category.get("title")
            content = obj.get("content")
            req = self.req()
            
            user = obj.get("author")
            if user is not None:
                user = self.obj(User, user)
            elif req and req.user():
                user = self.obj(User, req.user())
            topic = self.call("forum.newtopic", forum_category, user, title, content, category)
            topic.set("news_entry", obj.uuid)
            topic.store()
            obj.set("forum_topic", topic.uuid)
    
    def delete(self, uuid):
        try:
            obj = self.obj(DBNewsEntry, uuid)
        except ObjectNotFoundException:
            pass
        else:
            self.call("news.removing", obj)
            obj.remove()
    
    def news_removing(self, obj):
        forum_topic = obj.get("forum_topic")
        if forum_topic:
            self.call("forum.topic-delete", forum_topic)
            
    def news_updating(self, obj):
        topic_uuid = obj.get("forum_topic")
        if topic_uuid:
            category = self.call("news.category-by-uuid", obj.get("category"))
            if category:
                category = category.get("title")
            try:
                self.call("forum.topic-update", topic_uuid, content = obj.get("content"), tags=category, subject=obj.get("title"))
            except ObjectNotFoundException:
                pass
    
    def headmenu_categories(self, args):
        req = self.req()
        if args == "new":
            return [self._("New category"), "news/categories"]
            
        m = re_news.match(args)
        if m:
            cmd, uuid = m.group(1, 2)
            if cmd == "edit":
                try:
                    cat = self.obj(DBNewsCategory, uuid)
                except ObjectNotFoundException:
                    pass
                else:
                    return [cat.get("title"), "news/categories"]
                    
        return self._("News categories")
        
    def headmenu_config(self, args):
        return self._("News configuration")
        
    def headmenu_publish(self, args):
        return self._("News publishing")
    
class News(Module):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("indexpage.render", self.indexpage_render)
        self.rhook("ext-news.index", self.news_index, priv="public")
        self.rhook("ext-news.view", self.view, priv="public")
        self.rhook("news.paginate", self.paginate)
        
    def objclasses_list(self, objclasses):
        objclasses["NewsEntry"] = (DBNewsEntry, DBNewsEntryList)
        objclasses["NewsCategory"] = (DBNewsCategory, DBNewsCategoryList)

    def child_modules(self):
        return ["mg.socio.news.NewsAdmin"]
    
    def indexpage_render(self, vars):
        limit = self.conf("socio.news.on_start_page", news_on_start_page)
        news_lst = self.objlist(DBNewsEntryList, query_index="news", query_equal=0, query_limit=limit, query_reversed=True)
        news_lst.load()
        news = []
        for entry in news_lst:
            news.append({
                "created": entry.get("publication_date"),
                "subject": htmlescape(entry.get("title")),
                "announce": self.call("socio.format_text", entry.get("announce")),
                "more": 'news/view/%s' % entry.uuid
            })
        vars["news"] = news
        vars["more_news"] = {"href": "/news/", "html": self._("More news...")}

    def news_index(self):
        req = self.req()
        news_lst = self.objlist(DBNewsEntryList, query_index="news", query_equal=0, query_reversed=True)
        page = intz(req.param("page"))
        if page == 0:
            page = 1
        pages = self.call("news.paginate", news_lst, page, news_per_page)
        if pages > 1:
            pages = range(1, pages + 1)
        else:
            pages = None
            
        news_lst.load()
        news = []
        categories = {}
        for n in news_lst:
            cat_uuid = n.get("category")
            if cat_uuid:
                if not cat_uuid in categories:
                    category = self.call("news.category-by-uuid", cat_uuid)
                    if category:
                        category = htmlescape(category.get("title"));
                        categories[cat_uuid] = category
                else:
                    category = categories[cat_uuid]
            else:
                category = ""
                
            news.append({
                "uuid": n.uuid,
                "subject": n.get("title"),
                "announce": self.call("socio.format_text", n.get("announce")),
                "category": category,
                "publication_date": self.call("l10n.time_local", n.get("publication_date")),
                "forum_topic": n.get("forum_topic")
            })
            
        vars = {
            "news": news,
            "page": page,
            "pages": pages,
            "translation": {
                "read_more": self._("Read more..."),
                "comments": self._("Comments"),
                "pages": self._("Pages"),
                "news_archive": self._("News archive")
            },
            "title": "%s - %s" % (self._("News archive"), self.call("project.title")),
            "topmenu": [
                {   "id": "left",
                    "items": [
                        {
                            "html": self._("Game"),
                            "href": "//%s/" % self.app().canonical_domain,
                            "lst": True
                        }
                    ]
                }
            ]
        }
        
        self.call("socio.response_template", "news_list.html", vars)
    
    def view(self):
        req = self.req()
        uuid = req.args
        try:
            news = self.obj(DBNewsEntry, uuid)
        except ObjectNotFoundException:
            self.call("web.not_found")
        cat_uuid = news.get("category")
        if cat_uuid:
            category = self.call("news.category-by-uuid", cat_uuid)
            if category:
                category = htmlescape(category.get("title"))
        else:
            category = ""
            
        vars = {
            "subject": htmlescape(news.get("title")),
            "announce": self.call("socio.format_text", news.get("announce")),
            "content": self.call("socio.format_text", news.get("content")),
            "category": category,
            "publication_date": self.call("l10n.time_local", news.get("publication_date")),
            "forum_topic": news.get("forum_topic"),
             "translation": {
                "comments": self._("Comments")
            },
            "title": "%s - %s - %s" % (htmlescape(news.get("title")), self._("News"), self.call("project.title")),
            "menu_left": [{ "html": self._("News"), "href": "//%s/news" % self.app().canonical_domain}, { "html": vars["subject"]}]
        }
        
        self.call("socio.response_template", "socio/news_entry.html", vars)
    
    def paginate(self, lst, page, npp=news_per_page):
        pages = (len(lst) - 1) / npp + 1
        if not page:
            page = 1
        if pages < 1:
            pages = 1
        if page < 1:
            page = 1
        elif page > pages:
            page = pages
        del lst[page * npp:]
        del lst[0:(page - 1) * npp]
        return pages