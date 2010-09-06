from mg.core import Module
from operator import itemgetter
import gettext
import mg
import os
import re

def gettext_noop(x):
    return x

timeencode2_month = {
    "01": gettext_noop("of January"),
    "02": gettext_noop("of February"),
    "03": gettext_noop("of March"),
    "04": gettext_noop("of April"),
    "05": gettext_noop("of May"),
    "06": gettext_noop("of June"),
    "07": gettext_noop("of July"),
    "08": gettext_noop("of August"),
    "09": gettext_noop("of September"),
    "10": gettext_noop("of October"),
    "11": gettext_noop("of November"),
    "12": gettext_noop("of December")
}

class L10n(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.translations = {}
        self.localedir = mg.__path__[0] + "/locale"
        self.languages = set()
        self.languages.add("en")
        for lang in os.listdir(self.localedir):
            try:
                os.stat(self.localedir + "/" + lang + "/LC_MESSAGES")
                self.languages.add(lang)
            except:
                pass

    def register(self):
        Module.register(self)
        self.rhook("l10n.domain", self.l10n_domain)
        self.rhook("l10n.lang", self.l10n_lang)
        self.rhook("l10n.translation", self.l10n_translation)
        self.rhook("l10n.gettext", self.l10n_gettext)
        self.rhook("l10n.set_request_lang", self.l10n_set_request_lang)
        self.rhook("web.universal_variables", self.universal_variables)
        self.rhook("l10n.timeencode2", self.l10n_timeencode2)
        self.re_timeencode2 = re.compile(r'^(\d\d\d\d)-(\d\d)-(\d\d) (\d\d:\d\d):\d\d$')

    def l10n_domain(self):
        return "mg_server"

    def l10n_lang(self):
        try:
            return self.req().lang
        except:
            pass
        try:
            return self.app().lang
        except:
            pass
        return None

    def l10n_translation(self, domain, lang):
        key = "%s.%s" % (domain, lang)
        try:
            return self.translations[key]
        except KeyError:
            pass
        trans = gettext.translation(domain, localedir=self.localedir, languages=[lang])
        self.translations[key] = trans
        return trans

    def l10n_gettext(self, str):
        request = self.req()
        try:
            return request.trans.gettext(str)
        except:
            pass
        lang = self.call("l10n.lang")
        if lang is None:
            return str
        domain = self.call("l10n.domain")
        trans = self.call("l10n.translation", domain, lang)
        request.trans = trans
        return trans.gettext(str)

    def l10n_set_request_lang(self):
        request = self.req()
        accept_language = request.environ.get("HTTP_ACCEPT_LANGUAGE")
        if accept_language is not None:
            weight = []
            for ent in accept_language.split(","):
                try:
                    tokens = ent.split(";")
                    if tokens[0] in self.languages:
                        if len(tokens) == 1:
                            weight.append((tokens[0], 1))
                        elif len(tokens) == 2:
                            subtokens = tokens[1].split("=")
                            if len(subtokens) == 2 and subtokens[0] == "q":
                                weight.append((tokens[0], float(subtokens[1])))
                except:
                    pass
            if len(weight):
                weight.sort(key=itemgetter(1), reverse=True)
                if weight[0][0] != "en":
                   request.lang = weight[0][0]

    def universal_variables(self, struct):
        struct["lang"] = self.call("l10n.lang")

    def l10n_timeencode2(self, time):
        m = self.re_timeencode2.match(time)
        if not m:
            return ""
        year, month, day, time = m.group(1, 2, 3, 4)
        year = int(year)
        day = int(day)
        th = "th"
        day100 = day % 100
        if day100 <= 10 or day100 >= 20:
            day10 = day % 10
            if day10 == 1:
                th = "st"
            elif day10 == 2:
                th = "nd"
            elif day10 == 3:
                th = "rd"
        return self._("at the {2:d}{4} {1}, {0} at {3}").format(year, self._(timeencode2_month.get(month)), day, time, th)
