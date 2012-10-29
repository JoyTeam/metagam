import mg

class MySQLMonitor(mg.Module):
    def register(self):
        self.rhook("mysql.register", self.register_mysql)

    def register_mysql(self):
        inst = self.app().inst
        # Register service
        int_app = inst.int_app
        srv = mg.SingleApplicationWebService(self.app(), "%s-mysql" % inst.instid, "mysql", "mysql")
        srv.serve_any_port()
        int_app.call("cluster.register-service", srv)
