import mg

class RedirectSSLModule(mg.Module):
    def register(self):
        self.rhook("web.security_check", self.check, priority=100)

    def check(self):
        req = self.req()
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
