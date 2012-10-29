from mg.constructor import *

class MarketingAdmin(ConstructorModule):
    def register(self):
        self.rhook("menu-admin-root.index", self.menu_root_index)

    def menu_root_index(self, menu):
        menu.append({"id": "marketing.index", "text": self._("Marketing"), "order": 40})

class MarketingStat(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-marketing.index", self.menu_marketing)
        self.rhook("ext-admin-marketing.users", self.admin_marketing_users, priv="marketing.users")
        self.rhook("headmenu-admin-marketing.users", self.headmenu_marketing_users)
        self.rhook("advice-admin-marketing.index", self.advice_marketing)

    def child_module(self):
        return ["mg.constructor.marketing.MarketingAdmin"]

    def advice_marketing(self, hook, args, advice):
        advice.append({"title": self._("Marketing documentation"), "content": self._('You can find detailed information on the marketing of online games in the <a href="//www.%s/doc/marketing" target="_blank">Marketing page</a> in the reference manual.') % self.main_host})

    def permissions_list(self, perms):
        perms.append({"id": "marketing.users", "name": self._("Marketing: statistics on users")})

    def menu_marketing(self, menu):
        req = self.req()
        if req.has_access("marketing.users"):
            menu.append({"id": "marketing/users", "text": self._("Statistics on the userbase"), "leaf": True, "order": 10})

    def headmenu_marketing_users(self, args):
        return self._("Statistics on the userbase")

    def admin_marketing_users(self):
        rows = []
        for row in self.sql_read.selectall_dict("select * from visits where app=? order by period desc limit 100", self.app().tag):
            rows.append([
                row["period"],
                row["peak_ccu"],
                row["new_users"],
                row["registered"],
                row["returned"],
                row["abandoned"],
                row["active"],
                row["dau"],
                row["wau"],
                row["mau"],
            ])
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Period"),
                        self._("CCU"),
                        self._("players///New"),
                        self._("players///Reg"),
                        self._("players///Ret"),
                        self._("players///Aban"),
                        self._("players///Act"),
                        self._("DAU"),
                        self._("WAU"),
                        self._("MAU"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

class GoogleAnalyticsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-marketing.index", self.menu_marketing)
        self.rhook("headmenu-admin-googleanalytics.config", self.headmenu_config)
        self.rhook("ext-admin-googleanalytics.config", self.admin_config, priv="googleanalytics.config")

    def child_module(self):
        return ["mg.constructor.marketing.MarketingAdmin"]

    def permissions_list(self, perms):
        perms.append({"id": "googleanalytics.config", "name": self._("Configuration of Google Analytics")})

    def menu_marketing(self, menu):
        req = self.req()
        if req.has_access("googleanalytics.config"):
            menu.append({"id": "googleanalytics/config", "text": self._("Google Analytics"), "leaf": True, "order": 20})

    def headmenu_config(self, args):
        return self._("Google Analytics configuration")

    def admin_config(self):
        req = self.req()
        if req.ok():
            reg_code = req.param("reg-code").strip()
            config = self.app().config_updater()
            config.set("googleanalytics.registration-code", reg_code or None)
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        fields = [
            {"name": "reg-code", "type": "textarea", "value": self.conf("googleanalytics.registration-code"), "label": self._("Google Analytics code for tracking registrations")},
        ]
        self.call("admin.form", fields=fields)

class GoogleAnalytics(ConstructorModule):
    def register(self):
        self.rhook("auth.render-activated-form", self.render_activated_form)

    def render_activated_form(self, user, form):
        reg_code = self.conf("googleanalytics.registration-code")
        if reg_code:
            form.add_message_bottom(reg_code)
