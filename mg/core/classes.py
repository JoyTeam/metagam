from mg.core.cass import CassandraObject, CassandraObjectList

class StaticUploadError(Exception):
    "Error uploading object to the static server"
    pass

class WorkerStatus(CassandraObject):
    clsname = "WorkerStatus"
    indexes = {
        "all": [[]],
    }

class WorkerStatusList(CassandraObjectList):
    objcls = WorkerStatus

class DoubleResponseException(Exception):
    "start_response called twice on the same request"
    pass

class WebResponse(Exception):
    def __init__(self, content):
        self.content = content

