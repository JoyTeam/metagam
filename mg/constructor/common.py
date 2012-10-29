from mg.core.cass import CassandraObject, CassandraObjectList

class Domain(CassandraObject):
    clsname = "Domain"
    indexes = {
        "all": [[], "created"],
        "user": [["user"], "created"],
        "registered": [["registered"], "created"],
        "project": [["project"]],
    }

class DomainList(CassandraObjectList):
    objcls = Domain

