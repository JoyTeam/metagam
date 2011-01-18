from mg import *
from mg.core.cluster import StaticUploadError
import re
import zipfile
import cStringIO
import HTMLParser

max_design_size = 10000000
max_design_files = 100
permitted_extensions = {
    "gif": "image/gif",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "swf": "application/x-shockwave-flash",
    "flv": "video/x-flv",
    "css": "text/css",
    "html": "text/html",
    "js": "text/javascript"
}

re_valid_filename = re.compile(r'^(?:.*[/\\]|)([a-z0-9_\-]+)\.([a-z0-9]+)$')
re_proto = re.compile(r'^[a-z]+://')
re_slash = re.compile(r'^/')
re_template = re.compile(r'\[%')
re_valid_decl = re.compile(r'^DOCTYPE (?:html|HTML).*XHTML')
re_make_filename = re.compile(r'\W+', re.UNICODE)
re_design_root_prefix = re.compile(r'^\[%design_root%\]\/(.*)')
re_rename = re.compile('^rename\/[a-f0-9]{32}$')
re_remove_time = re.compile(' \d\d:\d\d:\d\d')

class Design(CassandraObject):
    "A design package (CSS file, multiple image and script files, HTML template)"

    _indexes = {
        "all": [[], "uploaded"],
        "group": [["group"], "uploaded"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Design-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Design._indexes

class DesignList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Design-"
        kwargs["cls"] = Design
        CassandraObjectList.__init__(self, *args, **kwargs)

class DesignHTMLParser(HTMLParser.HTMLParser, Module):
    "HTML parser validating HTML file received from the user and modifying it adding [%design_root%] prefixes"
    def __init__(self, app):
        HTMLParser.HTMLParser.__init__(self)
        Module.__init__(self, app, "mg.constructor.design.DesignHTMLParser")
        self.output = ""
        self.tagstack = []
        self.decl_ok = False
        self.content_type_ok = False

    def handle_starttag(self, tag, attrs):
        self.process_tag(tag, attrs)
        html = "<%s" % tag
        for key, val in attrs:
            html += ' %s="%s"' % (key, htmlescape(val))
        html += ">";
        self.output += html
        self.tagstack.append(tag)

    def handle_endtag(self, tag):
        expected = self.tagstack.pop() if len(self.tagstack) else None
        if expected != tag:
            raise HTMLParser.HTMLParseError(self._("Closing tag '{0}' doesn't match opening tag '{1}'").format(tag, expected), (self.lineno, self.offset))
        self.output += "</%s>" % tag

    def handle_startendtag(self, tag, attrs):
        self.process_tag(tag, attrs)
        html = "<%s" % tag
        for key, val in attrs:
            html += ' %s="%s"' % (key, htmlescape(val))
        html += " />";
        self.output += html

    def handle_data(self, data):
        self.output += data

    def handle_charref(self, name):
        self.output += "&#%s;" % name

    def handle_entityref(self, name):
        self.output += "&%s;" % name

    def handle_comment(self, data):
        self.output += "<!--%s-->" % data

    def handle_decl(self, decl):
        self.output += "<!%s>" % decl
        if not re_valid_decl.match(decl):
            raise HTMLParser.HTMLParseError(self._("Valid XHTML doctype required"), (self.lineno, self.offset))
        self.decl_ok = True

    def close(self):
        HTMLParser.HTMLParser.close(self)
        if len(self.tagstack):
            raise HTMLParser.HTMLParseError(self._("Not closed tags at the end of file: %s") % (", ".join(self.tagstack)))
        if not self.decl_ok:
            raise HTMLParser.HTMLParseError(self._("DOCTYPE not specified"))
        if not self.content_type_ok:
            raise HTMLParser.HTMLParseError(self._('Content-type not specified. Add <meta http-equiv="Content-type" content="text/html; charset=utf-8" /> into the head tag'))

    def process_tag(self, tag, attrs):
        if tag == "img" or tag == "link" or tag == "input" or tag == "script":
            attrs_dict = dict(attrs)
            att = "href" if tag == "link" else "src"
            href = attrs_dict.get(att)
            if href and not re_proto.match(href) and not re_slash.match(href) and not re_template.search(href):
                for i in range(0, len(attrs)):
                    if attrs[i][0] == att:
                        attrs[i] = (att, "[%design_root%]/" + attrs[i][1])
        elif tag == "meta":
            attrs_dict = dict(attrs)
            key = attrs_dict.get("http-equiv")
            val = attrs_dict.get("content")
            if key is not None and val is not None:
                if key.lower() == "content-type":
                    if val.lower() != "text/html; charset=utf-8":
                        raise HTMLParser.HTMLParseError(self._('Invalid character set. Specify: content="text/html; charset=utf-8"'), (self.lineno, self.offset))
                    self.content_type_ok = True

class DesignHTMLUnparser(HTMLParser.HTMLParser, Module):
    "HTML parser modifying HTML files before sending it to the user by removing [%design_root%] prefixes"
    def __init__(self, app):
        HTMLParser.HTMLParser.__init__(self)
        Module.__init__(self, app, "mg.constructor.design.DesignHTMLUnparser")
        self.output = ""

    def handle_starttag(self, tag, attrs):
        self.process_tag(tag, attrs)
        html = "<%s" % tag
        for key, val in attrs:
            html += ' %s="%s"' % (key, htmlescape(val))
        html += ">";
        self.output += html

    def handle_endtag(self, tag):
        self.output += "</%s>" % tag

    def handle_startendtag(self, tag, attrs):
        self.process_tag(tag, attrs)
        html = "<%s" % tag
        for key, val in attrs:
            html += ' %s="%s"' % (key, htmlescape(val))
        html += " />";
        self.output += html

    def handle_data(self, data):
        self.output += data

    def handle_charref(self, name):
        self.output += "&#%s;" % name

    def handle_entityref(self, name):
        self.output += "&%s;" % name

    def handle_comment(self, data):
        self.output += "<!--%s-->" % data

    def handle_decl(self, decl):
        self.output += "<!%s>" % decl

    def close(self):
        HTMLParser.HTMLParser.close(self)

    def process_tag(self, tag, attrs):
        if tag == "img" or tag == "link" or tag == "input" or tag == "script":
            attrs_dict = dict(attrs)
            att = "href" if tag == "link" else "src"
            href = attrs_dict.get(att)
            if href:
                m = re_design_root_prefix.match(href)
                if m:
                    href = m.group(1)
                    for i in range(0, len(attrs)):
                        if attrs[i][0] == att:
                            attrs[i] = (att, href)

class DesignZip(Module):
    "Uploaded ZIP file with a design package"
    def __init__(self, app, zipdata):
        Module.__init__(self, app, "mg.constructor.design.DesignZip")
        self.zip = zipfile.ZipFile(cStringIO.StringIO(zipdata), "r")

    def upload(self, group):
        """
        Uploads the package to the server
        Return value:
            on error: ["error1", "error2", ...]
            on success: Design_object
        """
        errors = []
        size = 0
        count = 0
        list_errors = []
        filenames = set()
        html = []
        css = []
        upload_list = []
        files = {}
        for ent in self.zip.infolist():
            zip_filename = ent.filename.decode("utf-8")
            count += 1
            size += ent.file_size
            m = re_valid_filename.match(zip_filename)
            if not m:
                list_errors.append(self._("Filename '%s' is invalid. Only small latin letters (a-z), digits (0-9), underscore (_) and minus(-) are permitted. Filename must have an extention (a-z, 0-9 symbols)") % htmlescape(zip_filename))
                continue
            basename, ext = m.group(1, 2)
            filename = "%s.%s" % (basename, ext)
            content_type = permitted_extensions.get(ext)
            if not content_type:
                list_errors.append(self._("Filename '{0}' has unsupported extension: {1}. Permitted extensions are: {2}").format(htmlescape(filename), ext, ", ".join(permitted_extensions.keys())))
                continue
            if filename in filenames:
                list_errors.append(self._("Several files with the same name '%s' encountered") % htmlescape(filename))
                continue
            if ext == "html":
                html.append(filename)
            if ext == "css":
                css.append(filename)
            upload_list.append({"zipname": zip_filename, "filename": filename, "content-type": content_type})
            files[filename] = {"content-type": content_type}
        errors.extend(list_errors)
        if not len(errors):
            for file in upload_list:
                if file["content-type"] == "text/html":
                    data = self.zip.read(file["zipname"])
                    try:
                        parser = DesignHTMLParser(self.app())
                        parser.feed(data)
                        parser.close()
                        vars = {}
                        self.call("admin-%s.preview-data" % group, vars)
                        try:
                            self.call("web.parse_template", cStringIO.StringIO(parser.output), {})
                        except TemplateException as e:
                            errors.append(self._("Error parsing template {0}: {1}").format(file["filename"], str(e)))
                        else:
                            file["data"] = parser.output
                    except HTMLParser.HTMLParseError as e:
                        msg = e.msg
                        if e.lineno is not None:
                            msg += self._(", at line %d") % e.lineno
                        if e.offset is not None:
                            msg += self._(", column %d") % (e.offset + 1)
                        errors.append(self._("Error parsing {0}: {1}").format(file["filename"], msg))
        design = self.obj(Design)
        design.set("group", group)
        design.set("uploaded", self.now())
        design.set("files", files)
        if len(html):
            design.set("html", html)
        if len(css):
            design.set("css", css)
        self.call("admin-%s.validate" % group, design, errors)
        if len(errors):
            return errors
        try:
            uri = self.call("cluster.static_upload_zip", "design-%s" % group, self.zip, upload_list)
        except StaticUploadError as e:
            errors.append(unicode(e))
        if len(errors):
            return errors
        design.set("uri", uri)
        return design
        
class DesignMod(Module):
    def register(self):
        Module.register(self)
        self.rhook("design.response", self.response)

    def response(self, design, template, content, vars):
        vars["global_html"] = self.httpfile("%s/%s" % (design.get("uri"), template))
        vars["design_root"] = design.get("uri")
        self.call("web.response_global", content, vars)

    def child_modules(self):
        return [
            "mg.constructor.design.DesignAdmin",
            "mg.constructor.design.IndexPage", "mg.constructor.design.IndexPageAdmin",
            "mg.constructor.design.GameInterface", "mg.constructor.design.GameInterfaceAdmin",
            "mg.constructor.design.SocioInterface", "mg.constructor.design.SocioInterfaceAdmin"
        ]

class DesignAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("design-admin.editor", self.editor)
        self.rhook("design-admin.delete", self.delete)

    def menu_root_index(self, menu):
        req = self.req()
        if req.has_access("design"):
            menu.append({"id": "design.index", "text": self._("Design")})

    def editor(self, group):
        self.call("session.require_permission", "design")
        self.call("admin.advice", {"title": self._("Preview feature"), "content": self._('Use "preview" feature to check your design before installing it to the project. Then press "Reload" several times to check design on arbitrary data.')}, {"title": self._("Multiple browsers"), "content": self._('Check your design in the most popular browsers.') + u' <a href="http://www.google.com/search?q={0}" target="_blank">{1}</a>.'.format(urlencode(self._("google///browser statistics")), self._("Find the most popular browsers"))})
        with self.lock(["DesignAdmin-%s" % group]):
            req = self.req()
            if req.args == "":
                lst = self.objlist(DesignList, query_index="group", query_equal=group)
                lst.load(silent=True)
                designs = []
                for ent in lst:
                    title = ent.get("title")
                    if title is not None:
                        title = title.strip()
                    if title is None or title == "":
                        title = self._("Untitled")
                    filename = title
                    if len(filename) > 20:
                        filename = filename[0:20]
                    filename += "-%s" % ent.get("uploaded")
                    filename = re_make_filename.sub('-', filename.lower()) + ".zip"
                    previews = []
                    self.call("admin-%s.previews" % group, previews)
                    if not len(previews):
                        previews.append({"filename": "index.html", "title": self._("preview")})
                    designs.append({
                        "uuid": ent.uuid,
                        "uploaded": re_remove_time.sub("", ent.get("uploaded")),
                        "title": htmlescape(title),
                        "filename": htmlescape(filename),
                        "previews": previews
                    })
                vars = {
                    "group": group,
                    "UploadNewDesign": self._("Upload new design"),
                    "Uploaded": self._("Uploaded"),
                    "Title": self._("Title"),
                    "Preview": self._("Preview"),
                    "Deletion": self._("Deletion"),
                    "Installation": self._("Installation"),
                    "preview": self._("preview"),
                    "delete": self._("delete"),
                    "install": self._("install"),
                    "ConfirmDelete": self._("Do you really want to delete this design?"),
                    "ConfirmInstall": self._("Do you really want to install this design?"),
                    "designs": designs,
                    "download": self._("zip"),
                    "rename": self._("rename///ren")
                }
                self.call("admin.response_template", "admin/design/list.html", vars)
            if req.args == "new":
                if req.ok():
                    errors = {}
                    zipdata = req.param_raw("zip")
                    if zipdata is None or zipdata == "":
                        errors["zip"] = self._("Provide a ZIP archive")
                    if not len(errors):
                        try:
                            zip = DesignZip(self.app(), zipdata)
                            design = zip.upload(group)
                            if type(design) == list:
                                errors["zip"] = '; '.join(design)
                        except zipfile.BadZipfile:
                            errors["zip"] = self._("This is not a ZIP file")
                        except zipfile.LargeZipFile:
                            errors["zip"] = self._("ZIP64 is not supported")
                    if len(errors):
                        self.call("web.response_json_html", {"success": False, "errors": errors})
                    design.set("title", req.param("title"))
                    design.store()
                    self.call("web.response_json_html", {"success": True, "redirect": "%s/design" % group})
                fields = [
                    {"type": "fileuploadfield", "name": "zip", "label": self._("Zipped design package")},
                    {"name": "title", "label": self._("Design title")}
                ]
                buttons = [
                    {"text": self._("Upload")}
                ]
                self.call("admin.form", fields=fields, buttons=buttons, modules=["js/FileUploadField.js"])
            m = re.match(r'^([a-z]+)/([a-f0-9]{32})$', req.args)
            if m:
                cmd, uuid = m.group(1, 2)
                if cmd == "delete":
                    try:
                        design = self.obj(Design, uuid)
                    except ObjectNotFoundException:
                        pass
                    else:
                        self.call("design-admin.delete", design)
                        design.remove()
                    self.call("admin.redirect", "%s/design" % group)
                elif cmd == "rename":
                    try:
                        design = self.obj(Design, uuid)
                    except ObjectNotFoundException:
                        pass
                    else:
                        if req.ok():
                            title = req.param("title")
                            design.set("title", title)
                            design.store()
                            self.call("admin.redirect", "%s/design" % group)
                        else:
                            title = design.get("title")
                        fields = [
                            {"name": "title", "label": self._("Design title"), "value": title}
                        ]
                        buttons = [
                            {"text": self._("Rename")}
                        ]
                        self.call("admin.form", fields=fields, buttons=buttons)
                elif cmd == "install":
                    pass
            m = re.match(r'^preview/([a-f0-9]{32})/([a-z]+\.html)$', req.args)
            if m:
                uuid, template = m.group(1, 2)
                try:
                    design = self.obj(Design, uuid)
                except ObjectNotFoundException:
                    pass
                else:
                    self.call("admin-%s.preview" % group, design, template.encode("utf-8"))
                    if design.get("files").get(template, None):
                        vars = {}
                        self.call("admin-%s.preview-data" % group, vars)
                        self.call("design.response", design, template, "", vars)
            m = re.match(r'^download/([a-f0-9]{32})/.+\.zip$', req.args)
            if m:
                uuid = m.group(1)
                try:
                    design = self.obj(Design, uuid)
                except ObjectNotFoundException:
                    pass
                else:
                    output = cStringIO.StringIO()
                    zip = zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED)
                    for filename, ent in design.get("files").items():
                        try:
                            uri = design.get("uri") + "/" + filename
                            data = self.download(uri)
                            if ent.get("content-type") == "text/html":
                                unparser = DesignHTMLUnparser(self.app())
                                unparser.feed(data)
                                unparser.close()
                                data = unparser.output
                            zip.writestr(filename, data)
                        except DownloadError:
                            pass
                    zip.close()
                    self.call("web.response", output.getvalue(), "application/zip")

            self.call("web.not_found")

    def delete(self, design):
        uri = design.get("uri")
        for filename, ent in design.get("files").items():
            self.webdav_delete(uri + "/" + filename)

class IndexPage(Module):
    def register(self):
        Module.register(self)

class IndexPageAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-indexpage.design", self.ext_design)
        self.rhook("headmenu-admin-indexpage.design", self.headmenu_design)
        self.rhook("admin-indexpage.validate", self.validate)
        self.rhook("admin-indexpage.preview-data", self.preview_data)

    def headmenu_design(self, args):
        if args == "new":
            return [self._("New design"), "indexpage/design"]
        elif re_rename.match(args):
            return [self._("Renaming"), "indexpage/design"]
        return self._("Index page design")

    def menu_design_index(self, menu):
        menu.append({"id": "indexpage/design", "text": self._("Index page"), "leaf": True, "admin_index": not self.conf("index.design"), "order": 1})

    def ext_design(self):
        self.call("design-admin.editor", "indexpage")

    def validate(self, design, errors):
        html = design.get("html")
        if not html:
            errors.append(self._("Index page design package must contain an HTML file"))
        elif len(html) > 1:
            errors.append(self._("Index page design package must not contain more than one HTML file"))
        files = design.get("files")
        if not files.get("index.html", None):
            errors.append(self._("index.html must exist in the index page design package"))
        if not design.get("css"):
            errors.append(self._("Index page design package must contain a CSS file"))

    def preview_data(self, vars):
        demo_authors = [self._("Mike"), self._("Ivan Ivanov"), self._("John Smith"), self._("Lizard the killer"), self._("Cult of the dead cow")]
        vars["game"] = {
            "title_full": random.choice([self._("Some title"), self._("Very cool game with very long title")]),
            "title_short": random.choice([self._("Some title"), self._("Very cool game")]),
            "description": random.choice([self._("<p>This game is a very good sample of games with very long descriptions. In this game you become a strong warrior, a mighty wizard, a rich merchant or anyone else. It's your choice. It's your way.</p><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Suspendisse vel purus dolor. Integer aliquam lectus vel urna scelerisque eget viverra eros semper. Morbi aliquet auctor iaculis. Sed lectus mauris, elementum ut porta elementum, tincidunt vitae justo. Sed ac mauris eget lorem laoreet blandit a varius orci. Donec at dolor et quam feugiat dignissim a quis velit. Vestibulum elementum, tortor at eleifend ultricies, lorem felis scelerisque sapien, nec pretium dui ante quis tellus. Praesent at tellus erat, in malesuada nunc. Donec lectus nisi, placerat eget interdum ut, elementum in tellus. Vivamus quis elementum magna. Donec viverra adipiscing ante viverra porttitor. Nam aliquam elit nec turpis volutpat eu iaculis lectus pharetra. Fusce purus lacus, malesuada eu egestas sed, auctor vel sem. Ut tempus malesuada tincidunt. Duis in sem justo. Integer sodales rhoncus nibh, sed posuere lorem commodo ac. Donec tempor consequat venenatis. Vivamus velit tellus, dignissim venenatis viverra eu, porta eget augue. Quisque nec justo a nibh vehicula porttitor. Donec vitae elit tellus.</p>"), self._("This game has a very short description. It was written in hurry by a young game designer.")])
        }
        if random.random() < 0.8:
            vars["news"] = []
            for i in range(0, random.randrange(1, 10)):
                vars["news"].append({
                    "created": "%02d.%02d.%04d" % (random.randrange(1, 29), random.randrange(1, 13), random.randrange(2000, 2011)),
                    "subject": random.choice([self._("Breaking news"), self._("New updates related to the abandoned dungeon"), self._("Eternal shadow returns"), self._("Epic war event")]),
                    "announce": random.choice([self._("South Korea will hold its largest-ever winter live-fire drills Thursday in an area adjacent to North Korea, amid heightened tensions, the South Korean Army says."), self._("Europe travel chaos starts to clear"), self._('Even with legal protection, women victims of rape still face a social stigma that is hard to overcome. He said: "Women are still afraid to complain if they are victims of rape because there is an attitude from the society."</p><p>Coulibaly added: "There is no law to define rape but there will be one. And work is being done with police officers and judges ... to let them understand the problem is not the woman, but the perpetrator of the rape."')]),
                    "more": "#"
                })
            vars["news"][-1]["lst"] = True
        vars["htmlmeta"] = {
            "description": self._("This is a sample meta description"),
            "keywords": self._("online games, keyword 1, keyword 2"),
        }
        vars["year"] = "2099"
        vars["copyright"] = random.choice([self._("Joy Team, Author"), self._("Joy Team, Very Long Author Name Even So Long")])
        vars["links"] = random.sample([
            {
                "href": "#",
                "title": self._("Enter invisible"),
            },
            {
                "href": "#",
                "title": self._("Library"),
            },
            {
                "href": "#",
                "title": self._("World history"),
            },
            {
                "href": "#",
                "title": self._("Registration"),
            },
            {
                "href": "/forum",
                "title": self._("Game forum"),
                "target": "_blank",
            },
            {
                "href": "/screenshots",
                "title": self._("Screenshots"),
                "target": "_blank",
            },
            {
                "href": "#",
                "title": self._("Secure entrance"),
            },
        ], random.randrange(1, 8))
        vars["links"][-1]["lst"] = True
        if random.random() < 0.8:
            vars["ratings"] = []
            for i in range(0, random.randrange(1, 6)):
                lst = []
                vars["ratings"].append({
                    "href": "#",
                    "title": random.choice([self._("The biggest glory"), self._("The richest"), self._("Top clan"), self._("The best dragon hunter")]),
                    "list": lst,
                })
                for j in range(0, random.randrange(1, 20)):
                    lst.append({
                        "name": random.choice(demo_authors),
                        "value": random.randrange(1, random.choice([10, 100, 1000, 10000, 100000, 1000000, 10000000])),
                        "class": "rating-even" if j % 2 else "rating-odd",
                    })
                    lst[-1]["lst"] = True
            vars["ratings"][-1]["lst"] = True

class GameInterface(Module):
    def register(self):
        Module.register(self)

class GameInterfaceAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-gameinterface.design", self.ext_design)
        self.rhook("headmenu-admin-gameinterface.design", self.headmenu_design)
        self.rhook("admin-gameinterface.validate", self.validate)
        self.rhook("admin-gameinterface.preview-data", self.preview_data)

    def headmenu_design(self, args):
        if args == "new":
            return [self._("New design"), "gameinterface/design"]
        elif re_rename.match(args):
            return [self._("Renaming"), "gameinterface/design"]
        return self._("Game interface design")

    def menu_design_index(self, menu):
        menu.append({"id": "gameinterface/design", "text": self._("Game interface"), "leaf": True, "admin_index": not self.conf("game.design"), "order": 2})

    def ext_design(self):
        self.call("design-admin.editor", "gameinterface")

    def validate(self, design, errors):
        if not design.get("css"):
            errors.append(self._("Game interface design package must contain a CSS file"))
        if design.get("html"):
            errors.append(self._("Game interface design package must not contain HTML files"))

    def preview_data(self, vars):
        pass

class SocioInterface(Module):
    def register(self):
        Module.register(self)
        self.rhook("forum.vars-index", self.forum_vars_index)
        self.rhook("forum.vars-category", self.forum_vars_category)
        self.rhook("forum.vars-topic", self.forum_vars_topic)
        self.rhook("forum.vars-tags", self.forum_vars_tags)

    def forum_vars_index(self, vars):
        vars["title"] = self._("Forum categories")
        vars["topics"] = self._("Topics")
        vars["replies"] = self._("Replies")
        vars["unread"] = self._("Unread")
        vars["last_message"] = self._("Last message")
        vars["by"] = self._("by")
        vars["ForumCategories"] = self._("Forum categories")

    def forum_vars_category(self, vars):
        vars["new_topic"] = self._("New topic")
        vars["author"] = self._("Author")
        vars["replies"] = self._("Replies")
        vars["last_reply"] = self._("Last reply")
        vars["by"] = self._("by")
        vars["to_page"] = self._("Pages")
        vars["created_at"] = self._("topic///Opened")
        vars["Pages"] = self._("Pages")

    def forum_vars_topic(self, vars):
        vars["to_page"] = self._("Pages")
        vars["topic_started"] = self._("topic started")
        vars["all_posts"] = self._("All posts")
        vars["search_all_posts"] = self._("Search for all posts of this member")
        vars["to_the_top"] = self._("to the top")
        vars["written_at"] = self._("written at")
        vars["Tags"] = self._("Tags")

    def forum_vars_tags(self, vars):
        vars["title"] = self._("Forum tags")

class SocioInterfaceAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-sociointerface.design", self.ext_design)
        self.rhook("headmenu-admin-sociointerface.design", self.headmenu_design)
        self.rhook("admin-sociointerface.validate", self.validate)
        self.rhook("admin-sociointerface.previews", self.previews)
        self.rhook("admin-sociointerface.preview", self.preview)

    def headmenu_design(self, args):
        if args == "new":
            return [self._("New design"), "sociointerface/design"]
        elif re_rename.match(args):
            return [self._("Renaming"), "sociointerface/design"]
        return self._("Socio interface design")

    def menu_design_index(self, menu):
        menu.append({"id": "sociointerface/design", "text": self._("Socio interface"), "leaf": True, "admin_index": not self.conf("socio.design"), "order": 3})

    def ext_design(self):
        self.call("design-admin.editor", "sociointerface")

    def validate(self, design, errors):
        html = design.get("html")
        if not html:
            errors.append(self._("Socio interface design package must contain an HTML file"))
        elif len(html) > 1:
            errors.append(self._("Socio interface design package must not contain more than one HTML file"))
        files = design.get("files")
        if not files.get("index.html", None):
            errors.append(self._("index.html must exist in the socio interface design package"))
        if not design.get("css"):
            errors.append(self._("Socio interface design package must contain a CSS file"))

    def previews(self, previews):
        previews.append({"filename": "index.html", "title": self._("Forum categories")})
        previews.append({"filename": "category.html", "title": self._("Forum category")})
        previews.append({"filename": "topic.html", "title": self._("Forum topic")})
        previews.append({"filename": "tags.html", "title": self._("Tags cloud")})

    def preview(self, design, filename):
        vars = {}
        demo_contents = ["The most popular type of MMOG, and the sub-genre that pioneered the category, is the massively multiplayer online role playing game (MMORPG), which descended from university mainframe computer MUD and adventure games such as Rogue and Dungeon on the PDP-10. These games predate the commercial gaming industry and the Internet, but still featured persistent worlds and other elements of MMOGs still used today.", "The first graphical MMOG, and a major milestone in the creation of the genre, was the multi-player flight combat simulation game Air Warrior by Kesmai on the GEnie online service, which first appeared in 1986.<br /><br />Commercial MMORPGs gained early acceptance in the late 1980s and early 1990s. The genre was pioneered by the GemStone series on GEnie, also created by Kesmai, and Neverwinter Nights, the first such game to include graphics, which debuted on AOL in 1991.<br /><br />As computer game developers applied MMOG ideas to other computer and video game genres, new acronyms started to develop, such as MMORTS. MMOG emerged as a generic term to cover this growing class of games. These games became so popular that a magazine, called Massive Online Gaming, released an issue in October 2002 hoping to cover MMOG topics exclusively, but it never released its second issue.", "There are a number of factors shared by most MMOGs that make them different from other types of games. MMOGs create a persistent universe where the game milieu continues regardless of interaction. Since these games emphasize multiplayer gameplay, many have only basic single-player aspects and the artificial intelligence on the server is primarily designed to support group play. As a result, players cannot \"finish\" MMOGs in the typical sense of single-player games.<br /><br />However single player game play is quite viable, although this may result in the player being unable to experience all content. This is especially the case for content designed for a multiplayer group commonly called a \"party\" or \"raid party\" in the case of the largest player groups which are required for the most significant and potentially rewarding play experiences and \"boss fights\" which are often designed to require multiple players to ensure the creature or NPC is killed.<br /><br />Most MMOGs also share other characteristics that make them different from other multiplayer online games. MMOGs host a large number of players in a single game world, and all of those players can interact with each other at any given time. Popular MMOGs might have thousands of players online at any given time, usually on a company owned server. Non-MMOGs, such as Battlefield 1942 or Half-Life usually have fewer than 50 players online (per server) and are usually played on private servers. Also, MMOGs usually do not have any significant mods since the game must work on company servers. There is some debate if a high head-count is the requirement to be an MMOG. Some say that it is the size of the game world and its capability to support a large number of players that should matter. For example, despite technology and content constraints, most MMOGs can fit up to a few thousand players on a single game server at a time.<br /><br />To support all those players, MMOGs need large-scale game worlds, and servers to connect players to those worlds. Sometimes a game features a universe which is copied onto different servers, separating players, and this is called a \"sharded\" universe. Other games will feature a single universe which is divided among servers, and requires players to switch. Still others will only use one part of the universe at any time. For example, Tribes (which is not an MMOG) comes with a number of large maps, which are played in rotation (one at a time). In contrast, the similar title PlanetSide uses the second model, and allows all map-like areas of the game to be reached via flying, driving, or teleporting.<br /><br />MMORPGs usually have sharded universes, as they provide the most flexible solution to the server load problem, but not always. For example, the space sim Eve Online uses only one large cluster server peaking at over 51,500 simultaneous players.<br /><br />There are also a few more common differences between MMOGs and other online games. Most MMOGs charge the player a monthly or bimonthly fee to have access to the game's servers, and therefore to online play. Also, the game state in an MMOG rarely ever resets. This means that a level gained by a player today will still be there tomorrow when the player logs back on. MMOGs often feature in-game support for clans and guilds. The members of a clan or a guild may participate in activities with one another, or show some symbols of membership to the clan or guild."]
        demo_subjects = [self._("Unknown problem"), self._("Very important combat will take place tomorrow"), self._("Not so important but a very large forum topic title")]
        demo_authors = [self._("Mike"), self._("Ivan Ivanov"), self._("John Smith"), self._("Lizard the killer"), self._("Cult of the dead cow")]
        demo_dates = [self._("6th of December, 2010 at 12:01"), self._("13th of June, 2008 at 02:11"), self._("7th of February, 2011 at 23:17"), self._("21th of October, 2010 at 17:00")]
        demo_signatures = [self._("This is a sample signature line"), self._("Some another line"), self._("Very strange signature"), self._("Absolutely crazy signature line")]
        demo_tags = [self._("game"), self._("mmo"), self._("constructor"), self._("people"), self._("online games"), self._("game industry"), self._("game engine")]
        demo_author_menu = [self._("Profile"), self._("All posts"), self._("Rating"), self._("Projects"), self._("Wishlist")]
        demo_forum_actions = [self._("delete"), self._("edit"), self._("reply"), self._("ignore")]
        if filename == "index.html":
            self.call("forum.vars-index", vars)
            cats = []
            vars["categories"] = cats
            for i in range(0, random.randrange(1, 30)):
                if i == 0 or random.random() < 0.2:
                    cats.append({
                        "header": random.choice([self._("Main group"), self._("Additional categories"), self._("Important"), self._("Technical reference")]),
                    })
                cats.append({
                    "category": {
                        "title": random.choice([self._("News"), self._("Technical support"), self._("A very long forum category title"), self._("Developers club")]),
                        "description": random.choice(["", self._("This is a short category description"), self._("This is a very long category description. It can be very-very long. And even longer. It can take several lines. Most of us know him as the big jolly man with a white beard and red suit, but who was - or were - the real Santa Claus? Ivan Watson goes to Demre in Turkey to find out more about the legend of Saint Nicholas.")]),
                        "topics": random.randrange(0, random.choice([10, 100, 1000, 10000, 100000])) if random.random() < 0.9 else None,
                        "replies": random.randrange(0, random.choice([10, 100, 1000, 10000, 100000])) if random.random() < 0.9 else None,
                        "unread": random.random() < 0.5,
                        "lastinfo": {
                            "topic": "topic",
                            "post": "post",
                            "page": "page",
                            "subject_html": random.choice(demo_subjects),
                            "updated": random.choice(demo_dates),
                            "author_html": random.choice(demo_authors),
                        } if random.random() < 0.5 else None,
                    }
                })
        elif filename == "category.html":
            self.call("forum.vars-category", vars)
            topics = []
            vars["title"] = self._("Forum category")
            vars["topics"] = topics
            pinned = True
            for i in range(0, random.choice([0, 3, 10, 20])):
                if random.random() < 0.5:
                    pinned = False
                topics.append({
                    "pinned": pinned,
                    "unread": random.random() < 0.5,
                    "subject_html": random.choice(demo_subjects),
                    "subscribed": random.random() < 0.5,
                    "literal_created": random.choice(demo_dates),
                    "author_html": random.choice(demo_authors),
                    "posts": random.randrange(0, random.choice([10, 100, 1000, 10000, 100000])) if random.random() < 0.9 else None,
                    "uuid": "topic",
                })
                if random.random() < 0.5:
                    topic = topics[-1]
                    topic["last_post"] = "post"
                    topic["last_post_page"] = "page"
                    topic["last_post_created"] = random.choice(demo_dates)
                    topic["last_post_author_html"] = random.choice(demo_authors)
                if random.random() < 0.5:
                    pages = []
                    topics[-1]["pages"] = pages
                    for i in range(0, random.randrange(2, random.choice([3, 5, 10, 20, 50]))):
                        pages.append({"entry": {"text": i + 1, "a": {"href": "#"}}})
                    pages[-1]["lst"] = True
            if len(topics):
                topics[-1]["lst"] = True
        elif filename == "topic.html":
            self.call("forum.vars-topic", vars)
            vars["show_topic"] = random.random() < 0.8,
            vars["topic"] = {
                "subject_html": random.choice(demo_subjects),
                "subscribed": random.random() < 0.5,
                "literal_created": random.choice(demo_dates),
                "avatar": "http://%s/st/constructor/design/av%d.gif" % (self.app().inst.config["main_host"], random.randrange(0, 6)),
                "author_html": random.choice(demo_authors),
                "content_html": random.choice(demo_contents),
            }
            vars["title"] = vars["topic"]["subject_html"]
            if random.random() < 0.5:
                tags = []
                for i in range(0, random.randrange(1, 20)):
                    tags.append('<a href="#">%s</a>' % random.choice(demo_tags))
                vars["topic"]["tags_html"] = ", ".join(tags)
            if random.random() < 0.5:
                signature = random.sample(demo_signatures, random.randrange(1, 5))
                vars["topic"]["signature"] = "<br />".join(signature)
            if random.random() < 0.8:
                menu = []
                vars["topic"]["author_menu"] = menu
                for i in range(0, random.randrange(1, 6)):
                    menu.append({
                        "href": "#",
                        "title": random.choice(demo_author_menu),
                    })
            if random.random() < 0.8:
                actions = []
                for i in range(0, random.randrange(1, 4)):
                    actions.append('<a href="#">%s</a>' % random.choice(demo_forum_actions))
                vars["topic"]["topic_actions"] = " / ".join(actions)
            if random.random() < 0.75:
                vars["posts"] = []
                for i in range(0, random.choice([1, 5, 20])):
                    post = {
                        "literal_created": random.choice(demo_dates),
                        "avatar": "http://%s/st/constructor/design/av%d.gif" % (self.app().inst.config["main_host"], random.randrange(0, 6)),
                        "author_html": random.choice(demo_authors),
                        "content_html": random.choice(demo_contents),
                    }
                    vars["posts"].append(post)
                    if random.random() < 0.4:
                        post["post_title"] = random.choice(demo_subjects)
                        post["subscribed"] = random.random() < 0.5
                    if random.random() < 0.2:
                        tags = []
                        for i in range(0, random.randrange(1, 20)):
                            tags.append('<a href="#">%s</a>' % random.choice(demo_tags))
                        post["tags_html"] = ", ".join(tags)
                    if random.random() < 0.5:
                        signature = random.sample(demo_signatures, random.randrange(1, 5))
                        post["signature"] = "<br />".join(signature)
                    if random.random() < 0.8:
                        menu = []
                        post["author_menu"] = menu
                        for i in range(0, random.randrange(1, 6)):
                            menu.append({
                                "href": "#",
                                "title": random.choice(demo_author_menu),
                            })
                    if random.random() < 0.8:
                        actions = []
                        for i in range(0, random.randrange(1, 4)):
                            actions.append('<a href="#">%s</a>' % random.choice(demo_forum_actions))
                        post["topic_actions"] = " / ".join(actions)
        elif filename == "tags.html":
            self.call("forum.vars-tags", vars)
            tags = []
            vars["tags"] = tags
            for i in range(0, random.randrange(1, 1000)):
                tags.append({"url": "#", "html": htmlescape(random.choice(demo_tags))})
            tags[-1]["lst"] = True
        else:
            self.call("web.not_found")
        if filename == "category.html" or filename == "topic.html":
            if random.random() < 0.5:
                pages_list = []
                pages = random.choice([2, 5, 10, 30])
                page = random.randrange(1, pages)
                last_show = None
                for i in range(1, pages + 1):
                    show = (i <= 5) or (i >= pages - 5) or (abs(i - page) < 5)
                    if show:
                        pages_list.append({"entry": {"text": i, "a": None if i == page else {"href": "#"}}})
                    elif last_show:
                        pages_list.append({"entry": {"text": "..."}})
                    last_show = show
                pages_list[-1]["lst"] = True
                vars["pages"] = pages_list
        if random.random() < 0.9:
            if random.random() < 0.5:
                vars["topmenu_left"] = [{"header": True, "html": self._("Some header")}]
            else:
                lst = []
                vars["topmenu_left"] = lst
                for i in range(0, random.randrange(1, 3)):
                    lst.append({
                        "html": self._("Menu item"),
                        "href": "#" if random.random() < 0.8 else None,
                    })
                lst[-1]["lst"] = True
        lst = []
        vars["topmenu_right"] = lst
        for i in range(0, random.randrange(1, 3)):
            lst.append({
                "html": random.choice([self._("Login"), self._("Logout"), self._("Settings"), self._("Friends")]),
                "href": "#" if random.random() < 0.8 else None,
                "image": "http://%s/st/constructor/cabinet/%s" % (self.app().inst.config["main_host"], random.choice(["settings.gif", "constructor.gif"])) if random.random() < 0.7 else None,
            })
        if random.random() < 0.8:
            lst.insert(0, {"search": True, "button": self._("Search")})
        lst[-1]["lst"] = True
        if random.random() < 0.8:
            lst = []
            vars["menu_left"] = lst
            for i in range(0, random.randrange(1, 4)):
                lst.append({
                    "html": self._("Menu item"),
                    "href": "#" if random.random() < 0.8 else None,
                })
            lst[-1]["lst"] = True
        if random.random() < 0.8:
            lst = []
            vars["menu_right"] = lst
            for i in range(0, random.randrange(1, 5)):
                lst.append({
                    "html": random.choice([self._("Move"), self._("Pin"), self._("Unpin"), self._("Close"), self._("Open"), self._("New topic")]),
                    "href": "#" if random.random() < 0.8 else None,
                })
            lst[-1]["lst"] = True
        content = self.call("web.parse_template", "socio/%s" % filename, vars)
        self.call("design.response", design, "index.html", content, vars)
