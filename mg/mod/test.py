from mg.core import Module
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

