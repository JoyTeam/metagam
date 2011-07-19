from mg import *

class DBCharacterSettings(CassandraObject):
    _indexes = {
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "CharacterSettings-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBCharacterSettings._indexes

class DBCharacterSettingsList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "CharacterSettings-"
        kwargs["cls"] = DBCharacterSettings
        CassandraObjectList.__init__(self, *args, **kwargs)

