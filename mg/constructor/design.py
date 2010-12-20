from mg import *
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
    "html": "text/html"
}

re_valid_filename = re.compile(r'^(?:.*[/\\]|)([a-z0-9_\-]+)\.([a-z0-9]+)$')
re_proto = re.compile(r'^[a-z]+://')
re_slash = re.compile(r'^/')

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

class DesignHTMLParser(HTMLParser.HTMLParser):
    def __init__(self):
        HTMLParser.HTMLParser.__init__(self)
        self.output = ""
        self.tagstack = []

    def handle_starttag(self, tag, attrs):
        self.process_tag(tag, attrs)
        html = "<%s" % tag
        for key, val in attrs:
            html += ' %s="%s"' % (key, htmlescape(value))
        html += ">";
        self.output += html
        self.tagstack.append(tag)

    def handle_endtag(self, tag):
        expected = self.tagstack.pop() if len(self.tagstack) else None
        if expected != tag:
            raise HTMLParser.HTMLParseError(self._("Closing tag </{0}> doesn't match opening tag <{1}>").format(tag, expected), (self.lineno, self.offset))
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
        if len(self.tagstack):
            raise HTMLParser.HTMLParseError(self._("Not closed tags at the end of file: %s") % (", ".join(self.tagstack)))

    def process_tag(self, tag, attrs):
        if tag == "img" or tag == "link":
            attrs_dict = dict(attrs)
            att = "href" if tag == "link" else "src"
            href = attrs_dict.get(att)
            if not href:
                raise HTMLParser.HTMLParseError(self._("Mandatory attribute '{0}' missing in tag '{1}'").format(att, tag), (self.lineno, self.offset))
            if not re_proto.match(href) and not re_slash.match(href):
                for i in range(0, len(attrs)):
                    if attrs[i][0] == att:
                        attrs[i] = (att, "[%design_root%]/" + attrs[i][1])

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
        files = []
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
            files.append({"filename": filename, "content-type": content_type})
        if count >= max_design_files:
            errors.append(self._("Design package couldn't contain more than %d files") % max_design_files)
        if size >= max_design_size:
            errors.append(self._("Design package contents couldn't be more than %d bytes") % max_design_size)
        errors.extend(list_errors)
        if len(html) > 1:
            errors.append(self._("Design package must not contain more than 1 HTML file"))
        if len(css) > 1:
            errors.append(self._("Design package must not contain more than 1 CSS file"))
        elif len(css) == 0:
            errors.append(self._("Design package must contain at least 1 CSS file"))
        if not len(errors):
            for file in upload_list:
                if file["content-type"] == "text/html":
                    data = self.zip.read(file["zipname"])
                    print "parsing %s:\n===\n%s===" % (file["zipname"], data)
                    parser = DesignHTMLParser()
                    parser.feed(data)
                    parser.close()
                    print "result:\n===\n%s===" % parser.output
                    file["data"] = parser.output
        design = self.obj(Design)
        design.set("group", group)
        design.set("uploaded", self.now())
        design.set("files", files)
        if len(html):
            design.set("html", html[0])
        if len(css):
            design.set("css", css[0])
        # 3rd party validation
        self.call("admin-%s.validate" % group, design, errors)
        if len(errors):
            return errors
        uri = self.call("cluster.static_upload_zip", "design-%s" % group, self.zip, upload_list)
        design.set("uri", uri)
        return design
        
class IndexPage(Module):
    def register(self):
        Module.register(self)
        self.rhook("indexpage.response", self.response)

    def response(self, design, content, vars):
        vars["global_html"] = self.httpfile("%s/%s" % (design.get("uri"), design.get("html")))
        vars["design_root"] = design.get("uri")
        self.call("web.response_global", content, vars)

class IndexPageAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-indexpage.design", self.ext_design)
        self.rhook("headmenu-admin-indexpage.design", self.headmenu_design)
        self.rhook("admin-indexpage.validate", self.validate)

    def headmenu_design(self, args):
        if args == "new":
            return [self._("New design"), "indexpage/design"]
        return self._("Index page design")

    def menu_design_index(self, menu):
        menu.append({"id": "indexpage/design", "text": self._("Index page"), "leaf": True})

    def ext_design(self):
        self.call("design-admin.editor", "indexpage")

    def validate(self, design, errors):
        if not design.get("html"):
            errors.append(self._("Index page design package must contain at least 1 HTML file"))

class DesignAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("design-admin.editor", self.editor)

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
                lst = self.objlist(DesignList, query_index="all")
                lst.load(silent=True)
                designs = []
                for ent in lst:
                    designs.append({
                        "uuid": ent.uuid,
                        "uploaded": ent.get("uploaded"),
                        "title": htmlescape(ent.get("title")),
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
                    "install": self._("install to the project"),
                    "ConfirmDelete": self._("Do you really want to delete this design?"),
                    "ConfirmInstall": self._("Do you really want to install this design?"),
                    "designs": designs,
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
                    design = self.obj(Design, uuid, data={})
                    design.remove()
                    self.call("admin.redirect", "%s/design" % group)
                elif cmd == "install":
                    pass
                elif cmd == "preview":
                    try:
                        design = self.obj(Design, uuid)
                    except ObjectNotFoundException:
                        pass
                    else:
                        self.call("%s.response" % group, design, "Some response", {})
            self.call("web.not_found")
