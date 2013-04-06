import mg.constructor
import hashlib

class SoundAdmin(mg.constructor.ConstructorModule):
    def register(self):
        pass

class Sound(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("sound.play", self.play)

    def child_modules(self):
        return ["mg.constructor.sound.SoundAdmin"]

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("sound")

    def play(self, char, url, mode=None):
        m = hashlib.md5()
        m.update(url)
        self.call("stream.packet", "global", "sound", "play", id=m.hexdigest(), url=url, mode=mode)
