#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

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
