from mg.core.tools import *
from mg.constructor.storage import DBStaticObject, DBStaticObjectList
from mg.core.cass import ObjectNotFoundException
import mg.constructor
import hashlib
import re

re_valid_identifier = re.compile(r'^[a-z_][a-z0-9\_]*$', re.IGNORECASE)
re_del = re.compile(r'del/(.+)$')
re_tracks = re.compile(r'([a-z_0-9]+)/tracks(?:|/(.+))$', re.IGNORECASE)

class SoundAdmin(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-sound.index", self.menu_sound_index)
        self.rhook("headmenu-admin-music.playlists", self.headmenu_playlists)
        self.rhook("ext-admin-music.playlists", self.admin_playlists, priv="music.playlists")
        self.rhook("admin-locations.links", self.locations_links)
        self.rhook("ext-admin-locations.music", self.admin_locations_music, priv="music.locations")
        self.rhook("headmenu-admin-locations.music", self.headmenu_locations_music)
        self.rhook("admin-storage.nondeletable", self.nondeletable)
        self.rhook("admin-combats.profile-form", self.combats_profile_form)
        self.rhook("admin-combats.profile-update", self.combats_profile_update)
        self.rhook("advice-admin-music.index", self.advice_music)

    def advice_music(self, hook, args, advice):
        advice.append({"title": self._("Sound documentation"), "content": self._('You can find detailed information on the sound engine in the <a href="//www.%s/doc/sound" target="_blank">sound engine page</a> in the reference manual.') % self.main_host, "order": 10})

    def combats_profile_form(self, info, fields):
        fields.append({"type": "header", "html": self._("Music settings")})
        playlists = []
        playlists.append((None, self._("Don't touch background music")))
        for playlist in self.conf("music.playlists", []):
            playlists.append((playlist["code"], u'%s - %s' % (playlist["code"], htmlescape(playlist["name"]))))
        fields.append({"name": "music_playlist", "value": info.get("music_playlist"), "values": playlists, "type": "combo", "label": self._("Music during combat")})
        fields.append({"name": "music_volume", "label": self._("Music volume (0-100)"), "value": info.get("music_volume", 50), "condition": "[music_playlist]"})
        fields.append({"name": "music_fade", "label": self._("Music crossfade (in milliseconds)"), "value": info.get("music_fade", 3000), "condition": "[music_playlist]"})

    def combats_profile_update(self, info, errors):
        req = self.req()
        valid_playlists = set()
        for playlist in self.conf("music.playlists", []):
            valid_playlists.add(playlist["code"])
        # music_playlist
        music_playlist = req.param("v_music_playlist")
        if not music_playlist:
            music_playlist = None
        elif music_playlist not in valid_playlists:
            errors["v_music_playlist"] = self._("Select a valid playlist")
        else:
            info["music_playlist"] = music_playlist
        # music_volume
        if music_playlist:
            music_volume = req.param("music_volume")
            if not valid_nonnegative_int(music_volume):
                errors["music_volume"] = self._("Nonnegative integer expected")
            else:
                music_volume = intz(music_volume)
                if music_volume < 0:
                    errors["music_volume"] = self._("Minimal value is %d") % 0
                elif music_volume > 100:
                    errors["music_volume"] = self._("Maximal value is %d") % 100
                else:
                    info["music_volume"] = music_volume
        # music_fade
        if music_playlist:
            music_fade = req.param("music_fade")
            if not valid_nonnegative_int(music_fade):
                errors["music_fade"] = self._("Nonnegative integer expected")
            else:
                music_fade = intz(music_fade)
                if music_fade < 0:
                    errors["music_fade"] = self._("Minimal value is %d") % 0
                elif music_fade > 20000:
                    errors["music_fade"] = self._("Maximal value is %d") % 20000
                else:
                    info["music_fade"] = music_fade

    def nondeletable(self, uuids):
        for playlist in self.conf("music.playlists", []):
            for track in playlist.get("tracks", []):
                uuids.add(track)

    def headmenu_locations_music(self, args):
        return [self._("Music"), "locations/editor/%s" % htmlescape(args)]

    def admin_locations_music(self):
        req = self.req()
        loc_id = req.args
        loc = self.location(loc_id)
        if not loc.valid:
            self.call("web.not_found")
        # advice
        self.call("admin.advice", {"title": self._("Music documentation"), "content": self._('You can find detailed information on the location music system in the <a href="//www.%s/doc/sound" target="_blank">sounds page</a> in the reference manual.') % self.main_host, "order": 0})
        # process form
        if req.ok():
            errors = {}
            valid_playlists = set()
            for playlist in self.conf("music.playlists", []):
                valid_playlists.add(playlist["code"])
            # music_playlist
            music_playlist = req.param("v_music_playlist")
            if not music_playlist:
                music_playlist = None
            elif music_playlist not in valid_playlists:
                errors["v_music_playlist"] = self._("Select a valid playlist")
            # music_volume
            if music_playlist:
                music_volume = req.param("music_volume")
                if not valid_nonnegative_int(music_volume):
                    errors["music_volume"] = self._("Nonnegative integer expected")
                else:
                    music_volume = intz(music_volume)
                    if music_volume < 0:
                        errors["music_volume"] = self._("Minimal value is %d") % 0
                    elif music_volume > 100:
                        errors["music_volume"] = self._("Maximal value is %d") % 100
            # music_fade
            music_fade = req.param("music_fade")
            if not valid_nonnegative_int(music_fade):
                errors["music_fade"] = self._("Nonnegative integer expected")
            else:
                music_fade = intz(music_fade)
                if music_fade < 0:
                    errors["music_fade"] = self._("Minimal value is %d") % 0
                elif music_fade > 20000:
                    errors["music_fade"] = self._("Maximal value is %d") % 20000
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store
            loc.db_location.set("music_playlist", music_playlist)
            if music_playlist:
                loc.db_location.set("music_volume", music_volume)
            loc.db_location.store()
            self.call("admin.response", self._("Settings stored"), {})
        # show form
        playlists = []
        playlists.append((None, self._("No music")))
        for playlist in self.conf("music.playlists", []):
            playlists.append((playlist["code"], u'%s - %s' % (playlist["code"], htmlescape(playlist["name"]))))
        fields = [
            {"name": "music_playlist", "type": "combo", "label": self._("Background music"), "value": loc.db_location.get("music_playlist"), "values": playlists},
            {"name": "music_volume", "label": self._("Music volume (0-100)"), "value": loc.db_location.get("music_volume", 50), "condition": "[music_playlist]"},
            {"name": "music_fade", "label": self._("Music crossfade (in milliseconds)"), "value": loc.db_location.get("music_fade", 3000)},
        ]
        self.call("admin.form", fields=fields)

    def locations_links(self, location, links):
        req = self.req()
        if req.has_access("music.locations"):
            links.append({"hook": "locations/music/%s" % location.uuid, "text": self._("Music"), "order": 30})

    def permissions_list(self, perms):
        perms.append({"id": "music.playlists", "name": self._("Configuration of music playlists")})
        perms.append({"id": "music.locations", "name": self._("Configuration of locations music")})

    def menu_root_index(self, menu):
        menu.append({"id": "sound.index", "text": self._("Sounds"), "order": 50})

    def menu_sound_index(self, menu):
        req = self.req()
        if req.has_access("music.playlists"):
            menu.append({"id": "music/playlists", "text": self._("Music playlists"), "order": 0, "leaf": True})

    def headmenu_playlists(self, args):
        if args == "new":
            return [self._("New playlist"), "music/playlists"]
        elif args:
            m = re_tracks.match(args)
            if m:
                code, cmd = m.group(1, 2)
                if cmd == "new":
                    return [self._("New tracks"), "music/playlists/%s/tracks" % code]
                for p in self.conf("music.playlists", []):
                    if p["code"] == code:
                        return [self._("Track list"), "music/playlists/%s" % code]
            else:
                for p in self.conf("music.playlists", []):
                    if p["code"] == args:
                        return [htmlescape(p["name"]), "music/playlists"]
        return self._("Music playlists")

    def admin_playlists(self):
        req = self.req()
        playlists = self.conf("music.playlists", [])
        if req.args:
            if req.args == "new":
                # new
                playlist = {}
            else:
                # delete
                m = re_del.match(req.args)
                if m:
                    code = m.group(1)
                    playlists = [p for p in playlists if p["code"] != code]
                    config = self.app().config_updater()
                    config.set("music.playlists", playlists)
                    config.store()
                    self.call("admin.redirect", "music/playlists")
                # track editor
                m = re_tracks.match(req.args)
                if m:
                    code, cmd = m.group(1, 2)
                    for p in playlists:
                        if p["code"] == code:
                            return self.admin_playlist_tracks(p, cmd)
                    self.call("admin.redirect", "music/playlists")
                # edit
                playlist = None
                for p in playlists:
                    if p["code"] == req.args:
                        playlist = p.copy()
                        break
                if playlist is None:
                    self.call("admin.redirect", "music/playlists")
            # process form
            if req.ok():
                existing = set()
                for p in playlists:
                    existing.add(p["code"])
                errors = {}
                # code
                code = req.param("code").strip()
                if not code:
                    errors["code"] = self._("This field is mandatory")
                elif not re_valid_identifier.match(code):
                    errors["code"] = self._("Playlist identifier must start with a latin letter and contain latin letters, digits and underscores only")
                elif code in existing and (code != req.args or req.args == "new"):
                    errors["code"] = self._("Playlist with such code already exists")
                else:
                    playlist["code"] = code
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    playlist["name"] = name
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # store
                if req.args != "new":
                    playlists = [p for p in playlists if p["code"] != req.args]
                playlists.append(playlist)
                playlists.sort(cmp=lambda x, y: cmp(x["code"], y["code"]))
                config = self.app().config_updater()
                config.set("music.playlists", playlists)
                config.store()
                self.call("admin.redirect", "music/playlists")
            # render form
            fields = [
                {"name": "code", "label": self._("Playlist code (for use in scripting)"), "value": playlist.get("code")},
                {"name": "name", "label": self._("Playlist name"), "value": playlist.get("name")},
            ]
            self.call("admin.form", fields=fields)
        # render list
        rows = []
        for playlist in playlists:
            rows.append([
                playlist["code"],
                u'<hook:admin.link href="music/playlists/%s" title="%s" />' % (playlist["code"], htmlescape(playlist["name"])),
                u'<hook:admin.link href="music/playlists/%s/tracks" title="%s" />' % (playlist["code"], self._("track list")),
                u'<hook:admin.link href="music/playlists/del/%s" title="%s" confirm="%s" />' % (playlist["code"], self._("delete"), self._("Are you sure want to delete this playlist?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "music/playlists/new",
                            "text": self._("New playlist"),
                            "lst": True,
                        }
                    ],
                    "header": [
                        self._("Identifier"),
                        self._("Playlist name"),
                        self._("Track list"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def admin_playlist_tracks(self, playlist, cmd):
        req = self.req()
        tracks = playlist.get("tracks", [])
        # add tracks
        if cmd == "new":
            used = set()
            for track in tracks:
                used.add(track)
            lst = self.objlist(DBStaticObjectList, query_index="content_type", query_equal="audio/mp3")
            lst.load(silent=True)
            if req.ok():
                tracks = [t for t in tracks]
                added = None
                for ent in lst:
                    if req.param("track-%s" % ent.uuid):
                        if ent.uuid not in used:
                            tracks.append(ent.uuid)
                            added = True
                if added:
                    playlists = [p for p in self.conf("music.playlists", []) if p["code"] != playlist["code"]]
                    playlist = playlist.copy()
                    playlist["tracks"] = tracks
                    playlists.append(playlist)
                    playlists.sort(cmp=lambda x, y: cmp(x["code"], y["code"]))
                    config = self.app().config_updater()
                    config.set("music.playlists", playlists)
                    config.store()
                self.call("admin.redirect", "music/playlists/%s/tracks" % playlist["code"])
            fields = []
            for ent in lst:
                if ent.uuid in used:
                    continue
                fields.append({"name": "track-%s" % ent.uuid, "label": u'<a href="%s" target="_blank">%s</a>' % (ent.get("uri"), ent.get("filename")), "type": "checkbox"})
            if not fields:
                self.call("admin.response", u'<div class="admin-alert">%s</div>' % self._('To add new tracks to the playlist you need to <hook:admin.link href="storage/static" title="upload them" /> to the storage first'), {})
            buttons = [
                {"text": self._("btntext///Add selected tracks to the playlist")},
            ]
            self.call("admin.form", fields=fields, buttons=buttons)
        elif cmd:
            m = re_del.match(cmd)
            if m:
                track = m.group(1)
                tracks = [t for t in tracks if t != track]
                playlists = [p for p in self.conf("music.playlists", []) if p["code"] != playlist["code"]]
                playlist = playlist.copy()
                playlist["tracks"] = tracks
                playlists.append(playlist)
                playlists.sort(cmp=lambda x, y: cmp(x["code"], y["code"]))
                config = self.app().config_updater()
                config.set("music.playlists", playlists)
                config.store()
                self.call("admin.redirect", "music/playlists/%s/tracks" % playlist["code"])
        # render list
        trackinfo = {}
        for track in tracks:
            try:
                obj = self.obj(DBStaticObject, track)
            except ObjectNotFoundException:
                trackinfo[track] = self._("Deleted")
            else:
                trackinfo[track] = u'<a href="%s" target="_blank">%s</a>' % (obj.get("uri"), obj.get("filename"))
        rows = []
        for track in tracks:
            rows.append([
                trackinfo.get(track),
                u'<hook:admin.link href="music/playlists/%s/tracks/del/%s" title="%s" confirm="%s" />' % (playlist["code"], track, self._("delete"), self._("Are you sure want to delete this track from the playlist?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "music/playlists/%s/tracks/new" % playlist["code"],
                            "text": self._("Add tracks to the playlist"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Track"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

class Sound(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("sound.play", self.play)
        self.rhook("sound.music", self.music)
        self.rhook("locations.character_after_set", self.character_teleported)
        self.rhook("interface.settings-form", self.settings_form)
        self.rhook("character.busy-changed", self.busy_changed)

    def child_modules(self):
        return ["mg.constructor.sound.SoundAdmin"]

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("sound")
        vars["head"] = vars.get("head", "") + '<script type="text/javascript" src="/st/js/soundmanager2.js"></script>'
        self.sound_settings(character)
        self.send_music(character)

    def sound_settings(self, char):
        self.call("stream.packet", char.stream_channels, "sound", "settings", sound=char.settings.get("sound", 50), music=char.settings.get("music", 50))

    def play(self, char, url, mode="overlap", volume=50):
        m = hashlib.md5()
        m.update(url)
        id = "snd-%s" % m.hexdigest()
        self.call("stream.packet", char.stream_channels, "sound", "play", id=id, url=url, mode=mode, volume=volume)

    def music(self, char, playlist_code, fade=3000, volume=50):
        playlist = {}
        if playlist_code:
            for p in self.conf("music.playlists", []):
                if p["code"] == playlist_code:
                    lst = self.objlist(DBStaticObjectList, uuids=p.get("tracks", []))
                    lst.load(silent=True)
                    urls = []
                    for ent in lst:
                        urls.append(ent.get("uri"))
            for url in urls:
                m = hashlib.md5()
                m.update(url)
                id = "music-%s" % m.hexdigest()
                playlist[id] = url
        self.call("stream.packet", char.stream_channels, "sound", "music", playlist=playlist, fade=fade, volume=volume)

    def character_teleported(self, char, *args, **kwargs):
        self.send_music(char)

    def send_music(self, char):
        if char.busy and char.busy.get("music_playlist"):
            busy = char.busy
            playlist = busy.get("music_playlist")
            fade = busy.get("music_fade", 3000)
            volume = busy.get("music_volume", 50)
        elif char.location and char.location.valid:
            db_loc = char.location.db_location
            playlist = db_loc.get("music_playlist")
            fade = db_loc.get("music_fade", 3000)
            volume = db_loc.get("music_volume", 50)
        else:
            playlist = []
            fade = 3000
            volume = 50
        self.call("sound.music", char, playlist, fade, volume)

    def settings_form(self, form, action, settings):
        req = self.req()
        user_uuid = req.user()
        char = self.character(req.user())
        if action == "render":
            volumes = []
            for i in xrange(0, 11):
                if i > 0:
                    volumes.append({"value": i * 10, "description": "%s%%" % (i * 10)})
                else:
                    volumes.append({"value": 0, "description": self._("Disabled")})
            form.select(self._("Sounds in the game"), "sound", req.param("sound") if req.ok() else settings.get("sound", 50), volumes)
            form.select(self._("Music in the game"), "music", req.param("music") if req.ok() else settings.get("music", 50), volumes)
        elif action == "store":
            req = self.req()
            was_music = settings.get("music", 50)
            # sound
            sound = intz(req.param("sound"))
            if sound < 0:
                sound = 0
            if sound > 100:
                sound = 100
            settings.set("sound", sound)
            # music
            music = intz(req.param("music"))
            if music < 0:
                music = 0
            if music > 100:
                music = 100
            settings.set("music", music)
            self.sound_settings(char)
            if settings.get("music") and not was_music:
                self.send_music(char)

    def busy_changed(self, char):
        self.send_music(char)
