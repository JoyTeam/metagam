from mg import *

class DBLocation(CassandraObject):
    _indexes = {
        "all": [[]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Location-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return DBLocation._indexes

class DBLocationList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Location-"
        kwargs["cls"] = DBLocation
        CassandraObjectList.__init__(self, *args, **kwargs)

class Location(Module):
    def __init__(self, app, uuid, fqn="mg.mmo.locations.Location"):
        Module.__init__(self, app, fqn)
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
    def name_where(self):
        try:
            return self._name_where
        except AttributeError:
            self._name_where = self.db_location.get("name_where") or self.db_location.get("name")
            return self._name_where

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

