from mg import *
from mg.constructor.players import Character, Player, Characters

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
        else:
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
