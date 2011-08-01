from mg.constructor import *

class GameReporter(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("marketing.report", self.marketing_report)

    def schedule(self, sched):
        sched.add("marketing.report", "0 0 * * *", priority=20)

    def marketing_report(self):
        print "marketing report"
