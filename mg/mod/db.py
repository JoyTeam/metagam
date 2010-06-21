from mg.core import Module
from cassandra.ttypes import *
from mg.stor.db import DatabaseRestructure

class CommonDatabaseStruct(Module):
    def register(self):
        Module.register(self)
        self.rhook("core.dbstruct", self.database_struct)
        self.rhook("core.dbapply", self.database_apply)

    def database_struct(self, dbstruct):
        dbstruct["Core"] = CfDef()

    def database_apply(self, dbstruct):
        db = self.db()
        restruct = DatabaseRestructure(db)
        restruct.apply(restruct.diff(dbstruct))
