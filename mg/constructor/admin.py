from mg import *
from mg.core.auth import UserPermissions, UserPermissionsList
from mg.core.queue import Schedule
from mg.core.cluster import DBTempFileList
from mg.constructor.players import DBPlayer, DBCharacter, DBCharacterForm, DBCharacterList
import mg.constructor.common
from mg.core.projects import Project, ProjectList
from uuid import uuid4
import mg
import time
import datetime
import re

re_wmauth_remove = re.compile(r'^([0-9a-f]+)/([0-9a-f]+)$')
re_code = re.compile(r'\[code\].*?\[\/code\]', re.DOTALL)
re_script_line = re.compile(r'^(  )+[a-z]+')
re_script_curly = re.compile(r'^(  )*}')
re_cassmaint_uri = re.compile(r'^([a-z0-9]{1,32})(?:|/(.+))$')

class DBUserWMID(CassandraObject):
    clsname = "UserWMID"
    indexes = {
        "all": [[], "added"],
        "user": [["user"]],
        "wmid": [["wmid"]],
    }

class DBUserWMIDList(CassandraObjectList):
    objcls = DBUserWMID

class ConstructorUtils(Module):
    def register(self):
        self.rhook("menu-admin-top.list", self.menu_admin_top_list, priority=-500)

    def menu_admin_top_list(self, topmenu):
        topmenu.append({"href": "//www.%s/forum" % self.main_host, "text": self._("Forum"), "tooltip": self._("Go to the Constructor forum")})
        topmenu.append({"href": "//www.%s/cabinet" % self.main_host, "text": self._("Cabinet"), "tooltip": self._("Cabinet")})

class Constructor(Module):
    def register(self):
        self.rdep(["mg.core.web.Web"])
        self.rdep(["mg.socio.Socio", "mg.socio.SocioAdmin", "mg.socio.Forum", "mg.admin.AdminInterface", "mg.socio.ForumAdmin",
            "mg.core.auth.Sessions", "mg.core.auth.Interface", "mg.core.cluster.Cluster",
            "mg.core.emails.Email", "mg.core.queue.Queue", "mg.core.cass_maintenance.CassandraMaintenance", "mg.admin.wizards.Wizards",
            "mg.core.projects.Projects",
            "mg.constructor.admin.ConstructorUtils", "mg.core.money.Money", "mg.core.money.MoneyAdmin", "mg.constructor.dashboard.ProjectDashboard",
            "mg.constructor.domains.Domains", "mg.constructor.domains.DomainsAdmin",
            "mg.core.money.Xsolla", "mg.core.money.XsollaAdmin",
            "mg.constructor.design.SocioInterface",
            "mg.constructor.interface.Dynamic",
            "mg.constructor.doc.Documentation", "mg.core.sites.Counters", "mg.core.sites.CountersAdmin", "mg.core.sites.SiteAdmin",
            "mg.core.realplexor.Realplexor", "mg.core.realplexor.RealplexorAdmin", "mg.core.emails.EmailAdmin",
            "mg.socio.telegrams.Telegrams",
            "mg.core.cluster.ClusterAdmin", "mg.constructor.auth.AuthAdmin", "mg.core.auth.Dossiers",
            "mg.socio.smiles.Smiles", "mg.socio.smiles.SmilesAdmin",
            "mg.core.emails.EmailSender", "mg.constructor.emails.EmailSenderAdmin",
            "mg.socio.restraints.Restraints", "mg.socio.restraints.RestraintsAdmin",
            "mg.core.modifiers.Modifiers",
            "mg.constructor.paidservices.PaidServices", "mg.constructor.paidservices.PaidServicesAdmin",
            "mg.socio.paidservices.PaidServices",
            "mg.core.dbexport.Export",
            "mg.core.money.WebMoney", "mg.core.money.WebMoneyAdmin",
            "mg.constructor.reqauction.ReqAuction",
            "mg.core.sites.Favicon", "mg.core.sites.FaviconAdmin",
            "mg.core.permissions_editor.Permissions", "mg.core.permissions_editor.PermissionsAdmin",
            "mg.constructor.marketing.MarketingAdmin",
            "mg.constructor.marketing.GoogleAnalytics", "mg.constructor.marketing.GoogleAnalyticsAdmin",
            "mg.constructor.socialnets.SocialNets", "mg.constructor.socialnets.SocialNetsAdmin",
        ])
        self.rhook("web.setup_design", self.web_setup_design)
        self.rhook("ext-index.index", self.index, priv="public")
        self.rhook("ext-cabinet.index", self.cabinet_index, priv="logged")
        self.rhook("auth.redirects", self.redirects)
        self.rhook("ext-cabinet.settings", self.cabinet_settings, priv="logged")
        self.rhook("ext-constructor.newgame", self.constructor_newgame, priv="logged")
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("projects.cleanup_inactive", self.cleanup_inactive)
        self.rhook("core.appfactory", self.appfactory)
        self.rhook("core.webservice", self.webservice)
        self.rhook("project.title", self.project_title)
        self.rhook("forum-admin.init-categories", self.forum_init_categories)
        self.rhook("projects.list", self.projects_list)
        self.rhook("projects.owned_by", self.projects_owned_by)
        self.rhook("project.cleanup", self.cleanup)
        self.rhook("project.missing", self.missing)
        self.rhook("web.universal_variables", self.universal_variables)
        self.rhook("auth.register-form", self.register_form)
        self.rhook("auth.password-changed", self.password_changed)
        self.rhook("ext-test.delay", self.test_delay, priv="disabled")
        self.rhook("indexpage.render", self.indexpage_render)
        self.rhook("telegrams.params", self.telegrams_params)
        self.rhook("email.sender", self.email_sender)
        self.rhook("ext-constructor.game", self.constructor_game, priv="logged")
        self.rhook("currencies.list", self.currencies_list, priority=100)
        self.rhook("xsolla.payment-args", self.payment_args)
        self.rhook("wmlogin.authorized", self.wmlogin_authorized)
        self.rhook("wmid.check", self.wmid_check)
        self.rhook("auth.user-auth-table", self.auth_user_table)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-wmauth.remove", self.wmauth_remove, priv="auth.wmid")
        self.rhook("security.list-roles", self.list_roles)
        self.rhook("security.users-roles", self.users_roles)
        self.rhook("ext-favicon.ico.index", self.favicon, priv="public")
        self.rhook("forum.reply-form", self.forum_reply_form)
        self.rhook("forum.topic-form", self.forum_topic_form)
        self.rhook("constructor.project-options-main", self.project_options)
        self.rhook("ext-admin-cassmaint.validate", self.admin_validate, priv="cassmaint.validate")
        self.rhook("headmenu-admin-cassmaint.validate", self.headmenu_validate)
        self.rhook("project.logo", self.project_logo)
        self.rhook("project.description", self.project_description)

    def project_logo(self):
        return "http://www.%s/st/constructor/logo/rounded.jpg" % self.main_host

    def project_description(self):
        return self._("MMO Constructor is a service allowing users to create their own online games")

    def project_options(self, project, options):
        if self.req().has_access("cassmaint.validate"):
            if project:
                options.append({"title": self._("Cassandra DB validation"), "value": '<hook:admin.link href="cassmaint/validate/%s" title="%s" />' % (project.uuid, self._("open"))})
            else:
                options.append({"title": self._("Cassandra DB validation"), "value": '<hook:admin.link href="cassmaint/validate/%s" title="%s" />' % (self.app().tag, self._("open"))})

    def forum_topic_form(self, topic, form, mode):
        if mode == "validate":
            self.forum_reply_form(form, "validate")
        elif mode == "form":
            self.forum_reply_form(form, "render")

    def headmenu_validate(self, args):
        m = re_cassmaint_uri.match(args)
        if m:
            app_tag, cmd = m.group(1, 2)
            if cmd is None:
                return ["Cassandra", "constructor/project-dashboard/%s" % app_tag]
            else:
                return [htmlescape(cmd), "cassmaint/validate/%s" % app_tag]

    def admin_validate(self):
        req = self.req()
        m = re_cassmaint_uri.match(req.args)
        if not m:
            self.call("web.not_found")
        app_tag, cmd = m.group(1, 2)
        app = self.app().inst.appfactory.get_by_tag(app_tag)
        if not app:
            self.call("web.not_found")
        objclasses = {}
        app.hooks.call("objclasses.list", objclasses)
        if cmd is not None:
            if cmd not in objclasses:
                self.call("admin.redirect", "cassmaint/validate/%s" % app_tag)
            cnt = self.call("cassmaint.validate", app, cls=cmd)
            if cnt is None:
                self.call("admin.response", self._("Validation failed"), {})
            else:
                config = app.config_updater()
                config.set("cassmaint.%s" % cmd, {"cnt": cnt["obj"], "performed": self.now()})
                config.store()
                self.call("admin.response", self._("Validated objects: {obj}, indexes: {index}<br />Missing index keys restored: {missing}<br />Orphaned index keys deleted: {orphaned}").format(**cnt), {})
        rows = []
        for cls in sorted(objclasses.keys()):
            perf = app.config.get("cassmaint.%s" % cls)
            if perf:
                perf = self._("{cnt} objects at {performed}").format(cnt=perf["cnt"], performed=self.call("l10n.time_local", perf["performed"]))
            rows.append([
                cls,
                perf,
                u'<hook:admin.link href="cassmaint/validate/%s/%s" title="%s" />' % (app_tag, cls, self._("validate")),
            ])
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Table name"),
                        self._("Last validation"),
                        self._("Validation"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def forum_reply_form(self, form, mode):
        req = self.req()
        if not req.param("save") and not req.param("publish"):
            return
        content = req.param("content")
        if re_code.search(content):
            return
        script_lines = 0
        curly_lines = 0
        has_script = False
        for line in content.split("\n"):
            if re_script_line.match(line):
                script_lines += 1
            if re_script_curly.match(line):
                curly_lines += 1
            if script_lines >= 1 and curly_lines >= 1:
                has_script = True
                break
        if not has_script:
            return
        if mode == "validate":
            if not req.param("ignore_code"):
                form.error("ignore_code", self._("It seems that your post contains script code without [code]...[/code] tags. Please select your script and press the 'CODE' button. It will make you code looking better. If you think this message is erroneous set the checkbox"), overwrite=False)
        elif mode == "render":
            form.checkbox(self._("Post as is, without [code][/code] tags"), "ignore_code", req.param("ignore_code"))

    def favicon(self):
        f = open("%s/data/logo/favicon.ico" % mg.__path__[0], "rb")
        data = f.read()
        f.close()
        self.call("web.response", data, "image/x-icon")

    def permissions_list(self, perms):
        perms.append({"id": "auth.wmid", "name": self._("Managing authorized WMIDs")})
        perms.append({"id": "cassmaint.validate", "name": self._("Validating and repairing cassandra database")})

    def payment_args(self, args, options):
        req = self.req()
        if req and req.user():
            user = self.obj(User, req.user())
            args["v1"] = user.get("name")
            args["email"] = user.get("email")

    def currencies_list(self, currencies):
        currencies["MM$"] = {
            "real": True,
            "code": "MM$",
            "description": self._("This currency is sold for real money"),
            "format": "%.2f",
            "image": "/st-mg/constructor/money/mmdollar-image.png",
            "icon": "/st-mg/constructor/money/mmdollar-icon.png",
            "real_price": 30.0,
            "real_currency": "RUB",
            "real_roubles": 30.0,
            "precision": 2,
            "name_plural": self._("MMO Constructor Dollars"),
            "name_local": self._("MMO Constructor Dollar/MMO Constructor Dollars"),
            "name_en": "MMO Constructor Dollar/MMO Constructor Dollars",
        }
        raise Hooks.Return()

    def test_delay(self):
        Tasklet.sleep(20)
        self.call("web.response", "ok\n")

    def register_form(self, form, mode):
        req = self.req()
        age18 = req.param("age18")
        if mode == "validate":
            if not age18:
                form.error("age18", self._("You must confirm you are of the full legal age"))
        elif mode == "render":
            form.checkbox(self._("I confirm I'm of the full legal age"), "age18", age18)

    def missing(self, tag):
        app = self.app().inst.appfactory.get_by_tag(tag)
        return app is None

    def forum_init_categories(self, cats):
        cats.append({"id": uuid4().hex, "topcat": self._("Constructor"), "title": self._("News"), "description": self._("News related to the Constructor"), "order": 10.0, "default_subscribe": True})
        cats.append({"id": uuid4().hex, "topcat": self._("Constructor"), "title": self._("Support"), "description": self._("Constructor technical support"), "order": 20.0})
        cats.append({"id": uuid4().hex, "topcat": self._("Game Development"), "title": self._("Developers club"), "description": self._("Any talks related to the game development"), "order": 30.0})

    def project_title(self):
        return "MMO Constructor"

    def appfactory(self):
        raise Hooks.Return(mg.constructor.common.ApplicationFactory(self.app().inst))

    def webservice(self):
        raise Hooks.Return(mg.constructor.common.ConstructorWebService(self.app().inst))

    def objclasses_list(self, objclasses):
        objclasses["Project"] = (Project, ProjectList)

    def projects_list(self, projects):
        projects.append({"uuid": "main"})
        list = self.app().inst.int_app.objlist(ProjectList, query_index="created")
        list.load(silent=True)
        projects.extend(list.data())

    def projects_owned_by(self, owner, projects):
        list = self.app().inst.int_app.objlist(ProjectList, query_index="owner", query_equal=owner)
        list.load(silent=True)
        projects.extend(list.data())

    def schedule(self, sched):
        sched.add("projects.cleanup_inactive", "10 1 * * *", priority=10)

    def cleanup_inactive(self):
        inst = self.app().inst
        projects = inst.int_app.objlist(ProjectList, query_index="inactive", query_equal="1", query_finish=self.now(-30 * 86400))
        for project in projects:
            self.info("Removing inactive project %s", project.uuid)
            self.call("project.cleanup", project.uuid)

    def web_setup_design(self, vars):
        req = self.req()
        topmenu = []
        cabmenu = []
        if req.group == "index" and req.hook == "index":
            vars["global_html"] = "constructor/index_global.html"
        elif req.group == "constructor" and req.hook == "newgame" or req.group == "webmoney":
            vars["global_html"] = "constructor/cabinet_global.html"
            cabmenu.append({"title": self._("Return to the Cabinet"), "href": "/cabinet", "image": "/st/constructor/cabinet/constructor.gif"})
        elif req.group == "socio" and req.hook == "image":
            pass
        elif req.group == "auth" or req.group == "email":
            if req.hook == "change" or req.hook == "email":
                vars["global_html"] = "constructor/cabinet_global.html"
                vars["ToTheMainPage"] = self._("To the main page")
                if req.hook == "change":
                    cabmenu.append({"title": self._("Password changing"), "left": True})
                elif req.hook == "email":
                    cabmenu.append({"title": self._("E-mail changing"), "left": True})
                cabmenu.append({"image": "/st/constructor/cabinet/settings.gif", "title": self._("Return to the Settings"), "href": "/cabinet/settings"})
            else:
                vars["global_html"] = "constructor/index_global.html"
        elif req.group == "reqauction":
            vars["title_suffix"] = " - %s" % self._("MMO Constructor Requests auction")
            vars["global_html"] = "constructor/socio_global.html"
            topmenu.append({"href": "/doc", "html": self._("Documentation")})
            topmenu.append({"href": "/forum", "html": self._("Forum")})
            if req.user():
                topmenu.append({"href": "/cabinet", "html": self._("Cabinet")})
            topmenu.append({"html": self._("MMO Constructor Requests auction"), "header": True, "left": True})
        elif req.group == "cabinet":
            vars["global_html"] = "constructor/cabinet_global.html"
            vars["ToTheMainPage"] = self._("To the main page")
            if req.hook == "settings":
                cabmenu.append({"title": self._("Settings"), "left": True})
                cabmenu.append({"title": self._("Return to the Cabinet"), "href": "/cabinet", "image": "/st/constructor/cabinet/constructor.gif"})
            elif req.hook == "index":
                user = self.obj(User, req.user())
                cabmenu.append({"title": self._("Documentation"), "href": "/doc", "left": True})
                cabmenu.append({"title": self._("Settings"), "href": "/cabinet/settings", "left": True})
                cabmenu.append({"title": self._("Requests auction"), "href": "/reqauction", "left": True})
                cabmenu.append({"title": self._("Forum"), "href": "/forum", "left": True})
                links = []
                self.call("telegrams.menu", links)
                for link in links:
                    cabmenu.append({"image": "/st/constructor/cabinet/telegrams%s.gif" % ("-act" if link["suffix"] else ""), "title": link["html"], "href": link["href"], "left": True, "suffix": link["suffix"]})
                cabmenu.append({"image": "/st/constructor/cabinet/logout.gif", "title": self._("Logout %s") % htmlescape(user.get("name")), "href": "/auth/logout"})
        elif req.group == "forum" or req.group == "socio":
            vars["title_suffix"] = " - %s" % self._("MMO Constructor Forum")
            redirect = req.param("redirect")
            redirect_param = True
            if redirect is None or redirect == "":
                redirect = req.uri()
                redirect_param = False
            redirect = urlencode(redirect)
            if req.hook == "settings":
                pass
            else:
                if req.group == "forum":
                    topmenu.append({"search": True, "button": self._("socio-top///Search")})
                if req.user():
                    topmenu.append({"href": "/forum/settings?redirect=%s" % redirect, "html": self._("Settings")})
                    links = []
                    self.call("telegrams.menu", links)
                    for link in links:
                        topmenu.append({"image": "/st/constructor/cabinet/telegrams%s.gif" % ("-act" if link["suffix"] else ""), "html": link["html"], "href": link["href"], "suffix": link["suffix"]})
                topmenu.append({"href": "/doc", "html": self._("Documentation")})
                if req.user():
                    topmenu.append({"href": "/socio/paid-services", "html": u'<img src="/st-mg/img/coins-16x16.png" alt="{premium}" title="{premium}" />'.format(premium=self._("Premium"))})
                if req.group != "forum":
                    topmenu.append({"href": "/forum", "html": self._("Forum")})
                if req.user():
                    topmenu.append({"href": "/reqauction", "html": self._("Auction")})
                    topmenu.append({"href": "/cabinet", "html": self._("Cabinet")})
                else:
                    topmenu.append({"href": "/auth/login?redirect=%s" % redirect, "html": self._("Log in")})
                    topmenu.append({"href": "/auth/register?redirect=%s" % redirect, "html": self._("Register")})
            if redirect_param:
                topmenu.append({"href": htmlescape(req.param("redirect")), "html": self._("Cancel")})
        elif req.group == "telegrams":
            vars["title_suffix"] = " - %s" % self._("MMO Constructor")
            topmenu.append({"href": "/doc", "html": self._("Documentation")})
            topmenu.append({"href": "/forum", "html": self._("Forum")})
            links = []
            self.call("telegrams.menu", links)
            for link in links:
                topmenu.append({"image": "/st/constructor/cabinet/telegrams%s.gif" % ("-act" if link["suffix"] else ""), "html": link["html"], "href": link["href"], "suffix": link["suffix"]})
            topmenu.append({"href": "/cabinet", "html": self._("Cabinet")})
        elif req.group == "doc":
            #vars["global_html"] = "constructor/socio_global.html"
            if req.user():
                topmenu.append({"href": "/reqauction", "html": self._("Request auction")})
            topmenu.append({"href": "/forum", "html": self._("Forum")})
            if req.user():
                topmenu.append({"href": "/cabinet", "html": self._("Cabinet")})
            topmenu.append({"html": self._("MMO Constructor Documentation"), "header": True, "left": True})
        elif req.group == "admin":
            vars["global_html"] = "constructor/admin_global.html"
        # Topmenu
        if len(topmenu):
            topmenu_left = []
            topmenu_right = []
            for ent in topmenu:
                if ent.get("left"):
                    topmenu_left.append(ent)
                else:
                    topmenu_right.append(ent)
            if len(topmenu_left):
                topmenu_left[-1]["lst"] = True
                vars["topmenu_left"] = topmenu_left
            if len(topmenu_right):
                topmenu_right[-1]["lst"] = True
                vars["topmenu_right"] = topmenu_right
        # Cabmenu
        if len(cabmenu):
            cabmenu_left = []
            cabmenu_right = []
            first_left = True
            first_right = True
            for ent in cabmenu:
                if ent.get("left"):
                    cabmenu_left.append(ent)
                else:
                    cabmenu_right.append(ent)
            if len(cabmenu_left):
                cabmenu_left[-1]["lst"] = True
                vars["cabmenu_left"] = cabmenu_left
            if len(cabmenu_right):
                cabmenu_right[-1]["lst"] = True
                vars["cabmenu_right"] = cabmenu_right

    def universal_variables(self, vars):
        vars["ConstructorTitle"] = self._("Browser-based Games Constructor")
        vars["ConstructorCopyright"] = self._("Copyright &copy; Joy Team, 2009-%s") % datetime.datetime.utcnow().strftime("%Y")
        vars["ConstructorSupport"] = '<a href="mailto:support@{0}">support@{0}</a>'.format(self.main_host)

    def redirects(self, tbl):
        tbl["login"] = "/cabinet"
        tbl["register"] = "/cabinet"
        tbl["change"] = "/cabinet/settings"

    def index(self):
        req = self.req()
        vars = {
            "title": self._("Constructor of browser-based online games"),
            "login": self._("log in"),
            "register": self._("register"),
            "forum": self._("forum"),
            "cabinet": self._("cabinet"),
            "logout": self._("log out"),
            "documentation": self._("documentation"),
        }
        if req.user():
            vars["logged"] = True
        self.call("socialnets.render", vars, simple=True)
        self.call("web.response_template", "constructor/index.html", vars)

    def cabinet_index(self):
        req = self.req()
        menu = []
        menu_projects = []
        vars = {
            "title": self._("Cabinet"),
        }
        # constructor admin
        perms = req.permissions()
        if len(perms):
            menu_projects.append({"href": "/admin", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Constructor administration")})
        columns = 4
        if not self.call("wmid.check", req.user()):
            vars["cabinet_wmbtn"] = {
                "href": self.call("wmlogin.url"),
                "title": self._("Verify your WMID")
            }
            lang = self.call("l10n.lang")
            if lang == "ru":
                url = "https://start.webmoney.ru/"
            else:
                url = "https://start.wmtransfer.com/"
            vars["cabinet_comment"] = self._('<p>To get an ability to write to the forum and to use the Request auction follow the steps given below:</p><ul><li><a href="{url}" target="_blank">Register in the WebMoney system</a> please</li><li>Press "Verify your WMID" button</li></ul><p><a href="/doc/wmcertificates"><strong>For what reason we require it</strong></a></p>').format(url=url)
            columns = 3
        # list of games
        projects = self.app().inst.int_app.objlist(ProjectList, query_index="owner", query_equal=req.user())
        projects.load(silent=True)
        if len(projects):
            for project in projects:
                title = project.get("title_short")
                if title is None:
                    title = self._("Untitled game")
                href = None
                if project.get("inactive"):
                    domain = "%s.%s" % (project.uuid, self.conf("constructor.projects-domain", self.main_host))
                    href = "http://%s/admin" % domain
                else:
                    href = "/constructor/game/%s" % project.uuid
                logo = project.get("logo")
                if logo is None:
                    logo = "/st/constructor/cabinet/untitled.gif"
                menu_projects.append({"href": href, "image": logo, "text": title})
                if len(menu_projects) >= columns:
                    menu.append(menu_projects)
                    menu_projects = []
        if len(menu_projects):
            menu.append(menu_projects)
        if menu:
            vars["cabinet_menu"] = menu
        vars["cabinet_leftbtn"] = {
            "href": "/constructor/newgame",
            "title": self._("Create a new game")
        }
        self.call("web.response_global", None, vars)

    def cabinet_settings(self):
        req = self.req()
        vars = {
            "title": self._("MMO Constructor Settings"),
            "cabinet_menu": [
                [
                    { "href": "/auth/change", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Change password") },
                    { "href": "/auth/email", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Change e-mail") },
                    { "href": "/forum/settings?redirect=/cabinet/settings", "image": "/st/constructor/cabinet/untitled.gif", "text": self._("Forum settings") },
                ],
            ],
        }
        wmids = self.wmid_check(req.user())
        if wmids:
            vars["cabinet_center"] = self._('Your verified WMID: {wmid}. <a href="{url}">Check again</a>').format(wmid=', '.join([self._('<strong>{wmid}</strong> (certificate: <strong>{certificate}</strong>)').format(wmid=wmid, certificate=self.cert_name(cert)) for wmid, cert in wmids.iteritems()]), url=self.call("wmlogin.url"))
        self.call("web.response_global", None, vars)

    def cert_name(self, cert):
        if cert >= 130:
            return self._("wmcert///personal")
        elif cert >= 120:
            return self._("wmcert///initial")
        elif cert >= 110:
            return self._("wmcert///formal")
        else:
            return self._("wmcert///pseudonymous")

    def constructor_newgame(self):
        req = self.req()
        if not self.call("wmid.check", req.user()) and False:
            vars = {
                "title": self._("Verified WMID required"),
                "text": self._("You haven't passed WMID verification yet"),
            }
            self.call("web.response_template", "constructor/setup/info.html", vars)
        # Registration on invitations
        invitations = self.conf("constructor.invitations")
        if invitations == 2:
            vars = {
                "title": self._("Registration closed"),
                "text": self.conf("constructor.invitations-text", self._("Open registration of new games is unavailable at the moment")),
            }
            self.call("web.response_template", "constructor/setup/info.html", vars)
        elif invitations:
            if not self.call("invitation.ok", req.user(), "newproject"):
                invitation = req.param("invitation")
                form = self.call("web.form")
                if req.param("ok"):
                    if not invitation or invitation == "":
                        form.error("invitation", self._("Enter invitation code"))
                    else:
                        err = self.call("invitation.enter", req.user(), "newproject", invitation)
                        if err:
                            form.error("invitation", err)
                    if not form.errors:
                        self.call("web.redirect", "/constructor/newgame")
                form.input(self._("Invitation code"), "invitation", invitation)
                form.submit(None, None, self._("Proceed"))
                form.add_message_top(self.conf("constructor.invitations-text", self._("Open registration of new games is unavailable at the moment")))
                vars = {
                    "title": self._("Invitation required"),
                }
                self.call("web.response_global", form.html(), vars)
        inst = self.app().inst
        # creating new project and application
        int_app = inst.int_app
        project = int_app.obj(Project)
        project.set("created", self.now())
        project.set("owner", req.user())
        project.set("inactive", 1)
        project.set("storage", 2)
        project.set("keyspace", "eden")
        project.store()
        # accessing new application
        app = inst.appfactory.get_by_tag(project.uuid)
        # setting up everything
        app.hooks.call("app.check")
        # creating setup wizard
        app.hooks.call("wizards.new", "mg.constructor.setup.ProjectSetupWizard")
        self.call("web.redirect", "http://%s/admin" % app.domain)

    def constructor_game(self):
        req = self.req()
        try:
            project = self.int_app().obj(Project, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        if project.get("owner") != req.user():
            self.call("web.forbidden")
        app = self.app().inst.appfactory.get_by_tag(project.uuid)
        domain = project.get("domain")
        if domain is None:
            domain = "%s.%s" % (project.uuid, self.conf("constructor.projects-domain", self.main_host))
        else:
            domain = "www.%s" % domain
        admins = app.objlist(DBCharacterList, query_index="admin", query_equal="1")
        if not len(admins):
            self.call("web.redirect", "http://%s" % domain)
        admin = admins[0]
        # restoring admin rights
        perms = app.hooks.call("auth.permissions", admin.uuid)
        if not perms.get("project.admin"):
            self.info("Restoring admin permissions for user %s", admin.uuid)
            app.hooks.call("auth.grant-permission", admin.uuid, "project.admin")
        # logging in
        autologin = app.hooks.call("auth.autologin", admin.uuid)
        self.call("web.redirect", "http://%s/auth/autologin/%s" % (domain, autologin))

    def cleanup(self, tag):
        inst = self.app().inst
        int_app = inst.int_app
        app = inst.appfactory.get_by_tag(tag)
        int_app.sql_write.do("delete from queue_tasks where app=?", tag)
        sched = int_app.obj(Schedule, tag, silent=True)
        sched.remove()
        project = int_app.obj(Project, tag, silent=True)
        project.remove()
        if app is not None:
            sessions = app.objlist(SessionList, query_index="valid_till")
            sessions.remove()
            users = app.objlist(UserList, query_index="created")
            users.remove()
            perms = app.objlist(UserPermissionsList, users.uuids())
            perms.remove()
            config = app.objlist(DBConfigGroupList, query_index="all")
            config.remove()
            hook_modules = app.objlist(DBHookGroupModulesList, query_index="all")
            hook_modules.remove()
            wizards = app.objlist(WizardConfigList, query_index="all")
            wizards.remove()
        temp_files = int_app.objlist(DBTempFileList, query_index="app", query_equal=tag)
        temp_files.load(silent=True)
        for file in temp_files:
            file.delete()
        temp_files.remove()

    def password_changed(self, user, password):
        self.info("Changed password of user %s", user.uuid)
        projects = self.app().inst.int_app.objlist(ProjectList, query_index="owner", query_equal=user.uuid)
        projects.load(silent=True)
        for project in projects:
            app = self.app().inst.appfactory.get_by_tag(project.uuid)
            users = app.objlist(UserList, query_index="name", query_equal=user.get("name"))
            users.load(silent=True)
            for u in users:
                self.info("Replicated password to the user %s in the project %s", u.uuid, project.uuid)
                u.set("salt", user.get("salt"))
                u.set("pass_reminder", user.get("pass_reminder"))
                u.set("pass_hash", user.get("pass_hash"))
                u.store()

    def indexpage_render(self, vars):
        fields = [
            {"code": "name", "prompt": self._("Enter your name, please"), "type": 0},
            {"code": "sex", "prompt": self._("What\\'s your sex"), "type": 1, "values": [[0, "Male"], [1, "Female", True]]},
            {"code": "motto", "prompt": self._("This is a very long text asking you to enter your motto. So be so kind entering your motto"), "type": 2},
            {"code": "password", "prompt": self._("Enter your password")},
        ]
        vars["register_fields"] = fields

    def telegrams_params(self, params):
        params["menu_title"] = self._("telegrams menu///Post")
        params["page_title"] = self._("Messages")
        params["last_telegram"] = self._("Last message")
        params["all_telegrams"] = self._("All messages")
        params["send_telegram"] = self._("Send a new message")
        params["text"] = self._("Message text")
        params["system_name"] = self._("MMO Constructor")
        params["telegrams_with"] = self._("Correspondence with {0}")

    def email_sender(self, params):
        params["email"] = "robot@mmoconstructor.ru"
        params["name"] = self._("MMO Constructor")
        params["prefix"] = "[mmo] "
        params["signature"] = self._("MMO Constructor - http://www.mmoconstructor.ru - constructor of browser-based online games")

    def wmlogin_authorized(self, authtype, remote_addr, wmid):
        req = self.req()
        with self.lock(["WMLogin.%s" % req.user(), "WMLogin.%s" % wmid]):
            self.debug("User %s uses WMID %s", req.user(), wmid)
            wmids = self.wmid_check(req.user())
            self.debug("Authorized WMIDS are: %s", wmids)
            if wmids and wmid not in wmids:
                vars = {
                    "title": self._("WMID verified already"),
                    "text": self._("You have verified another WMID already: %s") % (', '.join(wmids)),
                }
                self.call("web.response_template", "constructor/setup/info.html", vars)
            else:
                cert = self.call("wmcert.get", wmid)
                self.debug("Certificate of %s is %s", wmid, cert)
                if cert < 110:
                    vars = {
                        "title": self._("WMID not verified"),
                        "text": self._('We have ensured your WMID is <strong>{wmid}</strong>. But to our regret you has not even formal certificate. Please <a href="https://passport.wmtransfer.com/asp/aProcess.asp">get the formal certificate</a> (data are not verified by notaries or the center\'s legal department) and retry WMID verification').format(wmid=wmid, cert=self.cert_name(cert)),
                    }
                    self.call("web.response_template", "constructor/setup/info.html", vars)
                if not wmids or wmid not in wmids:
                    lst = self.objlist(DBUserWMIDList, query_index="wmid", query_equal=wmid)
                    lst.load()
                    if len(lst):
                        user = self.obj(User, lst[0].get("user"))
                        vars = {
                            "title": self._("WMID is assigned to another user"),
                            "text": self._("This WMID is assigned already to the user <strong>%s</strong>. You can't assign one WMID to several accounts") % htmlescape(user.get("name")),
                        }
                        self.call("web.response_template", "constructor/setup/info.html", vars)
                    obj = self.obj(DBUserWMID)
                    obj.set("added", self.now())
                    obj.set("user", req.user())
                    obj.set("wmid", wmid)
                    obj.set("cert", cert)
                    obj.set("authtype", authtype)
                    obj.set("ip", remote_addr)
                    obj.store()
                elif cert > wmids[wmid]:
                    lst = self.objlist(DBUserWMIDList, query_index="wmid", query_equal=wmid)
                    lst.load()
                    for ent in lst:
                        ent.set("cert", cert)
                        ent.store()
                vars = {
                    "title": self._("WMID verified"),
                    "text": self._("We have verified your WMID <strong>{wmid}</strong> successfully. Certificate level: <strong>{cert}>/strong>").format(wmid=wmid, cert=self.cert_name(cert)),
                }
                self.call("web.response_template", "constructor/setup/info.html", vars)

    def wmid_check(self, user_uuid):
        lst = self.objlist(DBUserWMIDList, query_index="user", query_equal=user_uuid)
        if not len(lst):
            return None
        lst.load()
        return dict([(ent.get("wmid"), ent.get("cert")) for ent in lst])

    def auth_user_table(self, user, tbl):
        req = self.req()
        if req.has_access("auth.wmid"):
            wmids = self.wmid_check(user.uuid)
            tbl["rows"].append([self._("Authorized WMID"), ', '.join([u'<strong>{wmid}</strong> ({cert}) &mdash; <hook:admin.link href="wmauth/remove/{user}/{wmid}" title="{remove}" confirm="{confirm}" />'.format(cert=self._("wm///certificate: %s") % self.cert_name(cert), wmid=wmid, user=user.uuid, remove=self._("remove"), confirm=self._("Are you sure want to delete this WMID?")) for wmid, cert in wmids.iteritems()]) if wmids else self._("none")])

    def wmauth_remove(self):
        req = self.req()
        m = re_wmauth_remove.match(req.args)
        if not m:
            self.call("web.not_found")
        user_uuid, wmid = m.group(1, 2)
        lst = self.objlist(DBUserWMIDList, query_index="user", query_equal=user_uuid)
        lst.load()
        for ent in lst:
            if ent.get("wmid") == wmid:
                ent.remove()
        self.call("admin.redirect", "auth/user-dashboard/%s" % user_uuid, {"active_tab": "auth"})

    def list_roles(self, roles):
        roles.append(("wmid", self._("Authorized WMID")))
        roles.append(("nowmid", self._("Not authorized WMID")))

    def users_roles(self, users, roles):
        authorized = set()
        lst = self.objlist(DBUserWMIDList, query_index="user", query_equal=users)
        lst.load()
        for ent in lst:
            authorized.add(ent.get("user"))
        for user in users:
            role = "wmid" if user in authorized else "nowmid"
            try:
                roles[user].append(role)
            except KeyError:
                roles[user] = [rol]
