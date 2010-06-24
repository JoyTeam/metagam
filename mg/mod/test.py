from mg.core import Module, Hooks
from cassandra.ttypes import *

class Test1(Module):
    def register(self):
        Module.register(self)
        self.rhook("core.dbstruct", self.database_struct)
        self.rhook("grp1.test1", self.test1)
        self.rhook("grp1.test2", self.test2)
        self.rhook("grp2.test3", self.test3)

    def database_struct(self, dbstruct):
        dbstruct["TestFamily"] = CfDef(comparator_type="BytesType")

    def test1(self):
        pass

    def test2(self):
        pass

    def test3(self):
        pass

class Test2(Module):
    def register(self):
        Module.register(self)
        self.rhook("grp1.test1", self.test1)
        self.rhook("grp1.test2", self.test2)
        self.rhook("grp2.test3", self.test3)

    def test1(self):
        pass

    def test2(self):
        pass

    def test3(self):
        pass

class TestJoin(Module):
    def register(self):
        Module.register(self)
        self.rhook("join.empty", self.empty)
        self.rhook("join.single", self.single)
        self.rhook("join.prio1", self.prio1)
        self.rhook("join.prio1", self.prio2)
        self.rhook("join.prio2", self.prio2)
        self.rhook("join.prio2", self.prio1)
        self.rhook("join.prio3", self.prio1)
        self.rhook("join.prio3", self.prio2, 10)
        self.rhook("join.filter1", self.res)
        self.rhook("join.filter2", self.filter1)
        self.rhook("join.filter2", self.res)
        self.rhook("join.filter3", self.filter1)
        self.rhook("join.filter3", self.filter2)
        self.rhook("join.filter3", self.res)
        self.rhook("join.immed", self.filter1)
        self.rhook("join.immed", self.immed)
        self.rhook("join.immed", self.filter2)
        self.rhook("join.immed", self.res)

    def empty(self):
        pass

    def single(self):
        return "single"

    def prio1(self):
        return "prio1"

    def prio2(self):
        return "prio2"

    def res(self, arg):
        return arg

    def filter1(self, arg):
        return (arg * 2,)

    def filter2(self, arg):
        return (arg + 10,)

    def immed(self, arg):
        raise Hooks.Return("immed")
