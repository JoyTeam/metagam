from mg.mmorpg.combats.core import CombatMemberController
from mg.constructor.script_classes import ScriptRuntimeError

class AIController(CombatMemberController):
    def __init__(self, member, aitype, fqn="mg.mmorpg.combats.ai.AIController"):
        CombatMemberController.__init__(self, member, fqn)
        self.aitype = aitype

    @property
    def ai_types(self):
        try:
            return self._ai_types
        except AttributeError:
            pass
        self._ai_types = self.conf("combats-%s.ai-types" % self.combat.rules, [])
        return self._ai_types

    @property
    def ai_description(self):
        try:
            return self._ai_description
        except AttributeError:
            pass
        for ai_type in self.ai_types:
            if ai_type["code"] == self.aitype:
                self._ai_description = ai_type
                return self._ai_description
        return {}

    def script_code(self, tag):
        return self.ai_description.get("script-%s" % tag, [])

    def execute_script(self, tag, globs, description=None):
        self.call("combats.execute-script", self.combat, self.script_code(tag), globs, description=description)

    def globs(self):
        globs = self.combat.globs()
        globs["member"] = self.member
        return globs

    def turn_got(self):
        globs = self.globs()
        self.execute_script("turn-got", globs, lambda: self._("AI '%s' script when it has got turn right") % self.aitype)
