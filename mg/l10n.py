from concurrence import Tasklet
from mg.core import Module
from operator import itemgetter
import gettext
import mg
import os

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

    def l10n_domain(self):
        return "mg_server"

    def l10n_lang(self):
        try:
            return Tasklet.current().req.lang
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
        lang = self.call("l10n.lang")
        if lang is None:
            return str
        domain = self.call("l10n.domain")
        trans = self.call("l10n.translation", domain, lang)
        return trans.gettext(str)

    def l10n_set_request_lang(self, request):
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
