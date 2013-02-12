import mg.constructor
from mg.constructor.design import DesignGenerator
from mg.core.tools import *
import re
import random

re_design_url = re.compile('^[a-z0-9_]+/(.+)$', re.IGNORECASE)

class DesignCombatCommonBlocks(DesignGenerator):
    def group(self):
        return "combatinterface"

    def generate_files(self):
        vars = {
            "tpl": self.id(),
            "lang": self.call("l10n.lang"),
        }
        data = self.call("web.parse_template", "combatinterface/common-blocks.html", vars)
        self.add_file("global.html", "text/html", data)
        vars = {
            "tpl": self.id(),
            "lang": self.call("l10n.lang"),
        }
        self.add_file("main.css", "text/css", self.call("web.parse_template", "combatinterface/common-blocks.css", vars))

class DesignCombatRustedMetal(DesignCombatCommonBlocks):
    def id(self): return "combat-rusted-metal"
    def name(self): return self._("Rusted Metal")
    def preview(self): return "/st/constructor/design/gen/combat-rusted-metal.jpg"

def design_class_wrapper(cls, tp):
    class DesignClass(cls):
        def group(self):
            return "combatinterface-%s" % tp
    return DesignClass

class CombatInterface(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("forum.vars-log", self.forum_vars_log)
        self.rhook("combat.parse", self.parse, priority=10)
        self.rhook("combat.response", self.response, priority=10)
        self.rhook("combat.response_template", self.response_template, priority=10)
        self.rhook("combat.response_simple", self.response_simple, priority=10)
        self.rhook("combat.response_simple_template", self.response_simple_template, priority=10)

    def forum_vars_log(self, vars):
        vars["title"] = self._("Combat log")

    def parse(self, template, vars):
        self.call("combat.setup-interface", vars)
        design = self.design("combatinterface")
        return self.call("design.parse", design, template, None, vars, "combat")

    def response(self, content, vars):
        self.call("combat.setup-interface", vars)
        design = self.design("combatinterface")
        self.call("design.response", design, "global.html", content, vars, "combat")

    def response_template(self, template, vars):
        self.call("combat.setup-interface", vars)
        design = self.design("combatinterface")
        content = self.call("design.parse", design, template, None, vars, "combat")
        self.call("design.response", design, "global.html", content, vars, "combat")

    def response_simple(self, content, vars):
        self.call("combat.setup-interface", vars)
        design = self.design("combatinterface")
        self.call("design.response", design, "global-simple.html", content, vars, "combat")

    def response_simple_template(self, template, vars):
        self.call("combat.setup-interface", vars)
        design = self.design("combatinterface")
        content = self.call("design.parse", design, template, None, vars, "combat")
        self.call("design.response", design, "global-simple.html", content, vars, "combat")

class CombatInterfaceAdmin(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("admin-designs.subdirs", self.subdirs)
        for tp in self.conf("combats.rules", {}).keys():
            self.rhook("ext-admin-combatinterface-%s.design" % tp, curry(self.ext_design, tp), priv="design")
            self.rhook("headmenu-admin-combatinterface-%s.design" % tp, curry(self.headmenu_design, tp))
            self.rhook("admin-combatinterface-%s.validate" % tp, self.validate)
            self.rhook("admin-combatinterface-%s.previews" % tp, self.previews)
            self.rhook("admin-combatinterface-%s.preview" % tp, self.preview)
            self.rhook("admin-combatinterface-%s.generators" % tp, curry(self.generators, tp))
            self.rhook("admin-combatinterface-%s.design-files" % tp, self.design_files)

    def subdirs(self, subdirs):
        for tp in self.conf("combats.rules", {}).keys():
            subdirs["combatinterface-%s" % tp] = "combat"

    def generators(self, tp, gens):
        gens.append(design_class_wrapper(DesignCombatRustedMetal, tp))
        #gens.append(DesignCombatCelticCastle)
        #gens.append(DesignCombatJungle)
        #gens.append(DesignCombatMedieval)
        #gens.append(DesignCombatPinky)
        #gens.append(DesignCombatSpace)
        #gens.append(DesignCombatSubmarine)

    def headmenu_design(self, tp, args):
        if args == "":
            rules = self.conf("combats.rules", {}).get(tp)
            if rules is not None:
                return [self._("combats///%s: design") % htmlescape(rules.get("name")), "combats/rules"]
        else:
            return self.call("design-admin.headmenu", "combatinterface-%s" % tp, args)

    def ext_design(self, tp):
        rules = self.conf("combats.rules", {}).get(tp)
        if rules is None:
            self.call("admin.redirect", "combats/rules")
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('Read <a href="//www.%s/doc/design/combatinterface" target="_blank">the combat interface design reference manual</a> to create your own template or edit generated one') % self.main_host, "order": 30})
        self.call("design-admin.editor", "combatinterface-%s" % tp)

    def validate(self, design, parsed_html, errors):
        files = design.get("files")
        if not design.get("css"):
            errors.append(self._("Combat interface design package must contain a CSS file"))

    def previews(self, design, previews):
        previews.append({"filename": "log.html", "title": self._("Combat log")})

    def preview(self, design, filename):
        vars = {}
        if filename == "log.html":
            vars["title"] = self._("Combat log")
            vars["combat_title"] = random.choice([
                self._("The Monster attacks John"),
                self._("Epic battle near the main gates of the Rockbridge Castle"),
                self._("Extremely long combat name involving names of participating characters, NPCs and so on"),
            ])
            vars["counters"] = ""
            for i in range(0, random.randrange(0, 5)):
                vars["counters"] += ' <img src="/st/constructor/design/counter%d.gif" alt="" />' % random.randrange(0, 4)
            self.call("combat.vars-combat", vars)
        else:
            self.call("web.not_found")
        content = self.call("design.parse", design, filename, None, vars, "combat")
        self.call("design.response", design, "global.html", content, vars, design_type="combat")

    def design_files(self, files):
        files.append({"filename": "log.html", "description": self._("Combat log"), "doc": "/doc/design/combatinterface"})

