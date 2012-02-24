from mg.constructor import *
import re

re_tag = re.compile(r'\[(?:\/?[a-zA-Z]+|[A-Za-z]+|[A-Za-z]+=[^\[\]\r\n]+)\]')

class SocialNets(ConstructorModule):
    def register(self):
        self.rhook("web.setup_design", self.web_setup_design)
        self.rhook("socio.setup-interface", self.socio_setup_interface)
        self.rhook("forum.vars-topic", self.vars_topic)

    def child_modules(self):
        return ["mg.constructor.socialnets.SocialNetsAdmin"]

    def web_setup_design(self, vars):
        google_plus = self.conf("socialnets.google-plus")
        if google_plus:
            vars["googleplus_id"] = google_plus
            self.call("web.parse_template", "socialnets/googleplus-publisher.html", vars)

    def socio_setup_interface(self, vars):
        # google plus
        if self.conf("socialnets.google-plus"):
            self.call("web.parse_template", "socialnets/googleplus-script.html", vars)
        # facebook
        fb_app_id = self.conf("socialnets.facebook-app")
        if fb_app_id:
            html_attrs = ' xmlns:fb="http://ogp.me/ns/fb#" xmlns:og="http://ogp.me/ns#"'
            vars["facebook_app_id"] = fb_app_id
            try:
                vars["html_attrs"] += html_attrs
            except KeyError:
                vars["html_attrs"] = html_attrs
            self.call("web.before_content", self.call("web.parse_template", "socialnets/facebook-api.html", vars), vars)

    def vars_topic(self, vars):
        url = "http://%s/forum/topic/%s" % (getattr(self.app(), "canonical_domain", "www.%s" % self.app().domain), vars["topic"]["uuid"])
        title = vars["topic"]["subject_html"]
        image = self.call("project.logo")
        if image and image.startswith("//"):
            image = "http:" + image
        description = vars["topic"]["content"]
        if description:
            description = re_tag.sub('', description)
            description = htmlescape(description)
        # google plus
        if self.conf("socialnets.google-plus"):
            vars["googleplus"] = {
                "url": url,
                "title": title,
                "image": image,
                "description": description,
            }
            vars["googleplus_plusone"] = self.call("web.parse_template", "socialnets/googleplus-plusone.html", vars)
            html_attrs = ' itemscope itemtype="http://schema.org/Article"'
            try:
                vars["html_attrs"] += html_attrs
            except KeyError:
                vars["html_attrs"] = html_attrs
        # facebook
        fb_app_id = self.conf("socialnets.facebook-app")
        if fb_app_id:
            vars["facebook"] = {
                "url": url,
                "title": title,
                "image": image,
                "site_name": htmlescape(self.call("project.title")),
                "description": description,
            }
            vars["facebook"]["app_id"] = fb_app_id
            vars["facebook_like"] = self.call("web.parse_template", "socialnets/facebook-like.html", vars)

class SocialNetsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-site.index", self.menu_site)
        self.rhook("headmenu-admin-site.socialnets", self.headmenu_socialnets)
        self.rhook("ext-admin-site.socialnets", self.admin_socialnets, priv="site.socialnets")
        self.rhook("advice-admin-site.socialnets", self.advice_socialnets)

    def advice_socialnets(self, args, advice):
        advice.append({"title": self._("Social networks documentation"), "content": self._('You can find detailed information on the social networks interconnection in the <a href="//www.%s/doc/socialnets" target="_blank">Social networks page</a> in the reference manual.') % self.app().inst.config["main_host"]})

    def permissions_list(self, perms):
        perms.append({"id": "site.socialnets", "name": self._("Interoperation with social networks")})

    def menu_site(self, menu):
        req = self.req()
        if req.has_access("site.socialnets"):
            menu.append({"id": "site/socialnets", "text": self._("Social networks"), "leaf": True, "order": 10})

    def headmenu_socialnets(self, args):
        return self._("Interoperation with social networks")

    def admin_socialnets(self):
        req = self.req()
        if req.ok():
            config = self.app().config_updater()
            config.set("socialnets.google-plus", req.param("google-plus").strip() or None)
            config.set("socialnets.facebook-app", req.param("facebook-app").strip() or None)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        fields = [
            {"name": "google-plus", "value": self.conf("socialnets.google-plus"), "label": self._("Google+ circle identifier")},
            {"name": "facebook-app", "value": self.conf("socialnets.facebook-app"), "label": self._("Facebook application identifier")},
        ]
        self.call("admin.form", fields=fields)

