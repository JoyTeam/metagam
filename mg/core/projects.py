#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

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
        self.rhook("project.get", self.project_get)

    def applications_list(self, apps):
        apps.append({"cls": "metagam", "tag": "main"})
        projects = self.int_app().objlist(ProjectList, query_index="created")
        projects.load(silent=True)
        for proj in projects:
            apps.append({"cls": proj.get("cls") if proj.get("cls") else "metagam", "tag": proj.uuid})

    def project_get(self, uuid):
        try:
            return self.int_app().obj(Project, uuid)
        except mg.ObjectNotFoundException:
            return None
