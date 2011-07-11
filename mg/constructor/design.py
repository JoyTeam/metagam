from mg import *
from mg.constructor import *
from mg.core.cluster import StaticUploadError
import re
import zipfile
import cStringIO
import HTMLParser
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageFilter
import dircache
import mg
import cssutils
from cssutils import *
import mg

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
re_generator = re.compile('^gen\/.+$')
re_valid_color = re.compile('^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$')
re_newlines = re.compile(r'\r?\n\r?')
re_st_mg = re.compile(r'/st-mg(?:/\[%ver%\])?(/.*)')
re_dyn_mg = re.compile(r'/dyn-mg(/.*)')

cssutils.ser.prefs.lineSeparator = u' '
cssutils.ser.prefs.indent = u''

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
    def __init__(self, app, fragment=False):
        """
        HTML Parser constructor.
        app - application
        fragment - parse document fragment. Don't require DOCTYPE declaration, content-type declaration and so on
        """
        HTMLParser.HTMLParser.__init__(self)
        Module.__init__(self, app, "mg.constructor.design.DesignHTMLParser")
        self.output = ""
        self.tagstack = []
        self.decl_ok = False
        self.content_type_ok = False
        self.scripts = set()
        self.forms = []
        self.in_form = None
        self.fragment = fragment

    def handle_starttag(self, tag, attrs):
        self.process_tag(tag, attrs)
        html = "<%s" % tag
        for key, val in attrs:
            html += ' %s="%s"' % (key, htmlescape(val))
        html += ">";
        self.output += html
        self.tagstack.append(tag)
        if tag == "form":
            if self.in_form:
                raise HTMLParser.HTMLParseError(self._("Forms inside forms are not allowed"), (self.lineno, self.offset))
            self.in_form = dict(attrs)
            self.in_form["inputs"] = {}
            self.forms.append(self.in_form)

    def handle_endtag(self, tag):
        expected = self.tagstack.pop() if len(self.tagstack) else None
        if expected != tag:
            raise HTMLParser.HTMLParseError(self._("Closing tag '{0}' doesn't match opening tag '{1}'").format(tag, expected), (self.lineno, self.offset))
        self.output += "</%s>" % tag
        self.in_form = None

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
        if self.fragment:
            raise HTMLParser.HTMLParseError(self._("XML declarations are not allowed here"), (self.lineno, self.offset))
        self.output += "<!%s>" % decl
        if not re_valid_decl.match(decl):
            raise HTMLParser.HTMLParseError(self._("Valid XHTML doctype required"), (self.lineno, self.offset))
        self.decl_ok = True

    def close(self):
        HTMLParser.HTMLParser.close(self)
        if len(self.tagstack):
            raise HTMLParser.HTMLParseError(self._("Not closed tags at the end of file: %s") % (", ".join(self.tagstack)))
        if not self.fragment:
            if not self.decl_ok:
                raise HTMLParser.HTMLParseError(self._("DOCTYPE not specified"))
            if not self.content_type_ok:
                raise HTMLParser.HTMLParseError(self._('Content-type not specified. Add <meta http-equiv="Content-type" content="text/html; charset=utf-8" /> into the head tag'))

    def process_tag(self, tag, attrs):
        if tag == "img" or tag == "link" or tag == "input" or tag == "script":
            attrs_dict = dict(attrs)
            att = "href" if tag == "link" else "src"
            href = attrs_dict.get(att)
            if href:
                m = re_st_mg.search(href)
                if m:
                    href = m.group(1)
                    for i in range(0, len(attrs)):
                        if attrs[i][0] == att:
                            attrs[i] = (att, "/st-mg/[%%ver%%]%s" % href)
                    self.scripts.add(href)
                else:
                    m = re_dyn_mg.search(href)
                    if m:
                        href = m.group(1)
                        for i in range(0, len(attrs)):
                            if attrs[i][0] == att:
                                attrs[i] = (att, "/dyn-mg%s" % href)
                        self.scripts.add(href)
                    elif not re_proto.match(href) and not re_slash.match(href) and not re_template.search(href):
                        for i in range(0, len(attrs)):
                            if attrs[i][0] == att:
                                attrs[i] = (att, "[%design_root%]/" + attrs[i][1])
        elif tag == "meta":
            if self.fragment:
                raise HTMLParser.HTMLParseError(self._("Meta tags are not allowed here"), (self.lineno, self.offset))
            attrs_dict = dict(attrs)
            key = attrs_dict.get("http-equiv")
            val = attrs_dict.get("content")
            if key is not None and val is not None:
                if key.lower() == "content-type":
                    if val.lower() != "text/html; charset=utf-8":
                        raise HTMLParser.HTMLParseError(self._('Invalid character set. Specify: content="text/html; charset=utf-8"'), (self.lineno, self.offset))
                    self.content_type_ok = True
        elif tag == "input":
            if self.in_form:
                if not attrs.get("name"):
                    raise HTMLParser.HTMLParseError(self._('Form input must have "name" attribute'), (self.lineno, self.offset))
                self.in_form["inputs"][attrs["name"]] = attrs

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
                m = re_st_mg.match(href)
                if m:
                    href = m.group(1)
                    for i in range(0, len(attrs)):
                        if attrs[i][0] == att:
                            attrs[i] = (att, "http://www.%s/st-mg%s" % (str(self.app().inst.config["main_host"]), href))
                else:
                    m = re_dyn_mg.match(href)
                    if m:
                        href = m.group(1)
                        for i in range(0, len(attrs)):
                            if attrs[i][0] == att:
                                attrs[i] = (att, "http://www.%s/dyn-mg%s" % (str(self.app().inst.config["main_host"]), href))
                    else:
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
        parsed_html = {}
        if not len(errors):
            for file in upload_list:
                if file["content-type"] == "text/html":
                    data = self.zip.read(file["zipname"])
                    try:
                        if file["filename"] == "blocks.html":
                            fragment = True
                        else:
                            fragment = False
                        parser = DesignHTMLParser(self.app(), fragment=fragment)
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
                        parsed_html[file["filename"]] = parser
                    except HTMLParser.HTMLParseError as e:
                        self.exception(e)
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
        self.call("admin-%s.validate" % group, design, parsed_html, errors)
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

class Puzzle(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        self.elements = []

    def register_element(self, image, left, top):
        self.elements.append((image, left, top))

    def paste_element(self, image, left, top):
        self.image.paste(image, (left, top))
        self.register_element(image, left, top)

    def update_elements(self):
        for image, left, top in self.elements:
            width, height = image.size
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, width, height), fill=(0, 0, 0, 0), outline=(0, 0, 0, 0))
            del draw
            img = self.image.crop((left, top, left + width, top + height))
            image.paste(img, None, img)

class DesignGenerator(Module):
    def __init__(self, app):
        Module.__init__(self, app, "mg.constructor.design.DesignGenerator")

    def info(self):
        return {
            "id": self.id(),
            "group": self.group(),
            "name": self.name(),
            "preview": self.preview(),
        }

    def form_fields(self, fields):
        pass

    def form_parse(self, errors):
        pass

    def upload_image(self, param, errors):
        req = self.req()
        image = req.param_raw(param)
        if image is None or not len(image):
            errors[param] = self._("Upload an image")
            return None
        try:
            image_obj = Image.open(cStringIO.StringIO(image))
            if image_obj.load() is None:
                raise IOError
        except IOError:
            errors[param] = self._("Image format not recognized")
            return None
        except OverflowError:
            errors[param] = self._("Image format not recognized")
            return None
        try:
            image_obj.seek(1)
            errors[param] = self._("Animated images are not supported")
            return None
        except EOFError:
            pass
        return image_obj.convert("RGBA")

    def color_param(self, param, errors):
        req = self.req()
        val = req.param(param)
        m = re_valid_color.match(val)
        if not m:
            errors[param] = self._("Invalid color format")
            return None
        r, g, b = m.group(1, 2, 3)
        return (int(r, 16), int(g, 16), int(b, 16))

    def css_color(self, col):
        return "#%02x%02x%02x" % col

    def merge_color(self, ratio, col0, col1):
        return (
            int(col0[0] * (1 - ratio) + col1[0] * ratio + 0.5),
            int(col0[1] * (1 - ratio) + col1[1] * ratio + 0.5),
            int(col0[2] * (1 - ratio) + col1[2] * ratio + 0.5))

    def brightness(self, color):
        return ((color[0] / 255) ** 2 + (color[1] / 255) ** 2 + (color[2] / 255) ** 2) / 3

    def load(self):
        design = self.obj(Design)
        self.design = design
        design.set("group", self.group())
        design.set("uploaded", self.now())
        dir = "%s/data/design/%s/%s" % (mg.__path__[0], self.group(), self.id())
        html = []
        self.html_list = html
        css = []
        self.css_list = css
        files = {}
        upload_list = []
        self.upload_list = upload_list
        for filename in dircache.listdir(dir):
            m = re_valid_filename.match(filename)
            if not m:
                self.warning("Filename '%s' is invalid", filename)
                continue
            basename, ext = m.group(1, 2)
            content_type = permitted_extensions.get(ext)
            if not content_type:
                raise RuntimeError("Unsupported extension: %s" % ext)
            if ext == "html":
                html.append(filename)
            if ext == "css":
                css.append(filename)
            upload_list.append({"filename": filename, "content-type": content_type, "path": "%s/%s" % (dir, filename)})
            files[filename] = {"content-type": content_type}
        design.set("files", files)
        self.generate_files()
        if len(html):
            design.set("html", html)
        if len(css):
            design.set("css", css)
        errors = []
        self.call("admin-%s.validate" % self.group(), design, {}, errors)
        if len(errors):
            raise RuntimeError(", ".join(errors))
        for file in upload_list:
            if file["content-type"] == "text/html":
                try:
                    data = file["data"]
                except KeyError:
                    with open(file["path"], "r") as f:
                        data = f.read()
                    stackless.schedule()
                try:
                    if file["filename"] == "blocks.html":
                        fragment = True
                    else:
                        fragment = False
                    parser = DesignHTMLParser(self.app(), fragment=fragment)
                    parser.feed(data)
                    parser.close()
                    vars = {}
                    self.call("admin-%s.preview-data" % self.group(), vars)
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
                stackless.schedule()
        if len(errors):
            raise RuntimeError(", ".join(errors))
        self.puzzle = Puzzle(1280, 1024)
        self.elements = {}
        self.css = {}
        return design

    def generate_files(self):
        pass

    def edit_css(self, filename):
        parser = CSSParser()
        css = parser.parseFile("%s/data/design/%s/%s/%s" % (mg.__path__[0], self.group(), self.id(), filename), "utf-8")
        self.css[filename] = css
        return css

    def load_image(self, filename):
        image = Image.open("%s/data/design/%s/%s/%s" % (mg.__path__[0], self.group(), self.id(), filename)).convert("RGBA")
        stackless.schedule()
        return image

    def store_image(self, image, filename, format):
        self.elements[filename] = (image, format)

    def register_element(self, filename, format, left, top):
        image = self.load_image(filename)
        self.puzzle.register_element(image, left, top)
        self.store_image(image, filename, format)
        return image

    def paste_element(self, filename, format, left, top):
        image = self.load_image(filename)
        self.puzzle.paste_element(image, left, top)
        self.store_image(image, filename, format)
        return image

    def create_element(self, filename, format, left, top, width, height):
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        self.puzzle.register_element(image, left, top)
        self.store_image(image, filename, format)
        m = re_valid_filename.match(filename)
        if not m:
            raise RuntimeError("Filename '%s' is invalid" % filename)
        basename, ext = m.group(1, 2)
        content_type = permitted_extensions.get(ext)
        self.upload_list.append({"filename": filename, "content-type": content_type})
        self.design.get("files")[filename] = {"content-type": content_type}
        return image

    def temp_image(self, filename):
        self.upload_list[:] = [ent for ent in self.upload_list if ent["filename"] != filename]
        del self.design.get("files")[filename]
        return self.load_image(filename)

    def add_file(self, filename, content_type, data):
        self.upload_list.append({"filename": filename, "content-type": content_type, "data": data})
        self.design.get("files")[filename] = {"content-type": content_type}
        if content_type == "text/html":
            self.html_list.append(filename)
        if content_type == "text/css":
            self.css_list.append(filename)

    def process(self):
        pass

    def presets(self):
        return None

    def store(self):
        self.puzzle.update_elements()
        for ent in self.upload_list:
            el = self.elements.get(ent["filename"])
            if el:
                image, format = el
                stream = cStringIO.StringIO()
                image.save(stream, format, quality=95)
                stackless.schedule()
                ent["data"] = stream.getvalue()
            css = self.css.get(ent["filename"])
            if css:
                ent["data"] = ("".join(["%s\n" % rule.cssText for rule in css.cssRules])).encode("utf-8")
        uri = self.call("cluster.static_upload_zip", "design-%s" % self.group(), None, self.upload_list)
        self.design.set("uri", uri)
        self.design.set("title", self.name())
        self.design.store()

class DesignIndexMagicLands(DesignGenerator):
    def group(self): return "indexpage"
    def id(self): return "index-magiclands"
    def name(self): return "Magic Lands"
    def preview(self): return "/st/constructor/design/gen/test.jpg"

    def form_fields(self, fields):
        fields.append({"name": "base-image", "type": "fileuploadfield", "label": self._("Main image (normal size is {0}x{1}, will be automatically resized if not match)").format(902, 404)})

    def form_parse(self, errors):
        self.base_image = self.upload_image("base-image", errors)

    def process(self):
        self.paste_element("index_top.jpg", "JPEG", 0, 0)
        width, height = self.base_image.size
        if width != 902:
            height = height * 902.0 / width
            width = 902
        if height < 404:
            width = width * 404.0 / height
            height = 404
        width = int(width + 0.5)
        height = int(height + 0.5)
        self.puzzle.image.paste(self.base_image.resize((width, height), Image.ANTIALIAS), (535 - width / 2, (404 - height) / 3))
        over = self.temp_image("index_top-over.png")
        self.puzzle.image.paste(over, (0, 297), over)
        login = self.temp_image("login.png")
        self.puzzle.image.paste(login, (792, 85), login)

class DesignIndexBrokenStones(DesignGenerator):
    def group(self): return "indexpage"
    def id(self): return "broken-stones"
    def name(self): return self._("Broken Stones")
    def preview(self): return "/st/constructor/design/gen/index-broken-stones.jpg"

    def form_fields(self, fields):
        project = self.app().project
        fields.append({"name": "base-image", "type": "fileuploadfield", "label": self._("Main image (normal size is {0}x{1}, will be automatically resized if not match)").format(880, 476)})
        fields.append({"name": "body_dark", "label": self._("Background dark color"), "value": "#000000"})
        fields.append({"name": "body_light", "label": self._("Background light color"), "value": "#ffffff", "inline": True})
        fields.append({"name": "game_title", "label": self._("Game title (multiline permitted)"), "value": project.get("title_short"), "type": "textarea"})
        fields.append({"name": "game_title_color", "label": self._("Game title color"), "value": "#272727"})
        fields.append({"name": "game_title_glow", "label": self._("Game title glow color"), "value": "#ffffff", "inline": True})
        fields.append({"name": "about_text_color", "label": self._("Text color in the 'About' and 'News' blocks"), "value": "#000000"})
        fields.append({"name": "text_color", "label": self._("Text color of the footer, rating participants"), "value": "#000000", "inline": True})
        fields.append({"name": "href_color", "label": self._("Hyperlinks color"), "value": "#af0341"})
        fields.append({"name": "headers_color", "label": self._("Color of block headers"), "value": "#39322d", "inline": True})
        fields.append({"name": "rating_score_color", "label": self._("Color of rating score values"), "value": "#960036"})
        fields.append({"name": "links_color", "label": self._("Text color in the 'Links' block"), "value": "#413a36", "inline": True})

    def form_parse(self, errors):
        req = self.req()
        self.base_image = self.upload_image("base-image", errors)
        self.game_title = req.param("game_title")
        self.game_title_color = self.color_param("game_title_color", errors)
        self.game_title_glow = self.color_param("game_title_glow", errors)
        self.body_light = self.color_param("body_light", errors)
        self.body_dark = self.color_param("body_dark", errors)
        self.text_color = self.color_param("text_color", errors)
        self.about_text_color = self.color_param("about_text_color", errors)
        self.headers_color = self.color_param("headers_color", errors)
        self.href_color = self.color_param("href_color", errors)
        self.links_color = self.color_param("links_color", errors)
        self.rating_score_color = self.color_param("rating_score_color", errors)

    def colorize(self, image, black, white):
        image = image.convert("RGBA")
        new_image = Image.new("RGBA", image.size, (0, 0, 0, 0))
        new_image.paste(ImageOps.colorize(ImageOps.grayscale(image), black, white), (0, 0), image)
        return new_image

    def process(self):
        # minor images
        for file in ["border-bg.png", "border-bottom.png", "body-bg.png", "vintage-left.png", "vintage-right.png", "block.png", "block-sel.png", "rating-sel.png", "about-sel.png", "enter.png"]:
            self.store_image(self.colorize(self.load_image(file), self.body_dark, self.body_light), file, "PNG")
        # background
        body_bg = self.elements["body-bg.png"][0]
        for y in range(0, 3):
            for x in range(-2, 3):
                self.puzzle.image.paste(body_bg, (512 - 252 / 2 + 252 * x, 252 * y))
        # main image
        width, height = self.base_image.size
        if width != 880:
            height = height * 880.0 / width
            width = 880
        if height < 476:
            width = width * 476.0 / height
            height = 476
        width = int(width + 0.5)
        height = int(height + 0.5)
        # base image
        base_image = self.base_image.resize((width, height), Image.ANTIALIAS)
        base_image = base_image.crop((width / 2 - 440, 0, width / 2 + 440, 476))
        self.puzzle.image.paste(base_image, (512 - 880 / 2, 0))
        body_top = self.temp_image("body-top.png")
        body_top_colorized = self.colorize(body_top, self.body_dark, self.body_light)
        self.puzzle.image.paste(body_top_colorized, (0, 0), body_top)
        # game logo
        game_logo = self.temp_image("game-logo.png")
        game_logo_colorized = self.colorize(game_logo, self.body_dark, self.body_light)
        text = re_newlines.split(self.game_title.strip())
        font_size = 65
        watchdog = 0
        while font_size > 5:
            font = ImageFont.truetype(mg.__path__[0] + "/data/fonts/globus.ttf", font_size, encoding="unic")
            h = 0
            overflow = False
            for line in text:
                wl, hl = font.getsize(line)
                wmax = 240 - h * 60 / 76
                if wl > wmax:
                    overflow = True
                    break
                h += hl
            if h > 76:
                overflow = True
            if not overflow:
                break
            font_size -= 1
        # backgrounds
        game_logo_color = Image.new("RGBA", game_logo.size, (self.game_title_color[0], self.game_title_color[1], self.game_title_color[2], 255))
        game_logo_glow = Image.new("RGBA", game_logo.size, (self.game_title_glow[0], self.game_title_glow[1], self.game_title_glow[2], 255))
        # mask
        game_logo_mask = Image.new("RGBA", game_logo.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(game_logo_mask)
        y = (76 - h) / 2 + 18
        for line in text:
            wl, hl = font.getsize(line)
            x = 148 - wl / 2
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += hl
        del draw
        game_logo_glow_mask = game_logo_mask.filter(ImageFilter.BLUR).filter(ImageFilter.BLUR)
        game_logo_colorized.paste(game_logo_glow, (0, 0), game_logo_glow_mask)
        game_logo_colorized.paste(game_logo_color, (0, 0), game_logo_mask)
        self.puzzle.image.paste(game_logo_colorized, (350, 300), game_logo)
        # band
        band = self.temp_image("band.png")
        self.puzzle.image.paste(band, (0, 0), band)
        self.create_element("body-top.jpg", "JPEG", 0, 0, 1024, 627)
        # CSS
        css = self.edit_css("index.css")
        for rule in css.cssRules:
            if rule.type == cssutils.css.CSSRule.STYLE_RULE:
                if rule.selectorText == ".link-delim":
                    rule.style.setProperty("background-color", self.css_color(self.merge_color(0.8, self.body_dark, self.body_light)))
                    rule.style.setProperty("border-top", "solid 1px %s" % self.css_color(self.merge_color(0.1, self.body_dark, self.body_light)))
                elif rule.selectorText == "#about" or rule.selectorText == "#news":
                    rule.style.setProperty("border", "solid 1px %s" % self.css_color(self.merge_color(0.58, self.body_dark, self.body_light)))
                    rule.style.setProperty("color", self.css_color(self.about_text_color))
                elif rule.selectorText == "html, body, table, tr, td, form, input" or rule.selectorText == "#enter-remind a" or rule.selectorText == ".rating-member":
                    rule.style.setProperty("color", self.css_color(self.text_color))
                elif rule.selectorText == "#enter-remind a:hover":
                    rule.style.setProperty("color", self.css_color(self.merge_color(0.5, self.text_color, (255, 255, 255))))
                elif rule.selectorText == "a, a:visited":
                    rule.style.setProperty("color", self.css_color(self.href_color))
                elif rule.selectorText == "a:hover":
                    rule.style.setProperty("color", self.css_color(self.merge_color(0.5, self.href_color, (255, 255, 255))))
                elif rule.selectorText == ".vintage-title" or rule.selectorText == ".rating-title a":
                    rule.style.setProperty("color", self.css_color(self.headers_color))
                elif rule.selectorText == ".link-inactive" or rule.selectorText == "a.link-active":
                    rule.style.setProperty("color", self.css_color(self.links_color))
                elif rule.selectorText == "a.link-active:hover":
                    rule.style.setProperty("color", self.css_color(self.rating_score_color))
                elif rule.selectorText == ".rating-score" or rule.selectorText == "a.link-active:hover" or rule.selectorText == ".game-title":
                    rule.style.setProperty("color", self.css_color(self.rating_score_color))
                elif rule.selectorText == ".message-window":
                    rule.style.setProperty("background-color", self.css_color(self.merge_color(0.7, self.body_dark, self.body_light)))
                    rule.style.setProperty("border", "solid 1px %s" % self.css_color(self.merge_color(0.1, self.body_dark, self.body_light)))
                elif rule.selectorText == ".message-text-td":
                    rule.style.setProperty("color", self.css_color(self.text_color))
                elif rule.selectorText == ".message-button a" or rule.selectorText == "#field-submit-a":
                    rule.style.setProperty("background-color", self.css_color(self.merge_color(0.5, self.body_dark, self.body_light)))
                    rule.style.setProperty("color", self.css_color(self.text_color))
                elif rule.selectorText == ".message-button a:hover" or rule.selectorText == "#field-submit-a:hover":
                    rule.style.setProperty("background-color", self.css_color(self.merge_color(0.3, self.body_dark, self.body_light)))
                    rule.style.setProperty("color", self.css_color(self.text_color))

    def presets(self):
        presets = []
        presets.append({"title": self._("Grey"), "fields": [
            {"name": "body_light", "value": "#ffffff"},
            {"name": "body_dark", "value": "#000000"},
            {"name": "text_color", "value": "#000000"},
            {"name": "about_text_color", "value": "#000000"},
            {"name": "headers_color", "value": "#39322d"},
            {"name": "href_color", "value": "#af0341"},
            {"name": "links_color", "value": "#413a36"},
            {"name": "rating_score_color", "value": "#960036"},
            {"name": "game_title_color", "value": "#272727"},
            {"name": "game_title_glow", "value": "#ffffff"},
        ]})
        presets.append({"title": self._("White"), "fields": [
            {"name": "body_light", "value": "#ffffff"},
            {"name": "body_dark", "value": "#808080"},
            {"name": "text_color", "value": "#808080"},
            {"name": "about_text_color", "value": "#ffffff"},
            {"name": "headers_color", "value": "#383838"},
            {"name": "href_color", "value": "#8f0681"},
            {"name": "links_color", "value": "#816a66"},
            {"name": "rating_score_color", "value": "#c60056"},
            {"name": "game_title_color", "value": "#808080"},
            {"name": "game_title_glow", "value": "#ffffff"},
        ]})
        presets.append({"title": self._("Dark"), "fields": [
            {"name": "body_light", "value": "#404040"},
            {"name": "body_dark", "value": "#000000"},
            {"name": "text_color", "value": "#c0c0c0"},
            {"name": "about_text_color", "value": "#c0c0c0"},
            {"name": "headers_color", "value": "#c0c0c0"},
            {"name": "href_color", "value": "#c63066"},
            {"name": "links_color", "value": "#c0c0c0"},
            {"name": "rating_score_color", "value": "#c63066"},
            {"name": "game_title_color", "value": "#ffffff"},
            {"name": "game_title_glow", "value": "#c0c0c0"},
        ]})
        presets.append({"title": self._("Brick"), "fields": [
            {"name": "body_light", "value": "#e3520f"},
            {"name": "body_dark", "value": "#000000"},
            {"name": "text_color", "value": "#f4ba8f"},
            {"name": "about_text_color", "value": "#f4ba8f"},
            {"name": "headers_color", "value": "#f4ba8f"},
            {"name": "href_color", "value": "#d6b60a"},
            {"name": "links_color", "value": "#f4ba8f"},
            {"name": "rating_score_color", "value": "#ffffff"},
            {"name": "game_title_color", "value": "#ffffff"},
            {"name": "game_title_glow", "value": "#f4ba8f"},
        ]})
        presets.append({"title": self._("Night"), "fields": [
            {"name": "body_light", "value": "#101060"},
            {"name": "body_dark", "value": "#000000"},
            {"name": "text_color", "value": "#e0e0e0"},
            {"name": "about_text_color", "value": "#a9a9a9"},
            {"name": "headers_color", "value": "#6c73a4"},
            {"name": "href_color", "value": "#9ea9ff"},
            {"name": "links_color", "value": "#a9a9a9"},
            {"name": "rating_score_color", "value": "#ffffff"},
            {"name": "game_title_color", "value": "#ffffff"},
            {"name": "game_title_glow", "value": "#6c73ff"},
        ]})
        return presets

class DesignIndexCommonBlocks(DesignGenerator):
    def group(self): return "indexpage"

    def form_fields(self, fields):
        project = self.app().project
        fields.append({"id": "scheme1", "name": "scheme", "type": "radio", "label": self._("General layout scheme"), "value": 1, "boxLabel": '<img src="/st/constructor/indexpage/index-layout-1.png" alt="" />', "checked": True})
        fields.append({"id": "scheme2", "name": "scheme", "type": "radio", "label": "&nbsp;", "value": 2, "boxLabel": '<img src="/st/constructor/indexpage/index-layout-2.png" alt="" />', "inline": True})
        fields.append({"id": "scheme3", "name": "scheme", "type": "radio", "label": "&nbsp;", "value": 3, "boxLabel": '<img src="/st/constructor/indexpage/index-layout-3.png" alt="" />'})
        fields.append({"id": "scheme4", "name": "scheme", "type": "radio", "label": "&nbsp;", "value": 4, "boxLabel": '<img src="/st/constructor/indexpage/index-layout-4.png" alt="" />', "inline": True})
        fields.append({"name": "base-image", "type": "fileuploadfield", "label": self._("Main image (will be placed on the cyan area)")})

    def form_parse(self, errors):
        req = self.req()
        self.base_image = self.upload_image("base-image", errors)
        self.scheme = intz(req.param("scheme"))

    def generate_files(self):
        vars = {
            "tpl": self.id(),
            "scheme": self.scheme,
            "lang": self.call("l10n.lang"),
            "CharNameOrEmail": self._("Character name or e-mail"),
            "register": self._("registration"),
            "forgot": self._("forgot your password?"),
            "enter": self._("enter"),
            "News": self._("News"),
            "Description": self._("Description"),
            "Links": self._("Links"),
            "Ratings": self._("Ratings"),
            "main_host": self.app().inst.config.get("main_host"),
            "EnterTheGame": self._("Enter the game"),
            "MMOConstructor": self._("Browser based online games constructor"),
        }
        data = self.call("web.parse_template", "indexpage/common-blocks.html", vars)
        self.add_file("index.html", "text/html", data)
        vars = {
            "tpl": self.id(),
            "scheme": self.scheme,
            "lang": self.call("l10n.lang"),
        }
        self.add_file("index.css", "text/css", self.call("web.parse_template", "indexpage/common-blocks.css", vars))

    def process(self):
        # Box borders from the design
        box_left = self.load_image("box-left.png")
        box_right = self.load_image("box-right.png")
        box_top = self.load_image("box-top.png")
        box_bottom = self.load_image("box-bottom.png")
        box_left_top = self.load_image("box-left-top.png")
        box_right_top = self.load_image("box-right-top.png")
        box_left_bottom = self.load_image("box-left-bottom.png")
        box_right_bottom = self.load_image("box-right-bottom.png")
        # Borders geometry
        border_left = box_left.size[0]
        border_right = box_right.size[0]
        border_top = box_top.size[1]
        border_bottom = box_bottom.size[1]
        # Size of the base image given by the user
        base_width, base_height = self.base_image.size
        if self.scheme == 1 or self.scheme == 2:
            # Scaling base image
            if base_width != 1024:
                base_height = base_height * 1024.0 / base_width
                base_width = 1024
            base_width = int(base_width + 0.5)
            base_height = int(base_height + 0.5)
            base_image = self.base_image.resize((base_width, base_height), Image.ANTIALIAS)
            # Cropping if necessary
            if base_height > 1024 - border_bottom:
                base_image = base_image.crop((0, 0, base_width, 1024 - border_bottom))
                base_height = 1024 - border_bottom
            # Resizing puzzle image if necessary
            min_width = base_width + border_left + border_right
            if self.puzzle.width < min_width:
                self.puzzle = Puzzle(min_width, 1024)
            # Drawing base image on the puzzle
            self.create_element("base-image.jpg", "JPEG", 0, 0, base_width + border_left + border_right, base_height + border_bottom)
            self.puzzle.image.paste(base_image, (border_left, 0))
            # Drawing border on the puzzle
            x = 0
            while x < base_width + border_left + border_right:
                self.puzzle.image.paste(box_bottom, (x, base_height), box_bottom)
                x += box_bottom.size[0]
            y = 0
            while y < base_height + border_bottom:
                self.puzzle.image.paste(box_left, (0, y), box_left)
                self.puzzle.image.paste(box_right, (border_left + base_width, y), box_right)
                y += box_left.size[1]
            self.puzzle.image.paste(box_left_bottom, (0, base_height + border_bottom - box_left_bottom.size[1]), box_left_bottom)
            self.puzzle.image.paste(box_right_bottom, (base_width + border_left + border_right - box_right_bottom.size[0], base_height + border_bottom - box_right_bottom.size[1]), box_right_bottom)
        elif self.scheme == 3 or self.scheme == 4:
            # Scaling base image
            target_base_width = 482.0 - border_left - border_right
            if base_width != target_base_width:
                base_height = base_height * target_base_width / base_width
                base_width = target_base_width
            base_width = int(base_width + 0.5)
            base_height = int(base_height + 0.5)
            base_image = self.base_image.resize((base_width, base_height), Image.ANTIALIAS)
            # Resizing puzzle image if necessary
            min_height = base_height + border_top + border_bottom
            if self.puzzle.height < min_height:
                self.puzzle = Puzzle(482, min_height)
            # Drawing base image on the puzzle
            self.create_element("base-image.jpg", "JPEG", 0, 0, base_width + border_left + border_right, base_height + border_top + border_bottom)
            self.puzzle.image.paste(base_image, (border_left, border_top))
            # Drawing border on the puzzle
            x = 0
            while x < base_width + border_left + border_right:
                self.puzzle.image.paste(box_top, (x, 0), box_top)
                self.puzzle.image.paste(box_bottom, (x, base_height + border_top), box_bottom)
                x += box_bottom.size[0]
            y = 0
            while y < base_height + border_top + border_bottom:
                self.puzzle.image.paste(box_left, (0, y), box_left)
                self.puzzle.image.paste(box_right, (border_left + base_width, y), box_right)
                y += box_left.size[1]
            self.puzzle.image.paste(box_left_bottom, (0, base_height + border_top + border_bottom - box_left_bottom.size[1]), box_left_bottom)
            self.puzzle.image.paste(box_right_bottom, (base_width + border_left + border_right - box_right_bottom.size[0], base_height + border_top + border_bottom - box_right_bottom.size[1]), box_right_bottom)
            self.puzzle.image.paste(box_left_top, (0, 0), box_left_top)
            self.puzzle.image.paste(box_right_top, (base_width + border_left + border_right - box_right_top.size[0], 0), box_right_top)

class DesignIndexRustedMetal(DesignIndexCommonBlocks):
    def id(self): return "index-rusted-metal"
    def name(self): return self._("Rusted Metal")
    def preview(self): return "/st/constructor/design/gen/index-rusted-metal.jpg"

class DesignGameInterfaceTest(DesignGenerator):
    def group(self): return "gameinterface"
    def id(self): return "game-test"
    def name(self): return self._("Test")
    def preview(self): return "/st/constructor/design/gen/game-test.jpg"

class DesignGameInterfaceRustedMetal(DesignGenerator):
    def group(self): return "gameinterface"
    def id(self): return "game-rusted-metal"
    def name(self): return self._("Rusted Metal")
    def preview(self): return "/st/constructor/design/gen/game-rusted-metal.jpg"

class DesignMod(Module):
    def register(self):
        Module.register(self)
        self.rhook("design.response", self.response)
        self.rhook("design.parse", self.parse)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("design.get", self.get)
        self.rhook("design.prepare_button", self.prepare_button)

    def objclasses_list(self, objclasses):
        objclasses["Design"] = (Design, DesignList)

    def get(self, group):
        uuid = self.conf("%s.design" % group)
        if not uuid:
            return None
        return self.obj(Design, uuid)

    def child_modules(self):
        return [
            "mg.constructor.design.DesignAdmin",
        ]

    def parse(self, design, template, content, vars):
        if design and template in design.get("files"):
            template = self.httpfile("%s/%s" % (design.get("uri"), template))
        else:
            template = "game/%s" % template
        vars["design_root"] = design.get("uri") if design else None
        vars["content"] = content
        return self.call("web.parse_layout", template, vars)

    def response(self, design, template, content, vars):
        self.call("web.response", self.parse(design, template, content, vars))

    def prepare_button(self, design, target_filename, template, icon, over=None):
        """
        Return value:
           True - target_filename is available
           False - target_filename is not available and no way to generate
           None - error generating target_filename
        """
        if target_filename in design.get("files"):
            return True
        if not template in design.get("files"):
            return False
        with self.lock(["Design.%s" % design.uuid]):
            design.load()
            if target_filename in design.get("files"):
                return True
            # loading template
            template_uri = "%s/%s" % (design.get("uri"), template)
            try:
                template_data = self.download(template_uri)
            except DownloadError:
                self.error("Error downloading %s", template_uri)
                return None
            try:
                template_image = Image.open(cStringIO.StringIO(template_data))
                if template_image.load() is None:
                    self.error("Error parsing %s", template_image)
                    return None
            except IOError:
                self.error("Image %s format not recognized", template_uri)
                return None
            except OverflowError:
                self.error("Image %s format not recognized", template_uri)
                return None
            try:
                template_image.seek(1)
                self.error("Image %s is animated", template_uri)
                return None
            except EOFError:
                pass
            template_image.convert("RGBA")
            # loading icon
            icon_path = "%s/data/icons/%s" % (mg.__path__[0], icon)
            try:
                icon_image = Image.open(icon_path)
                if icon_image.load() is None:
                    self.error("Error parsing %s", icon_path)
                    return None
            except IOError:
                self.error("Image %s format not recognized", icon_path)
                return None
            except OverflowError:
                self.error("Image %s format not recognized", icon_path)
                return None
            # mastering image
#           self.debug("Loaded: %s and %s. Mastering image %s/%s", template_uri, icon_path, design.get("uri"), target_filename)
            template_w, template_h = template_image.size
            icon_w, icon_h = icon_image.size
            template_image.paste(icon_image, ((template_w - icon_w) / 2, (template_h - icon_h) / 2), icon_image)
            if over and over in design.get("files"):
                # loading overlay image
                over_uri = "%s/%s" % (design.get("uri"), over)
                try:
                    over_data = self.download(over_uri)
                except DownloadError:
                    self.error("Error downloading %s", over_uri)
                    return None
                try:
                    over_image = Image.open(cStringIO.StringIO(over_data))
                    if over_image.load() is None:
                        self.error("Error parsing %s", over_image)
                        return None
                except IOError:
                    self.error("Image %s format not recognized", over_uri)
                    return None
                except OverflowError:
                    self.error("Image %s format not recognized", over_uri)
                    return None
                try:
                    over_image.seek(1)
                    self.error("Image %s is animated", over_uri)
                    return None
                except EOFError:
                    pass
                over_image.convert("RGBA")
                over_w, over_h = over_image.size
                template_image.paste(over_image, ((template_w - over_w) / 2, (template_h - over_h) / 2), over_image)
            # uploading image
            stream = cStringIO.StringIO()
            template_image.save(stream, "PNG")
            try:
                self.call("cluster.static_put", "%s/%s" % (design.get("uri"), target_filename), "image/png", stream.getvalue())
            except IOError as e:
                self.error("Couldn't store %s/%s: %s", design.get("uri"), target_filename, e)
                return None
            except StaticUploadError as e:
                self.error("Couldn't store %s/%s: %s", design.get("uri"), target_filename, e)
                return None
            # storing updated design
            design.touch()
            design.get("files")[target_filename] = {"content-type": "image/png"}
            design.store()
            return True

class DesignAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("design-admin.editor", self.editor)
        self.rhook("design-admin.delete", self.delete)
        self.rhook("design-admin.headmenu", self.headmenu)
        self.rhook("permissions.list", self.permissions_list)

    def permissions_list(self, perms):
        perms.append({"id": "design", "name": self._("Design configuration")})

    def menu_root_index(self, menu):
        req = self.req()
        if req.has_access("design"):
            menu.append({"id": "design.index", "text": self._("Design"), "order": 110})

    def editor(self, group):
        self.call("admin.advice", {"title": self._("Preview feature"), "content": self._('Use "preview" feature to check your design before installing it to the project. Then press "Reload" several times to check design on arbitrary data.')}, {"title": self._("Multiple browsers"), "content": self._('Check your design in the most popular browsers.') + u' <a href="http://www.google.com/search?q={0}" target="_blank">{1}</a>.'.format(urlencode(self._("google///browser statistics")), self._("Find the most popular browsers"))})
        with self.lock(["DesignAdmin-%s" % group]):
            req = self.req()
            if req.args == "":
                installed = self.conf("%s.design" % group)
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
                    self.call("admin-%s.previews" % group, ent, previews)
                    if not len(previews):
                        previews.append({"filename": "index.html", "title": self._("preview")})
                    designs.append({
                        "uuid": ent.uuid,
                        "uploaded": re_remove_time.sub("", ent.get("uploaded")),
                        "title": htmlescape(title),
                        "filename": htmlescape(filename),
                        "previews": previews,
                        "installed": 1 if installed == ent.uuid else 0,
                    })
                vars = {
                    "group": group,
                    "UploadNewDesign": self._("Upload design package from your computer"),
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
                    "rename": self._("rename///ren"),
                    "SelectDesignTemplate": self._("Select from the list of templates"),
                    "installed": self._("installed"),
                }
                self.call("admin.response_template", "admin/design/list.html", vars)
            if req.args == "new":
                if req.ok():
                    self.call("web.upload_handler")
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
                self.call("admin.form", fields=fields, buttons=buttons, modules=["FileUploadField"])
            elif req.args == "gen":
                gens = []
                self.call("admin-%s.generators" % group, gens)
                vars = {
                    "Choose": self._("Choose any template you want. Then setup its parameters and you will get a personalised variant of the template."),
                    "group": group,
                }
                if len(gens):
                    vars["gens"] = [gen(self.app()).info() for gen in gens]
                self.call("admin.response_template", "admin/design/generators.html", vars)
            m = re.match(r'^gen/(.+)$', req.args)
            if m:
                id = m.group(1)
                gens = []
                self.call("admin-%s.generators" % group, gens)
                for gen in gens:
                    obj = gen(self.app())
                    if obj.id() == id and obj.group() == group:
                        if req.ok():
                            self.call("web.upload_handler")
                            errors = {}
                            obj.form_parse(errors)
                            if len(errors):
                                self.call("web.response_json_html", {"success": False, "errors": errors})
                            design = obj.load()
                            obj.process()
                            obj.store()
                            self.call("web.response_json_html", {"success": True, "redirect": "%s/design" % group})
                        fields = []
                        obj.form_fields(fields)
                        buttons = [
                            {"text": self._("Generate design template")}
                        ]
                        presets = obj.presets()
                        self.call("admin.response_js", "admin-form-presets", "FormPresets", {
                            "url": "/%s/%s/%s" % (req.group, req.hook, req.args),
                            "fields": fields,
                            "buttons": buttons,
                            "modules": ["FileUploadField"],
                            "presets": presets,
                            "upload": True,
                        })
                self.call("web.not_found")
            m = re.match(r'^([a-z]+)/([a-f0-9]{32})$', req.args)
            if m:
                cmd, uuid = m.group(1, 2)
                if cmd == "delete":
                    try:
                        design = self.obj(Design, uuid)
                    except ObjectNotFoundException:
                        pass
                    else:
                        if self.conf("%s.design" % group) != uuid:
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
                    try:
                        design = self.obj(Design, uuid)
                    except ObjectNotFoundException:
                        pass
                    else:
                        if self.conf("%s.design" % group) != uuid:
                            config = self.app().config_updater()
                            config.set("%s.design" % group, uuid)
                            config.store()
                    self.call("admin.redirect", "%s/design" % group)
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

    def headmenu(self, group, args):
        if args == "new":
            return [self._("New design"), "%s/design" % group]
        elif args == "gen":
            return [self._("Design templates"), "%s/design" % group]
        elif re_rename.match(args):
            return [self._("Renaming"), "%s/design" % group]
        elif re_generator.match(args):
            return [self._("Settings"), "%s/design/gen" % group]

class IndexPage(Module):
    def register(self):
        Module.register(self)

class IndexPageAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-indexpage.design", self.ext_design, priv="design")
        self.rhook("headmenu-admin-indexpage.design", self.headmenu_design)
        self.rhook("admin-indexpage.validate", self.validate)
        self.rhook("admin-indexpage.preview-data", self.preview_data)
        self.rhook("admin-indexpage.generators", self.generators)
        self.rhook("admin-game.recommended-actions", self.recommended_actions)

    def recommended_actions(self, actions):
        if not self.conf("indexpage.design"):
            actions.append({"icon": "/st/img/exclamation.png", "content": self._('Index page design of your game is not configured. Index page is the face of your game. It\'s the first that players see when they come. You can upload your own design or select one from the catalog. <hook:admin.link href="indexpage/design" title="Open configuration" />'), "order": 10})

    def headmenu_design(self, args):
        if args == "":
            return self._("Index page design")
        else:
            return self.call("design-admin.headmenu", "indexpage", args)

    def menu_design_index(self, menu):
        menu.append({"id": "indexpage/design", "text": self._("Index page"), "leaf": True, "order": 1})

    def ext_design(self):
        self.call("design-admin.editor", "indexpage")

    def validate(self, design, parsed_html, errors):
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
        for filename, parser in parsed_html.iteritems():
            if filename == "index.html":
                if not "/indexpage.js" in parser.scripts:
                    errors.append(self._('Your page must have HTML tag: %s') % htmlescape('<script type="text/javascript" src="http://www.%s/dyn-mg/indexpage.js"></script>'))
                if not "/indexpage.css" in parser.scripts:
                    errors.append(self._('Your page must have HTML tag: %s') % htmlescape('<link rel="stylesheet" href="http://www.%s/dyn-mg/indexpage.css" />'))
                loginform_ok = False
                for form in parser.forms:
                    if form["name"] == "loginform" and form["id"] == "loginform":
                        loginform_ok = True
                        if form["onsubmit"] != "return auth_login();":
                            errors.append(self._('Your loginform must contain onsubmit="return auth_login();"'))
                        email_ok = False
                        password_ok = False
                        for inp in form["inputs"]:
                            if inp["name"] == "email":
                                email_ok = True
                                if inp.get("id") != "email":
                                    errors.append(self._('Email input field must have id="email" and name="email"'))
                            if inp["name"] == "password":
                                password_ok = True
                                if inp.get("id") != "password":
                                    errors.append(self._('Password input field must have id="password" and name="password"'))
                        break
                if not loginform_ok:
                    errors.append(self._('Your page must have HTML form with id="loginform" and name="loginform"'))

    def preview_data(self, vars):
        demo_authors = [self._("Mike"), self._("Ivan Ivanov"), self._("John Smith"), self._("Lizard the killer"), self._("Cult of the dead cow")]
        vars["title"] = random.choice([self._("Some title"), self._("Very cool game")])
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
                    "more": "#" if random.random() < 0.5 else None
                })
            vars["news"][-1]["lst"] = True
        vars["htmlmeta"] = {
            "description": self._("This is a sample meta description"),
            "keywords": self._("online games, keyword 1, keyword 2"),
        }
        vars["counters"] = ""
        for i in range(0, random.randrange(0, 5)):
            vars["counters"] += ' <img src="/st/constructor/design/counter%d.gif" alt="" />' % random.randrange(0, 4)
        vars["year"] = "2099"
        vars["copyright"] = random.choice([self._("Joy Team, Author"), self._("Joy Team, Very Long Author Name Even So Long")])
        vars["links"] = random.sample([
            {
                "href": "#",
                "title": self._("Enter invisible"),
            } if random.random() < 0.5 else {
                "title": self._("Already invisible"),
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
                "onsubmit": "return auth_register()",
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
            } if random.random() < 0.5 else {
                "title": self._("Connection secured"),
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
        vars["main_host"] = self.app().inst.config["main_host"]

    def generators(self, gens):
        gens.append(DesignIndexBrokenStones)
        gens.append(DesignIndexRustedMetal)

class SocioInterface(ConstructorModule):
    def register(self):
        Module.register(self)
        self.rhook("forum.vars-index", self.forum_vars_index)
        self.rhook("forum.vars-category", self.forum_vars_category)
        self.rhook("forum.vars-topic", self.forum_vars_topic)
        self.rhook("forum.vars-tags", self.forum_vars_tags)
        self.rhook("ext-admin-sociointerface.templates", self.templates, priv="public")
        self.rhook("admin-game.recommended-actions", self.recommended_actions)
        self.rhook("forum.response", self.response, priority=10)
        self.rhook("forum.response_template", self.response_template, priority=10)

    def recommended_actions(self, actions):
        if not self.conf("sociointerface.design"):
            actions.append({"icon": "/st/img/exclamation.png", "content": self._('Socio interface design of your game is not configured. Socio interface is shown when forum, library or any other external interface is being accessed. You can upload your own design or select one from the catalog. <hook:admin.link href="sociointerface/design" title="Open configuration" />'), "order": 10})

    def templates(self):
        output = cStringIO.StringIO()
        zip = zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED)
        for filename in ["index.html", "category.html", "topic.html", "tags.html"]:
            zip.write("%s/templates/socio/%s" % (mg.__path__[0], filename), filename)
        zip.close()
        self.call("web.response", output.getvalue(), "application/zip")

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

    def response(self, content, vars):
        self.call("forum.setup-menu", vars)
        design = self.design("sociointerface")
        self.call("design.response", design, "index.html", content, vars)

    def response_template(self, template, vars):
        self.call("forum.setup-menu", vars)
        design = self.design("sociointerface")
        self.call("design.response", design, "index.html", self.call("web.parse_template", template, vars), vars)

class SocioInterfaceAdmin(Module):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-sociointerface.design", self.ext_design, priv="design")
        self.rhook("headmenu-admin-sociointerface.design", self.headmenu_design)
        self.rhook("admin-sociointerface.validate", self.validate)
        self.rhook("admin-sociointerface.previews", self.previews)
        self.rhook("admin-sociointerface.preview", self.preview)

    def headmenu_design(self, args):
        if args == "":
            return self._("Socio interface design")
        else:
            return self.call("design-admin.headmenu", "sociointerface", args)

    def menu_design_index(self, menu):
        menu.append({"id": "sociointerface/design", "text": self._("Socio interface"), "leaf": True, "order": 3})

    def ext_design(self):
        self.call("design-admin.editor", "sociointerface")

    def validate(self, design, parsed_html, errors):
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

    def previews(self, design, previews):
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
        vars["counters"] = ""
        for i in range(0, random.randrange(0, 5)):
            vars["counters"] += ' <img src="/st/constructor/design/counter%d.gif" alt="" />' % random.randrange(0, 4)
        if random.random() < 0.5:
            demo_messages = []
            demo_messages.extend(demo_subjects)
            vars["socio_message_top"] = random.choice(demo_messages)
        content = self.call("web.parse_template", "socio/%s" % filename, vars)
        self.call("design.response", design, "index.html", content, vars)

class GameInterface(Module):
    def register(self):
        Module.register(self)

class GameInterfaceAdmin(ConstructorModule):
    def register(self):
        Module.register(self)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-gameinterface.design", self.ext_design, priv="design")
        self.rhook("headmenu-admin-gameinterface.design", self.headmenu_design)
        self.rhook("admin-gameinterface.validate", self.validate)
        self.rhook("admin-gameinterface.preview-data", self.preview_data)
        self.rhook("advice-admin-gameinterface.design", self.gameinterface_advice)
        self.rhook("admin-gameinterface.generators", self.generators)
        self.rhook("admin-gameinterface.previews", self.previews)
        self.rhook("admin-gameinterface.preview", self.preview)
        self.rhook("admin-game.recommended-actions", self.recommended_actions)

    def recommended_actions(self, actions):
        if not self.conf("gameinterface.design"):
            actions.append({"icon": "/st/img/exclamation.png", "content": self._('Game interface design of your game is not configured. Game interface is a screen than player sees after entering the game. You can upload your own design or select one from the catalog. <hook:admin.link href="gameinterface/design" title="Open configuration" />'), "order": 10})

    def headmenu_design(self, args):
        if args == "":
            return self._("Game interface design")
        else:
            return self.call("design-admin.headmenu", "gameinterface", args)

    def menu_design_index(self, menu):
        menu.append({"id": "gameinterface/design", "text": self._("Game interface"), "leaf": True, "order": 2})

    def ext_design(self):
        self.call("design-admin.editor", "gameinterface")

    def validate(self, design, parsed_html, errors):
        for name in ["blocks.html", "interface.css", "game.css"]:
            if not name in design.get("files"):
                errors.append(self._("Game interface design package must contain %s file") % name)

    def preview_data(self, vars):
        pass

    def gameinterface_advice(self, args, advice):
        files = []
        files.append({"filename": "blocks.html", "description": self._("Game interface blocks")})
        files.append({"filename": "interface.css", "description": self._("Game interface CSS")})
        files.append({"filename": "game.css", "description": self._("Common game CSS (styles for character icons, level [5] markers etc). This file is included in every game page - index page, game interface, socio interface")})
        files.append({"filename": "external.html", "description": self._("External interface")})
        files.append({"filename": "cabinet.html", "description": self._("Cabinet interface (inside the external interface)")})
        files.append({"filename": "error.html", "description": self._("External error message (inside the external interface)")})
        files.append({"filename": "form.html", "description": self._("External form (inside the external interface)")})
        self.call("admin-gameinterface.design-files", files)
        files = "".join(["<li><strong>%s</strong>&nbsp;&mdash; %s</li>" % (f.get("filename"), f.get("description")) for f in files])
        advice.append({"title": self._("Required design files"), "content": self._("Here is a list of required files in your design with short descriptions: <ul>%s</ul>") % files})

    def generators(self, gens):
        gens.append(DesignGameInterfaceTest)
        gens.append(DesignGameInterfaceRustedMetal)

    def previews(self, design, previews):
        previews.append({"filename": "interface.html", "title": self._("Game interface")})
        previews.append({"filename": "cabinet.html", "title": self._("Cabinet")})
        previews.append({"filename": "error.html", "title": self._("Error")})
        previews.append({"filename": "form.html", "title": self._("Form")})

    def preview(self, design, filename):
        vars = {
            "title": self._("Demo page")
        }
        req = self.req()
        char = self.character(req.user())
        if filename == "interface.html":
            self.call("gameinterface.render", char, vars, design)
            self.call("gameinterface.gamejs", char, vars, design)
            self.call("gameinterface.blocks", char, vars, design)
            self.call("web.response", self.call("web.parse_template", "game/frameset.html", vars))
        elif filename == "cabinet.html" or filename == "error.html" or filename == "form.html":
            demo_users = [self._("Mike"), self._("Ivan Ivanov"), self._("John Smith"), self._("Lizard the killer"), self._("Crazy Warrior From Hell")]
            content = None
            if filename == "cabinet.html":
                self.call("gamecabinet.render", vars)
                if random.random() < 0.8:
                    lst = []
                    for i in range(1, random.randrange(1, 11)):
                        lst.append({"uuid": i, "name": random.choice(demo_users)})
                    vars["characters"] = lst
                if random.random() < 0.5:
                    vars["create"] = True
            elif filename == "error.html":
                content = random.choice([
                    self._("This is a short error message"),
                    self._("An error message is information displayed when an unexpected condition occurs, usually on a computer or other device. On modern operating systems with graphical user interfaces, error messages are often displayed using dialog boxes. Error messages are used when user intervention is required, to indicate that a desired operation has failed, or to relay important warnings (such as warning a computer user that they are almost out of hard disk space). Error messages are seen widely throughout computing, and are part of every operating system or computer hardware device. Proper design of error messages is an important topic in usability and other fields of humancomputer interaction."),
                ])
            elif filename == "form.html":
                form = self.call("web.form")
                demo_errors = [self._("Invalid value"), self._("Are you sure?"), self._("Something wrong"), self._("Something is completely wrong")]
                demo_descriptions = [self._("Enter your age"), self._("Specify your weight"), self._("What do you think about this?"), self._("Try to describe your choice")]
                demo_values = [self._("Some value"), self._("Some another value"), self._("Some strange value"), self._("Very important value"), self._("A simple value"), self._("A complex value")]
                demo_messages = [self._("Values you entered are not valid. Try again please"), self._("This is a very long message to tell user some important information about the form")]
                inlines = 0
                for i in range(0, random.randrange(2, 21)):
                    inline = (random.random() < 0.5) and (i > 0)
                    if inline:
                        inlines += 1
                        if inlines > 5:
                            inline = False
                            inlines = 0
                    else:
                        inlines = 0
                    if random.random() < 0.2:
                        form.error(i, random.choice(demo_errors))
                    if random.random() < 0.3:
                        form.select(random.choice(demo_descriptions), i, 0, random.sample([{"value": 1, "description": val} for val in demo_values], 3), inline=inline)
                    elif random.random() < 0.2:
                        form.checkbox(random.choice(demo_descriptions), i, 0, inline=inline)
                    elif random.random() < 0.3:
                        form.radio(random.choice(demo_descriptions), i, 0, 0, inline=inline)
                    else:
                        form.input(random.choice(demo_descriptions), i, random.choice(demo_values), inline=inline)
                if random.random() < 0.3:
                    form.textarea(random.choice(demo_descriptions), i, random.choice(demo_values))
                if random.random() < 0.3:
                    form.add_message_top(random.choice(demo_messages))
                if random.random() < 0.3:
                    form.add_message_bottom(random.choice(demo_messages))
                for i in range(0, random.randrange(1, 5)):
                    form.submit(None, None, random.choice(demo_values), inline=i>0)
                content = form.html()
            content = self.call("design.parse", design, filename, content, vars)
            self.call("design.response", design, "external.html", content, vars)
