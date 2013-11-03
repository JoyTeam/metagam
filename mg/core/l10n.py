# -*- coding: utf-8 -*-
from mg import *
from operator import itemgetter
import Stemmer
import gettext
import mg
import os
import re
import datetime

def gettext_noop(x):
    return x

time_local_month = {
    1: gettext_noop("of January"),
    2: gettext_noop("of February"),
    3: gettext_noop("of March"),
    4: gettext_noop("of April"),
    5: gettext_noop("of May"),
    6: gettext_noop("of June"),
    7: gettext_noop("of July"),
    8: gettext_noop("of August"),
    9: gettext_noop("of September"),
    10: gettext_noop("of October"),
    11: gettext_noop("of November"),
    12: gettext_noop("of December")
}

translations = {}
localedir = mg.__path__[0] + "/locale"
languages = set()
languages.add("en")
for lang in os.listdir(localedir):
    try:
        os.stat(localedir + "/" + lang + "/LC_MESSAGES")
        languages.add(lang)
    except OSError:
        pass

re_date = re.compile(r'^(\d\d\d\d)-(\d\d)-(\d\d)$')
re_datetime = re.compile(r'^(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)$')
re_date_ru = re.compile(r'^(\d\d)\.(\d\d)\.(\d\d\d\d)$')
re_datetime_ru = re.compile(r'^(\d\d)\.(\d\d)\.(\d\d\d\d) (\d\d):(\d\d):(\d\d)$')
re_time_local = re.compile(r'^(\d\d\d\d)-(\d\d)-(\d\d) (\d\d:\d\d):\d\d$')
re_000000 = re.compile(r' 00:00:00$')
re_235959 = re.compile(r' 23:59:59$')

ZERO = datetime.timedelta(0)

class UTC(datetime.tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()

class FixedOffset(datetime.tzinfo):
    """Fixed offset in minutes east from UTC."""

    def __init__(self, offset):
        self.__offset = datetime.timedelta(minutes = offset)

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return "Fixed(%d)" % self.__offset

    def dst(self, dt):
        return ZERO

class L10n(Module):
    def register(self):
        self.rhook("l10n.domain", self.l10n_domain)
        self.rhook("l10n.lang", self.l10n_lang)
        self.rhook("l10n.locale", self.l10n_locale)
        self.rhook("l10n.translation", self.l10n_translation)
        self.rhook("l10n.gettext", self.l10n_gettext)
        self.rhook("l10n.ngettext", self.l10n_ngettext)
        self.rhook("l10n.set_request_lang", self.l10n_set_request_lang)
        self.rhook("web.universal_variables", self.universal_variables)
        self.rhook("l10n.date_local", self.l10n_date_local)
        self.rhook("l10n.time_local", self.l10n_time_local)
        self.rhook("l10n.stemmer", self.l10n_stemmer)
        self.rhook("l10n.literal_value", self.l10n_literal_value)
        self.rhook("l10n.literal_values_valid", self.l10n_literal_values_valid)
        self.rhook("l10n.literal_values_sample", self.l10n_literal_values_sample)
        self.rhook("l10n.literal_interval", self.l10n_literal_interval)
        self.rhook("l10n.literal_interval_a", self.l10n_literal_interval_a)
        self.rhook("l10n.literal_enumeration", self.l10n_literal_enumeration)
        self.rhook("menu-admin-site.index", self.menu_site)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-site.timezone", self.admin_timezone, priv="site.timezone")
        self.rhook("l10n.now_local", self.now_local)
        self.rhook("l10n.date_sample", self.date_sample)
        self.rhook("l10n.datetime_sample", self.datetime_sample)
        self.rhook("l10n.parse_date", self.parse_date)
        self.rhook("l10n.unparse_date", self.unparse_date)
        self.rhook("l10n.date_round", self.date_round)

    def permissions_list(self, perms):
        perms.append({"id": "site.timezone", "name": self._("Site time zone settings")})

    def menu_site(self, menu):
        req = self.req()
        if req.has_access("site.timezone"):
            menu.append({"id": "site/timezone", "text": self._("Time zone"), "leaf": True, "order": 20})

    def l10n_domain(self):
        return "mg_server"

    def l10n_lang(self):
        try:
            return str(self.req().lang)
        except AttributeError:
            pass
        try:
            return str(self.app().lang)
        except AttributeError:
            pass
        try:
            return str(self.clconf("locale", "en"))
        except KeyError:
            pass
        return None

    def l10n_locale(self):
        lang = self.call("l10n.lang")
        if lang == "ru":
            return "ru_RU"
        else:
            return "en_US"

    def l10n_translation(self, domain, lang):
        if lang == "en":
            return gettext.NullTranslations()
        key = "%s.%s" % (domain, lang)
        try:
            return translations[key]
        except KeyError:
            pass
        try:
            trans = gettext.translation(domain, localedir=localedir, languages=[lang])
            translations[key] = trans
            return trans
        except IOError as e:
            self.error("Error loading language %s in %s: %s", lang, localedir, e)
            return self.l10n_translation(domain, "en")

    def l10n_stemmer(self):
        lang = self.call("l10n.lang")
        if lang == "ru":
            return Stemmer.Stemmer("russian")
        else:
            return Stemmer.Stemmer("english")

    def l10n_gettext(self, value):
        try:
            request = self.req()
        except AttributeError:
            request = None
        if request:
            try:
                value = request.trans.gettext(value)
                if type(value) == str:
                    value = unicode(value, "utf-8")
                return value
            except AttributeError:
                pass
        lang = self.call("l10n.lang")
        if lang is None:
            if type(value) == str:
                value = unicode(value, "utf-8")
            return value
        domain = self.call("l10n.domain")
        trans = self.call("l10n.translation", domain, lang)
        if request:
            request.trans = trans
        value = trans.gettext(value)
        if type(value) == str:
            value = unicode(value, "utf-8")
        return value

    def l10n_ngettext(self, n, singular, plural):
        try:
            request = self.req()
        except AttributeError:
            request = None
        if request:
            try:
                value = request.trans.ngettext(n, singular, plural)
                if type(value) == str:
                    value = unicode(value, "utf-8")
                return value
            except AttributeError:
                pass
        lang = self.call("l10n.lang")
        if lang is None:
            if type(value) == str:
                value = unicode(value, "utf-8")
            return value 
        domain = self.call("l10n.domain")
        trans = self.call("l10n.translation", domain, lang)
        if request:
            request.trans = trans
        value = trans.ngettext(n, singular, plural)
        if type(value) == str:
            value = unicode(value, "utf-8")
        return value

    def l10n_set_request_lang(self):
        request = self.req()
        accept_language = request.environ.get("HTTP_ACCEPT_LANGUAGE")
        if accept_language is not None:
            weight = []
            for ent in accept_language.split(","):
                try:
                    tokens = ent.split(";")
                    if tokens[0] in languages:
                        if len(tokens) == 1:
                            weight.append((tokens[0], 1))
                        elif len(tokens) == 2:
                            subtokens = tokens[1].split("=")
                            if len(subtokens) == 2 and subtokens[0] == "q":
                                weight.append((tokens[0], float(subtokens[1])))
                except ValueError:
                    pass
            if len(weight):
                weight.sort(key=itemgetter(1), reverse=True)
                if weight[0][0] != "en":
                   request.lang = weight[0][0]

    def universal_variables(self, struct):
        struct["lang"] = self.call("l10n.lang")
        struct["locale"] = self.call("l10n.locale")

    @property
    def tzinfo(self):
        try:
            return self._tzinfo
        except AttributeError:
            self._tzinfo = FixedOffset(self.tzoffset() * 60)
            return self._tzinfo

    def time_local(self, time):
        if time is None:
            return None, None
        m = re_datetime.match(time)
        if m:
            year, month, day, h, m, s = m.group(1, 2, 3, 4, 5, 6)
        else:
            m = re_date.match(time)
            if m:
                year, month, day = m.group(1, 2, 3)
                h = 0
                m = 0
                s = 0
            else:
                return None, None
        try:
            dt = datetime.datetime(int(year), int(month), int(day), int(h), int(m), int(s), tzinfo=utc).astimezone(self.tzinfo)
        except ValueError:
            return None, None
        th = "th"
        day100 = dt.day % 100
        if day100 <= 10 or day100 >= 20:
            day10 = dt.day % 10
            if day10 == 1:
                th = "st"
            elif day10 == 2:
                th = "nd"
            elif day10 == 3:
                th = "rd"
        return dt, th

    def l10n_time_local(self, time):
        dt, th = self.time_local(time)
        if not dt:
            return None
        return self._("at the {day:d}{th} {month}, {year} {hour:02d}:{min:02d}").format(
            year=dt.year,
            month=self._(time_local_month.get(dt.month)),
            day=dt.day,
            hour=dt.hour,
            min=dt.minute,
            sec=dt.second,
            th=th
        )

    def l10n_date_local(self, time):
        dt, th = self.time_local(time)
        if not dt:
            return None
        return self._("at the {day:d}{th} {month}, {year}").format(
            year=dt.year,
            month=self._(time_local_month.get(dt.month)),
            day=dt.day,
            th=th
        )

    def l10n_literal_enumeration(self, values):
        if not values:
            return u""
        if len(values) == 1:
            return values[0]
        lang = self.call("l10n.lang")
        if lang == "ru":
            res = values[0]
            for i in xrange(1, len(values) - 1):
                res += u', '
                res += values[i]
            res += u' и '
            res += values[-1]
            return res
        elif lang == "en":
            res = values[0]
            for i in xrange(1, len(values) - 1):
                res += u', '
                res += values[i]
            res += u', and '
            res += values[-1]
            return res
        else:
            return u", ".join(values)

    def l10n_literal_value(self, val, values):
        if values is None:
            return None
        if type(values) == str or type(values) == unicode:
            values = values.split("/")
        lang = self.call("l10n.lang")
        try:
            if type(val) is int:
                val = abs(val)
            else:
                val = abs(float(val))
        except OverflowError:
            val = 100
        try:
            if lang == "ru":
                if val != int(val):
                    if len(values) >= 4:
                        return values[3]
                    else:
                        return values[1]
                if (val % 100) >= 10 and (val % 100) <= 20:
                    return values[2]
                if (val % 10) >= 2 and (val % 10) <= 4:
                    return values[1]
                if (val % 10) == 1:
                    return values[0]
                return values[2]
            if val == 1:
                return values[0]
            return values[1]
        except IndexError:
            return values[-1]

    def l10n_literal_values_sample(self, singular):
        lang = self.call("l10n.lang")
        if lang == "ru":
            return u""
        stemmed = self.stem(singular)
        return u"{0}/{1}".format(singular, stemmed)

    def l10n_literal_values_valid(self, values):
        if type(values) == str or type(values) == unicode:
            values = values.split("/")
        lang = self.call("l10n.lang")
        if lang == "ru":
            return len(values) == 4
        return len(values) == 2

    def l10n_literal_interval(self, seconds, html=False):
        seconds = int(seconds)
        minutes = seconds / 60
        seconds -= minutes * 60
        hours = minutes / 60
        minutes -= hours * 60
        days = hours / 24
        hours -= days * 24
        items = []
        if days:
            show_days = '<span class="value">%s</span>' % days if html else days
            items.append("%s %s" % (show_days, self.call("l10n.literal_value", days, self._("day/days"))))
        if hours > 0:
            show_hours = '<span class="value">%s</span>' % hours if html else hours
            items.append("%s %s" % (show_hours, self.call("l10n.literal_value", hours, self._("hour/hours"))))
        if minutes > 0:
            show_minutes = '<span class="value">%s</span>' % minutes if html else minutes
            items.append("%s %s" % (show_minutes, self.call("l10n.literal_value", minutes, self._("minute/minutes"))))
        if not items or seconds > 0:
            show_seconds = '<span class="value">%s</span>' % seconds if html else seconds
            items.append("%s %s" % (show_seconds, self.call("l10n.literal_value", seconds, self._("second/seconds"))))
        return " ".join(items)

    def l10n_literal_interval_a(self, seconds, html=False):
        seconds = int(seconds)
        minutes = seconds / 60
        seconds -= minutes * 60
        hours = minutes / 60
        minutes -= hours * 60
        days = hours / 24
        hours -= days * 24
        items = []
        if days:
            show_days = '<span class="value">%s</span>' % days if html else days
            items.append("%s %s" % (show_days, self.call("l10n.literal_value", days, self._("accusative///day/days"))))
        if hours > 0:
            show_hours = '<span class="value">%s</span>' % hours if html else hours
            items.append("%s %s" % (show_hours, self.call("l10n.literal_value", hours, self._("accusative///hour/hours"))))
        if minutes > 0:
            show_minutes = '<span class="value">%s</span>' % minutes if html else minutes
            items.append("%s %s" % (show_minutes, self.call("l10n.literal_value", minutes, self._("accusative///minute/minutes"))))
        if not items or seconds > 0:
            show_seconds = '<span class="value">%s</span>' % seconds if html else seconds
            items.append("%s %s" % (show_seconds, self.call("l10n.literal_value", seconds, self._("accusative///second/seconds"))))
        return " ".join(items)

    def admin_timezone(self):
        req = self.req()
        timezones = []
        valid_timezones = set()
        for offset in xrange(-12, 13):
            timezones.append((str(offset), "UTC{offset:+d}".format(offset=offset)))
            valid_timezones.add(str(offset))
        if req.ok():
            errors = {}
            config = self.app().config_updater()
            timezone = req.param("v_timezone")
            if timezone not in valid_timezones:
                errors["v_timezone"] = self._("Select a valid timezone")
            else:
                config.set("l10n.timezone", intz(timezone))
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        else:
            timezone = self.tzoffset()
        fields = [
            {"name": "timezone", "label": self._("Site time zone"), "value": timezone, "type": "combo", "values": timezones},
        ]
        self.call("admin.form", fields=fields)

    def now_local(self, add=0):
        return datetime.datetime.now(self.tzinfo) + datetime.timedelta(seconds=add)

    def tzoffset(self):
        offset = self.conf("l10n.timezone")
        if offset is not None:
            return offset
        if self.l10n_lang() == "ru":
            return 4
        else:
            return 0

    def parse_date(self, datestr, dayend=False):
        if datestr is None:
            return None
        lang = self.call("l10n.lang")
        if lang == "ru":
            m = re_datetime_ru.match(datestr)
            if m:
                day, month, year, h, m, s = m.group(1, 2, 3, 4, 5, 6)
            else:
                m = re_date_ru.match(datestr)
                if m:
                    day, month, year = m.group(1, 2, 3)
                    if dayend:
                        h = "23"
                        m = "59"
                        s = "59"
                    else:
                        h = "00"
                        m = "00"
                        s = "00"
                else:
                    return None
        else:
            m = re_datetime.match(datestr)
            if m:
                year, month, day, h, m, s = m.group(1, 2, 3, 4, 5, 6)
            else:
                m = re_date.match(datestr)
                if m:
                    year, month, day = m.group(1, 2, 3)
                    if dayend:
                        h = "23"
                        m = "59"
                        s = "59"
                    else:
                        h = "00"
                        m = "00"
                        s = "00"
                else:
                    return None
        try:
            dt = datetime.datetime(int(year), int(month), int(day), int(h), int(m), int(s), tzinfo=self.tzinfo).astimezone(utc)
        except ValueError:
            return None
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def unparse_date(self, datestr, dayend=False):
        if datestr is None:
            return None
        m = re_datetime.match(datestr)
        if m:
            year, month, day, h, m, s = m.group(1, 2, 3, 4, 5, 6)
        else:
            return None
        try:
            dt = datetime.datetime(int(year), int(month), int(day), int(h), int(m), int(s), tzinfo=utc).astimezone(self.tzinfo)
        except ValueError:
            return None
        lang = self.call("l10n.lang")
        if lang == "ru":
            dt = dt.strftime("%d.%m.%Y %H:%M:%S")
        else:
            dt = dt.strftime("%Y-%m-%d %H:%M:%S")
        if dayend:
            dt = re_235959.sub("", dt)
        else:
            dt = re_000000.sub("", dt)
        return dt

    def date_sample(self):
        lang = self.call("l10n.lang")
        if lang == "ru":
            return "DD.MM.YYYY"
        else:
            return "YYYY-MM-DD"

    def datetime_sample(self):
        lang = self.call("l10n.lang")
        if lang == "ru":
            return "DD.MM.YYYY HH:MM:SS"
        else:
            return "YYYY-MM-DD HH:MM:SS"

    # input:
    #    datestr - datetime in UTC
    #    rounding - 0-day, 1-week, 2-month, 0-none
    #    local - rounding must be performed in the local timezone
    # retval:
    #    rounded datetime in UTC
    def date_round(self, datestr, rounding, local=True):
        if datestr is None:
            return None
        if rounding == 3:
            return datestr
        m = re_datetime.match(datestr)
        if m:
            year, month, day, h, m, s = m.group(1, 2, 3, 4, 5, 6)
        else:
            return None
        try:
            dt = datetime.datetime(int(year), int(month), int(day), int(h), int(m), int(s), tzinfo=utc)
        except ValueError:
            return None
        # converting from the local timezone
        if local:
            dt = dt.astimezone(self.tzinfo)
        # rounding
        dt = dt.replace(hour=23, minute=59, second=59)
        if rounding == 0:
            pass
        elif rounding == 1:
            dt += datetime.timedelta(days=6 - dt.weekday())
        elif rounding == 2:
            if dt.month == 12:
                month = 1
                year = dt.year + 1
            else:
                month = dt.month + 1
                year = dt.year
            dt = dt.replace(day=1, month=month, year=year) + datetime.timedelta(days=-1)
        else:
            return None
        # converting to the local timezone
        if local:
            dt = dt.astimezone(utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
