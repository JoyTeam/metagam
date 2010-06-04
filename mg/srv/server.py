from mg.srv.common import WebDaemon
from concurrence.web import Application, Controller, web
from concurrence import Tasklet

class Server(WebDaemon):
    "A web server starting on every node and handling server requests: 'spawn', 'kill', etc"

    class ServerController(Controller):
        @web.route('/srv/spawn')
        def spawn(self):
            print "spawn"
            return "ok"

    def register(self):
        WebDaemon.register(self)
        self.application.add_controller(Server.ServerController())

    def run(self):
        self.serve(("0.0.0.0", 3000))
