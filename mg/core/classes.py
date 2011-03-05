from mg.core.cass import CassandraObject, CassandraObjectList

class StaticUploadError(Exception):
    "Error uploading object to the static server"
    pass

class WorkerStatus(CassandraObject):
    _indexes = {
        "all": [[]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "WorkerStatus-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return WorkerStatus._indexes

class WorkerStatusList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "WorkerStatus-"
        kwargs["cls"] = WorkerStatus
        CassandraObjectList.__init__(self, *args, **kwargs)

