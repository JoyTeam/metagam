from mg import *

class DBCraftingRecipe(CassandraObject):
    clsname = "CraftingRecipe"
    indexes = {
        "all": [[]],
        "category": [["category"]],
    }

class DBCraftingRecipeList(CassandraObjectList):
    objcls = DBCraftingRecipe

