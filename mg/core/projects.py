from mg import *
import re

class Project(CassandraObject):
    _indexes = {
        "created": [[], "created"],
        "inactive": [["inactive"], "created"],
        "owner": [["owner"], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Project-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Project._indexes

class ProjectList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Project-"
        kwargs["cls"] = Project
        CassandraObjectList.__init__(self, *args, **kwargs)

    def tag_by_domain(self, domain):
        tag = super(ApplicationFactory, self).tag_by_domain(domain)
        if tag is not None:
            return tag
        m = re.match("^([0-9a-f]{32})\.%s" % self.inst.config["main_host"], domain)
        if m:
            return m.groups(1)[0]
        return None

class Projects(Module):
    def register(self):
        Module.register(self)
        self.rhook("applications.list", self.applications_list)

    def applications_list(self, apps):
        apps.append({"cls": "metagam", "tag": "main"})
        projects = self.app().inst.int_app.objlist(ProjectList, query_index="created")
        projects.load(silent=True)
        for proj in projects:
            apps.append({"cls": proj.get("cls") if proj.get("cls") else "metagam", "tag": proj.uuid})
