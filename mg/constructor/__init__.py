from mg import *
from mg.constructor.player_classes import Character, Player, Characters
from mg.mmorpg.locations_classes import Location
from mg.constructor.script_classes import ScriptError, ScriptParserError, ScriptRuntimeError, ScriptTemplateObject

class ConstructorModule(Module):
    def find_character(self, name):
        uuid = self.call("session.find_user", name, return_uuid=True)
        if not uuid:
            return None
        return self.character(uuid)

    def character(self, uuid):
        try:
            req = self.req()
        except AttributeError:
            return Character(self.app(), uuid)
        try:
            characters = req.characters
        except AttributeError:
            characters = {}
            req.characters = characters
        try:
            return characters[uuid]
        except KeyError:
            obj = Character(self.app(), uuid)
            characters[uuid] = obj
            return obj

    def player(self, uuid):
        try:
            req = self.req()
        except AttributeError:
            return Player(self.app(), uuid)
        try:
            players = req.players
        except AttributeError:
            players = {}
            req.players = players
        try:
            return players[uuid]
        except KeyError:
            obj = Player(self.app(), uuid)
            players[uuid] = obj
            return obj

    @property
    def myself(self):
        req = self.req()
        try:
            return req._myself
        except AttributeError:
            user = req.user()
            if user:
                req._myself = self.character(req.user())
            else:
                req._myself = None
            return req._myself

    def find_character(self, name):
        user = self.call("session.find_user", name, return_id=True)
        if not user:
            return None
        return self.character(user)

    @property
    def characters(self):
        try:
            req = self.req()
        except AttributeError:
            return Characters(self.app())
        else:
            try:
                return req.characters_obj
            except AttributeError:
                characters = Characters(self.app())
                req.characters_obj = characters
                return characters

    def design(self, group):
        try:
            req = self.req()
        except AttributeError:
            return self.call("design.get", group)
        else:
            try:
                designs = req.designs
            except AttributeError:
                designs = {}
                req.designs = designs
            try:
                return designs[group]
            except KeyError:
                obj = self.call("design.get", group)
                designs[group] = obj
                return obj

    def location(self, uuid):
        try:
            req = self.req()
        except AttributeError:
            return Location(self.app(), uuid)
        else:
            try:
                locations = req.locations
            except AttributeError:
                locations = {}
                req.locations = locations
            try:
                return locations[uuid]
            except KeyError:
                obj = Location(self.app(), uuid)
                locations[uuid] = obj
                return obj

    def find_item_type(self, name):
        uuid = self.call("inventory.find_item_type", name)
        if not uuid:
            return None
        return self.item_type(uuid)

    def item_type(self, *args, **kwargs):
        return self.call("item-types.item-type", *args, **kwargs)

    def item(self, *args, **kwargs):
        return self.call("item-types.item", *args, **kwargs)

    def item_types_all(self, load_item_types=True, load_params=True):
        return self.call("item-types.all", load_item_types, load_params)

    def item_types_load(self, uuids, load_item_types=True, load_params=True):
        return self.call("item-types.load", uuids, load_item_types, load_params)
