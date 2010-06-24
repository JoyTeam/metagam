from mg.core import Module
import gettext
import mg

class L10n(Module):
    def __init__(self, *args, **kwargs):
        Module.__init__(self, *args, **kwargs)
        self.translations = {}

    def register(self):
        Module.register(self)
        self.rhook("l10n.domain", self.l10n_domain)
        self.rhook("l10n.lang", self.l10n_lang)
        self.rhook("l10n.translation", self.l10n_translation)
        self.rhook("l10n.gettext", self.l10n_gettext)

    def l10n_domain(self):
        return "mg_server"

    def l10n_lang(self):
        lang = None
        try:
            lang = Tasklet.current().req.lang
        except:
            try:
                lang = self.app().lang
            except:
                lang = "en"
        return lang

    def l10n_translation(self, domain, lang):
        key = "%s.%s" % (domain, lang)
        try:
            return self.translations[key]
        except KeyError:
            pass
        trans = gettext.translation(domain, localedir=mg.__path__[0] + "/locale", languages=[lang])
        self.translations[key] = trans
        return trans

    def l10n_gettext(self, str):
        lang = self.call("l10n.lang")
        domain = self.call("l10n.domain")
        trans = self.call("l10n.translation", domain, lang)
        return trans.gettext(str)
