from mg import *
from mg.constructor import *
import re

re_find_tags = re.compile(r'{(NAME|NAME_CHAT|GENDER:[^}]+|LOCATION(?:|_G|_A|_W|_T|_F))}')
re_gender = re.compile(r'^GENDER:(.+)$')
re_name = re.compile(r'^NAME$')
re_name_chat = re.compile(r'^NAME_CHAT$')
re_location = re.compile(r'^LOCATION(|_G|_A|_W|_T|_F)$')

class QuestParserVariables(ConstructorModule):
    def __init__(self, app, kwargs, fqn="mg.constructor.quest.QuestParserVariables"):
        Module.__init__(self, app, fqn)
        self.kwargs = kwargs

    @property
    def character(self):
        try:
            return self._character
        except AttributeError:
            if self.kwargs.get("character"):
                self._character = self.kwargs["character"]
            else:
                self._character = None
            return self._character

    @property
    def gender(self):
        try:
            return self._gender
        except AttributeError:
            if self.kwargs.get("character"):
                self._gender = self.character.sex
            else:
                self._gender = 0
            return self._gender

    @property
    def name(self):
        try:
            return self._name
        except AttributeError:
            if self.kwargs.get("character"):
                self._name = self.character.name
            else:
                self._name = None
            return self._name

    @property
    def chat_name(self):
        try:
            return self._chat_name
        except AttributeError:
            if self.kwargs.get("character"):
                self._chat_name = "[ch:%s]" % self.character.uuid
            else:
                self._chat_name = None
            return self._chat_name

    @property
    def loc(self):
        try:
            return self._location
        except AttributeError:
            self._location = self.kwargs.get("location")
            return self._location

class QuestEngine(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("quest.format_text", self.format_text)

    def format_text(self, text, **kwargs):
        tokens = []
        start = 0
        variables = QuestParserVariables(self.app(), kwargs)
        for match in re_find_tags.finditer(text):
            match_start, match_end = match.span()
            if match_start > start:
                tokens.append(text[start:match_start])
            start = match_end
            if self.sub(re_name, self.name, match.group(1), tokens, variables):
                continue
            if self.sub(re_name_chat, self.name_chat, match.group(1), tokens, variables):
                continue
            if self.sub(re_gender, self.gender, match.group(1), tokens, variables):
                continue
            if self.sub(re_location, self.loc, match.group(1), tokens, variables):
                continue
            tokens.append(text[match_start:match_end])
        if len(text) > start:
            tokens.append(text[start:])
        return u"".join(tokens)

    def sub(self, regexp, handler, token, tokens, variables):
        m = regexp.match(token)
        if m:
            res = handler(m, variables)
            if res is None:
                res = ""
            tokens.append(res)
            return True
        else:
            return False

    def gender(self, match, variables):
        lst = match.group(1).split(",")
        gender = variables.gender
        if gender > len(lst) or gender < 0:
            return lst[0]
        else:
            return lst[gender]

    def name(self, match, variables):
        return variables.name

    def name_chat(self, match, variables):
        return variables.chat_name

    def loc(self, match, variables):
        loc = variables.loc
        if loc is None:
            return ""
        tp = match.group(1)
        if tp == "_G":
            return loc.name_w
        elif tp == "_A":
            return loc.name_a
        elif tp == "_W":
            return loc.name_w
        elif tp == "_T":
            return loc.name_t
        elif tp == "_F":
            return loc.name_f
        else:
            return loc.name
