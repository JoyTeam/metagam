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

from mg import *
from mg.constructor.paramobj import ParametrizedObject
import re

default_location_delay = 20
re_param_attr = re.compile(r'^p_(.+)')
re_dyn_attr = re.compile(r'^dyn_(.+)')
re_html_attr = re.compile(r'^html_(.+)')

class DBLocation(CassandraObject):
    clsname = "Location"
    indexes = {
        "all": [[], "name"],
        "name": [["name"]],
    }

class DBLocationList(CassandraObjectList):
    objcls = DBLocation

class DBCharacterLocation(CassandraObject):
    clsname = "CharacterLocation"
    indexes = {
        "location": [["location"]],
        "instance": [["instance"]],
    }

class DBCharacterLocationList(CassandraObjectList):
    objcls = DBCharacterLocation

class DBLocParams(CassandraObject):
    clsname = "LocParams"

class DBLocParamsList(CassandraObjectList):
    objcls = DBLocParams

class FakeLocation(object):
    "Simulate real location when parsing expressions"
    def script_attr(self, attr, handle_exceptions=True):
        return None

class Location(Module, ParametrizedObject):
    def __init__(self, app, uuid, fqn="mg.mmorpg.locations.Location"):
        Module.__init__(self, app, fqn)
        ParametrizedObject.__init__(self, "locations")
        self.uuid = uuid

    @property
    def db_location(self):
        try:
            return self._db_location
        except AttributeError:
            self._db_location = self.obj(DBLocation, self.uuid)
            return self._db_location

    @property
    def name(self):
        try:
            return self._name
        except AttributeError:
            self._name = self.db_location.get("name")
            return self._name

    @property
    def name_g(self):
        try:
            return self._name_g
        except AttributeError:
            self._name_g = self.db_location.get("name_g") or self.db_location.get("name")
            return self._name_g

    @property
    def name_a(self):
        try:
            return self._name_a
        except AttributeError:
            self._name_a = self.db_location.get("name_a") or self.db_location.get("name")
            return self._name_a

    @property
    def name_w(self):
        try:
            return self._name_w
        except AttributeError:
            self._name_w = self.db_location.get("name_w") or self.db_location.get("name")
            return self._name_w

    @property
    def name_f(self):
        try:
            return self._name_f
        except AttributeError:
            self._name_f = self.db_location.get("name_f") or self.db_location.get("name")
            return self._name_f

    @property
    def name_t(self):
        try:
            return self._name_t
        except AttributeError:
            self._name_t = self.db_location.get("name_t") or self.db_location.get("name")
            return self._name_t

    def valid(self):
        try:
            db = self.db_location
        except ObjectNotFoundException:
            return False
        else:
            return True

    @property
    def image_type(self):
        try:
            return self._image_type
        except AttributeError:
            self._image_type = self.db_location.get("image_type")
            return self._image_type

    @property
    def transitions(self):
        try:
            return self._transitions
        except AttributeError:
            self._transitions = self.db_location.get("transitions")
            return self._transitions

    @property
    def delay(self):
        try:
            return self._delay
        except AttributeError:
            self._delay = self.db_location.get("delay", default_location_delay)
            return self._delay

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "id":
            return self.uuid
        elif attr == "name":
            return self.name
        elif attr == "name_g":
            return self.name_g
        elif attr == "name_a":
            return self.name_a
        elif attr == "name_f":
            return self.name_f
        elif attr == "name_t":
            return self.name_t
        elif attr == "name_w":
            return self.name_w
        elif attr == "channel":
            return "loc-%s" % self.uuid
        else:
            m = re_param_attr.match(attr)
            if m:
                param = m.group(1)
                return self.param(param, handle_exceptions)
            m = re_html_attr.match(attr)
            if m:
                param = m.group(1)
                return self.param_html(param, handle_exceptions)
            m = re_dyn_attr.match(attr)
            if m:
                param = m.group(1)
                return self.param_dyn(param, handle_exceptions)
            raise AttributeError(attr)

    def script_set_attr(self, attr, val, env):
        # parameters
        m = re_param_attr.match(attr)
        if m:
            param = m.group(1)
            return self.set_param(param, val)
        raise AttributeError(attr)

    def store(self):
        if self.db_params.dirty:
            self.db_params.store()

    @property
    def db_params(self):
        try:
            return self._db_params
        except AttributeError:
            self._db_params = self.obj(DBLocParams, self.uuid, silent=True)
            return self._db_params

    def script_params(self):
        return {"loc": self}

    def __str__(self):
        return u"[loc %s]" % self.name
    
    __repr__ = __str__
