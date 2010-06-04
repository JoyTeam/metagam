class Database(object):
    def __init__(self, addr):
        object.__init__(self)
        (self._host, self._name) = addr
