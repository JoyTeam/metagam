import mg
import re

class Project(mg.CassandraObject):
    clsname = "Project"
    indexes = {
        "created": [[], "created"],
        "inactive": [["inactive"], "created"],
        "owner": [["owner"], "created"],
        "moderation": [["moderation"], "created"],
        "published": [[], "published"],
        "name_short": [[], "name_short"],
        "name_en": [[], "name_en"],
    }

class ProjectList(mg.CassandraObjectList):
    objcls = Project

class Projects(mg.Module):
    def register(self):
        self.rhook("applications.list", self.applications_list)

    def applications_list(self, apps):
        apps.append({"cls": "metagam", "tag": "main"})
        projects = self.int_app().objlist(ProjectList, query_index="created")
        projects.load(silent=True)
        for proj in projects:
            apps.append({"cls": proj.get("cls") if proj.get("cls") else "metagam", "tag": proj.uuid})
