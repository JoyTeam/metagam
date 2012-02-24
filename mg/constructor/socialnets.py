from mg.constructor import *
import re

re_tag = re.compile(r'\[(?:\/?[a-zA-Z]+|[A-Za-z]+|[A-Za-z]+=[^\[\]\r\n]+)\]')
max_description_length = 150

class SocialNets(ConstructorModule):
    def register(self):
        self.rhook("socialnets.render", self.render)
        self.rhook("forum.vars-topic", self.vars_topic)
        self.rhook("socio.setup-interface", self.setup_interface)

    def child_modules(self):
        return ["mg.constructor.socialnets.SocialNetsAdmin"]

    def render(self, vars, simple=False):
        if not vars.get("socialnets_processed"):
            vars["socialnets_processed"] = True
            # open graph
            vars["opengraph_image"] = self.call("project.logo")
            vars["opengraph_site_name"] = htmlescape(self.call("project.title"))
            vars["opengraph_type"] = "website"
            if "opengraph_url" not in vars:
                vars["opengraph_url"] = "http://%s/" % getattr(self.app(), "canonical_domain", "www.%s" % self.app().domain)
                vars["opengraph_title"] = vars["opengraph_site_name"]
                description = self.call("project.description")
                if len(description) > max_description_length:
                    description = description[0:max_description_length] + "..."
                vars["opengraph_description"] = htmlescape(description)
            if not vars.get("htmlmeta"):
                vars["htmlmeta"] = {"description": vars.get("opengraph_description")}
            elif not vars["htmlmeta"].get("description"):
                vars["htmlmeta"]["description"] = vars.get("opengraph_description")
            self.call("web.parse_template", "socialnets/opengraph-head.html", vars)
            # google plus
            google_plus = self.conf("socialnets.google-plus")
            if google_plus:
                vars["googleplus_id"] = google_plus
                if "googleplus_rendered" not in vars:
                    if simple:
                        vars["counters"] = utf2str(vars.get("counters", "")) + utf2str(self.call("web.parse_template", "socialnets/googleplus-plusone-simple.html", vars))
                    else:
                        vars["googleplus_size"] = "standard"
                        vars["counters"] = utf2str(vars.get("counters", "")) + utf2str(self.call("web.parse_template", "socialnets/googleplus-plusone.html", vars))
                self.call("web.parse_template", "socialnets/googleplus-head.html", vars)
            # facebook
            fb_app_id = self.conf("socialnets.facebook-app")
            if fb_app_id:
                vars["facebook_app_id"] = fb_app_id
                vars["html_attrs"] = utf2str(vars.get("html_attrs", "")) + ' xmlns:fb="http://ogp.me/ns/fb#" xmlns:og="http://ogp.me/ns#"'
                if not simple:
                    vars["counters"] = utf2str(vars.get("counters", "")) + utf2str(self.call("web.parse_template", "socialnets/facebook-api.html", vars))
                    if "facebook_rendered" not in vars:
                        vars["counters"] = utf2str(vars.get("counters", "")) + utf2str(self.call("web.parse_template", "socialnets/facebook-like.html", vars))

    def vars_topic(self, vars):
        vars["opengraph_url"] = "http://%s/forum/topic/%s" % (getattr(self.app(), "canonical_domain", "www.%s" % self.app().domain), vars["topic"]["uuid"])
        vars["opengraph_title"] = vars["topic"]["subject_html"]
        description = vars["topic"]["content"]
        if description:
            description = re_tag.sub('', description)
            description = htmlescape(description)
            if len(description) > max_description_length:
                description = description[0:max_description_length] + "..."
            vars["opengraph_description"] = description
        # google plus
        if self.conf("socialnets.google-plus"):
            vars["googleplus_size"] = "small"
            vars["googleplus_plusone"] = self.call("web.parse_template", "socialnets/googleplus-plusone.html", vars)
            vars["googleplus_rendered"] = True
        # facebook
        fb_app_id = self.conf("socialnets.facebook-app")
        if fb_app_id:
            vars["facebook_like"] = self.call("web.parse_template", "socialnets/facebook-like.html", vars)
            vars["facebook_rendered"] = True

    def setup_interface(self, vars):
        req = self.req()
        if req.group == "forum":
            self.call("socialnets.render", vars)

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

