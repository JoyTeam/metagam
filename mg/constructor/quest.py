from mg import *
from mg.constructor import *
import re

re_find_tags = re.compile(r'{(NAME|NAME_CHAT|GENDER:[^}]+)}')
re_gender = re.compile(r'^GENDER:(.+)$')
re_name = re.compile(r'^NAME$')
re_name_chat = re.compile(r'^NAME_CHAT$')

class QuestParserVariables(ConstructorModule):
    def __init__(self, app, kwargs, fqn="mg.constructor.quest.QuestParserVariables"):
        Module.__init__(self, app, fqn)
        self.kwargs = kwargs

    @property
    def character(self):
        try:
            return self._character
        except AttributeError:
            self._character = ConstructorModule.character(self, self.kwargs["character"])
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
