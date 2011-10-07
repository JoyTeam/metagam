from mg import *

class DBPopup(CassandraObject):
    clsname = "Popup"
    indexes = {
        "all": [[]],
    }

class DBPopupList(CassandraObjectList):
    objcls = DBPopup

