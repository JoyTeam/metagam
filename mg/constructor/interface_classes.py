from mg import *

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

