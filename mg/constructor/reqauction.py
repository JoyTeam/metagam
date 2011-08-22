from mg.constructor import *

max_votes = 3

class DBRequest(CassandraObject):
    _indexes = {
        "all": [[], "created"],
        "draft": [["draft", "author"], "created"],
        "moderation": [["moderation"], "moderation_since"],
        "published-priority": [["published"], "priority"],
        "published-since": [["published"], "published_since"],
        "closed": [["closed"], "closed_since"],
        "implemented": [["implemented"], "closed_since"],
        "author": [["author"], "created"],
        "canbeparent": [["canbeparent"], "created"],
        "children": [["parent"], "published_since"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Request-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBRequest._indexes

class DBRequestList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Request-"
        kwargs["cls"] = DBRequest
        CassandraObjectList.__init__(self, *args, **kwargs)

class DBRequestVote(CassandraObject):
    _indexes = {
        "user": [["user"]],
        "request": [["request"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "RequestVote-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBRequestVote._indexes

class DBRequestVoteList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "RequestVote-"
        kwargs["cls"] = DBRequestVote
        CassandraObjectList.__init__(self, *args, **kwargs)

class DBRequestDependency(CassandraObject):
    _indexes = {
        "parent": [["parent"]],
        "child": [["child"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "RequestDependency-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBRequestDependency._indexes

class DBRequestDependencyList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "RequestDependency-"
        kwargs["cls"] = DBRequestDependency
        CassandraObjectList.__init__(self, *args, **kwargs)

class ReqAuction(ConstructorModule):
    def register(self):
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-reqauction.index", self.index, priv="logged")
        self.rhook("ext-reqauction.request", self.request, priv="logged")
        self.rhook("ext-reqauction.mine", self.mine, priv="logged")
        self.rhook("ext-reqauction.delete-mine", self.delete_mine, priv="logged")
        self.rhook("ext-reqauction.tomoderation", self.tomoderation, priv="logged")
        self.rhook("ext-reqauction.moderation", self.moderation, priv="reqauction.control")
        self.rhook("ext-reqauction.moderate", self.moderate, priv="reqauction.control")
        self.rhook("ext-reqauction.view", self.view, priv="logged")
        self.rhook("ext-reqauction.edit", self.edit, priv="reqauction.control")
        self.rhook("ext-reqauction.vote", self.vote, priv="logged")
        self.rhook("ext-reqauction.unvote", self.unvote, priv="logged")
        self.rhook("ext-reqauction.implemented", self.implemented, priv="logged")
        self.rhook("ext-reqauction.parent", self.parent, priv="reqauction.control")
        self.rhook("ext-reqauction.depend", self.depend, priv="reqauction.control")
        self.rhook("ext-reqauction.undepend", self.undepend, priv="reqauction.control")

    def objclasses_list(self, objclasses):
        objclasses["Request"] = (DBRequest, DBRequestList)
        objclasses["RequestVote"] = (DBRequestVote, DBRequestVoteList)
        objclasses["RequestDependency"] = (DBRequestDependency, DBRequestDependencyList)

    def permissions_list(self, perms):
        perms.append({"id": "reqauction.control", "name": self._("Requests auction control")})

    def format_priority(self, priority):
        if priority is None:
            priority = 0
        else:
            priority = float(priority)
            if priority < 1:
                priority = 0
            else:
                priority = math.log(priority)
        return '%.3f' % priority

    def index(self):
        req = self.req()
        # my votes
        lst = self.objlist(DBRequestVoteList, query_index="user", query_equal=req.user())
        lst.load()
        myvotes = set()
        for ent in lst:
            myvotes.add(ent.get("request"))
        # list of requests
        lst = self.objlist(DBRequestList, query_index="published-priority", query_equal="1", query_reversed=True)
        lst.load(silent=True)
        rows = []
        for ent in lst:
            votes = ent.get("votes", 0)
            if ent.uuid in myvotes:
                votes = '<img src="/st-mg/icons/ok.png" alt="" /> %s' % votes
            rows.append([
                {"html": '<a href="/reqauction/view/%s">%s</a>' % (ent.uuid, htmlescape(ent.get("title"))), "cls": "reqauction-title"},
                {"html": votes, "cls": "reqauction-votes"},
                {"html": self.format_priority(ent.get("priority")), "cls": "reqauction-priority"},
            ])
        vars = {
            "title": self._("reqauction///Waiting for implementation"),
            "tables": [
                {
                    "title": self._("reqauction///Waiting for implementation"),
                    "cols": [
                        {"title": self._("Title"), "cls": "reqauction-title"},
                        {"title": self._("Votes"), "cls": "reqauction-votes"},
                        {"title": self._("Priority"), "cls": "reqauction-priority"},
                    ],
                    "rows": rows,
                }
            ],
            "menu_left": [
                {"html": self._("reqauction///Waiting for implementation")},
                {"href": "/reqauction/mine", "html": self._("reqauction///My requests")},
                {"href": "/reqauction/request/new", "html": self._("reqauction///New request")},
            ],
            "menu_right": [
                {"href": "/reqauction/implemented", "html": self._("reqauction///Implemented requests")},
            ]
        }
        if req.has_access("reqauction.control"):
            ent = {"href": "/reqauction/moderation", "html": self._("Moderation")}
            lst = self.objlist(DBRequestList, query_index="moderation", query_equal="1")
            if len(lst):
                ent["suffix"] = ' <span class="menu-counter">(%d)</span>' % len(lst)
            vars["menu_right"].append(ent)
        if vars["menu_left"]:
            vars["menu_left"][-1]["lst"] = True
        if vars["menu_right"]:
            vars["menu_right"][-1]["lst"] = True
        self.response_template("constructor/reqauction/list.html", vars)

    def response(self, content, vars):
        req = self.req()
        vars["content"] = content
        lst = self.objlist(DBRequestVoteList, query_index="user", query_equal=req.user())
        lst.load()
        req_uuids = [ent.get("request") for ent in lst]
        rows = []
        if req_uuids:
            redirect = urlencode(req.uri())
            lst = self.objlist(DBRequestList, req_uuids)
            lst.load()
            for ent in lst:
                title = htmlescape(ent.get("title"))
                rows.append([
                    {"html": '<a href="/reqauction/view/%s">%s</a>' % (ent.uuid, title) if ent.get("published") else title, "cls": "reqauction-title"},
                    {"html": '<a href="/reqauction/unvote/%s?redirect=%s">%s</a>' % (ent.uuid, redirect, self._("don't want it anymore")), "cls": "reqauction-title"},
                ])
        vars_myreq = {
            "tables": [
                {
                    "title": self._("I want this features"),
                    "cols": [
                        {"title": self._("Title"), "cls": "reqauction-title"},
                        {"title": self._("Removal"), "cls": "reqauction-remove"},
                    ],
                    "rows": rows,
                }
            ],
        }
        vars["myreq"] = self.call("web.parse_template", "constructor/reqauction/list.html", vars_myreq)
        vars["ReqAuctionDoc"] = self._("Request auction documentation")
        self.call("web.response_template", "constructor/reqauction/global.html", vars)

    def response_template(self, template, vars):
        self.response(self.call("web.parse_template", template, vars), vars)

    def cert_check(self):
        req = self.req()
        wmids = self.call("wmid.check", req.user())
        if not wmids:
            self.error(self._("Certificate required"), self._("To use request auction you must have certified WMID"))
        for wmid, cert in wmids.iteritems():
            if cert >= 110:
                return
        self.error(self._("Certificate required"), self._('<p>To use request auction you must have WMID with the <strong>formal certificate</strong>. Your current certificate level is not enough. <a href="https://passport.wmtransfer.com/">Get the formal certificate</a> and recheck your WMID certificate.</p><p><a href="{url}">Recheck your WMID</a></p>').format(url=self.call("wmlogin.url")))

    def request(self):
        self.cert_check()
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid]):
            if uuid != "new":
                try:
                    request = self.obj(DBRequest, uuid)
                except ObjectNotFoundException:
                    self.call("web.not_found")
                if request.get("draft"):
                    if request.get("author") != req.user():
                        self.call("web.forbidden")
                else:
                    self.call("web.forbidden")
            else:
                request = self.obj(DBRequest)
            form = self.call("web.form")
            if req.ok():
                title = req.param("title").strip()
                content = req.param("content").strip()
                if not title:
                    form.error("title", self._("This field is mandatory"))
                if not content:
                    form.error("content", self._("This field is mandatory"))
                if not form.errors:
                    if req.param("preview"):
                        form.add_message_top('<h1>%s</h1>%s' % (htmlescape(title), self.call("socio.format_text", content)))
                    else:
                        if uuid == "new":
                            request.set("draft", 1)
                            request.set("author", req.user())
                            request.set("created", self.now())
                        request.set("title", title)
                        request.set("author_text", content)
                        request.store()
                        self.call("web.redirect", "/reqauction/mine")
            else:
                title = request.get("title")
                content = request.get("author_text")
            form.input(self._("Title"), "title", title)
            form.texteditor(self._("Content"), "content", content)
            form.submit(None, None, self._("Save"))
            form.submit(None, "preview", self._("Preview"), inline=True)
            vars = {
                "title": self._("reqauction///Request editor"),
                "menu_left": [
                    {"href": "/reqauction/mine", "html": self._("reqauction///My requests")},
                    {"html": self._("reqauction///New request") if uuid == "new" else htmlescape(request.get("title")), "lst": True}
                ]
            }
            self.response(form.html(), vars)

    def mine(self):
        req = self.req()
        lst = self.objlist(DBRequestList, query_index="author", query_equal=req.user(), query_reversed=True)
        lst.load()
        rows = []
        for ent in lst:
            actions = []
            title = htmlescape(ent.get("title"))
            if ent.get("draft"):
                if ent.get("moderation_reject"):
                    status = self._("moderation reject: %s") % htmlescape(ent.get("moderation_reject"))
                else:
                    status = self._("draft")
                title = '<a href="/reqauction/request/%s">%s</a>' % (ent.uuid, title)
                actions.append('<a href="/reqauction/tomoderation/%s">%s</a>' % (ent.uuid, self._("send to moderation")))
                actions.append('<a href="/reqauction/delete-mine/%s">%s</a>' % (ent.uuid, self._("delete")))
            elif ent.get("moderation"):
                status = self._("on moderation since %s") % self.call("l10n.time_local", ent.get("moderation_since"))
            elif ent.get("published"):
                if ent.get("parent"):
                    parent = self.obj(DBRequest, ent.get("parent"))
                    status = self._("reqauction///attached to another request")
                    actions.append('<a href="/reqauction/view/%s">%s</a>' % (parent.uuid, htmlescape(parent.get("title"))))
                else:
                    status = self._("reqauction///waiting for implementation since %s") % self.call("l10n.time_local", ent.get("published_since"))
                    title = '<a href="/reqauction/view/%s">%s</a>' % (ent.uuid, title)
            elif ent.get("implemented"):
                status = self._("reqauction///implemented on {time}").format(time=self.call("l10n.time_local", ent.get("closed_since")))
                title = '<a href="/reqauction/view/%s">%s</a>' % (ent.uuid, title)
            elif ent.get("closed"):
                status = self._("reqauction///cancelled on {time}").format(time=self.call("l10n.time_local", ent.get("closed_since")))
                title = '<a href="/reqauction/view/%s">%s</a>' % (ent.uuid, title)
            else:
                status = self._("status///unknown")
            if ent.get("forum_topic"):
                actions.append('<a href="/forum/topic/%s">%s</a>' % (ent.get("forum_topic"), self._("discussion on the forum")))
            rows.append([
                {"html": title, "cls": "reqauction-title"},
                {"html": status, "cls": "reqauction-status"},
                {"html": '<br />'.join(actions), "cls": "reqauction-actions"},
            ])
        vars = {
            "title": self._("reqauction///My requests"),
            "tables": [
                {
                    "title": self._("reqauction///My requests"),
                    "cols": [
                        {"title": self._("Title"), "cls": "reqauction-title"},
                        {"title": self._("Status"), "cls": "reqauction-status"},
                        {"title": self._("Menu"), "cls": "reqauction-actions"},
                    ],
                    "rows": rows,
                }
            ],
            "menu_left": [
                {"href": "/reqauction", "html": self._("reqauction///Waiting for implementation")},
                {"html": self._("reqauction///My requests")},
                {"href": "/reqauction/request/new", "html": self._("reqauction///New request"), "lst": True},
            ]
        }
        self.response_template("constructor/reqauction/list.html", vars)

    def delete_mine(self):
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.redirect", "/reqauction/mine")
            if not request.get("draft") or request.get("author") != req.user():
                self.call("web.redirect", "/reqauction/mine")
            request.remove()
            self.call("web.redirect", "/reqauction/mine")

    def tomoderation(self):
        self.cert_check()
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.redirect", "/reqauction/mine")
            if not request.get("draft") or request.get("author") != req.user():
                self.call("web.redirect", "/reqauction/mine")
            # checking for my votes
            lst = self.objlist(DBRequestVoteList, query_index="user", query_equal=req.user())
            lst.load()
            for ent in lst:
                if ent.get("request") == request.uuid:
                    self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
            if len(lst) >= max_votes:
                self.error(self._("Voting error"), self._("reqauction///You have spent all your voices to other requests. If you want to vote for this request remove one of your votes via the rightmost panel"))
            request.delkey("draft")
            request.delkey("moderation_reject")
            request.set("moderation", 1)
            request.set("moderation_since", self.now())
            request.store()
            # storing vote
            obj = self.obj(DBRequestVote)
            obj.set("request", request.uuid)
            obj.set("user", req.user())
            obj.set("priority", self.user_priority(req.user()))
            obj.store()
            # sending notification
            email = self.main_app().config.get("constructor.reqauction-email")
            if email:
                content = self._("reqauction///New request: {title}\nPlease perform required moderation actions: http://www.{main_host}/reqauction/moderate/{request}").format(title=request.get("title"), main_host=self.app().inst.config["main_host"], request=request.uuid)
                self.main_app().hooks.call("email.send", email, self._("Request auction moderator"), self._("reqauction///Request moderation: %s") % request.get("title"), content)
            self.call("web.redirect", "/reqauction/mine")

    def moderation(self):
        req = self.req()
        lst = self.objlist(DBRequestList, query_index="moderation", query_equal="1")
        lst.load()
        rows = []
        for ent in lst:
            actions = []
            actions.append('<a href="/reqauction/moderate/%s">%s</a>' % (ent.uuid, self._("moderate")))
            author = self.obj(User, ent.get("author"))
            author = htmlescape(author.get("name"))
            rows.append([
                {"html": htmlescape(ent.get("title")), "cls": "reqauction-title"},
                {"html": self.call("l10n.time_local", ent.get("moderation_since")), "cls": "reqauction-date"},
                {"html": author, "cls": "reqaction-author"},
                {"html": '<br />'.join(actions), "cls": "reqauction-actions"},
            ])
        vars = {
            "title": self._("reqauction///Requests on moderation"),
            "tables": [
                {
                    "title": self._("reqauction///Requests on moderation"),
                    "cols": [
                        {"title": self._("Title"), "cls": "reqauction-title"},
                        {"title": self._("request///Sent"), "cls": "reqauction-date"},
                        {"title": self._("Author"), "cls": "reqauction-author"},
                        {"title": self._("Actions"), "cls": "reqauction-actions"},
                    ],
                    "rows": rows,
                }
            ],
            "menu_left": [
                {"href": "/reqauction", "html": self._("reqauction///Waiting for implementation")},
                {"html": self._("reqauction///Requests on moderation"), "lst": True},
            ]
        }
        self.response_template("constructor/reqauction/list.html", vars)

    def moderate(self):
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.redirect", "/reqauction/moderation")
            if not request.get("moderation"):
                self.call("web.redirect", "/reqauction/moderation")
            # requests can be parents
            parents = []
            parents.append({})
            valid_parents = set()
            lst = self.objlist(DBRequestList, query_index="canbeparent", query_equal="1")
            lst.load()
            for ent in lst:
                parents.append({"value": ent.uuid, "description": ent.get("title")})
                valid_parents.add(ent.uuid)
            # form processing
            form = self.call("web.form")
            if req.ok():
                title = req.param("title").strip()
                reason = req.param("reason").strip()
                parent = req.param("parent")
                text = req.param("text").strip()
                author_text = req.param("author_text").strip()
                time = intz(req.param("time"))
                if not title:
                    form.error("title", self._("This field is mandatory"))
                if not author_text:
                    form.error("author_text", self._("This field is mandatory"))
                if req.param("reject"):
                    if not reason:
                        form.error("reason", self._("This field is mandatory"))
                    if not form.errors:
                        request.delkey("moderation")
                        request.delkey("moderation_since")
                        request.set("title", title)
                        request.set("author_text", author_text)
                        request.set("draft", 1)
                        request.set("moderation_reject", reason)
                        request.store()
                        self.call("web.redirect", "/reqauction/moderation")
                elif req.param("publish") or req.param("preview"):
                    if time <= 0:
                        form.error("time", self._("This field must be greater than zero"))
                    if not form.errors:
                        if req.param("publish"):
                            request.delkey("moderation")
                            request.delkey("moderation_since")
                            request.set("canbeparent", 1)
                            request.set("author_text", author_text)
                            request.set("text", text)
                            request.set("published", 1)
                            request.set("published_since", self.now())
                            request.set("time", time)
                            request.set("title", title)
                            self.update_priority(request)
                            # creating forum topic
                            cat = self.call("forum.category-by-tag", "reqauction")
                            if cat:
                                user = self.obj(User, request.get("author"))
                                topic = self.call("forum.newtopic", cat, user, request.get("title"), self._("reqauction///{text}\n\n{author_text}\n\n[url=//{host}/reqauction/view/{request}]Open request page[/url]").format(text=text, author_text=author_text, user=user.get("name"), host=req.host(), request=request.uuid).strip())
                                if topic:
                                    request.set("forum_topic", topic.uuid)
                            request.store()
                            self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
                elif req.param("link"):
                    if parent not in valid_parents:
                        form.error("parent", self._("reqauction///Select a valid parent request"))
                    if not form.errors:
                        request.delkey("moderation")
                        request.delkey("moderation_since")
                        request.set("parent", parent)
                        request.set("author_text", author_text)
                        request.set("text", text)
                        request.set("published", 1)
                        request.set("published_since", self.now())
                        request.set("title", title)
                        self.update_priority(request)
                        request.store()
                        with self.lock(["Requests.recalc"]):
                            self.link(request.uuid, parent)
                            self.recalculate(parent)
                        self.call("web.redirect", "/reqauction/view/%s" % parent)
            else:
                reason = ""
                parent = ""
                text = ""
                author_text = request.get("author_text")
                time = 0
                title = request.get("title")
            form.input(self._("Title"), "title", title)
            form.texteditor(self._("reqauction///Request description (may be empty)"), "text", text)
            form.texteditor(self._("Author text"), "author_text", author_text)
            form.input(self._("Time in days to implement this feature"), "time", time)
            form.submit(None, "preview", self._("Preview"))
            form.submit(None, "publish", self._("Publish"), inline=True)
            form.input(self._("Reject reason"), "reason", reason)
            form.submit(None, "reject", self._("Reject"), inline=True)
            form.select(self._("reqauction///Parent request"), "parent", parent, parents)
            form.submit(None, "link", self._("Link to this parent"), inline=True)
            vars = {
                "title": htmlescape(request.get("title")),
                "request": {
                    "title": htmlescape(request.get("title")),
                    "text": self.call("socio.format_text", text),
                    "author_text": self.call("socio.format_text", author_text),
                },
                "form": form.html(),
                "menu_left": [
                    {"href": "/reqauction/moderation", "html": self._("reqauction///Requests moderation")},
                    {"html": htmlescape(request.get("title")), "lst": True},
                ]
            }
            self.response_template("constructor/reqauction/moderate.html", vars)

    def view(self):
        req = self.req()
        uuid = req.args
        try:
            request = self.obj(DBRequest, uuid)
        except ObjectNotFoundException:
            self.call("web.not_found")
        if not request.get("published") and not request.get("implemented") and not request.get("closed"):
            self.call("web.redirect", "/reqauction")
        if request.get("parent"):
            self.call("web.redirect", "/reqauction/view/%s" % request.get("parent"))
        # voted already
        voted_already = False
        lst = self.objlist(DBRequestVoteList, query_index="user", query_equal=req.user())
        lst.load()
        for ent in lst:
            if ent.get("request") == request.uuid:
                voted_already = True
                break
        menu = []
        if request.get("published"):
            if voted_already:
                menu.append({"href": "/reqauction/unvote/%s" % request.uuid, "html": self._("reqauction///recall my vote")})
            else:
                menu.append({"href": "/reqauction/vote/%s" % request.uuid, "html": self._("reqauction///vote for this request")})
        if req.has_access("reqauction.control"):
            menu.append({"href": "/reqauction/edit/%s" % request.uuid, "html": self._("edit")})
            menu.append({"href": "/reqauction/parent/%s" % request.uuid, "html": self._("reqauction///link to another request")})
            menu.append({"href": "/reqauction/depend/%s" % request.uuid, "html": self._("reqauction///add dependency")})
        if menu:
            menu[-1]["lst"] = True
        info = {}
        vars = {
            "title": htmlescape(request.get("title")),
            "menu_left": [
                {"html": htmlescape(request.get("title")), "lst": True},
            ],
            "request": {
                "title": htmlescape(request.get("title")),
                "text": self.call("socio.format_text", request.get("text")),
                "author_text": self.call("socio.format_text", request.get("author_text")),
                "forum_topic": request.get("forum_topic"),
                "linked_texts": [],
                "menu": menu,
                "info": info
            },
            "ForumDiscussion": self._("Forum discussion"),
        }
        # dependencies
        dependencies = []
        lst = self.objlist(DBRequestDependencyList, query_index="child", query_equal=request.uuid)
        lst.load()
        for ent in lst:
            parent = self.obj(DBRequest, ent.get("parent"))
            html = self._("Depends on: %s") % ('<a href="/reqauction/view/%s">%s</a>' % (parent.uuid, htmlescape(parent.get("title"))))
            if req.has_access("reqauction.control"):
                html = u'%s &mdash; <a href="/reqauction/undepend/%s/%s">%s</a>' % (html, request.uuid, parent.uuid, self._("remove dependency"))
            dependencies.append(html)
        if dependencies:
            vars["request"]["dependencies"] = dependencies
        # linked texts
        lst = self.objlist(DBRequestList, query_index="children", query_equal=request.uuid)
        lst.load()
        for ent in lst:
            vars["request"]["linked_texts"].append({
                "html": self.call("socio.format_text", ent.get("author_text")),
                "forum_topic": ent.get("forum_topic"),
            })
        # header
        if request.get("published"):
            info["Votes"] = self._("Votes:")
            info["votes"] = request.get("votes")
            info["Priority"] = self._("Priority:")
            info["priority"] = self.format_priority(request.get("priority"))
        elif request.get("closed"):
            info["status"] = self._("reqauction///cancelled")
        elif request.get("implemented"):
            info["status"] = self._("reqauction///implemented")
        if request.get("implemented"):
            vars["menu_left"].insert(0, {"href": "/reqauction/implemented", "html": self._("reqauction///Implemented requests")})
        else:
            vars["menu_left"].insert(0, {"href": "/reqauction", "html": self._("reqauction///Waiting for implementation")})
        self.response_template("constructor/reqauction/request.html", vars)

    def edit(self):
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.not_found")
            if not request.get("published") and not request.get("implemented") and not request.get("closed"):
                self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
            if request.get("parent"):
                self.call("web.redirect", "/reqauction/edit/%s" % request.get("parent"))
            form = self.call("web.form")
            if req.ok():
                time = intz(req.param("time"))
                title = req.param("title").strip()
                text = req.param("text").strip()
                if time <= 0:
                    form.error("time", self._("This field must be greater than zero"))
                if not form.errors:
                    if req.param("close"):
                        if request.get("published"):
                            request.set("title", title)
                            request.set("text", text)
                            request.set("time", time)
                            request.delkey("published")
                            request.delkey("canbeparent")
                            request.set("closed", 1)
                            request.set("closed_since", self.now())
                            request.delkey("priority")
                            request.delkey("votes")
                            request.store()
                            self.objlist(DBRequestVoteList, query_index="request", query_equal=request.uuid).remove()
                            if request.get("forum_topic"):
                                self.call("forum.reply", None, request.get("forum_topic"), self.obj(User, req.user()), self._('reqauction///[url=/reqauction/view/%s]Request cancelled[/url]') % request.uuid)
                            # updating linked requests
                            lst = self.objlist(DBRequestList, query_index="children", query_equal=request.uuid)
                            lst.load()
                            for ent in lst:
                                ent.delkey("published")
                                ent.set("closed", 1)
                                ent.set("closed_since", self.now())
                                ent.store()
                                if ent.get("forum_topic"):
                                    self.call("forum.reply", None, ent.get("forum_topic"), self.obj(User, req.user()), self._('reqauction///[url=/reqauction/view/%s]Request cancelled[/url]') % request.uuid)
                            # must recalculate parents and children
                            recalculate = set()
                            recalculate.add(request.uuid)
                            lst = self.objlist(DBRequestDependencyList, query_index="child", query_equal=request.uuid)
                            lst.load()
                            for ent in lst:
                                recalculate.add(ent.get("parent"))
                            lst = self.objlist(DBRequestDependencyList, query_index="parent", query_equal=request.uuid)
                            lst.load()
                            for ent in lst:
                                recalculate.add(ent.get("child"))
                            with self.lock(["Requests.recalc"]):
                                for uuid in recalculate:
                                    self.recalculate(uuid)
                        self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
                    elif req.param("implemented"):
                        if request.get("published"):
                            request.set("title", title)
                            request.set("text", text)
                            request.set("time", time)
                            request.delkey("published")
                            request.delkey("canbeparent")
                            request.set("implemented", 1)
                            request.set("closed_since", self.now())
                            request.delkey("priority")
                            request.delkey("votes")
                            request.store()
                            lst = self.objlist(DBRequestVoteList, query_index="request", query_equal=request.uuid)
                            lst.load()
                            voters = []
                            for ent in lst:
                                voters.append(ent.get("user"))
                            lst.remove()
                            if request.get("forum_topic"):
                                self.call("forum.reply", None, request.get("forum_topic"), self.obj(User, req.user()), self._('reqauction///[url=/reqauction/view/%s]Request implemented[/url]') % request.uuid)
                            # updating linked requests
                            lst = self.objlist(DBRequestList, query_index="children", query_equal=request.uuid)
                            lst.load()
                            for ent in lst:
                                ent.delkey("published")
                                ent.set("implemented", 1)
                                ent.set("closed_since", self.now())
                                ent.store()
                                if ent.get("forum_topic"):
                                    self.call("forum.reply", None, ent.get("forum_topic"), self.obj(User, req.user()), self._('reqauction///[url=/reqauction/view/%s]Request implemented[/url]') % request.uuid)
                            # must recalculate parents and children
                            recalculate = set()
                            recalculate.add(request.uuid)
                            lst = self.objlist(DBRequestDependencyList, query_index="child", query_equal=request.uuid)
                            lst.load()
                            for ent in lst:
                                recalculate.add(ent.get("parent"))
                            lst = self.objlist(DBRequestDependencyList, query_index="parent", query_equal=request.uuid)
                            lst.load()
                            for ent in lst:
                                recalculate.add(ent.get("child"))
                            with self.lock(["Requests.recalc"]):
                                for uuid in recalculate:
                                    self.recalculate(uuid)
                            # sending e-mails
                            self.call("email.users", voters, self._("Implemented: %s") % request.get("title"), self._("reqauction///Request '{title}' you voted for is implemented.\nDetails: http://{host}/reqauction/view/{request}").format(title=request.get("title"), host=req.host(), request=request.uuid))
                        self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
                    elif req.param("publish"):
                        request.set("title", title)
                        request.set("text", text)
                        request.set("time", time)
                        if request.get("published"):
                            self.update_priority(request)
                        request.store()
                        with self.lock(["Requests.recalc"]):
                            self.recalculate(request.uuid)
                        self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
                    elif req.param("preview"):
                        form.add_message_top(self.call("socio.format_text", text))
            else:
                time = request.get("time")
                title = request.get("title")
                text = request.get("text")
            form.input(self._("Title"), "title", title)
            form.texteditor(self._("reqauction///Request description"), "text", text)
            form.input(self._("Time in days to implement this feature"), "time", time)
            form.submit(None, "publish", self._("Save"))
            form.submit(None, "preview", self._("Preview"), inline=True)
            if request.get("published"):
                form.submit(None, "close", self._("reqauction///Cancel request"), inline=True)
                form.submit(None, "implemented", self._("reqauction///Request implemented"), inline=True)
            vars = {
                "title": self._("reqauction///Request editor"),
                "menu_left": [
                    {"href": "/reqauction/view/%s" % request.uuid, "html": htmlescape(request.get("title"))},
                    {"html": self._("Editor"), "lst": True}
                ]
            }
            if request.get("implemented"):
                vars["menu_left"].insert(0, {"href": "/reqauction/implemented", "html": self._("reqauction///Implemented requests")})
            else:
                vars["menu_left"].insert(0, {"href": "/reqauction", "html": self._("reqauction///Waiting for implementation")})
            self.response(form.html(), vars)

    def user_priority(self, user_uuid):
        return 100

    def error(self, title, msg):
        vars = {}
        vars["title"] = title
        vars["content"] = msg
        self.response_template("constructor/reqauction/error.html", vars)

    def vote(self):
        self.cert_check()
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid, "RequestUser.%s" % req.user()]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.not_found")
            if not request.get("published"):
                self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
            if request.get("parent"):
                self.call("web.redirect", "/reqauction/vote/%s" % request.get("parent"))
            # checking for my votes
            lst = self.objlist(DBRequestVoteList, query_index="user", query_equal=req.user())
            lst.load()
            for ent in lst:
                if ent.get("request") == request.uuid:
                    self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
            if len(lst) >= max_votes:
                self.error(self._("Voting error"), self._("reqauction///You have spent all your voices to other requests. If you want to vote for this request remove one of your votes via the rightmost panel"))
            # storing vote
            obj = self.obj(DBRequestVote)
            obj.set("request", request.uuid)
            obj.set("user", req.user())
            obj.set("priority", self.user_priority(req.user()))
            obj.store()
            with self.lock(["Requests.recalc"]):
                self.recalculate(request.uuid)
            self.call("web.redirect", "/reqauction/view/%s" % request.uuid)

    def unvote(self):
        req = self.req()
        uuid = req.args
        redirect = req.param("redirect")
        with self.lock(["Request.%s" % uuid, "RequestUser.%s" % req.user()]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.not_found")
            # checking for my votes
            lst = self.objlist(DBRequestVoteList, query_index="user", query_equal=req.user())
            lst.load()
            for ent in lst:
                if ent.get("request") == request.uuid:
                    ent.remove()
                    with self.lock(["Requests.recalc"]):
                        self.recalculate(request.uuid)
                    break
            self.call("web.redirect", redirect or ("/reqauction/view/%s" % request.uuid))

    def implemented(self):
        req = self.req()
        lst = self.objlist(DBRequestList, query_index="implemented", query_equal="1", query_reversed=True)
        lst.load()
        rows = []
        for ent in lst:
            rows.append([
                {"html": '<a href="/reqauction/view/%s">%s</a>' % (ent.uuid, htmlescape(ent.get("title"))), "cls": "reqauction-title"},
                {"html": self.call("l10n.time_local", ent.get("closed_since")), "cls": "reqauction-date"},
            ])
        vars = {
            "title": self._("reqauction///Implemented requests"),
            "tables": [
                {
                    "title": self._("reqauction///Implemented requests"),
                    "cols": [
                        {"title": self._("Title"), "cls": "reqauction-title"},
                        {"title": self._("Implemented"), "cls": "reqauction-date"},
                    ],
                    "rows": rows,
                }
            ],
            "menu_left": [
                {"href": "/reqauction", "html": self._("reqauction///Waiting for implementation")},
                {"html": self._("reqauction///Implemented requests")},
            ],
            "menu_right": [
            ]
        }
        if vars["menu_left"]:
            vars["menu_left"][-1]["lst"] = True
        if vars["menu_right"]:
            vars["menu_right"][-1]["lst"] = True
        self.response_template("constructor/reqauction/list.html", vars)

    def recalculate(self, request_uuid):
        children = set()
        self.children(request_uuid, children)
        parents = set()
        self.parents(request_uuid, parents)
        request = self.obj(DBRequest, request_uuid)
        self.update_priority(request)
        request.store()
        for uuid in children:
            request = self.obj(DBRequest, uuid)
            self.update_priority(request)
            request.store()
        for uuid in parents:
            request = self.obj(DBRequest, uuid)
            self.update_priority(request)
            request.store()

    def link(self, request_uuid, parent_uuid):
        # looking for votes for the parent
        votes = set()
        lst = self.objlist(DBRequestVoteList, query_index="request", query_equal=parent_uuid)
        lst.load()
        for ent in lst:
            votes.add(ent.get("user"))
        # moving votes from child to parent
        lst = self.objlist(DBRequestVoteList, query_index="request", query_equal=request_uuid)
        lst.load()
        for ent in lst:
            if ent.get("user") in votes:
                # this user already voted for parent
                ent.remove()
            else:
                # moving vote to the parent
                ent.set("request", parent_uuid)
                ent.store()
        # moving children of this request to new parent
        lst = self.objlist(DBRequestList, query_index="children", query_equal=request_uuid)
        lst.load()
        for ent in lst:
            ent.set("parent", parent_uuid)
            ent.store()
        # moving dependencies of this request to new parent
        lst = self.objlist(DBRequestDependencyList, query_index="parent", query_equal=request_uuid)
        lst.load()
        for ent in lst:
            ent.set("parent", parent_uuid)
            ent.store()
        lst = self.objlist(DBRequestDependencyList, query_index="child", query_equal=request_uuid)
        lst.load()
        for ent in lst:
            ent.set("child", parent_uuid)
            ent.store()

    def parent(self):
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.redirect", "/reqauction/moderation")
            if not request.get("published"):
                self.call("web.redirect", "/reqauction")
            # requests can be parents
            parents = []
            parents.append({})
            valid_parents = set()
            lst = self.objlist(DBRequestList, query_index="canbeparent", query_equal="1")
            lst.load()
            for ent in lst:
                if ent.uuid != request.uuid and ent.get("published") and not ent.get("parent"):
                    parents.append({"value": ent.uuid, "description": ent.get("title")})
                    valid_parents.add(ent.uuid)
            # form processing
            form = self.call("web.form")
            if req.ok():
                parent = req.param("parent")
                if parent not in valid_parents:
                    form.error("parent", self._("reqauction///Select a valid parent request"))
                if not form.errors:
                    request.set("parent", parent)
                    request.delkey("time")
                    request.delkey("priority")
                    request.delkey("canbeparent")
                    self.update_priority(request)
                    request.store()
                    with self.lock(["Requests.recalc"]):
                        self.link(request.uuid, parent)
                        self.recalculate(parent)
                    self.call("web.redirect", "/reqauction/view/%s" % parent)
            else:
                parent = ""
            form.select(self._("reqauction///Parent request"), "parent", parent, parents)
            form.submit(None, None, self._("Link to this parent"), inline=True)
            vars = {
                "title": htmlescape(request.get("title")),
                "form": form.html(),
                "menu_left": [
                    {"href": "/reqauction", "html": self._("reqauction///Waiting for implementation")},
                    {"href": "/reqauction/view/%s" % request.uuid, "html": htmlescape(request.get("title"))},
                    {"html": self._("linking"), "lst": True},
                ]
            }
            self.response(form.html(), vars)

    def parents(self, request_uuid, parents):
        lst = self.objlist(DBRequestDependencyList, query_index="child", query_equal=request_uuid)
        lst.load()
        for ent in lst:
            if not ent.get("parent") in parents:
                parents.add(ent.get("parent"))
                self.parents(ent.get("parent"), parents)

    def children(self, request_uuid, children):
        lst = self.objlist(DBRequestDependencyList, query_index="parent", query_equal=request_uuid)
        lst.load()
        for ent in lst:
            if not ent.get("child") in children:
                children.add(ent.get("child"))
                self.children(ent.get("child"), children)

    def depend(self):
        req = self.req()
        uuid = req.args
        with self.lock(["Request.%s" % uuid, "Requests.recalc"]):
            try:
                request = self.obj(DBRequest, uuid)
            except ObjectNotFoundException:
                self.call("web.redirect", "/reqauction/moderation")
            if not request.get("published"):
                self.call("web.redirect", "/reqauction")
            # list of children to avoid dependency cycles
            children = set()
            self.children(request.uuid, children)
            # requests can be dependency parents
            parents = []
            parents.append({})
            valid_parents = set()
            lst = self.objlist(DBRequestList, query_index="canbeparent", query_equal="1")
            lst.load()
            for ent in lst:
                # children may not be parents to the same request
                if ent.uuid != request.uuid and ent.uuid not in children and ent.get("published") and not ent.get("parent"):
                    parents.append({"value": ent.uuid, "description": ent.get("title")})
                    valid_parents.add(ent.uuid)
            # form processing
            form = self.call("web.form")
            if req.ok():
                parent = req.param("parent")
                if parent not in valid_parents:
                    form.error("parent", self._("reqauction///Select a valid parent request"))
                if not form.errors:
                    already = False
                    lst = self.objlist(DBRequestDependencyList, query_index="parent", query_equal=parent)
                    lst.load()
                    for ent in lst:
                        if ent.get("child") == request.uuid:
                            already = True
                            break
                    # storing dependency
                    if not already:
                        obj = self.obj(DBRequestDependency)
                        obj.set("child", request.uuid)
                        obj.set("parent", parent)
                        obj.store()
                        self.recalculate(parent)
                    self.call("web.redirect", "/reqauction/view/%s" % request.uuid)
            else:
                parent = ""
            form.select(self._("reqauction///Parent request"), "parent", parent, parents)
            form.submit(None, None, self._("Link to this parent"), inline=True)
            vars = {
                "title": htmlescape(request.get("title")),
                "form": form.html(),
                "menu_left": [
                    {"href": "/reqauction", "html": self._("reqauction///Waiting for implementation")},
                    {"href": "/reqauction/view/%s" % request.uuid, "html": htmlescape(request.get("title"))},
                    {"html": self._("linking"), "lst": True},
                ]
            }
            self.response(form.html(), vars)

    def update_priority(self, request):
        time = request.get("time")
        if time:
            lst = self.objlist(DBRequestVoteList, query_index="request", query_equal=request.uuid)
            lst.load()
            request.set("votes", len(lst))
            # own priority
            priority = 0.0
            users = set()
            for ent in lst:
                users.add(ent.get("user"))
                priority += ent.get("priority")
            # votes for children increase our priority
            children = set()
            self.children(request.uuid, children)
            for uuid in children:
                lst = self.objlist(DBRequestVoteList, query_index="request", query_equal=uuid)
                lst.load()
                for ent in lst:
                    if ent.get("user") not in users:
                        users.add(ent.get("user"))
                        priority += ent.get("priority")
            # parents increase our time
            parents = set()
            self.parents(request.uuid, parents)
            for uuid in parents:
                obj = self.obj(DBRequest, uuid)
                if obj.get("published") and obj.get("time"):
                    time += obj.get("time")
            # calculating priority
            priority /= time
            request.set("priority", '%015.5f' % priority)
        else:
            request.delkey("votes")
            request.delkey("priority")

    def undepend(self):
        req = self.req()
        uuids = req.args.split("/")
        if len(uuids) != 2:
            self.call("web.not_found")
        uuid = uuids[0]
        parent = uuids[1]
        with self.lock(["Request.%s" % uuid, "Requests.recalc", "Request.%s" % parent]):
            lst = self.objlist(DBRequestDependencyList, query_index="parent", query_equal=parent)
            lst.load()
            for ent in lst:
                if ent.get("child") == uuid:
                    ent.remove()
                    self.recalculate(parent)
                    self.recalculate(uuid)
                    break
            self.call("web.redirect", "/reqauction/view/%s" % uuid)
