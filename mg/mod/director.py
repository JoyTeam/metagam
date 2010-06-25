from mg.core import Module
import cgi
import re

class Director(Module):
    def register(self):
        Module.register(self)
        self.rdep(["web.Web"])
        self.rhook("web.template", self.web_template, 5)
        self.rhook("int-director.ready", self.director_ready)
        self.rhook("int-director.test", self.director_test)
        self.rhook("int-director.reload", self.director_reload)
        self.rhook("int-index.index", self.director_index)
        self.rhook("int-director.setup", self.director_setup)
        self.rhook("int-director.config", self.director_config)
        self.app().lang = "ru"

    def director_test(self, args, request):
        # TODO: remove
        args = cgi.escape(args)
        param = request.param('param')
        param = cgi.escape(param)
        return request.uresponse('<html><body>Director test handler: args=%s, param=%s</body></html>' % (args, param))

    def director_ready(self, args, request):
        return request.jresponse({ "ok": 1 })

    def director_reload(self, args, request):
        errors = self.app().reload()
        if errors:
            return request.jresponse({ "errors": errors })
        else:
            return request.jresponse({ "ok": 1 })

    def web_template(self, filename, struct):
        self.call("web.set_global_html", "director/global.html")

    def director_index(self, args, request):
        return self.call("web.template", "director/index.html", {
            "title": self._("Welcome to the Director control center"),
            "setup": self._("Change director settings")
        })

    def config(self):
        conf = self.conf("director.config")
        if conf is None:
            conf = {
                "cassandra": [("director-db", 9160)],
                "memcached": [("director-mc", 11211)]
            }
        return conf

    def director_config(self, args, request):
        return request.jresponse(self.config())

    def split_host_port(self, str, defport):
        ent = re.split(':', str)
        if len(ent) >= 2:
            return (ent[0], int(ent[1]))
        else:
            return (str, defport)
        
    def director_setup(self, args, request):
        memcached = request.param("memcached")
        cassandra = request.param("cassandra")
        config = self.config()
        if self.ok():
            config["memcached"] = [self.split_host_port(srv, 11211) for srv in re.split('\s*,\s*', memcached)]
            config["cassandra"] = [self.split_host_port(srv, 9160) for srv in re.split('\s*,\s*', cassandra)]
            self.app().config.set("director.config", config)
            print config
            return request.redirect('/')
        else:
            memcached = ", ".join("%s:%s" % (port, host) for port, host in config["memcached"])
            cassandra = ", ".join("%s:%s" % (port, host) for port, host in config["cassandra"])
        return self.call("web.template", "director/setup.html", {
            "title": self._("Director settings"),
            "form": {
                "memcached_desc": self._("<strong>Memcached servers</strong> (host:port, host:port, ...)"),
                "cassandra_desc": self._("<strong>Cassandra servers</strong> (host:port, host:post, ...)"),
                "memcached": memcached,
                "cassandra": cassandra,
                "submit_desc": self._("Save")
            }
        })
