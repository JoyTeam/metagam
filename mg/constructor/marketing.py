from mg.constructor import *

class MarketingStat(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-marketing.index", self.menu_marketing)
        self.rhook("ext-admin-marketing.users", self.admin_marketing_users, priv="marketing.users")
        self.rhook("headmenu-admin-marketing.users", self.headmenu_marketing_users)
        self.rhook("advice-admin-marketing.index", self.advice_marketing)

    def advice_marketing(self, hook, args, advice):
        advice.append({"title": self._("Marketing documentation"), "content": self._('You can find detailed information on the marketing of online games in the <a href="//www.%s/doc/marketing" target="_blank">Marketing page</a> in the reference manual.') % self.app().inst.config["main_host"]})

    def permissions_list(self, perms):
        perms.append({"id": "marketing.users", "name": self._("Marketing: statistics on users")})

    def menu_root_index(self, menu):
        menu.append({"id": "marketing.index", "text": self._("Marketing"), "order": 40})

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
