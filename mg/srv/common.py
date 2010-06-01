from concurrence.web import Application, Controller, web
from concurrence import Tasklet

class WebDaemon(object):
    "Abstract web application serving HTTP requests"

    class BasicController(Controller):
        "A controller providing basic services for all web daemons"

        @web.route('/sys/ping')
        def ping(self):
            Tasklet.sleep(1)
            return "pong"

    def __init__(self):
        object.__init__(self)
        self.application = Application()
        self.register()

    def serve(self, addr):
        self.application.configure()
        self.application.serve(addr)

    def register(self):
        self.application.add_controller(WebDaemon.BasicController())

    def request(self, environ, start_response):
        start_response("200 OK", [])

        return ["<html>Hello, world!</html>"]

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
