import mg.constructor
import hashlib

class SoundAdmin(mg.constructor.ConstructorModule):
    def register(self):
        pass

class Sound(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("sound.play", self.play)
        self.rhook("sound.music", self.music)

    def child_modules(self):
        return ["mg.constructor.sound.SoundAdmin"]

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("sound")

    def play(self, char, url, mode="overlap", volume=50):
        m = hashlib.md5()
        m.update(url)
        id = "snd-%s" % m.hexdigest()
        self.call("stream.packet", "global", "sound", "play", id=id, url=url, mode=mode, volume=volume)

    def music(self, char, url, fade=3000, volume=50):
        m = hashlib.md5()
        m.update(url)
        id = "music-%s" % m.hexdigest()
        self.call("stream.packet", "global", "sound", "music", id=id, url=url, fade=fade, volume=volume)
