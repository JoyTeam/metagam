import mg

class RedirectSSLModule(mg.Module):
    def register(self):
        if self.conf("ssl.enabled"):
            self.app().protocol = "https"
            self.rhook("web.security_check", self.check, priority=100)
        else:
            self.app().protocol = "http"

    def check(self):
        req = self.req()
        if req.group == "ext-payment":
            return
        if req.environ.get("HTTP_X_INSECURE"):
            uri = 'https://%s' % self.app().canonical_domain
            if req.environ.get("REQUEST_METHOD") == "POST":
                uri += "/"
            else:
                if req.group == "index":
                    uri += "/"
                else:
                    uri += "/" + req.group
                    if req.hook != "index":
                        uri += "/" + req.hook
                        if req.args != "":
                            uri += "/" + req.args
            self.call("web.redirect", uri)
