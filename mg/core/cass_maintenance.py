from mg import *
from cassandra.ttypes import *
import logging
import re
import json
import time

class CassandraMaintenance(Module):
    def register(self):
        Module.register(self)
        self.rhook("cassmaint.validate", self.validate)
        self.rhook("cassmaint.load_database", self.load_database)

    def load_database(self):
        app = self.app()
        db = app.db
        return db.get_range_slices(ColumnParent("Objects"), SlicePredicate(slice_range=SliceRange(start="", finish="", count=1000000)), KeyRange(start_key="", end_key="", count=1000000), ConsistencyLevel.QUORUM)

    def validate(self, slices_list=None):
        objclasses = {}
        objclasses["ConfigGroup"] = (ConfigGroup, ConfigGroupList)
        objclasses["HookGroupModules"] = (HookGroupModules, HookGroupModulesList)
        self.call("objclasses.list", objclasses)
        app = self.app()
        db = app.db
        if slices_list is None:
            slices_list = self.load_database()
        prefix = app.keyprefix
        parsers = []
        re_prefix = re.compile('^%s' % prefix)
        index_names = []
        for name, info in objclasses.iteritems():
            parsers.append((re.compile('^%s%s-(.+)$' % (prefix, name)), 1, info[0]))
            if info[1]:
                indexes = info[0](db, "", {}).indexes()
                for index_name, index_info in indexes.iteritems():
                    index_names.append(name + "-" + index_name)
                    if len(index_info[0]):
                        # If index has no equal keys these keys must be appended to the key
                        parsers.append((re.compile('^%s%s-%s-(.*)$' % (prefix, name, index_name), re.DOTALL), 2, info, index_info))
                    else:
                        # If index has no equal keys no keys are appended to the key
                        parsers.append((re.compile('^%s%s-%s$' % (prefix, name, index_name)), 3, info, index_info))
        slices_list = [slice for slice in slices_list if re_prefix.match(slice.key) and len(slice.columns)]
        slices_dict = dict([(slice.key, slice.columns) for slice in slices_list])
        valid_keys = set()
        re_any_index = ('^%s(?:' % prefix) + '|'.join(index_names) + ')(?:-|$)'
        re_any_index = re.compile(re_any_index)
        for slice in slices_list:
            key = slice.key
            #self.debug(key)
            if re_any_index.match(key):
                continue
            for parser in parsers:
                # Parsers of object containers
                if parser[1] == 1:
                    m = parser[0].match(key)
                    if m:
                        # checking object integrity
                        uuid = m.groups(1)[0]
                        try:
                            data = json.loads(slice.columns[0].column.value)
                        except (ValueError, IndexError):
                            data = None
                        if data and type(data) == dict:
                            valid_keys.add(key)
                            obj = parser[2](db, uuid, data, dbprefix=prefix)
                            obj.calculate_indexes()
                            index_values = obj.index_values()
                            update = False
                            for index_name, index_info in index_values.iteritems():
                                key = "%s%s%s%s" % (prefix, obj.clsprefix, index_name, index_info[0])
                                if type(key) == unicode:
                                    key = key.encode("utf-8")
                                index = slices_dict.get(key)
                                #self.debug("Searching for object in the index key %s (having uuids %s)", uuid, key, index)
                                if index is None:
                                    self.debug("index %s is missing", key)
                                    update = True
                                    break
                                else:
                                    index_ok = False
                                    for col in index:
                                        if col.column.name == index_info[1] and col.column.value == uuid:
                                            index_ok = True
                                            # removing correct index value
                                            index.remove(col)
                                            break
                                    if not index_ok:
                                        self.debug("in the index %s column %s is missing (available columns: %s)", key, index_info[1], [col.column.name for col in index])
                                        update = True
                                        break
                            if update:
                                obj._indexes = {}
                                obj.touch()
                                obj.store()
                            break
        mutations = {}
        for slice in slices_list:
            key = slice.key
            for parser in parsers:
                # Parsers of object indices
                if parser[1] != 1:
                    m = parser[0].match(key)
                    if m:
                        valid_keys.add(key)
                        # checking index integrity
                        for col in slice.columns:
                            self.debug("in the index %s column %s (holding data %s) is invalid", key, col.column.name, col.column.value)
                            mutation = Mutation(deletion=Deletion(predicate=SlicePredicate([col.column.name]), clock=Clock(col.column.clock.timestamp+1)))
                            try:
                                mutations[key]["Objects"].append(mutation)
                            except KeyError:
                                mutations[key] = {"Objects": [mutation]}
                        break
        if len(mutations):
            db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
        return valid_keys
