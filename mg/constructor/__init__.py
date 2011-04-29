from mg import *
from mg.constructor.players import Character, Player

class ConstructorModule(Module):
    def character(self, uuid):
        try:
            req = self.req()
        except AttributeError:
            return Character(self.app(), uuid)
        else:
            try:
                characters = req.characters
            except AttributeError:
                characters = {}
                req.character = characters
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
        else:
            try:
                players = req.players
            except AttributeError:
                players = {}
                req.player = players
            try:
                return players[uuid]
            except KeyError:
                obj = Player(self.app(), uuid)
                players[uuid] = obj
                return obj
