#!/usr/bin/python2.6

import unittest
from concurrence import dispatch, Tasklet
from mg.constructor import *
from mg.core.cass import CassandraPool
from mg.core.memcached import MemcachedPool
from mg.mmorpg.inventory_classes import DBItemType, DBItemTypeParams
from uuid import uuid4

class TestItems(unittest.TestCase, ConstructorModule):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.inst = Instance("test", "test")
        self.inst._dbpool = CassandraPool((("localhost", 9160),))
        self.inst._mcpool = MemcachedPool()
        self.app_obj = Application(self.inst, "mgtest")
        self.app_obj.modules.load(["mg.mmorpg.inventory.Inventory", "mg.core.l10n.L10n"])
        ConstructorModule.__init__(self, self.app_obj, "mg.test.testitems.TestItems")
        mc = Memcached(prefix="mgtest-")
        mc.delete("Cassandra-CF-mgtest-Data")
        self.cleanup()

    def test(self):
        # creating parameters metadata
        config = self.app().config_updater()
        params = []
        for i in xrange(1, 6):
            params.append({
                "code": "param%d" % i,
                "description": "Parameter %d" % i,
                "grp": "",
                "default": i,
                "visual_mode": 0,
                "order": 0.0,
                "type": 0,
                "name": "Parameter %d" % i,
            })
        config.set("item-types.params", params)
        config.store()
        # creating test item type
        db_item_type = self.obj(DBItemType)
        db_item_type.set("name", "Test Item")
        db_item_type.set("name_lower", "test item")
        db_item_type.store()
        # creating item type parameters
        db_params = self.obj(DBItemTypeParams, db_item_type.uuid, data={})
        db_params.set("param1", 10)
        db_params.set("param2", 20)
        db_params.store()
        # testing ItemType class
        item_type = self.item_type(db_item_type.uuid)
        self.assertTrue(item_type)
        self.assertEqual(item_type.name, "Test Item")
        self.assertEqual(item_type.param("param1"), 10)
        self.assertEqual(item_type.param("param2"), 20)
        self.assertEqual(item_type.param("param3"), 3)
        self.assertEqual(item_type.param("param4"), 4)
        self.assertEqual(item_type.param("param5"), 5)
        # creating member inventory
        inv = self.call("inventory.get", "char", uuid4().hex)
        # testing MemberInventory class
        self.assertEqual(len(inv.items()), 0)
        inv.give(item_type.uuid, 5)
        self.assertEqual(len(inv.items()), 1)
        # reloading inventory contents
        inv = self.call("inventory.get", "char", inv.uuid)
        self.assertEqual(len(inv.items()), 1)
        inv_item_type, inv_quantity = inv.items()[0]
        self.assertEqual(inv_item_type.uuid, item_type.uuid)
        self.assertEqual(inv_quantity, 5)
        # giving items
        inv.give(item_type.uuid, 3)
        self.assertEqual(len(inv.items()), 1)
        inv_item_type, inv_quantity = inv.items()[0]
        self.assertEqual(inv_item_type.uuid, item_type.uuid)
        self.assertEqual(inv_quantity, 8)
        # taking items
        inv.take_type(item_type.uuid, 7)
        self.assertEqual(len(inv.items()), 1)
        inv_item_type, inv_quantity = inv.items()[0]
        self.assertEqual(inv_item_type.uuid, item_type.uuid)
        self.assertEqual(inv_quantity, 1)
        inv.take_type(item_type.uuid, 1)
        self.assertEqual(len(inv.items()), 0)
        # giving some items back
        inv.give(item_type.uuid, 2)
        # creating item object
        item = self.item(inv, db_item_type.uuid)
        self.assertTrue(item)
        # testing translation of calls to the underlying item type
        self.assertEqual(item.name, "Test Item")
        self.assertEqual(item.param("param1"), 10)
        self.assertEqual(item.param("param2"), 20)
        self.assertEqual(item.param("param3"), 3)
        self.assertEqual(item.param("param4"), 4)
        self.assertEqual(item.param("param5"), 5)
        # modifying item
        item.set_param("param3", 30)
        items = inv.items()
        self.assertEqual(len(items), 2)
        items.sort(cmp=lambda x, y: cmp(x[0].dna, y[0].dna))
        self.assertEqual(items[0][0].dna, item.uuid)
        self.assertEqual(items[0][1], 1)
        self.assertEqual(items[0][0].param("param1"), 10)
        self.assertEqual(items[0][0].param("param2"), 20)
        self.assertEqual(items[0][0].param("param3"), 3)
        self.assertEqual(items[0][0].param("param4"), 4)
        self.assertEqual(items[0][0].param("param5"), 5)
        self.assertEqual(items[1][0].dna, item.dna)
        self.assertEqual(items[1][1], 1)
        self.assertEqual(items[1][0].param("param1"), 10)
        self.assertEqual(items[1][0].param("param2"), 20)
        self.assertEqual(items[1][0].param("param3"), 30)
        self.assertEqual(items[1][0].param("param4"), 4)
        self.assertEqual(items[1][0].param("param5"), 5)
        # modifying this item again
        item.set_param("param4", 40)
        items = inv.items()
        self.assertEqual(len(items), 2)
        items.sort(cmp=lambda x, y: cmp(x[0].dna, y[0].dna))
        self.assertEqual(items[0][0].dna, item.uuid)
        self.assertEqual(items[0][1], 1)
        self.assertEqual(items[0][0].param("param1"), 10)
        self.assertEqual(items[0][0].param("param2"), 20)
        self.assertEqual(items[0][0].param("param3"), 3)
        self.assertEqual(items[0][0].param("param4"), 4)
        self.assertEqual(items[0][0].param("param5"), 5)
        self.assertEqual(items[1][0].dna, item.dna)
        self.assertEqual(items[1][1], 1)
        self.assertEqual(items[1][0].param("param1"), 10)
        self.assertEqual(items[1][0].param("param2"), 20)
        self.assertEqual(items[1][0].param("param3"), 30)
        self.assertEqual(items[1][0].param("param4"), 40)
        self.assertEqual(items[1][0].param("param5"), 5)
        # modifying another item to the same value
        item = self.item(inv, db_item_type.uuid)
        item.set_param("param3", 30)
        item.set_param("param4", 40)
        items = inv.items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][0].dna, item.dna)
        self.assertEqual(items[0][1], 2)
        self.assertEqual(items[0][0].param("param1"), 10)
        self.assertEqual(items[0][0].param("param2"), 20)
        self.assertEqual(items[0][0].param("param3"), 30)
        self.assertEqual(items[0][0].param("param4"), 40)
        self.assertEqual(items[0][0].param("param5"), 5)

if __name__ == "__main__":
    dispatch(unittest.main)
