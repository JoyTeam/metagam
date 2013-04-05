import mg
from mg.core.tools import *
from uuid import uuid4
import re
import json

re_del = re.compile(r'^del/(.+)$')

class DBForumRulesAgreement(mg.CassandraObject):
    clsname = "ForumRulesAgreement"

class ForumRules(mg.Module):
    def register(self):
        self.rhook("forum.vars-category", self.vars_category)
        self.rhook("ext-forum.rules", self.rules, priv="public")
        self.rhook("forum.rules-agreement", self.rules_agreement)

    def child_modules(self):
        return ["mg.socio.rules.ForumRulesAdmin"]

    def vars_category(self, vars):
        cat = vars.get("category")
        if not cat:
            return
        # get list of rules
        rules = []
        for rule in self.conf("forum.rules", []):
            if rule["all_categories"] or rule.get("cat-%s" % cat["id"]):
                rules.append({
                    "text": htmlescape(rule["text"])
                })
        # show rules
        if rules:
            if cat.get("rules_show_above"):
                vars["rules_above_title"] = self._("Rules for this category")
                vars["rules_above"] = rules
            else:
                vars["menu"].insert(0, {
                    "href": "/forum/rules/%s" % cat["id"],
                    "html": self._("Rules for this category"),
                    "right": True,
                })

    def rules(self):
        req = self.req()
        cat = self.call("forum.category", req.args)
        if cat is None:
            self.call("web.not_found")
        # get list of rules
        rules = []
        for rule in self.conf("forum.rules", []):
            if rule["all_categories"] or rule.get("cat-%s" % cat["id"]):
                rules.append({
                    "text": htmlescape(rule["text"])
                })
        # show rules
        vars = {}
        vars["rules"] = rules
        vars["title"] = self._("Forum rules for category '%s'") % cat["title"]
        vars["menu"] = [
            { "href": "/forum", "html": self._("Forum categories") },
            { "href": "/forum/cat/%s" % cat["id"], "html": cat["title"] },
            { "html": self._("Rules for this category") },
        ]
        self.call("socio.response_template", "rules.html", vars)

    def rules_agreement(self, cat, form):
        req = self.req()
        user = req.user()
        if not user:
            return
        # check whether the user has already accepted the rules
        agreement = self.obj(DBForumRulesAgreement, user, silent=True)
        rules = []
        for rule in self.conf("forum.rules", []):
            if rule.get("all_categories") or rule.get("cat-%s" % cat["id"]):
                if rule.get("exam") and agreement.get("rule-%s" % rule["uuid"], 0) < rule.get("version", 1):
                    rules.append(rule)
        if not rules:
            return
        if agreement.get("cooldown") and self.now() < agreement.get("cooldown"):
            return self._("You have failed the exam unfortunately. Next attempt can be made at %s") % self.call("l10n.time_local", agreement.get("cooldown"))
        # check exam result
        if req.param("passed"):
            for rule in rules:
                agreement.set("rule-%s" % rule["uuid"], rule.get("version", 1))
            agreement.store()
            return
        if req.param("failed"):
            agreement.set("cooldown", self.now(3600))
            agreement.store()
            return self._("You have failed the exam unfortunately. You can try again in an hour")
        # preserve form data
        for key, values in req.param_dict().iteritems():
            for val in values:
                form.hidden(str2unicode(key), str2unicode(val))
        # render rules
        vars = {
            "title": self._("Forum rules agreement"),
            "note": self._("Your message was saved and it will be posted after you pass the exam on forum rules knowledge successfully. Don't close your browser window."),
            "rules": json.dumps(rules),
            "form": form.html(),
        }
        self.call("socio.response_template", "rules-exam.html", vars)

class ForumRulesAdmin(mg.Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-forum.index", self.menu_forum_index)
        self.rhook("ext-admin-forum.rules", self.admin_rules, priv="forum.rules")
        self.rhook("headmenu-admin-forum.rules", self.headmenu_rules)
        self.rhook("admin-forum.category-form", self.category_form)
        self.rhook("admin-forum.category-validate", self.category_validate)
        self.rhook("admin-forum.category-store", self.category_store)
        self.rhook("admin-sociointerface.design-files", self.design_files)
        self.rhook("objclasses.list", self.objclasses_list)

    def objclasses_list(self, objclasses):
        objclasses["ForumRulesAgreement"] = (ForumRulesAgreement, None)

    def design_files(self, files):
        files.append({"filename": "rules.html", "description": self._("Forum category rules"), "doc": "/doc/design/forum"})

    def permissions_list(self, perms):
        perms.append({"id": "forum.rules", "name": self._("Forum rules editor")})

    def menu_forum_index(self, menu):
        req = self.req()
        if req.has_access("forum.rules"):
            menu.append({ "id": "forum/rules", "text": self._("Forum rules"), "leaf": True, "order": 30})

    def headmenu_rules(self, args):
        if args == "new":
            return [self._("New rule"), "forum/rules"]
        elif args:
            return [self._("Rule editor"), "forum/rules"]
        return self._("Forum rules")

    def admin_rules(self):
        req = self.req();
        rules = self.conf("forum.rules", [])
        if req.args:
            m = re_del.match(req.args)
            if m:
                uuid = m.group(1)
                rules = [r for r in rules if r["uuid"] != uuid]
                config = self.app().config_updater()
                config.set("forum.rules", rules)
                config.store()
                self.call("admin.redirect", "forum/rules")
            if req.args == "new":
                rule = {}
                order = None
                for r in rules:
                    if order is None or r["order"] > order:
                        order = r["order"]
                rule["order"] = order + 10.0 if order is not None else 0.0
            else:
                rule = None
                for r in rules:
                    if r["uuid"] == req.args:
                        rule = r
                        break
                if rule is None:
                    self.call("admin.redirect", "forum/rules")
            categories = self.call("forum.categories") or []
            if req.ok():
                errors = {}
                new_rule = {}
                if req.args == "new":
                    new_rule["uuid"] = uuid4().hex
                    new_rule["version"] = 1
                else:
                    new_rule["uuid"] = rule["uuid"]
                    new_rule["version"] = rule.get("version", 1)
                # version
                if req.param("increment"):
                    new_rule["version"] += 1
                # order
                new_rule["order"] = floatz(req.param("order"))
                # text
                text = req.param("text").strip()
                if not text:
                    errors["text"] = self._("This field is mandatory")
                else:
                    new_rule["text"] = text
                # exam
                exam = True if req.param("exam") else False
                new_rule["exam"] = exam
                if exam:
                    # question
                    question = req.param("question").strip()
                    if not question:
                        errors["question"] = self._("This field is mandatory")
                    else:
                        new_rule["question"] = question
                    # correct_answer
                    correct_answer = req.param("correct_answer").strip()
                    if not correct_answer:
                        errors["correct_answer"] = self._("This field is mandatory")
                    else:
                        new_rule["correct_answer"] = correct_answer
                    # incorrect_answers
                    incorrect_answers = [a.strip() for a in req.param("incorrect_answers").split(";") if a.strip()]
                    if not incorrect_answers:
                        errors["incorrect_answers"] = self._("This field is mandatory")
                    else:
                        new_rule["incorrect_answers"] = incorrect_answers
                # all_categories
                all_categories = True if req.param("all_categories") else False
                new_rule["all_categories"] = all_categories
                if not all_categories:
                    for cat in categories:
                        if req.param("cat-%s" % cat["id"]):
                            new_rule["cat-%s" % cat["id"]] = True
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # store
                rules = [r for r in rules if r["uuid"] != new_rule["uuid"]]
                rules.append(new_rule)
                rules.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
                config = self.app().config_updater()
                config.set("forum.rules", rules)
                config.store()
                self.call("admin.redirect", "forum/rules")
            # render form
            fields = [
                {"name": "order", "label": self._("Sorting order"), "value": rule.get("order")},
                {"name": "text", "type": "textarea", "label": self._("Rule text (for the list if forum rules)"), "value": rule.get("text")},
                {"name": "exam", "type": "checkbox", "label": self._("Exam question"), "checked": rule.get("exam")},
                {"name": "question", "type": "textarea", "label": self._("Question for the exam"), "value": rule.get("question"), "condition": "[exam]"},
                {"name": "correct_answer", "label": self._("Correct answer"), "value": rule.get("correct_answer"), "condition": "[exam]"},
                {"name": "incorrect_answers", "label": self._("Incorrect answers (semicolon separated)"), "value": u'; '.join(rule.get("incorrect_answers", [])), "condition": "[exam]"},
                {"name": "all_categories", "label": self._("This rule is shown in all forum categories"), "type": "checkbox", "checked": rule.get("all_categories", True)},
            ]
            for cat in categories:
                fields.append({"name": "cat-%s" % cat["id"], "label": cat["title"], "type": "checkbox", "checked": rule.get("cat-%s" % cat["id"]), "condition": "![all_categories]"})
            if req.args != "new":
                fields.append({"name": "increment", "label": self._("Require everybody to accept this rule again"), "type": "checkbox", "condition": "[exam]"})
            self.call("admin.form", fields=fields)
        # render list
        rows = []
        for rule in rules:
            rows.append([
                htmlescape(rule["text"]),
                rule["order"],
                u'<hook:admin.link href="forum/rules/%s" title="%s" />' % (rule["uuid"], self._("edit")),
                u'<hook:admin.link href="forum/rules/del/%s" title="%s" confirm="%s" />' % (rule["uuid"], self._("delete"), self._("Are you sure want to delete this rule?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "forum/rules/new",
                            "text": self._("New rule"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Rule text"),
                        self._("Sorting order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def category_form(self, cat, fields):
        fields.extend([
            {"type": "header", "html": self._("Forum rules")},
            {"name": "rules_show_above", "type": "checkbox", "label": self._("Show forum rules above the list of topics"), "checked": cat.get("rules_show_above")},
        ])

    def category_validate(self, values, errors):
        req = self.req()
        values["rules_show_above"] = True if req.param("rules_show_above") else False

    def category_store(self, values, cat):
        cat["rules_show_above"] = values["rules_show_above"]
