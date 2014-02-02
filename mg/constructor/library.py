#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

from mg.constructor import *
import re

re_double_slash = re.compile(r'//')
re_valid_code = re.compile(r'^[a-z0-9][a-z0-9\-_]*(\/[a-z0-9\-_]*[a-z0-9_])*$')
re_del = re.compile(r'^del\/(.+)$')
re_valid_pgcode = re.compile(r'u_[a-z0-9_]+$')

class DBLibraryPage(CassandraObject):
    clsname = "LibraryPage"
    indexes = {
        "all": [[], "code"],
        "code": [["code"]],
    }

class DBLibraryPageList(CassandraObjectList):
    objcls = DBLibraryPage

class DBLibraryGroup(CassandraObject):
    clsname = "LibraryGroup"
    indexes = {
        "all": [[], "code"],
        "code": [["code"]],
        "everywhere": [["everywhere"]],
    }

class DBLibraryGroupList(CassandraObjectList):
    objcls = DBLibraryGroup

class DBLibraryPageGroup(CassandraObject):
    clsname = "LibraryPageGroup"
    indexes = {
        "grp": [["grp"]],
        "page": [["page"]],
    }

class DBLibraryPageGroupList(CassandraObjectList):
    objcls = DBLibraryPageGroup

class Library(ConstructorModule):
    def register(self):
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("ext-library.index", self.library_index, priv="public")
        self.rhook("ext-library.handler", self.library_handler, priv="public")
        self.rhook("socio.button-blocks", self.button_blocks)
        self.rhook("sociointerface.buttons", self.buttons)
        self.rhook("library-page-index.content", self.page_index)
        self.rhook("hook-lib.catalog", self.hook_catalog)
        self.rhook("library.page-groups", self.page_groups)
        self.rhook("library.icon", self.icon)
        self.rhook("admin-icons.list", self.icons_list)

    def icons_list(self, icons):
        icons.append({
            "code": "library-icon",
            "title": self._("Library icon"),
            "default": "/st-mg/icons/library-icon.png",
        })

    def icon(self, uri):
        img = self.call("icon.get", "library-icon", default_icon="/st-mg/icons/library-icon.png")
        return ' <a href="%s" target="_blank"><img src="%s" alt="?" class="library-icon" /></a>' % (uri, img)

    def button_blocks(self, blocks):
        blocks.append({"id": "library", "title": self._("Library"), "class": "library"})

    def child_modules(self):
        return ["mg.constructor.library.LibraryAdmin"]

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "library",
            "href": "/library",
            "target": "_blank",
            "icon": "library.png",
            "title": self._("Game library"),
            "block": "top-menu",
            "order": 8,
        })

    def library_index(self):
        self.library_page("index")

    def library_handler(self):
        req = self.req()
        self.library_page(req.args)

    def library_page(self, code):
        if not re_valid_code.match(code):
            self.call("web.not_found")
        lst = self.objlist(DBLibraryPageList, query_index="code", query_equal=code)
        lst.load()
        if len(lst):
            pent = lst[0]
        else:
            pent = self.call("library-page-%s.content" % code, render_content=True)
            if not pent:
                self.call("web.not_found")
        vars = {
            "title": htmlescape(pent.get("title")),
            "keywords": htmlescape(pent.get("keywords")),
            "description": htmlescape(pent.get("description")),
            "allow_bracket_hooks": True,
        }
        vars["library_content"] = self.call("web.parse_inline_layout", pent.get("content"), vars)
        # loading blocks
        blocks = {}
        lst = self.objlist(DBLibraryGroupList, query_index="everywhere", query_equal="1")
        lst.load()
        for ent in lst:
            blocks[ent.get("code")] = {
                "code": ent.get("code"),
                "content": ent.get("block_content"),
                "order": ent.get("block_order"),
            }
        lst = self.objlist(DBLibraryPageGroupList, query_index="page", query_equal=code)
        lst.load(silent=True)
        for ent in lst:
            if ent.get("grp") not in blocks:
                grplst = self.objlist(DBLibraryGroupList, query_index="code", query_equal=ent.get("grp"))
                grplst.load()
                for grp in grplst:
                    if grp.get("block"):
                        blocks[grp.get("code")] = {
                            "code": grp.get("code"),
                            "content": grp.get("block_content"),
                            "order": grp.get("block_order"),
                        }
        if len(blocks):
            blocks = blocks.values()
            blocks.sort(cmp=lambda x, y: cmp(x.get("order"), y.get("order")) or cmp(x.get("code"), y.get("code")))
            vars["library_blocks"] = [self.call("web.parse_inline_layout", blk["content"], vars) for blk in blocks]
        # loading parents
        menu_left = [{"html": vars["title"], "lst": True}]
        parent = pent.get("parent")
        shown = set()
        shown.add(pent.get("code"))
        while parent and parent not in shown:
            shown.add(parent)
            lst = self.objlist(DBLibraryPageList, query_index="code", query_equal=parent)
            lst.load()
            if len(lst):
                parent_ent = lst[0]
            else:   
                parent_ent = self.call("library-page-%s.content" % parent, render_content=False)
                if not parent_ent:
                    break
            menu_left.insert(0, {"html": htmlescape(parent_ent.get("title")), "href": "/library" if parent == "index" else "/library/%s" % parent})
            parent = parent_ent.get("parent")
        if menu_left:
            vars["menu_left"] = menu_left
        self.call("socio.response_template", "library.html", vars)

    def buttons(self, buttons):
        buttons.append({
            "id": "forum-library",
            "href": "/library",
            "title": self._("Library"),
            "target": "_self",
            "block": "forum",
            "order": 10,
            "left": True,
        })

    def page_index(self, render_content):
        pageinfo = {
            "title": self._("Library - %s") % self.app().project.get("title_short"),
        }
        if render_content:
            pageinfo["content"] = '[hook:lib.catalog grp="index"]'
        return pageinfo

    def page_groups(self, page_groups):
        page_groups.append({
            "code": "index",
            "title": self._("Publish on the library indexpage"),
        })
        lst = self.objlist(DBLibraryGroupList, query_index="all")
        lst.load()
        for ent in lst:
            page_groups.append({
                "code": ent.get("code"),
                "title": ent.get("title"),
                "uuid": ent.uuid,
                "manual": True,
                "everywhere": ent.get("everywhere"),
            })

    def hook_catalog(self, vars, grp, delim="<br />"):
        lst = self.objlist(DBLibraryPageGroupList, query_index="grp", query_equal=grp)
        lst.load(silent=True)
        pages = []
        for ent in lst:
            pages.append({"page": ent.get("page"), "order": ent.get("order")})
        self.call("library-grp-%s.pages" % grp, pages)
        pages.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["page"], y["page"]))
        page_info = {}
        lst = self.objlist(DBLibraryPageList, query_index="code", query_equal=[ent["page"] for ent in pages])
        lst.load(silent=True)
        for ent in lst:
            page_info[ent.get("code")] = ent
        result = []
        for ent in pages:
            page = page_info.get(ent["page"]) or self.call("library-page-%s.content" % ent["page"], render_content=False)
            if page:
                code = page.get("code")
                result.append('<a href="%s">%s</a>' % ("/library" if code == "index" else "/library/%s" % code, htmlescape(page.get("title"))))
        return delim.join(result)

class LibraryAdmin(ConstructorModule):
    def register(self):
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-library.index", self.menu_library_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-library.pages", self.admin_pages, priv="library.edit")
        self.rhook("headmenu-admin-library.pages", self.headmenu_pages)
        self.rhook("ext-admin-library.page-groups", self.admin_page_groups, priv="library.edit")
        self.rhook("headmenu-admin-library.page-groups", self.headmenu_page_groups)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("advice-admin-library.index", self.advice_library)
        self.rhook("admin-sociointerface.design-files", self.design_files)

    def design_files(self, files):
        files.append({"filename": "library.html", "description": self._("Library page layout"), "doc": "/doc/design/library"})

    def advice_library(self, hook, args, advice):
        advice.append({"title": self._("Library documentation"), "content": self._('You can find detailed information on the library system in the <a href="//www.%s/doc/library" target="_blank">library page</a> in the reference manual.') % self.main_host})

    def objclasses_list(self, objclasses):
        objclasses["LibraryPage"] = (DBLibraryPage, DBLibraryPageList)
        objclasses["LibraryGroup"] = (DBLibraryGroup, DBLibraryGroupList)
        objclasses["LibraryPageGroup"] = (DBLibraryPageGroup, DBLibraryPageGroupList)

    def menu_root_index(self, menu):
        menu.append({"id": "library.index", "text": self._("Library"), "order": 80})

    def menu_library_index(self, menu):
        req = self.req()
        if req.has_access("library.edit"):
            menu.append({"id": "library/page-groups", "text": self._("Library page groups"), "order": 5, "leaf": True})
            menu.append({"id": "library/pages", "text": self._("Library pages"), "order": 10, "leaf": True})

    def permissions_list(self, perms):
        perms.append({"id": "library.edit", "name": self._("Library editing")})

    def headmenu_pages(self, args):
        if args == "new":
            return [self._("New page"), "library/pages"]
        elif args:
            try:
                page = self.obj(DBLibraryPage, args)
            except ObjectNotFoundException:
                pass
            else:
                return [htmlescape(page.get("title")), "library/pages"]
        return self._("Library pages")

    def admin_pages(self):
        req = self.req()
        m = re_del.match(req.args)
        if m:
            uuid = m.group(1)
            try:
                page = self.obj(DBLibraryPage, uuid)
            except ObjectNotFoundException:
                pass
            else:
                page.remove()
                self.objlist(DBLibraryPageGroupList, query_index="page", query_equal=page.get("code")).remove()
            self.call("admin.redirect", "library/pages")
        if req.args:
            if req.args != "new":
                try:
                    page = self.obj(DBLibraryPage, req.args)
                except ObjectNotFoundException:
                    self.call("admin.redirect", "library/pages")
            else:
                page = self.obj(DBLibraryPage)
            page_groups = []
            self.call("library.page-groups", page_groups)
            page_groups = [pg for pg in page_groups if not pg.get("everywhere")]
            if req.ok():
                errors = {}
                code = req.param("code").strip()
                if not code:
                    errors["code"] = self._("This field is mandatory")
                elif code.startswith('/'):
                    errors["code"] = self._("Code can't start with slash")
                elif code.endswith('/'):
                    errors["code"] = self._("Code can't end with slash")
                elif re_double_slash.search(code):
                    errors["code"] = self._("Code can't contain '//'")
                elif not re_valid_code.match(code):
                    errors["code"] = self._("Invalid format")
                else:
                    lst = self.objlist(DBLibraryPageList, query_index="code", query_equal=code)
                    if len(lst) and lst[0].uuid != page.uuid:
                        errors["code"] = self._("There is a page with the same code already")
                    else:
                        page.set("code", code)
                title = req.param("title").strip()
                if not title:
                    errors["title"] = self._("This field is mandatory")
                else:
                    page.set("title", title)
                content = req.param("content").strip()
                page.set("content", content)
                keywords = req.param("keywords").strip()
                if not keywords:
                    errors["keywords"] = self._("This field is mandatory")
                else:
                    page.set("keywords", keywords)
                description = req.param("description").strip()
                if not description:
                    errors["description"] = self._("This field is mandatory")
                else:
                    page.set("description", description)
                page.set("parent", req.param("parent").strip())
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                page.store()
                self.objlist(DBLibraryPageGroupList, query_index="page", query_equal=page.get("code")).remove()
                for grp in page_groups:
                    order = req.param("grp-%s" % grp.get("code"))
                    if order != "":
                        obj = self.obj(DBLibraryPageGroup)
                        obj.set("page", page.get("code"))
                        obj.set("grp", grp.get("code"))
                        obj.set("order", intz(order))
                        obj.store()
                self.call("admin.redirect", "library/pages")
            fields = [
                {"name": "code", "label": self._("Page code (latin letters, slashes, digits and '-'). This page code is practically a component of the page URL. This library page will be available as '/library/&lt;code&gt;'. You may use slashes. For example, 'clans/wars' will be available at '/library/clans/wars'. Special code 'index' means library index page: '/library'"), "value": page.get("code")},
                {"name": "title", "label": self._("Page title"), "value": page.get("title")},
                {"name": "parent", "label": self._("Code of the parent page"), "value": page.get("parent")},
                {"name": "content", "type": "htmleditor", "label": self._("Page content. You may use hooks to include any dynamic content"), "value": page.get("content")},
                {"name": "keywords", "label": self._("Page keywords (visible to search engines). Comma delimited"), "value": page.get("keywords")},
                {"name": "description", "label": self._("Page decription (visible to search engines only)"), "value": page.get("description")},
            ]
            lst = self.objlist(DBLibraryPageGroupList, query_index="page", query_equal=page.get("code"))
            lst.load()
            group_enabled = {}
            for ent in lst:
                group_enabled[ent.get("grp")] = ent.get("order")
            fields.append({"type": "header", "html": self._("Which groups this page belongs to. If you want any page to show in the group specify an integer value here. This value will be the sorting order of the page in the group")})
            col = 0
            for grp in page_groups:
                fields.append({"name": "grp-%s" % grp.get("code"), "label": htmlescape(grp.get("title")), "value": group_enabled.get(grp.get("code")), "inline": (col % 3 != 0)})
                col += 1
            while col % 3 != 0:
                fields.append({"type": "empty", "inline": True})
                col += 1
            self.call("admin.form", fields=fields, modules=["HtmlEditorPlugins"])
        rows = []
        lst = self.objlist(DBLibraryPageList, query_index="all")
        lst.load()
        for ent in lst:
            code = ent.get("code")
            rows.append([
                code,
                '<hook:admin.link href="library/pages/%s" title="%s" />' % (ent.uuid, htmlescape(ent.get("title"))),
                '<hook:admin.link href="library/pages/del/%s" title="%s" confirm="%s" />' % (ent.uuid, self._("delete"), self._("Are you sure want to delete this page?")),
                '<a href="%s" target="_blank">%s</a>' % ("/library" if code == "index" else "/library/%s" % code, self._("view")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "library/pages/new", "text": self._("New library page"), "lst": True},
                    ],
                    "header": [
                        self._("Page code"),
                        self._("Title"),
                        self._("Deletion"),
                        self._("Viewing"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_page_groups(self, args):
        if args == "new":
            return [self._("New page group"), "library/page-groups"]
        elif args:
            try:
                page_group = self.obj(DBLibraryGroup, args)
            except ObjectNotFoundException:
                pass
            else:
                return [htmlescape(page_group.get("title")), "library/page-groups"]
        return self._("Library page groups")

    def admin_page_groups(self):
        req = self.req()
        m = re_del.match(req.args)
        if m:
            uuid = m.group(1)
            try:
                page_group = self.obj(DBLibraryGroup, uuid)
            except ObjectNotFoundException:
                pass
            else:
                page_group.remove()
                self.objlist(DBLibraryPageGroupList, query_index="grp", query_equal=page_group.get("code")).remove()
            self.call("admin.redirect", "library/page-groups")
        if req.args:
            if req.args != "new":
                try:
                    page_group = self.obj(DBLibraryGroup, req.args)
                except ObjectNotFoundException:
                    self.call("admin.redirect", "library/page-groups")
            else:
                page_group = self.obj(DBLibraryGroup)
            if req.ok():
                errors = {}
                code = req.param("code").strip()
                if not code:
                    errors["code"] = self._("This field is mandatory")
                elif not code.startswith("u_"):
                    errors["code"] = self._("Identifier must start with 'u_'")
                elif not re_valid_pgcode.match(code):
                    errors["code"] = self._("Invalid format")
                else:
                    lst = self.objlist(DBLibraryGroupList, query_index="code", query_equal=code)
                    if len(lst) and lst[0].uuid != page_group.uuid:
                        errors["code"] = self._("There is a page group with the same code already")
                    else:
                        page_group.set("code", code)
                title = req.param("title").strip()
                if not title:
                    errors["title"] = self._("This field is mandatory")
                else:
                    page_group.set("title", title)
                if req.param("block"):
                    page_group.set("block", 1)
                    page_group.set("block_order", intz(req.param("block_order")))
                    if req.param("block_everywhere"):
                        page_group.set("everywhere", 1)
                    else:
                        page_group.delkey("everywhere")
                    page_group.set("block_content", req.param("block_content"))
                else:
                    page_group.delkey("block")
                    page_group.delkey("block_order")
                    page_group.delkey("block_everywhere")
                    page_group.delkey("block_content")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                page_group.store()
                self.call("admin.redirect", "library/page-groups")
            fields = [
                {"name": "code", "label": self._("Page group code (must start with u_ and contain latin letters, digits and '_' symbols)"), "value": page_group.get("code")},
                {"name": "title", "label": self._("Page group title"), "value": page_group.get("title")},
                {"name": "block", "label": self._("This group is a block (HTML portion that will be shown on every page in the group)"), "type": "checkbox", "checked": page_group.get("block")},
                {"name": "block_content", "type": "htmleditor", "label": self._("Block content. You may use hooks to include any dynamic content"), "value": page_group.get("block_content"), "condition": "[block]"},
                {"name": "block_order", "label": self._("Block sorting order"), "value": page_group.get("block_order"), "condition": "[block]"},
                {"name": "block_everywhere", "type": "checkbox", "label": self._("This block is shown on the every library page"), "checked": page_group.get("everywhere"), "condition": "[block]"},
            ]
            self.call("admin.form", fields=fields, modules=["HtmlEditorPlugins"])
        page_groups = []
        self.call("library.page-groups", page_groups)
        rows = []
        for ent in page_groups:
            code = ent.get("code")
            manual = ent.get("manual")
            title = htmlescape(ent.get("title"))
            rows.append([
                code,
                '<hook:admin.link href="library/page-groups/%s" title="%s" />' % (ent.get("uuid"), title) if manual else title,
                '<hook:admin.link href="library/page-groups/del/%s" title="%s" confirm="%s" />' % (ent.get("uuid"), self._("delete"), self._("Are you sure want to delete this page group?")) if manual else None,
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "library/page-groups/new", "text": self._("New library page group"), "lst": True},
                    ],
                    "header": [
                        self._("Page group code"),
                        self._("Title"),
                        self._("Deletion"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)
