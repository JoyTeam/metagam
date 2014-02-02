#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

from mg.constructor import *
from mg.mmorpg.quest_parser import *
from mg.core.money_classes import MoneyError
from mg.mmorpg.combats.daemon import CombatRequest, CombatInterface
from mg.mmorpg.combats.core import CombatRunError, CombatMemberBusyError, CombatUnavailable
from mg.constructor.script_classes import ScriptMemoryObject
from uuid import uuid4
import re
import random
import stackless
from concurrence import Tasklet

re_info = re.compile(r'^([a-z0-9_]+)/(.+)$', re.IGNORECASE)
re_state = re.compile(r'^state/(.+)$', re.IGNORECASE)
re_param = re.compile(r'^p_(.+)$')
re_del = re.compile(r'del/(.+)$')
re_item_action = re.compile(r'^([a-z0-9_]+)/(.+)$', re.IGNORECASE)
re_mod_timer = re.compile(r'^timer-(.+)-(.+)$')
re_mod_lock = re.compile(r'^q_(.+)_locked$')
re_remove_dialog = re.compile(r'^([a-z0-9]+)/([a-z0-9]+)$')
re_remove_lock = re.compile(r'^user/([a-f0-9]{32})/(.+)$')
re_arg_param = re.compile(r'^arg_(.+)$')
re_valid_identifier = re.compile(r'^[a-z_][a-z0-9\_]*$', re.IGNORECASE)

class DBCharQuests(CassandraObject):
    clsname = "CharQuests"

class DBCharQuestsList(CassandraObjectList):
    objcls = DBCharQuests

class QuestSystemError(Exception):
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return self.val

class QuestError(Exception):
    def __init__(self, val):
        self.val = val

class AbortHandler(Exception):
    pass

class CharActivity(ConstructorModule):
    def __init__(self, app, char):
        Module.__init__(self, app, "mg.mmorpg.quests.CharActivity")
        self.char = char

    @property
    def lock_key(self):
        return "CharActivity.%s" % self.char.uuid

    def store(self):
        self.char.db_busy.store()

    @property
    def state(self):
        busy = self.char.busy
        if not busy or busy["tp"] != "activity":
            return {}
        return busy["vars"]

    @property
    def handlers(self):
        busy = self.char.busy
        if not busy or busy["tp"] != "activity":
            return {}
        return busy["hdls"]

    def script_attr(self, attr, handle_exceptions=True):
        busy = self.char.busy
        if not busy or busy["tp"] != "activity":
            raise QuestError(self._("Cannot access '{attr}' attribute because of missing activity").format(attr=attr))
        if re_param.match(attr):
            if attr in busy["vars"]:
                return busy["vars"].get(attr)
            elif handle_exceptions:
                return None
            else:
                raise AttributeError(attr)
        else:
            raise AttributeError(attr)

    def script_set_attr(self, attr, val, env):
        busy = self.char.busy
        if not busy or busy["tp"] != "activity":
            raise QuestError(self._("Cannot set '{attr}' attribute because of missing activity").format(attr=attr))
        m = re_param.match(attr)
        if m:
            busy["vars"][attr] = val
            self.char.db_busy.touch()
        else:
            raise AttributeError(attr)

    def __str__(self):
        return u"%s.[activity]" % htmlescape(self.char)

    __repr__ = __str__

class CharQuests(ConstructorModule):
    def __init__(self, app, uuid):
        Module.__init__(self, app, "mg.mmorpg.quests.CharQuests")
        self.uuid = uuid

    @property
    def lock_key(self):
        return "CharQuests.%s" % self.uuid

    @property
    def char(self):
        try:
            return self._char
        except AttributeError:
            self._char = self.character(self.uuid)
            return self._char

    def load(self):
        try:
            self._quests = self.obj(DBCharQuests, self.uuid)
        except ObjectNotFoundException:
            self._quests = self.obj(DBCharQuests, self.uuid, data={})

    def touch(self):
        self._quests.touch()

    def store(self):
        self._quests.store()

    def state(self, qid):
        if not getattr(self, "_quests", None):
            self.load()
        quest = self._quests.get(qid)
        if quest is None:
            return {"state": "init"}
        else:
            return quest

    def get(self, qid, param, default=None):
        if not getattr(self, "_quests", None):
            self.load()
        quest = self._quests.get(qid)
        if quest is None:
            return default
        else:
            return quest.get(param, default)

    def set(self, qid, param, val):
        if not getattr(self, "_quests", None):
            self.load()
        quest = self._quests.get(qid)
        if quest is None:
            if param != "state":
                raise QuestError(self._("Quest '{quest}' is not taken yet when trying to set attribute {attr}").format(quest=qid, attr=param))
            old_val = "init"
            self._quests.set(qid, {param: val})
        else:
            old_val = quest.get(param)
            quest[param] = val
            self.touch()
        return old_val

    def destroy(self, qid):
        if not getattr(self, "_quests", None):
            self.load()
        self._quests.delkey(qid)

    def touch(self):
        self._quests.touch()

    def quest(self, qid):
        return CharQuest(self, qid)

    def locked(self, qid):
        return self.char.modifiers.get("q_%s_locked" % qid)

    def lock(self, qid, timeout=None):
        if timeout is None:
            till = None
        else:
            timeout = intz(timeout)
            if timeout <= 0:
                return
            till = self.now(timeout)
        self.char.modifiers.add("q_%s_locked" % qid, 1, till)

    @property
    def dialogs(self):
        if not getattr(self, "_quests", None):
            self.load()
        dialogs = self._quests.get(":dialogs")
        if dialogs is None:
            dialogs = []
            self._quests.set(":dialogs", dialogs)
        return dialogs

    @property
    def finished(self):
        if not getattr(self, "_quests", None):
            self.load()
        finished = self._quests.get(":finished")
        if finished is None:
            finished = {}
            self._quests.set(":finished", finished)
        return finished

    def add_finished(self, qid):
        self.finished[qid] = {
            "performed": self.now(),
        }
        self.touch()

    def dialog(self, dialog, quest=None):
        dialog["uuid"] = uuid4().hex
        if quest:
            dialog["quest"] = quest
        if not dialog.get("buttons"):
            dialog["buttons"] = [
                {
                    "text": self._("Close")
                }
            ]
        # remove other dialogs from the same quest
        dialogs = self.dialogs
        if quest:
            dialogs = [ent for ent in dialogs if ent.get("quest") != quest or ent.get("type") != None]
        dialogs.insert(0, dialog)
        self._quests.set(":dialogs", dialogs)

    def itemselector(self, dialog, quest=None):
        dialog["uuid"] = uuid4().hex
        dialog["type"] = "itemselector"
        if quest:
            dialog["quest"] = quest
        # remove other dialogs from the same quest
        dialogs = self.dialogs
        if quest:
            dialogs = [ent for ent in dialogs if ent.get("quest") != quest or ent.get("type") != "itemselector"]
        dialogs.insert(0, dialog)
        self._quests.set(":dialogs", dialogs)

class CharQuest(object):
    def __init__(self, quests, qid):
        self.quests = quests
        self.qid = qid

    def script_attr(self, attr, handle_exceptions=True):
        if attr == "state":
            return self.quests.get(self.qid, attr, "init")
        elif attr == "locked":
            return 1 if self.locked else 0
        elif attr == "notlocked":
            return 0 if self.locked else 1
        elif attr == "finished":
            return 1 if self.finished else 0
        elif attr == "notfinished":
            return 0 if self.finished else 1
        else:
            m = re_param.match(attr)
            if m:
                param = m.group(1)
                return self.quests.get(self.qid, param)
            if handle_exceptions:
                return None
            else:
                raise AttributeError(attr)

    def script_set_attr(self, attr, val, env):
        if attr == "state":
            attr = "p_state"
        m = re_param.match(attr)
        if m:
            param = m.group(1)
            return self.quests.set(self.qid, param, val)
        else:
            raise AttributeError(attr)

    def store(self):
        self.quests.store()

    def __str__(self):
        return u"%s.[quest %s]" % (htmlescape(self.quests.char), self.qid)

    __repr__ = __str__

    @property
    def locked(self):
        return self.quests.locked(self.qid)

    @property
    def finished(self):
        return self.quests.finished.get(self.qid)

def parse_quest_tp(qid, tp):
    if tp[0] == "event":
        return "event-%s-%s" % (qid, tp[1])
    elif tp[0] == "expired":
        if tp[1] == "timer":
            return "expired-timer-%s-%s" % (qid, tp[2])
    elif tp[0] == "button":
        return "button-%s-%s" % (qid, tp[1])
    return "-".join(tp)

class QuestsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-quests.index", self.menu_quests_index)
        self.rhook("menu-admin-inventory.index", self.menu_inventory_index)
        self.rhook("headmenu-admin-quests.editor", self.headmenu_quests_editor)
        self.rhook("ext-admin-quests.editor", self.admin_quests_editor, priv="quests.editor")
        self.rhook("advice-admin-quests.index", self.advice_quests)
        self.rhook("quest-admin.script-field", self.quest_admin_script_field)
        self.rhook("quest-admin.unparse-script", self.quest_admin_unparse_script)
        if self.conf("module.inventory"):
            self.rhook("ext-admin-inventory.actions", self.admin_inventory_actions, priv="quests.inventory")
            self.rhook("headmenu-admin-inventory.actions", self.headmenu_inventory_actions)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("admin-modifiers.descriptions", self.mod_descriptions)
        self.rhook("ext-admin-quests.removedialog", self.remove_dialog, priv="quests.dialogs")
        self.rhook("admin-locations.map-zone-actions", self.location_map_zone_actions, priority=20)
        self.rhook("admin-locations.map-zone-action-event", self.location_map_zone_action_event)
        self.rhook("admin-locations.map-zone-event-render", self.location_map_zone_event_render)
        self.rhook("admin-interface.button-actions", self.interface_button_actions)
        self.rhook("admin-interface.button-action-qevent", self.interface_button_action_qevent)
        self.rhook("admin-interface.button-action", self.interface_button_action)
        self.rhook("ext-admin-quests.remove-lock", self.admin_remove_lock, priv="quests.remove-locks")
        self.rhook("admin-gameinterface.design-files", self.design_files)
        self.rhook("quest-admin.update-quest-handlers", self.update_quest_handlers)
        self.rhook("ext-admin-quests.abort-activity", self.abort_activity, priv="quests.abort-activities")
        self.rhook("advice-admin-crafting.index", self.advice_activities)
        self.rhook("advice-admin-quests.index", self.advice_activities)

    def advice_activities(self, hook, args, advice):
        advice.append({"title": self._("Activities documentation"), "content": self._('You can find detailed information on the activities system in the <a href="//www.%s/doc/activities" target="_blank">activities page</a> in the reference manual.') % self.main_host, "order": 20})

    def design_files(self, files):
        files.append({"filename": "dialog.html", "description": self._("Quest dialog"), "doc": "/doc/quests"})
        files.append({"filename": "quests.html", "description": self._("Quests list"), "doc": "/doc/quests"})

    def interface_button_action(self, btn):
        if btn.get("qevent"):
            raise Hooks.Return("qevent")

    def interface_button_actions(self, button, actions, fields):
        actions.append(("qevent", self._("Call 'clicked' quest event")))
        fields.append({"name": "qevent", "label": self._("Event identifier"), "value": button.get("qevent") if button else None, "condition": "[[action]]=='qevent'"})

    def interface_button_action_qevent(self, btn, errors):
        req = self.req()
        key = "qevent"
        ev = req.param(key).strip()
        if not ev:
            errors[key] = self._("Event identifier not specified")
        elif not re_valid_identifier.match(ev):
            errors[key] = self._("Event identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
        else:
            btn["qevent"] = ev
        return True

    def location_map_zone_actions(self, location, actions):
        actions.append(("event", jsencode(self._("Call 'clicked' quest event"))))

    def location_map_zone_action_event(self, zone_id, zone, errors):
        req = self.req()
        key = "event-%d" % zone_id
        ev = req.param(key).strip()
        if not ev:
            errors[key] = self._("Event identifier not specified")
        elif not re_valid_identifier.match(ev):
            errors[key] = self._("Event identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
        else:
            zone["ev"] = ev
        return True

    def location_map_zone_event_render(self, zone, rzone):
        rzone["ev"] = jsencode(zone.get("ev"))

    def admin_remove_lock(self):
        req = self.req()
        m = re_remove_lock.match(req.args)
        if not m:
            self.call("web.not_found")
        target_uuid, mod_kind = m.group(1, 2)
        character = self.character(target_uuid)
        if not character.valid:
            self.call("web.not_found")
        character.modifiers.destroy(mod_kind)
        self.call("admin.redirect", "auth/user-dashboard/%s?active_tab=modifiers" % target_uuid)

    def mod_descriptions(self, modifiers, mods):
        req = self.req()
        for key, mod in mods.iteritems():
            m = re_mod_timer.match(key)
            if m:
                qid, tid = m.group(1, 2)
                quest = self.conf("quests.list", {}).get(qid)
                if quest:
                    mod["description"] = self._("Timer '{timer}' in quest '{quest}'").format(timer=tid, quest=htmlescape(quest.get("name")))
            else:
                m = re_mod_lock.match(key)
                if m:
                    qid = m.group(1)
                    quest = self.conf("quests.list", {}).get(qid)
                    if quest:
                        mod["description"] = utf2str(self._("Quest '{quest}' is locked").format(quest=htmlescape(quest.get("name"))))
                        if req.has_access("quests.remove-locks"):
                            mod["description"] += utf2str(self.call("web.parse_inline_layout", u' (<hook:admin.link href="quests/remove-lock/%s/%s/%s" title="%s" confirm="%s" />)' % (modifiers.target_type, modifiers.uuid, key, self._("remove lock"), self._("Are you sure want to remove this lock?")), {}))

    def permissions_list(self, perms):
        perms.append({"id": "quests.view", "name": self._("Quest engine: viewing players' quest information")})
        perms.append({"id": "quests.editor", "name": self._("Quest engine: editor")})
        perms.append({"id": "quests.dialogs", "name": self._("Quest engine: clearing users' dialogs")})
        perms.append({"id": "quests.remove-locks", "name": self._("Quest engine: removing quest locks")})
        if self.conf("module.inventory"):
            perms.append({"id": "quests.inventory", "name": self._("Quest engine: actions for items")})
        perms.append({"id": "quests.abort-activities", "name": self._("Quest engine: aborting activities")})

    def menu_root_index(self, menu):
        menu.append({"id": "quests.index", "text": self._("Quests and triggers"), "order": 25})

    def menu_quests_index(self, menu):
        req = self.req()
        if req.has_access("quests.editor"):
            menu.append({"id": "quests/editor", "text": self._("Quests editor"), "order": 20, "leaf": True})

    def menu_inventory_index(self, menu):
        if self.conf("module.inventory"):
            req = self.req()
            if req.has_access("quests.inventory"):
                menu.append({"id": "inventory/actions", "text": self._("Actions for items"), "order": 30, "leaf": True})

    def advice_quests(self, hook, args, advice):
        advice.append({"title": self._("Scripts documentation"), "content": self._('You can find detailed information on the scripting engine in the <a href="//www.%s/doc/script" target="_blank">scripting engine page</a> in the reference manual.') % self.main_host, "order": 10})
        advice.append({"title": self._("Quests documentation"), "content": self._('You can find detailed information on the quests engine in the <a href="//www.%s/doc/quests" target="_blank">quests engine page</a> in the reference manual.') % self.main_host, "order": 20})

    def headmenu_quests_editor(self, args):
        if args == "new":
            return [self._("New quest"), "quests/editor"]
        elif args:
            m = re_info.match(args)
            if m:
                qid, cmd = m.group(1, 2)
                if cmd == "info":
                    quest = self.conf("quests.list", {}).get(qid)
                    if quest:
                        return [htmlescape(quest["name"]), "quests/editor"]
                else:
                    m = re_state.match(cmd)
                    if m:
                        cmd = m.group(1)
                        if cmd == "new":
                            return [self._("New state"), "quests/editor/%s/info" % qid]
                        else:
                            m = re_info.match(cmd)
                            if m:
                                pass
                            else:
                                return [self._("State %s") % cmd, "quests/editor/%s/info" % qid]
            else:
                return [self._("Parameters"), "quests/editor/%s/info" % htmlescape(args)]
        return self._("Quests")

    def admin_quests_editor(self):
        req = self.req()
        if req.args:
            with self.lock(["QuestsEditor"]):
                m = re_info.match(req.args)
                if m:
                    return self.admin_quest_editor(m.group(1), m.group(2))
                quest_list = self.conf("quests.list", {})
                if req.args == "new":
                    order = None
                    for quest in quest_list.values():
                        if order is None or quest.get("order", 0) > order:
                            order = quest.get("order", 0)
                    quest = {
                        "order": 0 if order is None else order + 10.0
                    }
                else:
                    quest = quest_list.get(req.args)
                    if not quest:
                        self.call("admin.redirect", "quests/editor")
                if req.ok():
                    errors = {}
                    # id
                    qid = req.param("id").strip()
                    if not qid:
                        errors["id"] = self._("This field is mandatory")
                    elif qid == "new":
                        errors["id"] = self._("Identifer 'new' is reserved")
                    elif not re_valid_identifier.match(qid):
                        errors["id"] = self._("Quest identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
                    elif qid != req.args and qid in quest_list:
                        errors["id"] = self._("Quest with the same identifier already exists")
                    # name
                    name = req.param("name").strip()
                    if not name:
                        errors["name"] = self._("This field is mandatory")
                    else:
                        quest["name"] = name
                    # order
                    quest["order"] = floatz(req.param("order"))
                    # flags
                    quest["enabled"] = True if req.param("enabled") else False
                    # availability
                    char = self.character(req.user())
                    quest["available"] = self.call("script.admin-expression", "available", errors, globs={"char": char})
                    if errors:
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # storing
                    config = self.app().config_updater()
                    if req.param("debug"):
                        config.set("quests.debug_%s" % qid, True)
                    else:
                        config.delete("quests.debug_%s" % qid)
                    if req.args == "new":
                        quest_list[qid] = quest
                    else:
                        if req.args != qid:
                            del quest_list[req.args]
                            quest_list[qid] = quest
                            old_states = self.conf("quest-%s.states" % req.args)
                            if old_states is not None:
                                config.delete("quest-%s.states" % req.args)
                                config.set("quest-%s.states" % qid, old_states)
                    config.set("quests.list", quest_list)
                    self.update_quest_handlers(config)
                    config.store()
                    self.call("admin.redirect", "quests/editor/%s/info" % qid)
                fields = [
                    {"name": "id", "value": "" if req.args == "new" else req.args, "label": self._("Quest identifier")},
                    {"name": "order", "value": quest.get("order", 0), "label": self._("Sorting order"), "inline": True},
                    {"name": "name", "value": quest.get("name"), "label": self._("Quest name")},
                    {"name": "enabled", "checked": quest.get("enabled"), "label": self._("Quest is enabled"), "type": "checkbox"},
                    {"name": "debug", "checked": True if req.args == "new" else self.conf("quests.debug_%s" % req.args), "label": self._("Write debugging information to the debug channel"), "type": "checkbox", "inline": True},
                    {"name": "available", "value": self.call("script.unparse-expression", quest.get("available", 1)), "label": self._("Quest is available for the character") + self.call("script.help-icon-expressions")},
                ]
                self.call("admin.form", fields=fields)
        rows = []
        quest_list = [(qid, quest) for qid, quest in self.conf("quests.list", {}).iteritems()]
        quest_list.sort(cmp=lambda x, y: cmp(x[1].get("order", 0), y[1].get("order", 0)) or cmp(x[1].get("name"), y[1].get("name")) or cmp(x[0], y[0]))
        for qid, quest in quest_list:
            qid_html = qid
            name_html = htmlescape(quest["name"])
            if quest.get("enabled"):
                qid_html = u'<span class="admin-enabled">%s</span>' % qid_html
                name_html = u'<span class="admin-enabled">%s</span>' % name_html
            rows.append([
                qid_html,
                name_html,
                quest.get("order", 0.0),
                u'<hook:admin.link href="quests/editor/%s/info" title="%s" />' % (qid, self._("open")),
                u'<hook:admin.link href="quests/editor/%s/del" title="%s" confirm="%s" />' % (qid, self._("delete"), self._("Are you sure want to delete this quest?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "quests/editor/new", "text": self._("New quest"), "lst": True}
                    ],
                    "header": [
                        self._("Quest ID"),
                        self._("Quest name"),
                        self._("Order"),
                        self._("Opening"),
                        self._("Deletion"),
                    ],
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def update_quest_handlers(self, config):
        events = set(config.get("quests.events", []))
        handlers = {}
        for qid, quest in config.get("quests.list", {}).iteritems():
            if not quest.get("enabled"):
                continue
            for sid, state in config.get("quest-%s.states" % qid, {}).iteritems():
                script = state.get("script")
                if script:
                    if script[0] != "state":
                        raise RuntimeError(self._("Invalid quest states object. Expected {expected}. Found: {found}").format(expected="state", found=script[0]))
                    if "hdls" in script[1]:
                        for handler in script[1]["hdls"]:
                            if handler[0] == "comment":
                                continue
                            if handler[0] != "hdl":
                                raise RuntimeError(self._("Invalid quest states object. Expected {expected}. Found: {found}").format(expected="hdl", found=script[0]))
                            tp = handler[1]["type"]
                            tp = parse_quest_tp(qid, tp)
                            events.add(tp)
                            try:
                                handlers[tp].add((qid, sid))
                            except KeyError:
                                handlers[tp] = set([(qid, sid)])
        for event in events:
            lst = handlers.get(event)
            if lst:
                config.set("qevent-%s.handlers" % event, [[qid, sid] for qid, sid in lst])
            else:
                config.delete("qevent-%s.handlers" % event)
        config.set("quests.events", handlers.keys())

    def admin_quest_editor(self, qid, cmd):
        req = self.req()
        if cmd == "del":
            config = self.app().config_updater()
            lst = self.conf("quests.list", {})
            try:
                del lst[qid]
            except KeyError:
                pass
            config.set("quests.list", lst)
            config.delete("quest-%s.states" % qid)
            self.update_quest_handlers(config)
            config.store()
            self.call("admin.redirect", "quests/editor")
        elif cmd == "info":
            quest_list = self.conf("quests.list", {})
            quest = quest_list.get(qid)
            if not quest:
                self.call("admin.redirect", "quests/editor")
            rows = []
            states = [(sid, state) for sid, state in self.conf("quest-%s.states" % qid, {}).iteritems()]
            states.sort(cmp=lambda x, y: cmp(x[1].get("order", 0), y[1].get("order", 0)) or cmp(x[0], y[0]))
            for sid, state in states:
                rows.append([
                    sid,
                    u'<hook:admin.link href="quests/editor/%s/state/%s" title="%s" />' % (qid, sid, self._("edit")),
                    u'<hook:admin.link href="quests/editor/%s/state/%s/del" title="%s" confirm="%s" />' % (qid, sid, self._("delete"), self._("Are you sure want to delete this state?")),
                ])
            vars = {
                "tables": [
                    {
                        "links": [
                            {"hook": "quests/editor/%s" % qid, "text": self._("Edit quest parameters")},
                            {"hook": "quests/editor/%s/state/new" % qid, "text": self._("New quest state"), "lst": True}
                        ],
                        "header": [
                            self._("State"),
                            self._("Editing"),
                            self._("Deletion"),
                        ],
                        "rows": rows
                    }
                ]
            }
            self.call("admin.response_template", "admin/common/tables.html", vars)
        else:
            m = re_state.match(cmd)
            if m:
                cmd = m.group(1)
                states = self.conf("quest-%s.states" % qid, {})
                m = re_info.match(cmd)
                if m:
                    sid, cmd = m.group(1, 2)
                    if cmd == "del":
                        config = self.app().config_updater()
                        try:
                            del states[sid]
                        except KeyError:
                            pass
                        config.set("quest-%s.states" % qid, states)
                        self.update_quest_handlers(config)
                        config.store()
                        self.call("admin.redirect", "quests/editor/%s/info" % qid)
                    self.call("admin.redirect", "quests/editor/%s/info" % qid)
                if cmd == "new":
                    order = 0
                    for state in states.values():
                        if order is None or state.get("order", 0) > order:
                            order = state.get("order", 0)
                    show_sid = "" if states else "init"
                    state = {
                        "order": order + 10
                    }
                else:
                    state = states.get(cmd)
                    if state is None:
                        self.call("admin.redirect", "quests/editor/%s/info" % qid)
                    show_sid = cmd
                if req.ok():
                    errors = {}
                    # id
                    sid = req.param("id").strip()
                    if not sid:
                        errors["id"] = self._("This field is mandatory")
                    elif sid == "new":
                        errors["id"] = self._("Identifer 'new' is reserved")
                    elif not re_valid_identifier.match(sid):
                        errors["id"] = self._("State identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
                    elif sid != cmd and sid in states:
                        errors["id"] = self._("State with the same identifier already exists")
                    # order
                    state["order"] = floatz(req.param("order"))
                    # description
                    char = self.character(req.user())
                    if sid == "init":
                        if "description" in state:
                            del state["description"]
                    else:
                        state["description"] = self.call("script.admin-text", "description", errors, globs={"char": char, "quest": char.quests.quest(qid)}, mandatory=False)
                    # script
                    state["script"] = self.call("quest-admin.script-field", "script", errors, globs={"char": char}, mandatory=False)
                    if errors:
                        self.call("web.response_json", {"success": False, "errors": errors})
                    # storing
                    config = self.app().config_updater()
                    if cmd == "new":
                        states[sid] = state
                    else:
                        if cmd != sid:
                            del states[cmd]
                            states[sid] = state
                    config.set("quest-%s.states" % qid, states)
                    self.update_quest_handlers(config)
                    config.store()
                    self.call("admin.redirect", "quests/editor/%s/info" % qid)
                fields = [
                    {"name": "id", "value": show_sid, "label": self._("State identifier")},
                    {"name": "order", "value": state.get("order"), "label": self._("Sorting order"), "inline": True},
                    {"name": "script", "value": self.call("quest-admin.unparse-script", state.get("script")), "type": "textarea", "label": self._("Quest script") + self.call("script.help-icon-expressions", "quests"), "height": 300},
                    {"name": "description", "value": self.call("script.unparse-text", state.get("description")), "type": "textarea", "label": self._("Quest state description for the quest log (for instance, task for player)") + self.call("script.help-icon-expressions"), "condition": "[id]!='init'"},
                ]
                self.call("admin.form", fields=fields)
        self.call("admin.redirect", "quests/editor/%s/info" % qid)

    def quest_admin_script_field(self, name, errors, globs={}, expression=None, mandatory=True):
        req = self.req()
        if expression is None:
            expression = req.param(name).strip()
        if mandatory and expression == "":
            errors[name] = self._("This field is mandatory")
            return
        # Parsing
        try:
            expression = self.call("quests.parse-script", expression)
        except ScriptParserError as e:
            html = e.val.format(**e.kwargs)
            if e.exc:
                html += "\n%s" % e.exc
            errors[name] = html
            return
        # Evaluating
        try:
            env = ScriptEnvironment()
            env.globs = globs
            self.quest_script_validate(expression, env)
        except ScriptError as e:
            errors[name] = e.val
            return
        # Returning result
        return expression

    def quest_script_validate(self, val, env):
        if type(val) != list:
            raise ScriptParserError(self._("Script validation error. Expected list, received %s") % type(val).__name__)
        objtype = val[0]
        if objtype == "state":
            if val[1].get("hdls"):
                for handler in val[1]["hdls"]:
                    if handler[0] == "comment":
                        continue
                    if handler[0] != "hdl":
                        raise ScriptError(self._("Handler expected in the handlers list. Received: %s") % handler[0], env)
                    self.quest_script_validate(handler, env)
        elif objtype == "hdl":
            if val[1].get("act"):
                for act in val[1]["act"]:
                    self.quest_script_validate(act, env)

    def unparse_member(self, member):
        mtype = member["type"]
        if mtype[0] == "virtual":
            mtype = "virtual"
        elif mtype[0] == "expr":
            mtype = self.call("script.unparse-expression", mtype[1])
        else:
            mtype = "??? (%s)" % mtype[0]
        result = "member %s" % mtype
        if "team" in member:
            result += " team=%s" % self.call("script.unparse-expression", member["team"])
        if "control" in member:
            result += " control=%s" % self.call("script.unparse-expression", member["control"])
        if "name" in member:
            result += " name=%s" % self.call("script.unparse-expression", self.call("script.unparse-text", member["name"]))
        if "sex" in member:
            result += " sex=%s" % self.call("script.unparse-expression", member["sex"])
        if "ai" in member:
            result += " ai=%s" % self.call("script.unparse-expression", member["ai"])
        if "image" in member:
            result += " image=%s" % self.call("script.unparse-expression", member["image"])
        if "params" in member:
            params = member["params"]
            for key in sorted(params.keys()):
                result += " %s=%s" % (key, self.call("script.unparse-expression", params[key]))
        return result

    def quest_admin_unparse_script(self, val, indent=0):
        if val is None:
            return ""
        if type(val) != list:
            raise ScriptParserError(self._("Script unparse error. Expected list, received %s") % type(val).__name__)
        if len(val) == 0 or type(val[0]) == list:
            # list of objects
            result = u""
            last_comment = False
            for ent in val:
                is_comment = type(ent) is list and ent[0] == "comment"
                if is_comment and len(result) and not last_comment:
                    result += "\n"
                last_comment = is_comment
                result += self.quest_admin_unparse_script(ent, indent)
            return result
        else:
            objtype = val[0]
            if val[0] == "state":
                return self.quest_admin_unparse_script(val[1].get("hdls"))
            elif val[0] == "comment":
                return "%s#%s%s\n" % (
                    "  " * indent,
                    " " if len(val[1]) and val[1][0] != " " else "", # at least 1 space after "#"
                    val[1]
                )
            elif val[0] == "hdl":
                result = "  " * indent + self.quest_admin_unparse_script(val[1]["type"])
                evtype = val[1]["type"][0]
                attrs = val[1].get("attrs")
                if attrs:
                    attrs = attrs.copy()
                    if evtype == "oncombat":
                        events = attrs["events"]
                        del attrs["events"]
                        if events.get("start"):
                            result += " start"
                        if events.get("victory"):
                            result += " victory"
                        if events.get("defeat"):
                            result += " defeat"
                        if events.get("draw"):
                            result += " draw"
                        if "flags" in attrs:
                            if attrs.get("flags"):
                                attrs["flags"] = u','.join(attrs["flags"])
                            else:
                                del attrs["flags"]
                    attrs = [(k, v) for k, v in attrs.iteritems()]
                    attrs.sort(cmp=lambda x, y: cmp(x[0], y[0]))
                    for k, v in attrs:
                        result += u" %s=%s" % (k, self.call("script.unparse-expression", v))
                actions = val[1].get("act")
                if actions:
                    result += " {\n" + self.quest_admin_unparse_script(actions, indent + 1) + "  " * indent + "}\n\n"
                else:
                    result += " {\n" + "  " * indent + "}\n\n"
                return result
            elif val[0] == "event":
                return u"event %s" % self.call("script.unparse-expression", val[1])
            elif val[0] == "teleported":
                return "teleported"
            elif val[0] == "money-changed":
                return "money changed"
            elif val[0] == "expired":
                if val[1] == "mod":
                    return "expired %s" % self.call("script.unparse-expression", val[2])
                elif val[1] == "timer":
                    return "timeout %s" % self.call("script.unparse-expression", val[2])
            elif val[0] == "item":
                return "itemused %s" % self.call("script.unparse-expression", val[1])
            elif val[0] == "button":
                return "button id=%s text=%s" % (self.call("script.unparse-expression", val[1]), self.call("script.unparse-expression", self.call("script.unparse-text", val[2])))
            elif val[0] == "registered":
                return "registered"
            elif val[0] == "online":
                return "online"
            elif val[0] == "offline":
                return "offline"
            elif val[0] == "crafted":
                return "crafted"
            elif val[0] == "clicked":
                return "clicked %s" % self.call("script.unparse-expression", val[1])
            elif val[0] == "charclass-selected":
                return "class selected"
            elif val[0] == "paidservice":
                return "paidservice"
            elif val[0] == "oncombat":
                return "combat"
            elif val[0] == "shop-bought":
                return "shop bought"
            elif val[0] == "shop-sold":
                return "shop sold"
            elif val[0] == "equip-wear":
                return "equip wear"
            elif val[0] == "equip-unwear":
                return "equip unwear"
            elif val[0] == "equip-drop":
                return "equip drop"
            elif val[0] == "require":
                result = "  " * indent + u"require %s" % self.call("script.unparse-expression", val[1])
                if len(val) >= 4:
                    if val[2] == "error":
                        result += " else error %s" % self.call("script.unparse-expression", self.call("script.unparse-text", val[3]))
                result += "\n"
                return result
            elif val[0] == "call":
                if len(val) == 2:
                    return "  " * indent + u"call event=%s\n" % self.call("script.unparse-expression", val[1])
                else:
                    return "  " * indent + u"call quest=%s event=%s\n" % (self.call("script.unparse-expression", val[1]), self.call("script.unparse-expression", val[2]))
            elif val[0] == "call2":
                if val[1] is None:
                    result = "  " * indent + u"call event=%s" % self.call("script.unparse-expression", val[2])
                else:
                    result = "  " * indent + u"call quest=%s event=%s" % (self.call("script.unparse-expression", val[1]), self.call("script.unparse-expression", val[2]))
                args = val[3]
                if "char" in args:
                    result += " char=%s" % self.call("script.unparse-expression", args["char"])
                result += "\n"
                return result
            elif val[0] == "message" or val[0] == "error":
                return "  " * indent + u"%s %s\n" % (val[0], self.call("script.unparse-expression", self.call("script.unparse-text", val[1])))
            elif val[0] == "giveitem":
                attrs = [("p_%s" % k, v) for k, v in val[2].iteritems()]
                attrs.sort(cmp=lambda x, y: cmp(x[0], y[0]))
                attrs = u"".join([" %s=%s" % (k, self.call("script.unparse-expression", v)) for k, v in attrs])
                result = "  " * indent + "give item=" + self.call("script.unparse-expression", val[1])
                if len(val) >= 4:
                    quantity = val[3]
                else:
                    quantity = 1
                if quantity != 1:
                    result += " quantity=%s" % self.call("script.unparse-expression", quantity)
                result += attrs + "\n"
                return result
            elif val[0] == "givemoney":
                result = "  " * indent + "give amount=%s currency=%s" % (self.call("script.unparse-expression", val[1]), self.call("script.unparse-expression", val[2]))
                if len(val) >= 4 and val[3]:
                    result += " comment=%s" % self.call("script.unparse-expression", val[3])
                result += "\n"
                return result
            elif val[0] == "takeitem":
                result = "  " * indent + "take"
                if val[1] is not None:
                    result += " type=%s" % self.call("script.unparse-expression", val[1])
                if val[2] is not None:
                    result += " dna=%s" % self.call("script.unparse-expression", val[2])
                if val[3] is not None:
                    result += " quantity=%s" % self.call("script.unparse-expression", val[3])
                if len(val) >= 6 and val[5] is not None:
                    result += " fractions=%s" % self.call("script.unparse-expression", val[5])
                if len(val) >= 5 and val[4] is not None:
                    result += " onfail=%s" % self.call("script.unparse-expression", val[4])
                result += "\n"
                return result
            elif val[0] == "takemoney":
                result = "  " * indent + "take amount=%s currency=%s" % (self.call("script.unparse-expression", val[1]), self.call("script.unparse-expression", val[2]))
                if val[3] is not None:
                    result += " onfail=%s" % self.call("script.unparse-expression", val[3])
                if len(val) >= 5 and val[4]:
                    result += " comment=%s" % self.call("script.unparse-expression", val[4])
                result += "\n"
                return result
            elif val[0] == "if":
                result = "  " * indent + ("if %s {" % self.call("script.unparse-expression", val[1]))
                result += "\n%s%s}" % (self.quest_admin_unparse_script(val[2], indent + 1), "  " * indent)
                if len(val) >= 4 and val[3]:
                    result += " else {\n%s%s}" % (self.quest_admin_unparse_script(val[3], indent + 1), "  " * indent)
                result += "\n"
                return result
            elif val[0] == "set":
                return "  " * indent + ("set %s.%s = %s\n" % (self.call("script.unparse-expression", val[1]), val[2], self.call("script.unparse-expression", val[3])))
            elif val[0] == "setdynamic":
                add = ""
                if val[4] is not None:
                    add += " till=%s" % self.call("script.unparse-expression", val[4])
                return "  " * indent + ("set dynamic %s.%s = %s%s\n" % (self.call("script.unparse-expression", val[1]), val[2], self.call("script.unparse-expression", val[3]), add))
            elif val[0] == "slide":
                result = "  " * indent + "slide"
                result += " %s.%s" % (self.call("script.unparse-expression", val[1]), val[2])
                if val[3] is not None:
                    result += " from=%s" % self.call("script.unparse-expression", val[3])
                result += " to=%s" % self.call("script.unparse-expression", val[4])
                result += " time=%s" % self.call("script.unparse-expression", val[5])
                if val[6] is not None:
                    result += " round=%s" % self.call("script.unparse-expression", val[6])
                result += "\n"
                return result
            elif val[0] == "destroy":
                return "  " * indent + "%s\n" % ("finish" if val[1] else "fail")
            elif val[0] == "lock":
                attrs = ""
                if val[1] is not None:
                    attrs += ' timeout=%s' % self.call("script.unparse-expression", val[1])
                return "  " * indent + "lock%s\n" % attrs
            elif val[0] == "timer":
                return "  " * indent + 'timer id="%s" timeout=%s\n' % (val[1], self.call("script.unparse-expression", val[2]))
            elif val[0] == "activity-timer":
                options = val[1]
                res = "  " * indent + 'activity timer timeout=%s' % self.call("script.unparse-expression", options.get("timeout"))
                if "text" in options:
                    res += " text=%s" % self.call("script.unparse-expression", self.call("script.unparse-text", options["text"]))
                if "indicator" in options:
                    res += " indicator=%s" % self.call("script.unparse-expression", options["indicator"])
                res += "\n"
                return res
            elif val[0] == "modremove":
                return "  " * indent + 'modifier remove id="%s"\n' % val[1]
            elif val[0] == "modifier":
                op = val[2]
                modval = " val=%s" % self.call("script.unparse-expression", val[4]) if len(val) >= 5 else ""
                if op == "add":
                    if val[3] is None:
                        return "  " * indent + 'modifier id="%s"%s\n' % (val[1], modval)
                    else:
                        return "  " * indent + 'modifier id="%s" add=%s%s\n' % (val[1], self.call("script.unparse-expression", val[3]), modval)
                elif op == "prolong":
                    return "  " * indent + 'modifier id="%s" prolong=%s%s\n' % (val[1], self.call("script.unparse-expression", val[3]), modval)
            elif val[0] == "selectitem":
                options = val[1]
                result = "  " * indent + "selectitem {\n"
                if "title" in options:
                    result += "  " * (indent + 1) + "title %s\n" % self.call("script.unparse-expression", self.call("script.unparse-text", options["title"]))
                if "show" in options:
                    result += "  " * (indent + 1) + "show %s\n" % self.call("script.unparse-expression", options["show"])
                if "fields" in options:
                    result += "  " * (indent + 1) + "fields {\n"
                    for field in options["fields"]:
                        add = ""
                        if "visible" in field:
                            add += " visible=%s" % self.call("script.unparse-expression", field["visible"])
                        result += "  " * (indent + 2) + "field name=%s value=%s%s\n" % (
                            self.call("script.unparse-expression", self.call("script.unparse-text", field["name"])),
                            self.call("script.unparse-expression", self.call("script.unparse-text", field["value"])),
                            add,
                        )
                    result += "  " * (indent + 1) + "}\n"
                if "actions" in options:
                    result += "  " * (indent + 1) + "actions {\n"
                    for action in options["actions"]:
                        add = ""
                        if "available" in action:
                            add += " available=%s" % self.call("script.unparse-expression", action["available"])
                        result += u"  " * (indent + 2) + "action name=%s event=%s%s\n" % (
                            self.call("script.unparse-expression", self.call("script.unparse-text", action["name"])),
                            self.call("script.unparse-expression", action["event"]),
                            add
                        )
                    result += "  " * (indent + 1) + "}\n"
                if "oncancel" in options:
                    result += "  " * (indent + 1) + "oncancel %s\n" % self.call("script.unparse-expression", options["oncancel"])
                if "template" in options:
                    result += "  " * (indent + 1) + "template %s\n" % self.call("script.unparse-expression", options["template"])
                result += "  " * indent + "}\n"
                return result
            elif val[0] == "dialog":
                options = val[1]
                result = "  " * indent + "dialog {\n"
                if "title" in options:
                    result += "  " * (indent + 1) + "title %s\n" % self.call("script.unparse-expression", self.call("script.unparse-text", options["title"]))
                if "text" in options:
                    result += "  " * (indent + 1) + "text %s\n" % self.call("script.unparse-expression", self.call("script.unparse-text", options["text"]))
                if "template" in options:
                    result += "  " * (indent + 1) + "template %s\n" % self.call("script.unparse-expression", self.call("script.unparse-text", options["template"]))
                if "inputs" in options:
                    for inp in options["inputs"]:
                        result += "  " * (indent + 1) + 'input "%s" {' % inp["id"];
                        if "text" in inp:
                            result += " text %s" % self.call("script.unparse-expression", self.call("script.unparse-text", inp["text"]))
                        result += " }\n"
                if "buttons" in options:
                    for btn in options["buttons"]:
                        default = "default " if btn.get("default") else ""
                        result += "  " * (indent + 1) + "%sbutton {\n" % default;
                        if "text" in btn:
                            result += "%stext %s\n" % ("  " * (indent + 2), self.call("script.unparse-expression", self.call("script.unparse-text", btn["text"])))
                        if "event" in btn:
                            result += '%sevent "%s"\n' % ("  " * (indent + 2), btn["event"])
                        if "available" in btn:
                            result += '%savailable %s\n' % ("  " * (indent + 2), self.call("script.unparse-expression", btn["available"]))
                        result += "  " * (indent + 1) + "}\n"
                result += "  " * indent + "}\n"
                return result
            elif val[0] == "random":
                result = "  " * indent + "random {\n"
                for ent in val[1]:
                    weight = ent[0]
                    actions = ent[1]
                    result += "  " * (indent + 1) + "weight %s:\n" % self.call("script.unparse-expression", weight)
                    result += self.quest_admin_unparse_script(actions, indent + 2)
                result += "  " * indent + "}\n"
                return result
            elif val[0] == "chat":
                result = "  " * indent + "chat %s" % self.call("script.unparse-expression", self.call("script.unparse-text", val[1]))
                args = val[2]
                if "channel" in args:
                    result += " channel=%s" % self.call("script.unparse-expression", args["channel"])
                if "public" in args:
                    result += " public=%s" % self.call("script.unparse-expression", args["public"])
                if "cls" in args:
                    result += " cls=%s" % self.call("script.unparse-expression", args["cls"])
                result += "\n"
                return result
            elif val[0] == "combatlog":
                args = u''
                if len(val) >= 3:
                    for key in sorted(val[2].keys()):
                        args += u" %s=%s" % (key, self.call("script.unparse-expression", val[2][key]))
                return u"%scombat log %s%s\n" % ("  " * indent, self.call("script.unparse-expression", self.call("script.unparse-text", val[1])), args)
            elif val[0] == "combatjoin":
                return u"%scombat join %s %s\n" % ("  " * indent, self.call("script.unparse-expression", val[1]), self.unparse_member(val[2]))
            elif val[0] == "combatsyslog":
                args = u''
                if len(val) >= 3:
                    for key in sorted(val[2].keys()):
                        args += u" %s=%s" % (key, self.call("script.unparse-expression", val[2][key]))
                return u"%scombat syslog %s%s\n" % ("  " * indent, self.call("script.unparse-expression", self.call("script.unparse-text", val[1])), args)
            elif val[0] == "javascript":
                return "  " * indent + "javascript %s\n" % self.call("script.unparse-expression", val[1])
            elif val[0] == "teleport":
                return "  " * indent + "teleport %s\n" % self.call("script.unparse-expression", val[1])
            elif val[0] == "equipbreak":
                return "  " * indent + "equipbreak %s\n" % self.call("script.unparse-expression", val[1])
            elif val[0] == "combat":
                options = val[1]
                result = "  " * indent + "combat"
                if "rules" in options:
                    result += " rules=%s" % self.call("script.unparse-expression", options["rules"])
                if "title" in options:
                    result += " ctitle=%s" % self.call("script.unparse-expression", self.call("script.unparse-text", options["title"]))
                if "flags" in options:
                    result += " flags=%s" % self.call("script.unparse-expression", u','.join(options["flags"]))
                result += " {\n"
                for member in options.get("members", []):
                    result += "  " * indent + "  "
                    result += self.unparse_member(member)
                    result += "\n"
                result += "  " * indent + "}\n"
                return result
            elif val[0] == "sound":
                result = "  " * indent + "sound %s" % self.call("script.unparse-expression", self.call("script.unparse-text", val[1]))
                options = val[2]
                if "mode" in options:
                    result += " mode=%s" % self.call("script.unparse-expression", options["mode"])
                if "volume" in options:
                    result += " volume=%s" % self.call("script.unparse-expression", options["volume"])
                result += "\n"
                return result
            elif val[0] == "music":
                result = "  " * indent + "music %s" % self.call("script.unparse-expression", val[1])
                options = val[2]
                if "fade" in options:
                    result += " fade=%s" % self.call("script.unparse-expression", options["fade"])
                if "volume" in options:
                    result += " volume=%s" % self.call("script.unparse-expression", options["volume"])
                result += "\n"
                return result
            elif val[0] == "musicstop":
                result = "  " * indent + "music stop"
                options = val[1]
                if "fade" in options:
                    result += " fade=%s" % self.call("script.unparse-expression", options["fade"])
                result += "\n"
                return result
            elif val[0] == "sendchar":
                result = "  " * indent + "sendchar " + ", ".join([self.call("script.unparse-expression", v) for v in val[1]]) + "\n"
                return result
            elif val[0] == "activity":
                attrs = ""
                for k in sorted(val[2].keys()):
                    attrs += " %s=%s" % (k, self.call("script.unparse-expression", val[2][k]))
                result = "  " * indent + "activity%s {\n" % attrs
                result += self.quest_admin_unparse_script(val[1], indent + 1).rstrip() + "\n"
                result += "  " * indent + "}\n"
                return result
            return "  " * indent + "<<<%s: %s>>>\n" % (self._("Invalid script parse tree"), val)

    def headmenu_inventory_actions(self, args):
        if args == "new":
            return [self._("New action"), "inventory/actions"]
        elif args:
            actions = self.conf("quest-item-actions.list", [])
            for a in actions:
                if a["code"] == args:
                    return [htmlescape(a["text"]), "inventory/actions"]
        return self._("Quest actions for items")

    def admin_inventory_actions(self):
        req = self.req()
        actions = [act.copy() for act in self.conf("quest-item-actions.list", [])]
        self.call("admin.advice", {"title": self._("Quests and triggers subsystem documentation"), "content": self._('This is the coremost part of the MMO Constructor. It can be used to assign arbitrary actions to various game events. You can find detailed information on the quests engine in the <a href="//www.%s/doc/quests" target="_blank">quests engine page</a> in the reference manual.') % self.main_host, "order": 20})
        if req.args:
            m = re_del.match(req.args)
            if m:
                code = m.group(1)
                config = self.app().config_updater()
                actions = [ent for ent in actions if ent["code"] != code]
                config.set("quest-item-actions.list", actions)
                config.store()
                self.call("admin.redirect", "inventory/actions")
            if req.args == "new":
                order = None
                for a in actions:
                    if order is None or a["order"] > order:
                        order = a["order"]
                if order is None:
                    order = 0.0
                else:
                    order += 10.0
                action = {
                    "order": order
                }
                actions.append(action)
            else:
                action = None
                for a in actions:
                    if a["code"] == req.args:
                        action = a
                        break
                if not action:
                    self.call("admin.redirect", "inventory/actions")
            if req.ok():
                errors = {}
                # code
                code = req.param("code")
                if not code:
                    errors["code"] = self._("This field is mandatory")
                elif not re_valid_identifier.match(code):
                    errors["code"] = self._("Button code must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'")
                else:
                    for a in actions:
                        if a.get("code") == code and code != req.args:
                            errors["code"] = self._("There is already a button with this code")
                            break
                    action["code"] = code
                # order
                action["order"] = floatz(req.param("order"))
                # text
                text = req.param("text").strip()
                if not text:
                    errors["text"] = self._("This field is mandatory")
                else:
                    action["text"] = text
                # available
                char = self.character(req.user())
                item = self.call("admin-inventory.sample-item")
                action["available"] = self.call("script.admin-expression", "available", errors, globs={"char": char, "item": item})
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                config = self.app().config_updater()
                actions.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["text"], y["text"]))
                config.set("quest-item-actions.list", actions)
                config.store()
                self.call("admin.redirect", "inventory/actions")
            fields = [
                {"name": "code", "label": self._("Button code (used in quest scripts)"), "value": action.get("code")},
                {"name": "order", "label": self._("Sorting order"), "value": action.get("order"), "inline": True},
                {"name": "text", "label": self._("Button text"), "value": action.get("text"), "inline": True},
                {"name": "available", "label": self._("Is the button available for the character (you may use 'char' and 'item' objects)") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", action.get("available")) if action.get("available") is not None else None},
            ]
            self.call("admin.form", fields=fields)
        rows = []
        for ent in actions:
            rows.append([
                ent["code"],
                htmlescape(ent["text"]),
                ent["order"],
                u'<hook:admin.link href="inventory/actions/%s" title="%s" />' % (ent["code"], self._("edit")),
                u'<hook:admin.link href="inventory/actions/del/%s" title="%s" confirm="%s" />' % (ent["code"], self._("delete"), self._("Are you sure want to delete this button?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "inventory/actions/new", "text": self._("New action button"), "lst": True}
                    ],
                    "header": [self._("Code"), self._("Button text"), self._("Order"), self._("Editing"), self._("Deletion")],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def abort_activity(self):
        req = self.req()
        character = self.character(req.args)
        if not character.valid:
            self.call("web.not_found")
        if character.activity:
            character.unset_busy()
        self.call("quests.send-activity-modifier", character)
        self.call("admin.redirect", "auth/user-dashboard/%s?active_tab=quests" % character.uuid)

    def user_tables(self, user, tables):
        req = self.req()
        if req.has_access("quests.view"):
            character = self.character(user.uuid)
            if character.valid:
                cur_quests = []
                finished_quests = []
                quest_list = []
                for qid, quest in self.conf("quests.list", {}).iteritems():
                    if quest.get("enabled"):
                        quest_list.append((qid, quest))
                quest_list.sort(cmp=lambda x, y: cmp(x[1].get("order", 0), y[1].get("order", 0)) or cmp(x[1].get("name"), y[1].get("name")) or cmp(x[0], y[0]))
                for qid, quest in quest_list:
                    # current quest
                    sid = character.quests.get(qid, "state", "init")
                    if sid != "init":
                        try:
                            available = self.call("script.evaluate-expression", quest.get("available", 1), globs={"char": character}, description=self._("Quest %s availability") % qid)
                        except ScriptError as e:
                            self.exception(e)
                            available = False
                        if available:
                            if req.has_access("quests.editor"):
                                state = self.conf("quest-%s.states" % qid, {}).get(sid)
                                if state:
                                    quest_name = '<hook:admin.link href="quests/editor/%s/state/%s" title="%s" />' % (qid, sid, htmlescape(quest.get("name")))
                                else:
                                    quest_name = '<hook:admin.link href="quests/editor/%s/info" title="%s" />' % (qid, htmlescape(quest.get("name")))
                            else:
                                quest_name = htmlescape(quest.get("name"))
                            state = []
                            for key, val in character.quests.state(qid).iteritems():
                                if type(val) is list:
                                    val = htmlescape(self.call("script.unparse-expression", val[1])) + u' <img class="inline-icon" src="/st/icons/dyn-script.gif" alt="{title}" title="{title}" />'.format(title=self._("Parameter changing with time"))
                                else:
                                    val = htmlescape(val)
                                state.append(u'quest.p_%s = <strong>%s</strong>' % (htmlescape(key), val))
                            state.sort()
                            cur_quests.append([
                                "char.q_%s" % qid,
                                quest_name,
                                '<br />'.join(state),
                            ])
                    # finished quest
                    finished = character.quests.finished.get(qid)
                    if finished:
                        performed = finished.get("performed")
                        finished_quests.append([
                            "char.q_%s.finished" % qid,
                            '<hook:admin.link href="quests/editor/%s/info" title="%s" />' % (qid, htmlescape(quest.get("name"))),
                            self.call("l10n.time_local", performed),
                        ])
                # activities
                cur_activities = []
                activity = character.activity
                if activity:
                    state = []
                    for key, val in activity.state.iteritems():
                        if type(val) is list:
                            val = htmlescape(self.call("script.unparse-expression", val[1])) + u' <img class="inline-icon" src="/st/icons/dyn-script.gif" alt="{title}" title="{title}" />'.format(title=self._("Parameter changing with time"))
                        else:
                            val = htmlescape(val)
                        state.append(u'activity.%s = <strong>%s</strong>' % (htmlescape(key), val))
                    state.sort()
                    atype = character.busy.get("atype")
                    if atype:
                        state.insert(0, self._("Activity type: %s") % htmlescape(atype))
                    if activity.handlers:
                        state.append('<pre class="admin-code">%s</pre>' % htmlescape(self.call("quest-admin.unparse-script", activity.handlers).strip()))
                    if req.has_access("quests.abort-activities"):
                        state.append('<hook:admin.link href="quests/abort-activity/%s" title="%s" />' % (character.uuid, self._("Abort activity")))
                    cur_activities.append([
                        "char.activity",
                        '<br />'.join(state),
                    ])
                # dialogs
                may_dialogs = req.has_access("quests.dialogs")
                dialogs = []
                for dialog in character.quests.dialogs:
                    quest = dialog.get("quest")
                    if req.has_access("quests.editor"):
                        quest = '<hook:admin.link href="quests/editor/%s/info" title="%s" />' % (quest, quest)
                    rdialog = [
                        htmlescape(dialog.get("title")),
                        quest,
                        htmlescape(dialog.get("template", self._("default"))),
                    ]
                    if may_dialogs:
                        rdialog.append(u'<hook:admin.link href="quests/removedialog/%s/%s" title="%s" />' % (character.uuid, dialog.get("uuid"), self._("remove")))
                    dialogs.append(rdialog)
                dialogs_header = [
                    self._("Title"),
                    self._("Quest"),
                    self._("Template"),
                ]
                if may_dialogs:
                    dialogs_header.append(self._("Removal"))
                vars = {
                    "tables": [
                        {
                            "title": self._("Currently opened dialogs"),
                            "header": dialogs_header,
                            "rows": dialogs,
                        },
                        {
                            "title": self._("Current activity"),
                            "header": [
                                self._("Object"),
                                self._("Activity state"),
                            ],
                            "rows": cur_activities,
                        },
                        {
                            "title": self._("Current quests"),
                            "header": [
                                self._("Object"),
                                self._("Quest name"),
                                self._("Quest state"),
                            ],
                            "rows": cur_quests,
                        },
                        {
                            "title": self._("Finished quests"),
                            "header": [
                                self._("Object"),
                                self._("Quest name"),
                                self._("Finish date"),
                            ],
                            "rows": finished_quests,
                        },
                    ]
                }
                table = {
                    "type": "quests",
                    "title": self._("Quests"),
                    "order": 40,
                    "before": self.call("web.parse_template", "admin/common/tables.html", vars),
                }
                tables.append(table)

    def remove_dialog(self):
        req = self.req()
        m = re_remove_dialog.match(req.args)
        if not m:
            self.call("web.not_found")
        char_uuid, dialog_uuid = m.group(1, 2)
        character = self.character(char_uuid)
        if not character.valid:
            self.call("web.not_found")
        dialogs = character.quests.dialogs
        for i in xrange(0, len(dialogs)):
            if dialogs[i]["uuid"] == dialog_uuid:
                del dialogs[i]
                character.quests.touch()
                character.quests.store()
                character.main_open("/quest/dialog")
                break
        self.call("admin.redirect", "auth/user-dashboard/%s?active_tab=quests" % char_uuid)

class Quests(ConstructorModule):
    def register(self):
        self.rhook("quests.parse-script", self.parse_script)
        self.rhook("quests.event", self.quest_event)
        self.rhook("quests.char", self.get_char)
        self.rhook("items.menu", self.items_menu)
        self.rhook("ext-item.action", self.action, priv="logged")
        self.rhook("ext-quest.dialog", self.dialog, priv="logged")
        self.rhook("quest.check-dialogs", self.check_dialogs)
        self.rhook("quest.check-redirects", self.check_redirects)
        self.rhook("web.request_processed", self.request_processed)
        self.rhook("money-description.quest-give", self.money_description_quest)
        self.rhook("money-description.quest-take", self.money_description_quest)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("ext-quests.index", self.quests, priv="logged")
        self.rhook("session.character-online", self.character_online, priority=-100)
        self.rhook("session.character-offline", self.character_offline)
        self.rhook("ext-quest.event", self.ext_quest_event, priv="logged")
        self.rhook("locations.map-zone-event-render", self.location_map_zone_event_render)
        self.rhook("interface.render-button", self.interface_render_button)
        self.rhook("modules.list", self.modules_list)
        self.rhook("quests.char-activity", self.char_activity)
        self.rhook("quests.send-activity-modifier", self.send_activity_modifier)
        self.rhook("session.character-init", self.character_init)
        self.rhook("ext-quests.activity-end", self.ext_activity_end, priv="logged")
        self.rhook("quests.activity-aborted", self.activity_aborted)

    def activity_aborted(self, char):
        self.qevent("event-:activity-abort", char=char)

    def ext_activity_end(self):
        req = self.req()
        self.call("modifiers.stop", "user", req.user())
        self.call("web.response_json", {"ok": 1})

    def char_activity(self, char):
        if char.busy and char.busy["tp"] == "activity":
            return CharActivity(self.app(), char)
        else:
            return None

    def character_init(self, session_uuid, char):
        self.send_activity_modifier(char)

    def send_activity_modifier(self, char):
        if char.activity:
            timer = char.modifiers.get("timer-:activity-done")
            if timer and timer["mods"]:
                mod = timer["mods"][-1]
                progress_expr = mod.get("progress_expr")
                progress_till = mod.get("progress_till")
                text = mod.get("text")
                if progress_expr is not None and progress_till:
                    now = self.time()
                    if now < progress_till:
                        self.call("stream.character", char, "game", "activity_start", progress_expr=progress_expr, progress_till=progress_till, text=text)
                        return
        self.call("stream.character", char, "game", "activity_stop")

    def child_modules(self):
        modules = ["mg.mmorpg.quests.QuestsAdmin"]
        if self.conf("module.combats"):
            modules.extend(["mg.mmorpg.combats.interfaces.Combats"])
        return modules

    def modules_list(self, modules):
        modules.extend([
            {
                "id": "combats",
                "name": self._("Combats engine"),
                "description": self._("Creating highly customizable combats"),
                "parent": "quests",
            }
        ])

    @property
    def general_parser_spec(self):
        inst = self.app().inst
        try:
            return inst._parser_spec
        except AttributeError:
            inst._parser_spec = Parsing.Spec(sys.modules["mg.constructor.script_classes"], skinny=False)
            return inst._parser_spec

    @property
    def quest_parser_spec(self):
        inst = self.app().inst
        try:
            return inst._quest_parser_spec
        except AttributeError:
            inst._quest_parser_spec = Parsing.Spec(sys.modules["mg.mmorpg.quest_parser"], skinny=False)
            return inst._quest_parser_spec

    def parse_script(self, text):
        parser = QuestScriptParser(self.app(), self.quest_parser_spec, self.general_parser_spec)
        try:
            parser.scan(text)
            # Tell the parser that the end of input has been reached.
            try:
                parser.eoi()
            except Parsing.SyntaxError as e:
                raise ScriptParserError(self._("Script unexpectedly ended"), e)
        except ScriptParserResult as e:
            return e.val

    def quest_event(self, event, **kwargs):
        char = kwargs.get("char")
        if not char:
            return
        tasklet = Tasklet.current()
        # avoid recursive call of the same events
        try:
            events = tasklet.quest_processing_events
        except AttributeError:
            events = set()
            tasklet.quest_processing_events = events
        key = "%s-%s" % (char.uuid, event)
        if key in events:
            return
        events.add(key)
        try:
            self.execute_quest_event(event, **kwargs)
        finally:
            events.discard(key)

    def execute_quest_event(self, event, **kwargs):
        # load list of quests handling this type of event
        char = kwargs.get("char")
        if not char:
            return
        tasklet = Tasklet.current()
        old_indent = getattr(tasklet, "quest_indent", None)
        if old_indent is None:
            indent = 0
        else:
            indent = old_indent + 4
        tasklet.quest_indent = indent
        try:
            def event_str():
                event_str = utf2str(self._("event=%s") % event)
                for key in sorted(kwargs.keys()):
                    if key != "char":
                        val = kwargs[key]
                        if val:
                            event_str += ', %s=%s' % (utf2str(key), utf2str(htmlescape(val)))
                return event_str
            if indent == 0:
                self.call("debug-channel.character", char, event_str, cls="quest-first-event", indent=indent)
            else:
                self.call("debug-channel.character", char, event_str, cls="quest-event", indent=indent)
            if not "local" in kwargs:
                kwargs["local"] = ScriptMemoryObject()
            # loading list of quest handlers
            quests_states = self.conf("qevent-%s.handlers" % event, [])
            # checking for character states and choosing quests
            quests = set()
            for ent in quests_states:
                quest = ent[0]
                state = ent[1]
                if char.quests.get(quest, "state", "init") == state:
                    quests.add(quest)
            quests = [quest for quest in quests]
            quests.sort()
            # loading quests configuration
            self.app().config.load_groups(["quest-%s" % quest for quest in quests])
            # executing quests scripts
            def eval_description():
                return self._("Quest '{quest}', event '{event}'").format(quest=quest, event=event)
            # check list of handlers for matching events
            def execute_handlers(hdls, quest, kwargs):
                if not hdls:
                    return
                for hdl in hdls:
                    if hdl[0] != "hdl":
                        continue
                    handler = hdl[1]
                    tp = handler.get("type")
                    if not tp:
                        continue
                    tp = parse_quest_tp(quest, tp)
                    if event != tp:
                        continue
                    attrs = handler.get("attrs")
                    if event == "teleported":
                        if attrs and attrs.get("to") and kwargs["new_loc"].uuid != attrs.get("to"):
                            continue
                        if attrs and attrs.get("from") and kwargs["old_loc"].uuid != attrs.get("from"):
                            continue
                    elif event == "money-changed":
                        if attrs and attrs.get("currency") and kwargs["currency"] != attrs.get("currency"):
                            continue
                    elif event == "oncombat":
                        if attrs and attrs.get("events") and kwargs["cevent"] not in attrs["events"]:
                            continue
                        if attrs and attrs.get("flags"):
                            match = False
                            cflags = kwargs["combat"].flags
                            for flag in attrs.get("flags"):
                                if flag in cflags:
                                    match = True
                                    break
                            if not match:
                                continue
                    act = handler.get("act")
                    if not act:
                        continue
                    modified_objects = set()
                    def execute_actions(actions, indent):
                        # testing stack overflows
                        try:
                            sys._getframe(900)
                        except ValueError:
                            pass
                        else:
                            # this is a real error
                            env = ScriptEnvironment()
                            env.globs = kwargs
                            env.description = self._("Quest '{quest}', event '{event}'").format(quest=quest, event=event)
                            raise ScriptRuntimeError(self._("Max recursion depth exceeded"), env)
                        for cmd in actions:

                            def env():
                                env = ScriptEnvironment()
                                env.globs = kwargs
                                env.description = self._("Quest '{quest}', event '{event}', command '{command}'").format(quest=quest, event=event, command=self.call("quest-admin.unparse-script", cmd).strip())
                                return env

                            def evaluate_member(member):
                                mtype = member["type"]
                                if mtype[0] == "virtual":
                                    cmember = {
                                        "object": ["virtual"]
                                    }
                                elif mtype[0] == "expr":
                                    cmemberobj = self.call("script.evaluate-expression", mtype[1], globs=kwargs, description=lambda: self._("Combat member type"))
                                    makemember = getattr(cmemberobj, "combat_member", None)
                                    if makemember is None:
                                        raise QuestError(self._("'%s' is not a valid combat member") % self.call("script.unparse-expression", mtype[1]))
                                    cmember = makemember()
                                else:
                                    raise QuestError(self._("Unknown combat type %s") % mtype[0])
                                rmember = cmember
                                team = self.call("script.evaluate-expression", member["team"], globs=kwargs, description=lambda: self._("Combat member team"))
                                if type(team) != int:
                                    raise QuestError(self._("Team number must be integer. Got: %s") % type(team))
                                else:
                                    team = int(team)
                                    if team < 1 or team > 1000:
                                        raise QuestError(self._("Team number must be in range 1 .. 1000. Got: %s") % team)
                                    else:
                                        rmember["team"] = team
                                if "control" in member:
                                    rmember["control"] = self.call("script.evaluate-expression", member["control"], globs=kwargs, description=lambda: self._("Combat member control"))
                                elif cmember["object"][0] == "character":
                                    rmember["control"] = "web"
                                else:
                                    rmember["control"] = "ai"
                                if "name" in member:
                                    rmember["name"] = self.call("script.evaluate-text", member["name"], globs=kwargs, description=lambda: self._("Combat member name"))
                                if "sex" in member:
                                    rmember["sex"] = self.call("script.evaluate-expression", member["sex"], globs=kwargs, description=lambda: self._("Combat member sex"))
                                if "ai" in member:
                                    rmember["ai"] = self.call("script.evaluate-expression", member["ai"], globs=kwargs, description=lambda: self._("Combat member AI"))
                                if "image" in member:
                                    rmember["image"] = self.call("script.evaluate-expression", member["image"], globs=kwargs, description=lambda: self._("Combat member image"))
                                if "params" in member:
                                    params = {}
                                    rmember["params"] = params
                                    for key, val in member["params"].iteritems():
                                        params[key] = self.call("script.evaluate-expression", val, globs=kwargs, description=lambda: self._("Combat member parameter '%s'") % key)
                                return rmember

                            try:
                                cmd_code = cmd[0]
                                if cmd_code == "comment":
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: u'# %s' % cmd[1], cls="quest-comment", indent=indent+2)
                                elif cmd_code == "message" or cmd_code == "error":
                                    message = self.call("script.evaluate-text", cmd[1], globs=kwargs, description=eval_description)
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: u'%s %s' % (cmd_code, self.call("script.unparse-expression", message)), cls="quest-action", indent=indent+2)
                                    getattr(char, cmd_code)(message)
                                elif cmd_code == "require":
                                    res = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                    if not res:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: u'%s: %s' % (self.call("script.unparse-expression", cmd[1]), self._("false")), cls="quest-condition", indent=indent+2)
                                        if len(cmd) >= 4:
                                            if cmd[2] == "error":
                                                error = self.call("script.evaluate-text", cmd[3], globs=kwargs, description=lambda: self._("Error text for 'require' statement"))
                                                if debug:
                                                    self.call("debug-channel.character", char, lambda: self._("Error message: %s") % error, cls="quest-condition", indent=indent+2)
                                                char.error(error)
                                        raise AbortHandler()
                                elif cmd_code == "call":
                                    if len(cmd) == 2:
                                        ev = "event-%s-%s" % (quest, cmd[1])
                                    else:
                                        ev = "event-%s-%s" % (cmd[1], cmd[2])
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("calling event %s") % ev, cls="quest-action", indent=indent+2)
                                    self.qevent(ev, char=char)
                                elif cmd_code == "call2":
                                    target_quest = cmd[1]
                                    target_event = cmd[2]
                                    if target_quest is None:
                                        target_quest = quest
                                    ev = "event-%s-%s" % (target_quest, target_event)
                                    args = cmd[3]
                                    if "char" in args:
                                        char_id = utf2str(unicode(self.call("script.evaluate-expression", args["char"], globs=kwargs, description=lambda: self._("target character for call"))))
                                        target_char = self.character(char_id)
                                        if target_char.valid:
                                            if debug:
                                                self.call("debug-channel.character", char, lambda: self._("calling event {event} for character {character}").format(event=ev, character=target_char), cls="quest-action", indent=indent+2)
                                            self.qevent(ev, char=target_char)
                                        else:
                                            raise ScriptRuntimeError(self._("Character with id '%s' doesn't exist") % htmlescape(char_id), env)
                                    else:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("calling event %s") % ev, cls="quest-action", indent=indent+2)
                                        self.qevent(ev, char=char)
                                elif cmd_code == "giveitem":
                                    item_type_uuid = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                    mods = {}
                                    mods_list = []
                                    for param, value in cmd[2].iteritems():
                                        val = self.call("script.evaluate-expression", value, globs=kwargs, description=eval_description)
                                        mods[param] = val
                                        mods_list.append((param, val))
                                    quantity = intz(self.call("script.evaluate-expression", cmd[3], globs=kwargs, description=eval_description))
                                    if quantity > 0:
                                        if quantity > 1e9:
                                            quantity = 1e9
                                        item_type = self.item_type(item_type_uuid, mods=mods)
                                        if item_type and item_type.valid():
                                            def message():
                                                res = self._("giving {item_name}, quantity={quantity}").format(item_name=item_type.name, quantity=quantity)
                                                if mods_list:
                                                    mods_list.sort(cmp=lambda x, y: cmp(x[0], y[0]))
                                                    res += ", %s" % ", ".join([u"p_%s=%s" % (k, v) for k, v in mods_list])
                                                return res
                                            if debug:
                                                self.call("debug-channel.character", char, message, cls="quest-action", indent=indent+2)
                                            char.inventory.give(item_type_uuid, quantity, "quest.give", quest=quest, mod=mods)
                                            # information message: 'You have got ...'
                                            item_name = item_type.name
                                            try:
                                                char.quest_given_items[item_name] += quantity
                                            except AttributeError:
                                                char.quest_given_items = {item_name: quantity}
                                            except KeyError:
                                                char.quest_given_items[item_name] = quantity
                                elif cmd_code == "takeitem":
                                    quantity = cmd[3]
                                    if len(cmd) >= 6:
                                        fractions = cmd[5]
                                    else:
                                        fractions = None
                                    if quantity is not None:
                                        quantity = self.call("script.evaluate-expression", quantity, globs=kwargs, description=eval_description)
                                        quantity = intz(quantity)
                                    if fractions is not None:
                                        fractions = self.call("script.evaluate-expression", fractions, globs=kwargs, description=eval_description)
                                        fractions = intz(fractions)
                                    if cmd[1]:
                                        item_type = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                        it_obj = self.item_type(item_type)
                                        if fractions is not None:
                                            if fractions >= 1:
                                                max_fractions = it_obj.get("fractions", 0)
                                                if not max_fractions:
                                                    max_fractions = 1
                                                deleted = char.inventory.take_type(item_type, fractions, "quest.take", quest=quest, any_dna=True, fractions=max_fractions)
                                            else:
                                                deleted = 0
                                        elif quantity is None or quantity >= 1:
                                            deleted = char.inventory.take_type(item_type, quantity, "quest.take", quest=quest, any_dna=True)
                                        else:
                                            deleted = 0
                                        if debug:
                                            if it_obj.valid():
                                                name = it_obj.name
                                            else:
                                                name = "??? (%s)" % item_type
                                            if fractions is not None:
                                                self.call("debug-channel.character", char, self._("taking {quantity} fractions of items with type '{type}' and any DNA ({result})").format(quantity=fractions, type=name, result=self._("successfully") if deleted else self._("unsuccessfully")), cls="quest-action", indent=indent+2)
                                            elif quantity is None:
                                                self.call("debug-channel.character", char, self._("taking all ({quantity}) items with type '{type}' and any DNA").format(type=name, quantity=deleted), cls="quest-action", indent=indent+2)
                                            else:
                                                self.call("debug-channel.character", char, self._("taking {quantity} items with type '{type}' and any DNA ({result})").format(quantity=quantity, type=name, result=self._("successfully") if deleted else self._("unsuccessfully")), cls="quest-action", indent=indent+2)
                                        if (quantity is not None or fractions is not None) and not deleted:
                                            if len(cmd) >= 5 and cmd[4] is not None and it_obj.valid:
                                                self.qevent("event-%s-%s" % (quest, cmd[4]), char=char, item=it_obj)
                                            raise AbortHandler()
                                    elif cmd[2]:
                                        dna = self.call("script.evaluate-expression", cmd[2], globs=kwargs, description=eval_description)
                                        dna = utf2str(dna)
                                        if quantity is None or quantity >= 1:
                                            it_obj, deleted = char.inventory.take_dna(dna, quantity, "quest.take", quest=quest)
                                            if it_obj is None:
                                                it_obj = self.item_type(dna)
                                        else:
                                            deleted = 0
                                            it_obj = self.item_type(dna)
                                        if debug:
                                            if it_obj.valid():
                                                name = it_obj.name
                                            else:
                                                name = "??? (%s)" % dna
                                            if quantity is None:
                                                self.call("debug-channel.character", char, self._("taking all ({quantity}) items with exact DNA '{dna}'").format(dna=name, quantity=deleted or 0), cls="quest-action", indent=indent+2)
                                            else:
                                                self.call("debug-channel.character", char, self._("taking {quantity} items with exact DNA '{dna}' ({result})").format(quantity=quantity, dna=name, result=self._("successfully") if deleted else self._("unsuccessfully")), cls="quest-action", indent=indent+2)
                                        if quantity is not None and not deleted:
                                            if len(cmd) >= 5 and cmd[4] is not None and it_obj.valid:
                                                self.qevent("event-%s-%s" % (quest, cmd[4]), char=char, item=it_obj)
                                            raise AbortHandler()
                                    else:
                                        raise ScriptRuntimeError(self._("Neither item type nor DNA specified in 'take'"), env)
                                elif cmd_code == "givemoney":
                                    amount = floatz(self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description))
                                    currency = self.call("script.evaluate-expression", cmd[2], globs=kwargs, description=eval_description)
                                    if amount > 1e9:
                                        amount = 1e9
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("giving money, amount={amount}, currency={currency}").format(amount=amount, currency=currency), cls="quest-action", indent=indent+2)
                                    money_opts = {}
                                    if len(cmd) >= 4 and cmd[3]:
                                        money_opts["override"] = cmd[3]
                                    try:
                                        char.money.credit(amount, currency, "quest-give", quest=quest, **money_opts)
                                    except MoneyError as e:
                                        raise QuestError(e.val)
                                    # information message: 'You have got ...'
                                    try:
                                        char.quest_given_money[currency] += amount
                                    except AttributeError:
                                        char.quest_given_money = {currency: amount}
                                    except KeyError:
                                        char.quest_given_money[currency] = amount
                                elif cmd_code == "takemoney":
                                    amount = floatz(self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description))
                                    currency = self.call("script.evaluate-expression", cmd[2], globs=kwargs, description=eval_description)
                                    money_opts = {}
                                    if len(cmd) >= 5 and cmd[4]:
                                        money_opts["override"] = cmd[4]
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("taking money, amount={amount}, currency={currency}").format(amount=amount, currency=currency), cls="quest-action", indent=indent+2)
                                    try:
                                        res = char.money.debit(amount, currency, "quest-take", quest=quest, **money_opts)
                                    except MoneyError as e:
                                        raise QuestError(e.val)
                                    else:
                                        if not res:
                                            if cmd[3] is not None:
                                                self.qevent("event-%s-%s" % (quest, cmd[3]), char=char, amount=amount, currency=currency)
                                            raise AbortHandler()
                                elif cmd_code == "if":
                                    expr = cmd[1]
                                    val = self.call("script.evaluate-expression", expr, globs=kwargs, description=eval_description)
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("if {condition}: {result}").format(condition=self.call("script.unparse-expression", expr), result=self._("true") if val else self._("false")), cls="quest-condition", indent=indent+2)
                                    if val:
                                        execute_actions(cmd[2], indent+1)
                                    else:
                                        if len(cmd) >= 4:
                                            execute_actions(cmd[3], indent+1)
                                elif cmd_code == "set" or cmd_code == "setdynamic" or cmd_code == "slide":
                                    obj = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                    attr = cmd[2]
                                    if cmd_code == "slide":
                                        # from
                                        fr = cmd[3]
                                        if fr is None:
                                            getter = getattr(obj, "script_attr", None)
                                            if getter is None:
                                                raise ScriptTypeError(self._("Object '{val}' has no attributes").format(val=self.unparse_expression(cmd[1])), env)
                                            try:
                                                fr = getter(attr, handle_exceptions=False)
                                            except AttributeError as e:
                                                raise ScriptTypeError(self._("Object '{val}' has no attribute '{att}'").format(val=self.unparse_expression(cmd[1]), att=attr), env)
                                        else:
                                            fr = self.call("script.evaluate-expression", fr, globs=kwargs, description=eval_description)
                                        # to
                                        to = self.call("script.evaluate-expression", cmd[4], globs=kwargs, description=eval_description)
                                        # time
                                        time = floatz(self.call("script.evaluate-expression", cmd[5], globs=kwargs, description=eval_description))
                                        now = self.time()
                                        if time > 0:
                                            cmd_code = "setdynamic"
                                            val = [
                                                "+",
                                                fr,
                                                [
                                                    "*",
                                                    [
                                                        "-",
                                                        ["glob", "t"],
                                                        now
                                                    ],
                                                    [
                                                        "/",
                                                        [
                                                            "-",
                                                            to,
                                                            fr
                                                        ],
                                                        time
                                                    ]
                                                ]
                                            ]
                                            # rounding
                                            if cmd[6] is not None:
                                                rnd = self.call("script.evaluate-expression", cmd[6], globs=kwargs, description=eval_description)
                                                if (type(rnd) is int or type(rnd) is float) and rnd > 0:
                                                    val = [
                                                        "*",
                                                        [
                                                            "call",
                                                            "round",
                                                            [
                                                                "/",
                                                                val,
                                                                rnd
                                                            ]
                                                        ],
                                                        rnd
                                                    ]
                                            val = [now + time, val]
                                            val[1] = self.call("script.evaluate-expression", val[1], keep_globs={"t": True})
                                        else:
                                            cmd_code = "set"
                                            val = to
                                        val = self.call("script.encode-objects", val)
                                    elif cmd_code == "setdynamic":
                                        till = cmd[4]
                                        if till is not None:
                                            till = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                            if type(till) != int and type(till) != float:
                                                till = None
                                        val = self.call("script.evaluate-expression", cmd[3], globs=kwargs, description=eval_description, keep_globs={"t": True})
                                        val = [till, val]
                                    else:
                                        val = self.call("script.evaluate-expression", cmd[3], globs=kwargs, description=eval_description)
                                    set_attr = getattr(obj, "script_set_attr", None)
                                    if not set_attr:
                                        if getattr(obj, "script_attr", None):
                                            raise ScriptRuntimeError(self._("'%s' has no settable attributes") % self.call("script.unparse-expression", cmd[1]), env)
                                        else:
                                            raise ScriptRuntimeError(self._("'%s' is not an object") % self.call("script.unparse-expression", cmd[1]), env)
                                    tval = type(val)
                                    if not getattr(obj, "allow_compound", False):
                                        if tval != str and tval != type(None) and tval != unicode and tval != long and tval != float and tval != bool and tval != int and tval != list:
                                            raise ScriptRuntimeError(self._("Can't assign compound values ({val}) to the attributes").format(val=tval.__name__ if tval else None), env)
                                    if debug:
                                        if cmd_code == "setdynamic":
                                            if val[0] is None:
                                                self.call("debug-channel.character", char, lambda: self._("setting {obj}.{attr} = {val}").format(obj=self.call("script.unparse-expression", cmd[1]), attr=cmd[2], val=htmlescape(self.call("script.unparse-expression", val[1]))), cls="quest-action", indent=indent+2)
                                            else:
                                                self.call("debug-channel.character", char, lambda: self._("setting {obj}.{attr} = {val} till {till} ({till_human})").format(obj=self.call("script.unparse-expression", cmd[1]), attr=cmd[2], val=htmlescape(self.call("script.unparse-expression", val[1])), till=val[0], till_human=self.call("l10n.time_local", from_unixtime(val[0]))), cls="quest-action", indent=indent+2)
                                        else:
                                            self.call("debug-channel.character", char, lambda: self._("setting {obj}.{attr} = {val}").format(obj=self.call("script.unparse-expression", cmd[1]), attr=cmd[2], val=htmlescape(self.call("script.unparse-expression", val))), cls="quest-action", indent=indent+2)
                                    try:
                                        set_attr(attr, val, env)
                                        modified_objects.add(obj)
                                    except AttributeError as e:
                                        raise ScriptRuntimeError(self._("'{obj}.{attr}' of the {cls} object is not settable").format(obj=self.call("script.unparse-expression", cmd[1]), attr=cmd[2], cls=type(obj).__name__), env)
                                elif cmd_code == "destroy":
                                    if quest == ":activity":
                                        if char.busy and char.busy["tp"] == "activity":
                                            if debug:
                                                self.call("debug-channel.character", char, lambda: self._("activity finished"), cls="quest-action", indent=indent+2)
                                            char.unset_busy()
                                            self.call("quests.send-activity-modifier", char)
                                        else:
                                            if debug:
                                                self.call("debug-channel.character", char, lambda: self._("activity not finished"), cls="quest-error", indent=indent+2)
                                    else:
                                        if cmd[1]:
                                            if debug:
                                                self.call("debug-channel.character", char, lambda: self._("quest finished"), cls="quest-action", indent=indent+2)
                                            char.quests.add_finished(quest)
                                        else:
                                            if debug:
                                                self.call("debug-channel.character", char, lambda: self._("quest failed"), cls="quest-action", indent=indent+2)
                                            char.error(self._("Quest failed"))
                                        char.quests.destroy(quest)
                                        modified_objects.add(char.quests)
                                elif cmd_code == "lock":
                                    if cmd[1] is None:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("locking quest infinitely"), cls="quest-action", indent=indent+2)
                                        char.quests.lock(quest)
                                    else:
                                        timeout = intz(self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description))
                                        if timeout > 100e6:
                                            timeout = 100e6
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("locking quest for %s sec") % timeout, cls="quest-action", indent=indent+2)
                                        char.quests.lock(quest, timeout)
                                elif cmd_code == "timer":
                                    tid = cmd[1]
                                    timeout = intz(self.call("script.evaluate-expression", cmd[2], globs=kwargs, description=eval_description))
                                    if timeout > 100e6:
                                        timeout = 100e6
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("setting timer '{timer}' for {sec} sec").format(timer=tid, sec=timeout), cls="quest-action", indent=indent+2)
                                    if timeout > 0:
                                        char.modifiers.add("timer-%s-%s" % (quest, tid), 1, self.now(timeout))
                                elif cmd_code == "activity-timer":
                                    if quest != ":activity":
                                        raise QuestError(self._("Activity timers can be started within activities only"))
                                    options = cmd[1]
                                    timeout = intz(self.call("script.evaluate-expression", options["timeout"], globs=kwargs, description=eval_description))
                                    if timeout > 100e6:
                                        timeout = 100e6
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("setting activity timer for {sec} sec").format(sec=timeout), cls="quest-action", indent=indent+2)
                                    if timeout > 0:
                                        since_ts = self.time()
                                        till_ts = since_ts + timeout
                                        if "indicator" in options:
                                            progress_expr = self.call("script.evaluate-expression", options["indicator"], globs=kwargs, description=lambda: self._("Progress bar indicator value"), keep_globs={"t": True})
                                        else:
                                            progress_expr = ["/", ["-", ["glob", "t"], since_ts], timeout]
                                        if "text" in options:
                                            text = self.call("script.evaluate-text", options["text"], globs=kwargs, description=lambda: self._("Progress bar text"))
                                        else:
                                            text = None
                                        char.modifiers.add("timer-:activity-done", 1, self.now(timeout), progress_expr=progress_expr, progress_till=till_ts, text=text)
                                        self.call("quests.send-activity-modifier", char)
                                elif cmd_code == "modremove":
                                    mid = cmd[1]
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("removing modifier '{modifier}'").format(modifier=mid), cls="quest-action", indent=indent+2)
                                    char.modifiers.destroy(mid)
                                elif cmd_code == "modifier":
                                    mid = cmd[1]
                                    op = cmd[2]
                                    modval = self.call("script.evaluate-expression", cmd[4], globs=kwargs, description=lambda: self._("modifier value")) if len(cmd) >= 5 else 1
                                    timeout = self.call("script.evaluate-expression", cmd[3], globs=kwargs, description=eval_description)
                                    if timeout is None:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("setting modifier '{modifier}'={modval} infinitely").format(modifier=mid, modval=modval), cls="quest-action", indent=indent+2)
                                        char.modifiers.add(mid, modval, None)
                                    else:
                                        timeout = intz(timeout)
                                        if timeout > 0:
                                            if timeout > 100e6:
                                                timeout = 100e6
                                            if op == "add":
                                                if debug:
                                                    self.call("debug-channel.character", char, lambda: self._("adding modifier '{modifier}'={modval} for {sec} sec").format(modifier=mid, sec=timeout, modval=modval), cls="quest-action", indent=indent+2)
                                                char.modifiers.add(mid, modval, self.now(timeout))
                                            elif op == "prolong":
                                                if debug:
                                                    self.call("debug-channel.character", char, lambda: self._("prolonging modifier '{modifier}'={modval} for {sec} sec").format(modifier=mid, sec=timeout, modval=modval), cls="quest-action", indent=indent+2)
                                                char.modifiers.prolong(mid, modval, timeout)
                                elif cmd_code == "selectitem":
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("opening item selector"), cls="quest-action", indent=indent+2)
                                    itemselector = cmd[1].copy()
                                    if itemselector.get("title"):
                                        itemselector["title"] = self.call("script.evaluate-text", itemselector["title"], globs=kwargs, description=eval_description)
                                    char.quests.itemselector(itemselector, quest)
                                    modified_objects.add(char.quests)
                                elif cmd_code == "dialog":
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("opening dialog"), cls="quest-action", indent=indent+2)
                                    dialog = cmd[1].copy()
                                    if dialog.get("title"):
                                        dialog["title"] = self.call("script.evaluate-text", dialog["title"], globs=kwargs, description=eval_description)
                                    if dialog.get("text"):
                                        dialog["text"] = self.call("script.evaluate-text", dialog["text"], globs=kwargs, description=eval_description)
                                    if dialog.get("inputs"):
                                        inputs = [inp.copy() for inp in dialog["inputs"]]
                                        dialog["inputs"] = inputs
                                        for inp in inputs:
                                            if inp.get("text"):
                                                inp["text"] = self.call("script.evaluate-text", inp["text"], globs=kwargs, description=eval_description)
                                    if dialog.get("buttons"):
                                        buttons = [btn.copy() for btn in dialog["buttons"]]
                                        dialog["buttons"] = buttons
                                        for btn in buttons:
                                            if btn.get("text"):
                                                btn["text"] = self.call("script.evaluate-text", btn["text"], globs=kwargs, description=eval_description)
                                    char.quests.dialog(dialog, quest)
                                    modified_objects.add(char.quests)
                                elif cmd_code == "random":
                                    sum_weight = 0
                                    actions = []
                                    for act in cmd[1]:
                                        weight = self.call("script.evaluate-expression", act[0], globs=kwargs, description=eval_description)
                                        if weight > 0:
                                            sum_weight += weight
                                            actions.append((act, weight))
                                    if sum_weight > 0:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("selecting random execution branch"), cls="quest-action", indent=indent+2)
                                        rnd = random.random() * sum_weight
                                        sum_weight = 0
                                        selected = None
                                        for act, weight in actions:
                                            sum_weight += weight
                                            if sum_weight >= rnd:
                                                selected = act
                                                break
                                        # floating point rounding
                                        if selected is None:
                                            selected = actions[-1]
                                        execute_actions(selected[1], indent+1)
                                    else:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("no cases in random with positive weights"), cls="quest-error", indent=indent+2)
                                elif cmd_code == "combatlog":
                                    if not kwargs.get("combat"):
                                        raise QuestError(self._("'combat log' operator can be used in combat events only"))
                                    text = self.call("script.evaluate-text", cmd[1], globs=kwargs, description=lambda: self._("Evaluation of log text"))
                                    args = {
                                        "text": text
                                    }
                                    if len(cmd) >= 3:
                                        for key in cmd[2].keys():
                                            args[key] = self.call("script.evaluate-expression", cmd[2][key], globs=kwargs, description=lambda: self._("Evaluation of combat log {key} attribute").format(key=key))
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("writing to combat log: {text}").format(text=text), cls="quest-action", indent=indent+2)
                                    kwargs["combat"].textlog(args)
                                elif cmd_code == "combatsyslog":
                                    if not kwargs.get("combat"):
                                        raise QuestError(self._("'combat syslog' operator can be used in combat events only"))
                                    text = self.call("script.evaluate-text", cmd[1], globs=kwargs, description=lambda: self._("Evaluation of system log text"))
                                    args = {
                                        "text": text
                                    }
                                    if len(cmd) >= 3:
                                        for key in cmd[2].keys():
                                            args[key] = self.call("script.evaluate-expression", cmd[2][key], globs=kwargs, description=lambda: self._("Evaluation of combat system log {key} attribute").format(key=key))
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("writing to combat system log: {text}").format(text=text), cls="quest-action", indent=indent+2)
                                    kwargs["combat"].syslog(args)
                                elif cmd_code == "javascript":
                                    script = cmd[1]
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("sending javascript %s") % self.call("script.unparse-expression", script), cls="quest-action", indent=indent+2)
                                    char.javascript(script)
                                elif cmd_code == "chat":
                                    html = self.call("script.evaluate-text", cmd[1], globs=kwargs, description=eval_description)
                                    args = cmd[2]
                                    if "public" in args:
                                        public = self.call("script.evaluate-expression", args["public"], globs=kwargs, description=eval_description)
                                    else:
                                        public = False
                                    if "channel" in args:
                                        channel = self.call("script.evaluate-expression", args["channel"], globs=kwargs, description=eval_description)
                                        channel = utf2str(unicode(channel))
                                    else:
                                        channel = "wld"
                                    if "cls" in args:
                                        cls = self.call("script.evaluate-expression", args["cls"], globs=kwargs, description=eval_description)
                                    else:
                                        cls = "quest"
                                    if public:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("sending public chat message to channel {channel}: {msg}").format(channel=htmlescape(str2unicode(channel)), msg=htmlescape(str2unicode(html))), cls="quest-action", indent=indent+2)
                                        self.call("chat.message", html=html, cls=cls, hide_time=True, hl=True, channel=channel)
                                    else:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("sending chat message to channel {channel}: {msg}").format(channel=htmlescape(str2unicode(channel)), msg=htmlescape(str2unicode(html))), cls="quest-action", indent=indent+2)
                                        self.call("chat.message", html=html, cls=cls, private=True, recipients=[char], hide_time=True, hl=True, channel=channel)
                                elif cmd_code == "teleport":
                                    locid = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=eval_description)
                                    if type(locid) != str and type(locid) != unicode:
                                        raise QuestError(self._("Location id must be a string. Found %s" % type(locid).__name__))
                                    loc = self.call("location.info", locid)
                                    if loc:
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("teleporting %s") % htmlescape(loc.name_t), cls="quest-action", indent=indent+2)
                                        char.teleport(loc, char.instance, [self.now(), self.now()])
                                        try:
                                            tasklet.quest_teleported.add(char.uuid)
                                        except AttributeError:
                                            tasklet.quest_teleported = set()
                                            tasklet.quest_teleported.add(char.uuid)
                                    else:
                                        raise QuestError(self._("Missing location %s") % locid)
                                elif cmd_code == "equipbreak":
                                    globs = kwargs.copy()
                                    changed = False
                                    if char.equip:
                                        for slot_id, item in char.equip.equipped_slots():
                                            globs["slot"] = slot_id
                                            globs["item"] = item
                                            fractions = intz(self.call("script.evaluate-expression", cmd[1], globs=globs, description=lambda: self._("Evaluation of damage to the equip")))
                                            if debug:
                                                self.call("debug-channel.character", char, lambda: self._("breaking item {item} in slot {slot}. damage={damage}").format(item=htmlescape(item.name), slot=slot_id, damage=fractions), cls="quest-action", indent=indent+2)
                                            if fractions > 0:
                                                spent, destroyed = char.equip.break_item(slot_id, fractions, "break", quest=quest)
                                                if not spent and debug:
                                                    self.call("debug-channel.character", char, lambda: self._("could not break item {item} in slot {slot}").format(item=htmlescape(item.name), slot=slot_id), cls="quest-error", indent=indent+3)
                                                if spent and destroyed:
                                                    if debug:
                                                        self.call("debug-channel.character", char, lambda: self._("item {item} in slot {slot} has broken completely").format(item=htmlescape(item.name), slot=slot_id), cls="quest-action", indent=indent+3)
                                                    if kwargs.get("combat") and kwargs.get("member"):
                                                        kwargs["combat"].textlog({
                                                            "text": self._('<span class="combat-log-item">{item}</span> of character <span class="combat-log-member">{name}</span> has been broken').format(item=htmlescape(item.name), name=htmlescape(kwargs["member"].name)),
                                                            "cls": "combat-log-equipbreak",
                                                        })
                                                changed = True
                                    if changed:
                                        char.equip.validate()
                                        char.inventory.store()
                                elif cmd_code == "combat":
                                    options = cmd[1]
                                    # prepare combat request
                                    creq = CombatRequest(self.app())
                                    # combat system
                                    rules = options.get("rules")
                                    if rules is None:
                                        raise QuestError(self._("Combat rules not specified. Specify default combat rules in the combat comfiguration"))
                                    creq.set_rules(rules)
                                    # combat title
                                    title = options.get("title")
                                    if title:
                                        title = self.call("script.evaluate-text", title, globs=kwargs, description=lambda: self._("Combat title"))
                                        creq.set_title(title)
                                    # combat flags
                                    flags = options.get("flags")
                                    if flags:
                                        creq.set_flags(flags)
                                    # members
                                    n_char = 0
                                    n_npc = 0
                                    for member in options["members"]:
                                        rmember = evaluate_member(member)
                                        try:
                                            if rmember["object"][0] == "character":
                                                n_char += 1
                                            else:
                                                n_npc += 1
                                        except KeyError:
                                            n_npc += 1
                                        creq.add_member(rmember)
                                    # npc combat check
                                    if not n_char:
                                        raise QuestError(self._("Combats without character members are forbidden"))
                                    if n_npc > n_char * 10:
                                        raise QuestError(self._("Number of NPC characters in a combat can't be more then 10x number of player members"))
                                    # launch combat
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("launching combat"), cls="quest-action", indent=indent+2)
                                    try:
                                        creq.run()
                                    except CombatMemberBusyError as e:
                                        self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent+2)
                                        char.error(e.val)
                                        raise AbortHandler()
                                    except CombatRunError as e:
                                        raise QuestError(e.val)
                                    else:
                                        for member in creq.members:
                                            if member["object"][0] == "character":
                                                char_uuid = member["object"][1]
                                                try:
                                                    tasklet.quest_combat_started[char_uuid] = creq.uuid
                                                except AttributeError:
                                                    tasklet.quest_combat_started = {char_uuid: creq.uuid}
                                elif cmd_code == "combatjoin":
                                    combat_id = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=lambda: self._("Evaluation of the combat id"))
                                    rmember = evaluate_member(cmd[2])
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("joining {name} to combat {combat} for team {team}").format(name=rmember.get("name"), combat=combat_id, team=rmember.get("team")), cls="quest-action", indent=indent+2)
                                    try:
                                        combat = CombatInterface(self.app(), combat_id)
                                        result = combat.join(rmember)
                                    except CombatUnavailable as e:
                                        self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent+2)
                                        char.error(self._("Combat is unavailable"))
                                        raise AbortHandler()
                                    else:
                                        if result.get("error"):
                                            self.call("debug-channel.character", char, result["error"], cls="quest-error", indent=indent+2)
                                            char.error(self._("Unable to join the combat"))
                                            raise AbortHandler()
                                        else:
                                            if rmember["object"][0] == "character":
                                                char_uuid = rmember["object"][1]
                                                try:
                                                    tasklet.quest_combat_started[char_uuid] = combat_id
                                                except AttributeError:
                                                    tasklet.quest_combat_started = {char_uuid: combat_id}
                                elif cmd_code == "sound":
                                    url = self.call("script.evaluate-text", cmd[1], globs=kwargs, description=lambda: self._("Evaluation of the sound URL to play"))
                                    options = cmd[2]
                                    attrs = {}
                                    if "mode" in options:
                                        mode = self.call("script.evaluate-expression", options["mode"], globs=kwargs, description=lambda: self._("Evaluation of 'mode' argument"))
                                        if mode != "wait" and mode != "overlap" and mode != "stop":
                                            raise QuestError(self._("Invalid value for 'mode' attribute: '%s'") % mode)
                                        attrs["mode"] = mode
                                    if "volume" in options:
                                        volume = self.call("script.evaluate-expression", options["volume"], globs=kwargs, description=lambda: self._("Evaluation of 'volume' argument"))
                                        if type(volume) != int:
                                            raise QuestError(self._("Invalid value type for 'volume' attribute: '%s'") % type(volume).__name__)
                                        attrs["volume"] = volume
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("playing sound {url}").format(url=url.split("/")[-1]), cls="quest-action", indent=indent+2)
                                    self.call("sound.play", char, url, **attrs)
                                elif cmd_code == "music":
                                    playlist = self.call("script.evaluate-expression", cmd[1], globs=kwargs, description=lambda: self._("Evaluation of the music playlist identifier"))
                                    options = cmd[2]
                                    attrs = {}
                                    if "fade" in options:
                                        fade = self.call("script.evaluate-expression", options["fade"], globs=kwargs, description=lambda: self._("Evaluation of 'fade' argument"))
                                        if type(fade) != int:
                                            raise QuestError(self._("Invalid value type for 'fade' attribute: '%s'") % type(fade).__name__)
                                        attrs["fade"] = fade
                                    if "volume" in options:
                                        volume = self.call("script.evaluate-expression", options["volume"], globs=kwargs, description=lambda: self._("Evaluation of 'volume' argument"))
                                        if type(volume) != int:
                                            raise QuestError(self._("Invalid value type for 'volume' attribute: '%s'") % type(volume).__name__)
                                        attrs["volume"] = volume
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("playing music {playlist}").format(playlist=playlist), cls="quest-action", indent=indent+2)
                                    self.call("sound.music", char, playlist, **attrs)
                                elif cmd_code == "musicstop":
                                    options = cmd[1]
                                    attrs = {}
                                    if "fade" in options:
                                        fade = self.call("script.evaluate-expression", options["fade"], globs=kwargs, description=lambda: self._("Evaluation of 'fade' argument"))
                                        if type(fade) != int:
                                            raise QuestError(self._("Invalid value type for 'fade' attribute: '%s'") % type(fade).__name__)
                                        attrs["fade"] = fade
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("stopping music"), cls="quest-action", indent=indent+2)
                                    self.call("sound.music", char, None, **attrs)
                                elif cmd_code == "sendchar":
                                    for param_code in cmd[1]:
                                        param, val = char.find_param_and_eval(param_code)
                                        if param:
                                            char.send_param_force(param, val)
                                            if debug:
                                                self.call("debug-channel.character", char, lambda: self._("sending parameter %s") % param_code, cls="quest-action", indent=indent+2)
                                        else:
                                            raise QuestError(self._("Parameter '%s' not found") % param_code)
                                elif cmd_code == "activity":
                                    variables = {}
                                    for key, val in cmd[2].items():
                                        variables[key] = self.call("script.evaluate-expression", val, globs=kwargs, description=lambda: self._("Evaluation of '%s' argument") % key)
                                    options = {
                                        "hdls": cmd[1],
                                        "vars": variables,
                                        "debug": debug,
                                        "abort_event": "quests.activity-aborted",
                                    }
                                    if "priority" in variables:
                                        options["priority"] = variables["priority"]
                                        del variables["priority"]
                                        tp = type(options["priority"])
                                        if tp != int and tp != long and tp != float:
                                            raise QuestError(self._("Activity priority must be a number. Got: %s") % tp.__name__)
                                    if debug:
                                        self.call("debug-channel.character", char, lambda: self._("starting activity"), cls="quest-action", indent=indent+2)
                                    if not char.set_busy("activity", options):
                                        char.error(self._("You are busy"))
                                        if debug:
                                            self.call("debug-channel.character", char, lambda: self._("activity not started (character is busy)"), cls="quest-error", indent=indent+3)
                                        raise AbortHandler()
                                    char.modifiers.destroy("timer-:activity-done")
                                    self.qevent("event-:activity-start", char=char)
                                else:
                                    raise QuestSystemError(self._("Unknown quest action: %s") % cmd_code)
                            except QuestError as e:
                                e = ScriptError(e.val, env)
                                self.call("exception.report", e)
                                self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent+2)
                            except ScriptError as e:
                                self.call("exception.report", e)
                                self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent+2)
                            except AbortHandler:
                                raise
                            except Exception as e:
                                self.exception(e)
                                self.call("debug-channel.character", char, self._("System exception: %s") % e.__class__.__name__, cls="quest-error", indent=indent+2)
                            Tasklet.yield_()
                    try:
                        execute_actions(act, indent)
                    except AbortHandler:
                        pass
                    for obj in modified_objects:
                        obj.store()
            # check activity
            if char.busy and char.busy.get("tp") == "activity":
                try:
                    debug = char.busy.get("debug", True)
                    kwargs["activity"] = char.activity
                    execute_handlers(char.busy.get("hdls"), ":activity", kwargs)
                except QuestError as e:
                    raise ScriptError(e.val, env)
                finally:
                    del kwargs["activity"]
            # check quests
            for quest in quests:
                try:
                    kwargs["quest"] = CharQuest(char.quests, quest)
                    debug = self.conf("quests.debug_%s" % quest)
                    # quest availability
                    qinfo = self.conf("quests.list", {}).get(quest)
                    if not qinfo:
                        continue
                    available = self.call("script.evaluate-expression", qinfo.get("available", 1), globs={"char": char}, description=self._("Quest %s availability") % quest)
                    if not available:
                        if debug:
                            self.call("debug-channel.character", char, lambda: self._("skipping unavailable quest {quest}").format(quest=quest), cls="quest-handler", indent=indent+1)
                        continue
                    # state availability
                    states = self.conf("quest-%s.states" % quest, {})
                    state_id = char.quests.get(quest, "state", "init")
                    state = states.get(state_id)
                    if debug:
                        self.call("debug-channel.character", char, lambda: self._("quest={quest}, state={state}").format(quest=quest, state=state_id), cls="quest-handler", indent=indent+1)
                    if not state:
                        continue
                    script = state.get("script")
                    if not script:
                        continue
                    if script[0] != "state":
                        continue
                    script = script[1]
                    execute_handlers(script.get("hdls"), quest, kwargs)
                except QuestError as e:
                    raise ScriptError(e.val, env)
                finally:
                    del kwargs["quest"]
        except ScriptError as e:
            self.call("exception.report", e)
            self.call("debug-channel.character", char, e.val, cls="quest-error", indent=indent)
        except Exception as e:
            self.exception(e)
            self.call("debug-channel.character", char, self._("System exception: %s") % e.__class__.__name__, cls="quest-error", indent=indent)
        finally:
            tasklet.quest_indent = old_indent
            if old_indent is None:
                tokens = []
                quest_given_items = getattr(char, "quest_given_items", None)
                if quest_given_items:
                    for key, val in quest_given_items.iteritems():
                        name = '<span style="font-weight: bold">%s</span> &mdash; %s' % (htmlescape(key), self._("%d pcs") % val)
                        tokens.append(name)
                    delattr(char, "quest_given_items")
                quest_given_money = getattr(char, "quest_given_money", None)
                if quest_given_money:
                    for currency, amount in quest_given_money.iteritems():
                        tokens.append(self.call("money.price-html", amount, currency))
                    delattr(char, "quest_given_money")
                if tokens:
                    char.message(u"<br />".join(tokens), title=self._("You have got:"))
        # processing character redirects after processing quest operation
        if old_indent is None:
            try:
                req = self.req()
            except AttributeError:
                req = None
            quest_combat_started = getattr(tasklet, "quest_combat_started", None)
            if quest_combat_started:
                for char_uuid, combat_id in quest_combat_started.iteritems():
                    uri = "/combat/interface/%s" % combat_id
                    if req and req.user() == char_uuid:
                        try:
                            req.quest_redirects[char_uuid] = uri
                        except AttributeError:
                            req.quest_redirects = {char_uuid: uri}
                    else:
                        char = self.character(char_uuid)
                        char.main_open(uri)
            quest_teleported = getattr(tasklet, "quest_teleported", None)
            if quest_teleported:
                for char_uuid in quest_teleported:
                    if req and req.user() == char_uuid:
                        try:
                            req.quest_redirects[char.uuid] = "/location"
                        except AttributeError:
                            req.quest_redirects = {char.uuid: "/location"}
                    else:
                        char = self.character(char_uuid)
                        char.main_open("/location")
                del tasklet.quest_teleported
            if char.quests.dialogs:
                if req and req.user() == char.uuid:
                    try:
                        req.quest_redirects[char.uuid] = "/quest/dialog"
                    except AttributeError:
                        req.quest_redirects = {char.uuid: "/quest/dialog"}
                else:
                    char.main_open("/quest/dialog")
                
    def get_char(self, uuid):
        return CharQuests(self.app(), uuid)

    def items_menu(self, character, item_type, menu):
        globs = None
        for action in self.conf("quest-item-actions.list", []):
            if globs is None:
                globs = {"char": character, "item": item_type}
            available = self.call("script.evaluate-expression", action["available"], globs=globs, description=lambda: self._("Item action: %s") % action["code"])
            if available:
                menu.append({"href": "/item/action/%s/%s" % (utf2str(action["code"]), utf2str(item_type.dna)), "html": htmlescape(action["text"]), "order": action["order"]})

    def action(self):
        req = self.req()
        character = self.character(req.user())
        # validating args
        m = re_item_action.match(req.args)
        if not m:
            self.call("web.not_found")
        code, dna = m.group(1, 2)
        # validating item type
        item, quantity = character.inventory.find_dna(dna)
        if not item:
            character.error(self._("No items of such type"))
            self.call("web.redirect", "/inventory")
        cat = item.cat("inventory")
        # validating action
        action = None
        for a in self.conf("quest-item-actions.list", []):
            if a["code"] == code:
                action = a
                break
        if action is None:
            self.call("web.redirect", "/inventory?cat=%s#%s" % (cat, item.dna))
        # checking availability
        globs = {"char": character, "item": item}
        available = self.call("script.evaluate-expression", action["available"], globs=globs, description=lambda: self._("Item action: %s") % action["code"])
        if not available:
            character.error(self._("This item action is currently unavailable"))
            self.call("web.redirect", "/inventory?cat=%s#%s" % (cat, item.dna))
        self.qevent("item-%s" % action["code"], char=character, item=item)
        self.call("quest.check-redirects")
        self.call("web.redirect", "/inventory?cat=%s#%s" % (cat, item.dna))

    def request_processed(self):
        req = self.req()
        redirs = getattr(req, "quest_redirects", None)
        if redirs:
            for char_uuid, uri in redirs.iteritems():
                char = self.character(char_uuid)
                if char.tech_online:
                    char.main_open(uri)

    def check_dialogs(self):
        req = self.req()
        character = self.character(req.user())
        busy = character.busy
        if busy and busy.get("show_uri"):
            self.call("web.redirect", busy.get("show_uri"))
        if character.quests.dialogs:
            self.call("web.redirect", "/quest/dialog")

    def check_redirects(self):
        req = self.req()
        redirs = getattr(req, "quest_redirects", None)
        if redirs:
            user = req.user()
            uri = redirs.get(user)
            if uri:
                del redirs[user]
                self.call("web.redirect", uri)

    def dialog(self):
        req = self.req()
        character = self.character(req.user())
        dialogs = character.quests.dialogs
        if not dialogs:
            self.call("web.redirect", self.call("game-interface.default-location") or "/location")
        dialog = dialogs[0]
        globs = {"char": character}
        if "quest" in dialog:
            globs["quest"] = character.quests.quest(dialog["quest"])
        if dialog.get("type") == "itemselector":
            # item selector dialog
            vars = {}
            def cancel():
                # close dialog
                del dialogs[0]
                character.quests.touch()
                character.quests.store()
                # send event
                if "oncancel" in dialog:
                    self.qevent("event-%s-%s" % (dialog.get("quest"), dialog["oncancel"]), char=character)
                self.call("quest.check-redirects")
            def grep(item_type):
                if "show" not in dialog:
                    return True
                globs["item"] = item_type
                try:
                    available = self.call("script.evaluate-expression", dialog["show"], globs=globs, description=lambda: self._("Item %s availability") % item_type.dna)
                except ScriptError as e:
                    # Send only one exception report to admin (avoid flooding)
                    if "script_exception_shown" not in vars:
                        self.call("exception.report", e)
                        vars["script_exception_shown"] = True
                    available = False
                return available
            if req.param("dialog") == dialog["uuid"]:
                if req.param("cancel"):
                    cancel()
                    self.call("web.redirect", self.call("game-interface.default-location") or "/location")
                elif req.param("item"):
                    # search item
                    item_type, quantity = character.inventory.find_dna(req.param("item"))
                    if item_type and quantity > 0:
                        if grep(item_type):
                            globs["item"] = item_type
                            # search action
                            sel_action = req.param("action")
                            for action in dialog.get("actions", []):
                                if action["event"] == sel_action:
                                    # check action availability
                                    try:
                                        available = self.call("script.evaluate-expression", action.get("available", 1), globs=globs, description=lambda: self._("Action %s availability") % action["event"])
                                    except ScriptError as e:
                                        # Send only one exception report to admin (avoid flooding)
                                        if "script_exception_shown" not in vars:
                                            self.call("exception.report", e)
                                            vars["script_exception_shown"] = True
                                        available = False
                                    if available:
                                        # close dialog
                                        del dialogs[0]
                                        character.quests.touch()
                                        character.quests.store()
                                        # execute action
                                        self.qevent("event-%s-%s" % (dialog.get("quest"), action["event"]), char=character, item=item_type)
                                        self.call("quest.check-redirects")
                                        self.call("web.redirect", self.call("game-interface.default-location") or "/location")
            # looking for items to select
            def render(item_type, ritem):
                globs["item"] = item_type
                if dialog.get("actions"):
                    menu = []
                    for action in dialog["actions"]:
                        if not self.call("script.evaluate-expression", action.get("available", 1), globs=globs, description=lambda: self._("Action %s availability") % action["event"]):
                            continue
                        menu.append({
                            "href": "/quest/dialog?dialog=%s&amp;action=%s&amp;item=%s" % (
                                dialog["uuid"],
                                action["event"],
                                item_type.dna,
                            ),
                            "html": self.call("script.evaluate-text", action["name"], globs=globs, description=lambda: self._("Action %s text") % action["event"]),
                        })
                    ritem["menu"] = menu
                    # don't show item if no actions are available
                    if not menu:
                        ritem.clear()
                        return
                if dialog.get("fields"):
                    if "params" not in ritem:
                        ritem["params"] = []
                    for field in dialog["fields"]:
                        if not self.call("script.evaluate-expression", field.get("visible", 1), globs=globs, description=lambda: self._("Field visibility")):
                            continue
                        ritem["params"].append({
                            "name": self.call("script.evaluate-text", field["name"], globs=globs, description=lambda: self._("Field name")),
                            "value": self.call("script.evaluate-text", field["value"], globs=globs, description=lambda: self._("Field value")),
                        })
            self.call("inventory.render", character.inventory, vars, grep=grep, render=render, viewer=character)
            vars["title"] = dialog.get("title")
            vars["menu_left"] = [
                {
                    "href": "/quest/dialog?dialog=%s&amp;cancel=1" % dialog["uuid"],
                    "html": self._("Cancel"),
                    "lst": True
                }
            ]
            if not vars["categories"]:
                cancel()
                self.call("game.internal-error", self._("No items available"))
            self.call("game.response_internal", dialog.get("template", "inventory.html"), vars)
        else:
            # general dialog
            if req.ok():
                if utf2str(dialog.get("uuid", "")) != utf2str(req.args):
                    self.call("web.redirect", "/quest/dialog")
                event = req.param("event")
                found = False
                for btn in dialog["buttons"]:
                    if btn.get("event", "") == event:
                        try:
                            available = self.call("script.evaluate-expression", btn.get("available", 1), globs=globs, description=self._("Button '%s' availability") % event)
                        except ScriptError as e:
                            self.exception(e)
                        else:
                            if available:
                                found = True
                        break
                if found:
                    # close dialog
                    del dialogs[0]
                    character.quests.touch()
                    character.quests.store()
                    # send event
                    if event:
                        params = {}
                        if "inputs" in dialog:
                            for inp in dialog["inputs"]:
                                params["inp_%s" % inp["id"]] = req.param("input-%s" % inp["id"])
                        self.qevent("event-%s-%s" % (dialog.get("quest"), event), char=character, **params)
                    self.call("quest.check-redirects")
                    self.call("web.redirect", self.call("game-interface.default-location") or "/location")
                else:
                    character.error(self._("This button is unavailable"))
            buttons = []
            default_button = None
            default_event = None
            href = "/quest/dialog/%s" % dialog.get("uuid", "")
            btn_id = 0
            for btn in dialog["buttons"]:
                try:
                    available = self.call("script.evaluate-expression", btn.get("available", 1), globs=globs, description=self._("Button '%s' availability") % btn.get("event"))
                except ScriptError as e:
                    self.exception(e)
                    continue
                else:
                    if not available:
                        continue
                btn_id += 1
                buttons.append({
                    "id": btn_id,
                    "text": htmlescape(btn.get("text")),
                    "event": btn.get("event"),
                    "href": href,
                    "default": btn.get("default"),
                })
            if len(buttons) == 1:
                buttons[0]["default"] = True
            for btn in buttons:
                if btn.get("default"):
                    default_button = btn.get("id")
                    default_event = btn.get("event")
                    break
            vars = {
                "title": htmlescape(dialog.get("title")),
                "buttons": buttons,
                "href": href,
                "default_button": default_button,
                "default_event": default_event,
            }
            if "inputs" in dialog:
                inputs = []
                vars["inputs"] = inputs
                for inp in dialog["inputs"]:
                    inputs.append(inp)
            try:
                content = self.call("game.parse_internal", dialog.get("template", "dialog.html"), vars, dialog.get("text"))
            except TemplateException as e:
                self.exception(e)
                content = self.call("game.parse_internal", "dialog.html", vars, dialog.get("text"))
            self.call("game.response_internal", "dialog-scripts.html", vars, content)

    def money_description_quest(self):
        return {
            "args": ["quest"],
            "text": lambda op: self._("Quest: %s") % self.quest_name(op.get("quest")),
        }

    def quest_name(self, qid):
        quest = self.conf("quests.list", {}).get(qid)
        if quest is None:
            return self._("quest///deleted")
        return quest.get("name")

    def gameinterface_buttons(self, buttons):
        buttons.append({
            "id": "quests",
            "href": "/quests",
            "target": "main",
            "icon": "quests.png",
            "title": self._("Quests"),
            "block": "left-menu",
            "order": 15,
        })

    def quests(self):
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        quest_list = [(qid, quest) for qid, quest in self.conf("quests.list", {}).iteritems() if quest.get("enabled")]
        quest_list.sort(cmp=lambda x, y: cmp(x[1].get("order", 0), y[1].get("order", 0)) or cmp(x[1].get("name"), y[1].get("name")) or cmp(x[0], y[0]))
        # list of current quests
        cur_quests = []
        # list of finished quests
        finished_quests = []
        # button pressed
        button_pressed = req.ok() and req.environ.get("REQUEST_METHOD") == "POST"
        selected_quest = req.param("quest")
        selected_button = req.param("button")
        for qid, quest in quest_list:
            # current quest
            sid = character.quests.get(qid, "state", "init")
            if sid != "init":
                rquest = {
                    "id": qid,
                    "name": htmlescape(quest.get("name")),
                    "state": sid,
                }
                state = self.conf("quest-%s.states" % qid, {}).get(sid)
                if state:
                    # description
                    if state.get("description"):
                        rquest["description"] = self.call("script.evaluate-text", state.get("description"), globs={"char": character, "quest": character.quests.quest(qid)}, description=lambda: self._("Quest %s description") % qid)
                    cur_quests.append(rquest)
                    # buttons
                    rbuttons = []
                    script = state.get("script")
                    if script:
                        if script[0] != "state":
                            raise RuntimeError(self._("Invalid quest states object. Expected {expected}. Found: {found}").format(expected="state", found=script[0]))
                        if "hdls" in script[1]:
                            for handler in script[1]["hdls"]:
                                if handler[0] == "comment":
                                    continue
                                if handler[0] != "hdl":
                                    raise RuntimeError(self._("Invalid quest states object. Expected {expected}. Found: {found}").format(expected="hdl", found=script[0]))
                                tp = handler[1]["type"]
                                if tp[0] == "button":
                                    rbuttons.append({
                                        "id": tp[1],
                                        "text": self.call("script.evaluate-text", tp[2], globs={"char": character, "quest": character.quests.quest(qid)}, description=lambda: self._("Button '{button}' text in the quest '{quest}'").format(quest=qid, button=tp[1])),
                                        "href": "/quests#%s" % qid,
                                    })
                                    # handling button press
                                    if button_pressed and selected_quest == qid and selected_button == tp[1]:
                                        self.qevent("button-%s-%s" % (qid, tp[1]), char=character)
                                        self.call("quest.check-redirects")
                                        self.call("web.redirect", "/quests")
                    if rbuttons:
                        rbuttons[-1]["lst"] = True
                        rquest["buttons"] = rbuttons
            # finished quest
            finished = character.quests.finished.get(qid)
            if finished:
                performed = finished.get("performed")
                rquest = {
                    "performed": self.call("l10n.time_local", performed),
                    "performed_raw": performed,
                    "quest": {
                        "id": qid,
                        "name": htmlescape(quest.get("name")),
                    },
                }
                finished_quests.append(rquest)
        # button press was not handled (invalid params?)
        if button_pressed:
            character.error(self._("This button is no more valid"))
        # rendering output
        vars = {
            "Current": self._("questlist///Current"),
            "Finished": self._("questlist///Finished"),
            "NoQuestsUndergo": self._("No quests currently undergo"),
            "NoQuestsFinished": self._("No quests finished yet"),
        }
        if cur_quests:
            cur_quests[-1]["lst"] = True
            vars["cur_quests"] = cur_quests
        if finished_quests:
            finished_quests.sort(cmp=lambda x, y: cmp(y.get("performed_raw"), x.get("performed_raw")))
            finished_quests[-1]["lst"] = True
            vars["finished_quests"] = finished_quests
        self.call("game.response_internal", "quests.html", vars)

    def character_online(self, character):
        self.qevent("online", char=character)

    def character_offline(self, character):
        self.qevent("offline", char=character)

    def ext_quest_event(self):
        req = self.req()
        character = self.character(req.user())
        if character.quests.dialogs:
            character.error(self._("You have opened dialogs"))
        else:
            ev = req.param("ev")
            if not ev:
                character.error(self._("Event identifier not specified"))
            elif not re_valid_identifier.match(ev):
                character.error(self._("Event identifier must start with latin letter or '_'. Other symbols may be latin letters, digits or '_'"))
            else:
                globs = {}
                for k, v in req.param_dict().iteritems():
                    if k.startswith("targetchar") and re_valid_identifier.match(k):
                        targetchar = self.character(v[0])
                        if targetchar.valid:
                            globs[k] = targetchar
                    elif re_arg_param.match(k):
                        globs[k] = str2unicode(v[0])
                self.qevent("clicked-%s" % ev, char=character, **globs)
                redirs = getattr(req, "quest_redirects", None)
                if redirs:
                    uri = redirs.get(character.uuid)
                    if uri:
                        del redirs[character.uuid]
                        self.call("web.response_json", {"ok": True, "redirect": uri})
                self.call("web.response_json", {"ok": True})
        self.call("web.response_json", {"error": True})

    def location_map_zone_event_render(self, zone, rzone):
        rzone["ev"] = jsencode(zone.get("ev"))

    def interface_render_button(self, btn, rbtn):
        rbtn["qevent"] = jsencode(btn.get("qevent"))
