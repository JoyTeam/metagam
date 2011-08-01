from mg.constructor import *
from mg.core.auth import AuthLogList
from mg.constructor.player_classes import DBCharacterOnlineList, DBPlayerList
from mg.constructor.interface import DBFirstVisitList
import re

class GameReporter(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("marketing.report", self.marketing_report)

    def schedule(self, sched):
        sched.add("marketing.report", "0 0 * * *", priority=20)

    def marketing_report(self):
        since, till = self.yesterday_interval()
        since = "2011-08-01 00:00:00"
        till = "2011-08-02 00:00:00"
        app_tag = self.app().tag
        self.debug("a=%s: Preparing marketing report %s - %s", app_tag, since, till)
        # mapping: character_id => player_id
        character_players = {}
        # mapping: character_id => [session_id, since]
        characters_online = {}
        # mapping: player_id => [N_of_online_characters, since]
        players_online = {}
        # mapping: session_id => character_id
        sessions_online = {}
        # list of characters currently online
        online_lst = self.objlist(DBCharacterOnlineList, query_index="all")
        # auth logs since yesterday
        logs = self.objlist(AuthLogList, query_index="performed", query_start=since)
        logs.load(silent=True)
        # mapping: time => number. number is +1 when somebody online, -1 when offline
        events = {}
        # player_stats
        player_stats = {}
        # active players
        active_players = set()
        def player_stat(pl, s, t, comment):
            st = unix_timestamp(s)
            tt = unix_timestamp(t)
            elapsed = tt - st
            self.debug("a=%s: pl=%s online %s - %s (%d sec, %s)", app_tag, pl, s, t, elapsed, comment)
            try:
                player_stats[pl] += elapsed
            except KeyError:
                player_stats[pl] = elapsed
            try:
                events[st] += 1
            except KeyError:
                events[st] = 1
            try:
                events[tt] -= 1
            except KeyError:
                events[tt] = -1
        for ent in logs:
            performed = ent.get("performed")
            act = ent.get("act")
            char_uuid = ent.get("user")
            player_uuid = ent.get("player")
            session_uuid = ent.get("session")
            active_players.add(player_uuid)
            #self.debug("a=%s %s char=%s, player=%s, sess=%s", performed, act, char_uuid, player_uuid, session_uuid)
            if performed < till:
                # actual date
                went_online = False
                went_offline = False
                if char_uuid and player_uuid:
                    character_players[char_uuid] = player_uuid
                    # online events
                    if (act == "login" or act == "reconnect") and char_uuid and player_uuid:
                        try:
                            char = characters_online[char_uuid]
                            # character already online
                            if char[0] != session_uuid:
                                # session of the character changed
                                del sessions_online[char[0]]
                                sessions_online[session_uuid] = char_uuid
                                char[0] = session_uuid
                        except KeyError:
                            went_online = True
                    # offline events
                    if (act == "logout" or act == "disconnect") and char_uuid and player_uuid:
                        if not characters_online.get(char_uuid):
                            # logout without login. assuming login was at the "since" time
                            characters_online[char_uuid] = [session_uuid, since]
                            try:
                                players_online[player_uuid][0] += 1
                            except KeyError:
                                players_online[player_uuid] = [1, since]
                        went_offline = True
                # log into cabinet
                if act == "login" and player_uuid and not char_uuid:
                    try:
                        char_uuid = sessions_online[session_uuid]
                        char = characters_online[char_uuid]
                    except KeyError:
                        pass
                    else:
                        went_offline = True
                #self.debug("   went_online=%s, went_offline=%s", went_online, went_offline)
                # processing online/offline events
                if went_online:
                    characters_online[char_uuid] = [session_uuid, performed]
                    try:
                        if players_online[player_uuid][0] == 0:
                            players_online[player_uuid][1] = performed
                        players_online[player_uuid][0] += 1
                    except KeyError:
                        players_online[player_uuid] = [1, performed]
                    sessions_online[session_uuid] = char_uuid
                if went_offline:
                    char = characters_online[char_uuid]
                    try:
                        del sessions_online[char[0]]
                    except KeyError:
                        pass
                    try:
                        del characters_online[char_uuid]
                    except KeyError:
                        pass
                    try:
                        players_online[player_uuid][0] -= 1
                    except KeyError:
                        pass
                    else:
                        if players_online[player_uuid][0] == 0:
                            player_stat(player_uuid, players_online[player_uuid][1], performed, "regular")
                #self.debug("   current characters_online=%s, players_online=%s, sessions_online=%s", characters_online, players_online, sessions_online)
            else:
                # the next day
                if char_uuid and player_uuid and not character_players.get(char_uuid):
                    if act == "login" or act == "reconnect": 
                        # this character first appeared in the logs on the next day with "login" event.
                        # it means he was offline yesterday
                        character_players[char_uuid] = player_uuid
                    if act == "logout" or act == "disconnect":
                        # this character first apparead in the logs on the next day with "logout" event.
                        # it means he was online yesterday all the day
                        character_players[char_uuid] = player_uuid
                        player_stat(player_uuid, since, till, "afterlog")
        # getting characters online till the end of the day
        for player_uuid, ent in players_online.iteritems():
            if ent[0] > 0:
                player_stat(player_uuid, ent[1], till, "endofday")
        # looking for characters still online
        for ent in online_lst:
            char_uuid = ent.uuid
            if not character_players.get(char_uuid):
                # this character is still online and there were no mentions in logs about him
                # it means that he was online yesterday all the day
                player_uuid = self.character(char_uuid).player.uuid
                active_players.add(player_uuid)
                player_stat(player_uuid, since, till, "nolog")
        # CCU analysis
        since_ts = unix_timestamp(since)
        last = None
        ccu = 0
        peak_ccu = 0
        hours = [0] * 25
        for time in sorted(events.keys()):
            if last is not None:
                hour_begin = (last - since_ts) / 3600
                hour_end = (time - since_ts) / 3600
                #self.debug("Interval %d - %d: ccu=%d, hour_begin=%d, hour_end=%d", last, time, ccu, hour_begin, hour_end)
                if hour_begin == hour_end:
                    ratio = (time - last) / 3600.0
                    #self.debug("Hour %d gets %d * %f", hour_begin, ccu, ratio)
                    hours[hour_begin] += ccu * ratio
                else:
                    ratio = (since_ts + (hour_begin + 1) * 3600 - last) / 3600.0
                    #self.debug("Hour %d gets %d * %f", hour_begin, ccu, ratio)
                    hours[hour_begin] += ccu * ratio
                    for hour in xrange(hour_begin + 1, hour_end):
                        #self.debug("Hour %d gets %d * 1.0", hour, ccu)
                        hours[hour] += ccu
                    ratio = (time - hour_end * 3600 - since_ts) / 3600.0
                    #self.debug("Hour %d gets %d * %f", hour_end, ccu, ratio)
                    hours[hour_end] += ccu * ratio
            ccu += events[time]
            if ccu > peak_ccu:
                peak_ccu = ccu
            last = time
            #self.debug("CCU at %d = %d", time, ccu)
        hours = [int(val) for val in hours[0:24]]
        #self.debug("Distribution: %s", hours)
        # loading list of newly registered players
        lst = self.objlist(DBPlayerList, query_index="created", query_start=since, query_finish=till)
        lst.load(silent=True)
        registered = 0
        for ent in lst:
            if not ent.get("last_visit"):
                ent.set("last_visit", till)
                ent.set("active", 2)
                registered += 1
        lst.store()
        # loading list of active players
        returned = 0
        if len(active_players):
            lst = self.objlist(DBPlayerList, uuids=[uuid for uuid in active_players])
            lst.load(silent=True)
            for ent in lst:
                if ent.get("active") != 2:
                    ent.set("active", 2)
                    returned += 1
            lst.store()
        # loading list of active players that are really inactive for 30 days
        lst = self.objlist(DBPlayerList, query_index="active", query_equal="2", query_finish=self.now(-86400 * 30))
        lst.load(silent=True)
        left = 0
        for ent in lst:
            ent.set("active", 0)
            left += 1
        lst.store()
        # loading currently active playerbase
        lst = self.objlist(DBPlayerList, query_index="active", query_equal="2")
        active = len(lst)
        # loading list of new users on the index page
        lst = self.objlist(DBFirstVisitList, query_index="all")
        new_users = len(lst)
        lst.remove()
        # don't store information about abandoned games
        if len(online_lst) or len(logs) or active > 0:
            self.call("dbexport.add", "online", since=since, till=till, players=player_stats, peak_ccu=peak_ccu, ccu_dist=hours, registered=registered, returned=returned, left=left, active=active, new_users=new_users)

