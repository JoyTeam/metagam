from mg.core import Module
from cassandra.ttypes import *

class Test1(Module):
    def register(self):
        Module.register(self)
        self.rhook("database.struct", self.database_struct)

    def database_struct(self, dbstruct):
        dbstruct["TestFamily"] = CfDef(comparator_type="BytesType")
