from mg.constructor import *
from mg.constructor.interface_classes import *
from mg.constructor.paramobj import ParametrizedObject
import re

re_param_attr = re.compile(r'^p_(.+)')
re_html_attr = re.compile(r'^html_(.+)')
re_dyn_attr = re.compile(r'^dyn_(.+)')
re_perm_attr = re.compile(r'^perm_(.+)')
re_quest_attr = re.compile(r'^q_(.+)')

# Database objects

class DBPlayer(CassandraObject):
    clsname = "Player"
    indexes = {
        "created": [[], "created"],
        "active": [["active"], "last_visit"],
    }

class DBPlayerList(CassandraObjectList):
    objcls = DBPlayer

class DBCharImage(CassandraObject):
    clsname = "CharImage"

class DBCharImageList(CassandraObjectList):
    objcls = DBCharImage

class DBCharParams(CassandraObject):
    clsname = "CharParams"

class DBCharParamsList(CassandraObjectList):
    objcls = DBCharParams

class DBCharacter(CassandraObject):
    clsname = "Character"
    indexes = {
        "created": [[], "created"],
        "player": [["player"], "created"],
        "admin": [["admin"]]
    }

class DBCharacterList(CassandraObjectList):
    objcls = DBCharacter

class DBCharacterForm(CassandraObject):
    clsname = "CharacterForm"

class DBCharacterFormList(CassandraObjectList):
    objcls = DBCharacterForm

class DBCharacterOnline(CassandraObject):
    clsname = "CharacterOnline"
    indexes = {
        "all": [[]]
    }

class DBCharacterOnlineList(CassandraObjectList):
    objcls = DBCharacterOnline

class DBCharacterSettings(CassandraObject):
    clsname = "CharacterSettings"

class DBCharacterSettingsList(CassandraObjectList):
    objcls = DBCharacterSettings

class DBCharacterBusy(CassandraObject):
    clsname = "CharacterBusy"

class DBCharacterBusyList(CassandraObjectList):
    objcls = DBCharacterBusy

# Business logic objects

class Character(Module, ParametrizedObject):
    def __init__(self, app, uuid, fqn="mg.constructor.players.Character"):
        Module.__init__(self, app, fqn)
        ParametrizedObject.__init__(self, "characters")
        self.uuid = uuid

    @property
    def db_character(self):
        try:
            return self._db_character
        except AttributeError:
            self._db_character = self.obj(DBCharacter, self.uuid)
            return self._db_character

    @property
    def db_charimage(self):
        try:
            return self._db_charimage
        except AttributeError:
            self._db_charimage = self.obj(DBCharImage, self.uuid)
            return self._db_charimage

    @property
    def db_params(self):
        try:
            return self._db_params
        except AttributeError:
            self._db_params = self.obj(DBCharParams, self.uuid, silent=True)
            return self._db_params

    @property
    def valid(self):
        try:
            self.db_character
        except ObjectNotFoundException:
            return False
        else:
            return True

    @property
    def db_user(self):
        try:
            return self._db_user
        except AttributeError:
            self._db_user = self.obj(User, self.uuid)
            return self._db_user

    @property
    def db_form(self):
        try:
            return self._db_form
        except AttributeError:
            self._db_form = self.obj(DBCharacterForm, self.uuid, silent=True)
            return self._db_form

    @property
    def name(self):
        try:
            return self._name
        except AttributeError:
            self._name = self.db_user.get("name")
            return self._name

    def name_invalidate(self, **kwargs):
        try:
            del self._name
        except AttributeError:
            pass
        try:
            del self._html
        except AttributeError:
            pass
        self.app().mc.incr_ver("character-name.%s" % self.uuid)
        self.call("character.name-invalidated", self, kwargs)

    @property
    def player(self):
        try:
            return self._player
        except AttributeError:
            uuid = self.db_character.get("player")
            if uuid:
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
            else:
                self._player = None
            return self._player

    @property
    def sex(self):
        try:
            return self._sex
        except AttributeError:
            self._sex = self.db_user.get("sex")
            return self._sex

    def html(self, purpose="default"):
        # local cache
        try:
            html = self._html
        except AttributeError:
            html = {}
            self._html = html
        try:
            return html[purpose]
        except KeyError:
            pass
        # memcached
        mc = self.app().mc
        mcid = "Character.%s.html.%s%s" % (self.uuid, purpose, mc.ver(["character-names", "character-name.%s" % self.uuid]))
        val = mc.get(mcid)
        if not val:
            # evaluation
            params = {
                self.uuid: {}
            }
            template = self.conf("character.name-template-%s" % purpose)
            if template is None:
                pinfo = self.call("characters.name-purpose-%s" % purpose)
                template = pinfo["default"] if pinfo else "{NAME}"
            self.call("characters.name-params", [self], params)
            params = params[self.uuid]
            self.call("characters.name-fixup", self, purpose, params)
            val = self.call("characters.name-render", template, self, params)
            mc.set(mcid, val)
        html[purpose] = val
        return val

    def invalidate_name(self):
        self.app().mc.incr_ver("character-name.%s" % self.uuid)

    @property
    def tech_online(self):
        try:
            return self._tech_online
        except AttributeError:
            try:
                self.obj(DBCharacterOnline, self.uuid)
            except ObjectNotFoundException:
                self._tech_online = False
            else:
                self._tech_online = True
            return self._tech_online

    @property
    def lock(self):
        return "Character.%s" % self.uuid

    @property
    def location(self):
        try:
            return self._location[0]
        except AttributeError:
            self._location = self.call("locations.character_get", self) or [None, None, None]
            return self._location[0]

    @property
    def instance(self):
        try:
            return self._location[1]
        except AttributeError:
            self._location = self.call("locations.character_get", self) or [None, None, None]
            return self._location[1]

    @property
    def location_delay(self):
        try:
            return self._location[2]
        except AttributeError:
            self._location = self.call("locations.character_get", self) or [None, None, None]
            return self._location[2]

    def set_param(self, key, val):
        param = self.call("characters.param", key)
        if not param:
            return None
        res = ParametrizedObject.set_param(self, key, val)
        self.send_param(param, val)
        return res

    def send_param(self, param, val):
        if param.get("owner_visible") and self.call("characters.visibility-condition", param, self):
            if self.tech_online:
                self.call("stream.character", self, "characters", "myparam", param=param["code"], value=val)

    def set_location(self, location, instance=None, delay=None):
        old_location = self.location
        old_instance = self.instance
        self.call("locations.character_before_set", self, location, instance)
        self.call("locations.character_set", self, location, instance, delay)
        self._location = [location, instance, delay]
        self.call("locations.character_after_set", self, old_location, old_instance)
        self.qevent("teleported", char=self, old_loc=old_location, new_loc=location, old_inst=old_instance, new_inst=instance)

    @property
    def busy(self):
        try:
            return self._busy
        except AttributeError:
            self._busy = self.db_busy.get("busy") or None
            return self._busy

    @property
    def db_busy(self):
        try:
            return self._db_busy
        except AttributeError:
            self._db_busy = self.obj(DBCharacterBusy, self.uuid, silent=True)
            return self._db_busy

    @property
    def busy_lock(self):
        return "Busy.Character.%s" % self.uuid

    def set_busy(self, tp, options, dry_run=False):
        old_busy = self.busy
        if old_busy:
            priority = options.get("priority", 0)
            old_priority = old_busy.get("priority", 0)
            if old_priority >= priority:
                return False
            if not dry_run:
                abort = old_busy("abort_event")
                if abort:
                    self.call(abort, self)
        if not dry_run:
            options = options.copy()
            options["tp"] = tp
            self._db_busy.set("busy", options)
            self._db_busy.store()
            self._busy = options
            self.call("character.busy-changed", self)
        return True

    def unset_busy(self):
        self._db_busy.set("busy", None)
        self._db_busy.store()
        self._busy = None
        self.call("character.busy-changed", self)

    @property
    def db_settings(self):
        try:
            return self._db_settings
        except AttributeError:
            self._db_settings = self.obj(DBCharacterSettings, self.uuid, silent=True)
            return self._db_settings

    def invalidate_sessions(self):
        try:
            del self._sessions
        except AttributeError:
            pass

    @property
    def sessions(self):
        try:
            return self._sessions
        except AttributeError:
            self._sessions = []
            self.call("session.character-sessions", self, self._sessions)
            return self._sessions

    @property
    def stream_channels(self):
        return ["id_%s" %i for i in self.sessions]

    @property
    def money(self):
        try:
            return self._money
        except AttributeError:
            self._money = self.call("money.obj", "user", self.uuid)
            return self._money

    @property
    def modifiers(self):
        try:
            return self._modifiers
        except AttributeError:
            self._modifiers = self.call("modifiers.obj", "user", self.uuid)
            return self._modifiers

    @property
    def settings(self):
        try:
            return self._settings
        except AttributeError:
            self._settings = self.obj(DBCharacterSettings, self.uuid, silent=True)
            return self._settings

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "id":
            return self.uuid
        elif attr == "player":
            return self.player
        elif attr == "money":
            return self.money
        elif attr == "location":
            return self.location
        elif attr == "tech_online":
            return self.tech_online
        elif attr == "online":
            return self.tech_online
        elif attr == "name":
            return self.name
        elif attr == "chatname":
            return "[ch:%s]" % self.uuid
        elif attr == "sex":
            return self.sex
        elif attr == "mod" or attr == "modifiers":
            return self.modifiers
        elif attr == "anyperm":
            perms = self.call("auth.permissions", self.uuid)
            return 1 if perms and len(perms) else 0
        elif attr == "inv":
            return self.inventory
        elif attr == "equip":
            return self.equip
        elif attr == "combat":
            busy = self.busy
            if busy:
                return busy.get("combat")
            else:
                return None
        # parameters
        m = re_param_attr.match(attr)
        if m:
            param = m.group(1)
            return self.param(param, handle_exceptions)
        m = re_html_attr.match(attr)
        if m:
            param = m.group(1)
            return self.param_html(param, handle_exceptions)
        m = re_dyn_attr.match(attr)
        if m:
            param = m.group(1)
            return self.param_dyn(param, handle_exceptions)
        # permissions
        m = re_perm_attr.match(attr)
        if m:
            perm = m.group(1)
            perms = self.call("auth.permissions", self.uuid)
            if perms.get(perm) or perms.get("project.admin") or perms.get("global.admin"):
                return 1
            return 0
        # quests
        m = re_quest_attr.match(attr)
        if m:
            qid = m.group(1)
            return self.quests.quest(qid)
        raise AttributeError(attr)

    def script_set_attr(self, attr, val, env):
        # parameters
        m = re_param_attr.match(attr)
        if m:
            param = m.group(1)
            return self.set_param(param, val)
        raise AttributeError(attr)

    def store(self):
        if self.db_params.dirty:
            self.db_params.store()
            self.name_invalidate()

    def __str__(self):
        return "[char %s]" % utf2str(self.name)

    __repr__ = __str__

    def __unicode__(self):
        return u"[char %s]" % str2unicode(self.name)

    @property
    def restraints(self):
        try:
            return self._restraints
        except AttributeError:
            restraints = {}
            self.call("restraints.check", self.uuid, restraints)
            self._restraints = restraints
            return restraints

    def script_params(self):
        return {"char": self}

    @property
    def inventory(self):
        try:
            return self._inventory
        except AttributeError:
            self._inventory = self.call("inventory.get", "char", self.uuid)
            return self._inventory

    @property
    def equip(self):
        try:
            return self._equip
        except AttributeError:
            self._equip = self.call("equip.get", self)
            return self._equip

    @property
    def quests(self):
        try:
            return self._quests
        except AttributeError:
            self._quests = self.call("quests.char", self.uuid)
            return self._quests

    def message(self, content, title=None):
        self.call("stream.character", self, "game", "msg_info", title=title, content=content)

    def error(self, content, title=None):
        self.call("stream.character", self, "game", "msg_error", title=title, content=content)

    def javascript(self, script):
        self.call("stream.character", self, "game", "javascript", script=script)

    def teleport(self, *args, **kwargs):
        self.call("teleport.character", self, *args, **kwargs)

    def main_open(self, uri):
        self.call("stream.character", self, "game", "main_open", uri=uri)

    def combat_member(self):
        return {
            "object": ["character", self.uuid],
            "name": self.name,
            "sex": self.sex
        }

    def deliverable_params(self):
        return self.call("characters.deliverable-params", self)

class Player(Module):
    def __init__(self, app, uuid, fqn="mg.constructor.players.Player"):
        Module.__init__(self, app, fqn)
        self.uuid = uuid

    @property
    def db_player(self):
        try:
            return self._db_player
        except AttributeError:
            self._db_player = self.obj(DBPlayer, self.uuid)
            return self._db_player

    @property
    def valid(self):
        try:
            self.db_player
        except ObjectNotFoundException:
            return False
        else:
            return True

    @property
    def db_user(self):
        try:
            return self._db_user
        except AttributeError:
            self._db_user = self.obj(User, self.uuid)
            return self._db_user

    @property
    def email(self):
        try:
            return self._email
        except AttributeError:
            self._email = self.db_user.get("email")
            return self._email

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "id":
            return self.uuid
        elif attr == "mod" or attr == "modifiers":
            return self.call("modifiers.obj", self.uuid)
        else:
            raise AttributeError(attr)

    def __str__(self):
        return "[player %s]" % self.uuid
    
    __repr__ = __str__

    @property
    def characters(self):
        try:
            return self._characters
        except AttributeError:
            try:
                req = self.req()
                try:
                    characters = req.character
                except AttributeError:
                    characters = {}
                    req.characters = characters
            except AttributeError:
                characters = {}
            lst = self.objlist(DBCharacterList, query_index="player", query_equal=self.uuid)
            chars = []
            for ent in lst:
                character = characters.get(ent.uuid)
                if not character:
                    character = Character(self.app(), ent.uuid)
                    characters[ent.uuid] = character
                chars.append(character)
            self._characters = chars
            return chars

class Characters(Module):
    def __init__(self, app, fqn="mg.constructor.players.Characters"):
        Module.__init__(self, app, fqn)

    @property
    def tech_online(self):
        try:
            return self._tech_online
        except AttributeError:
            self._tech_online = []
            self.call("auth.characters-tech-online", self._tech_online)
            return self._tech_online

