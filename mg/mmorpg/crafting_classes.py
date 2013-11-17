from mg import *

class DBCraftingRecipe(CassandraObject):
    clsname = "CraftingRecipe"
    indexes = {
        "all": [[]],
    }

class DBCraftingRecipeList(CassandraObjectList):
    objcls = DBCraftingRecipe

