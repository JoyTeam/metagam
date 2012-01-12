from mg import *
from cassandra.ttypes import *
import logging
import re
import json
import time

class CassandraMaintenance(Module):
    def register(self):
        self.rhook("cassmaint.validate", self.validate)

    def validate(self, app, cls):
        objclasses = {}
        app.hooks.call("objclasses.list", objclasses)
        cinfo = objclasses[cls]
        uuids = app.db.dump_objects(cls)
        for uuid in uuids:
            obj = app.obj(cinfo[0], uuid)
            obj.touch()
            obj._indexes = {}
            obj.store()
        return len(uuids)
