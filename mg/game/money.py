from mg import *

class Money(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-ext-payment.2pay", self.payment_2pay)

    def payment_2pay(self):
        self.call("web.response", "ok", {})

