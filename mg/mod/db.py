from mg.core import Module
from cassandra.ttypes import *
from mg.stor.db import DatabaseRestructure

class CommonDatabaseStruct(Module):
    def register(self):
        Module.register(self)
        self.rhook("database.struct", self.database_struct)
        self.rhook("database.apply", self.database_apply)

    def database_struct(self, dbstruct):
        dbstruct["Config"] = CfDef()
        dbstruct["Hooks"] = CfDef()

    def database_apply(self, dbstruct):
        db = self.db()
        restruct = DatabaseRestructure(db)
        restruct.apply(restruct.diff(dbstruct))
