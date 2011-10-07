from mg import *
import re

class Project(CassandraObject):
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

class ProjectList(CassandraObjectList):
    objcls = Project

#    def tag_by_domain(self, domain):
#        tag = super(ApplicationFactory, self).tag_by_domain(domain)
#        if tag is not None:
#            return tag
#        m = re.match("^([0-9a-f]{32})\.%s" % self.inst.config["main_host"], domain)
#        if m:
#            return m.groups(1)[0]
#        return None

class Projects(Module):
    def register(self):
        self.rhook("applications.list", self.applications_list)

    def applications_list(self, apps):
        apps.append({"cls": "metagam", "tag": "main"})
        projects = self.int_app().objlist(ProjectList, query_index="created")
        projects.load(silent=True)
        for proj in projects:
            apps.append({"cls": proj.get("cls") if proj.get("cls") else "metagam", "tag": proj.uuid})
