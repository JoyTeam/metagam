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

class DBPopup(CassandraObject):
    _indexes = {
        "all": [[]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Popup-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBPopup._indexes

class DBPopupList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Popup-"
        kwargs["cls"] = DBPopup
        CassandraObjectList.__init__(self, *args, **kwargs)

