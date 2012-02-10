import urllib
import string
import re
import cgi
import datetime
import calendar
import logging

re_color = re.compile(r'^([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$', re.IGNORECASE)
re_human_time = re.compile(r'^(\d\d)\.(\d\d)\.(\d\d\d\d)(?:| (\d\d:\d\d:\d\d))$')
re_valid_nonnegative_int = re.compile(r'^[0-9]+$')
re_valid_nonnegative_float = re.compile(r'^[0-9]+(?:|\.[0-9]+)$')
re_valid_int = re.compile(r'^-?[0-9]+$')
re_valid_number = re.compile(r'^-?[0-9]+(?:|\.[0-9]+)$')
re_datetime = re.compile(r'^(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)$')
re_date = re.compile(r'^(\d\d\d\d)-(\d\d)-(\d\d)')
re_frac_part = re.compile(r'\..*?[1-9]')
re_exp_format = re.compile(r'^-?(\d+|\d+\.\d+)e([+-]\d+)$')
re_remove_frac = re.compile(r'\..*')
re_month = re.compile(r'^(\d\d\d\d)-(\d\d)')
re_sglquote = re.compile(r"'")
re_dblquote = re.compile(r'"')
re_backslash = re.compile(r'\\')
re_backslashed = re.compile(r'\\(.)')

def utf2str(s):
    if s is None:
        return ""
    ts = type(s)
    if ts == unicode:
        s = s.encode("utf-8")
    elif ts != str and ts != int and ts != long:
        s = unicode(s)
        if type(s) == unicode:
            s = s.encode("utf-8")
    return s

def urldecode(str):
    if str is None:
        return ""
    return urllib.unquote(str).decode("utf-8")

def urlencode(str):
    if str is None:
        return ""
    if type(str) == unicode:
        str = str.encode("utf-8")
    return urllib.quote(str)

def intz(str, onerror=0):
    try:
        return int(str)
    except (ValueError, TypeError):
        return onerror

def floatz(str, onerror=0):
    try:
        return float(str)
    except (ValueError, TypeError):
        return onerror

def valid_number(str):
    return re_valid_number.match(str)

def valid_int(str):
    return re_valid_int.match(str)

def valid_nonnegative_int(str):
    return re_valid_nonnegative_int.match(str)

def valid_nonnegative_float(str):
    return re_valid_nonnegative_float.match(str)

def jsencode(val):
    if val is None:
        return ""
    if type(val) != type("") and type(val) != unicode:
        val = str(val)
    val = string.replace(val, "\\", "\\\\")
    val = string.replace(val, "'", "\\'")
    val = string.replace(val, "\r", "\\r")
    val = string.replace(val, "\n", "\\n")
    return val

def jsdecode(val):
    if val is None:
        return ""
    if type(val) != type("") and type(val) != unicode:
        val = str(val)
    val = string.replace(val, "\\n", "\n")
    val = string.replace(val, "\\r", "\r")
    val = string.replace(val, "\\'", "'")
    val = string.replace(val, "\\\\", "\\")
    return val

def format_gender(gender, str):
    return re.sub(r'\[gender\?([^:\]]*):([^:\]]*)\]', lambda m: m.group(1) if gender == 1 or gender == "1" else m.group(2), str)

def parse_color(color):
    m = re_color.match(color)
    if not m:
        return None
    r, g, b = m.group(1, 2, 3)
    return (int(r, 16), int(g, 16), int(b, 16))

def htmlescape(val):
    if val is None:
        return ""
    if type(val) != type("") and type(val) != unicode:
        logging.getLogger("mg.core.tools").exception("Warning: type(val)=%s", type(val))
        val = unicode(val)
    val = string.replace(val, "&", "&amp;")
    val = string.replace(val, '"', "&quot;")
    val = string.replace(val, "<", "&lt;")
    val = string.replace(val, ">", "&gt;")
    return val

def htmldecode(val):
    if val is None:
        return ""
    if type(val) != type("") and type(val) != unicode:
        logging.getLogger("mg.core.tools").exception("Warning: type(val)=%s", type(val))
        val = unicode(val)
    val = string.replace(val, "&quot;", '"')
    val = string.replace(val, "&lt;", "<")
    val = string.replace(val, "&gt;", ">")
    val = string.replace(val, "&amp;", "&")
    return val

def from_unixtime(ts):
    return datetime.datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")

def parse_date(val):
    m = re_datetime.match(val)
    if m:
        y, m, d, hh, mm, ss = m.group(1, 2, 3, 4, 5, 6)
    else:
        m = re_date.match(val)
        if m:
            y, m, d = m.group(1, 2, 3)
            hh = 0
            mm = 0
            ss = 0
        else:
            return None
    return datetime.datetime(int(y), int(m), int(d), int(hh), int(mm), int(ss), tzinfo=None)

def unix_timestamp(val):
    date = parse_date(val)
    if date is None:
        return None
    return calendar.timegm(date.utctimetuple())

def time_interval(a, b):
    return unix_timestamp(b) - unix_timestamp(a)

def prev_month(date):
    m = re_month.match(date)
    if not m:
        return None
    y, m = m.group(1, 2)
    y = int(y)
    m = int(m) - 1
    if m < 1:
        m = 12
        y -= 1
    return "%04d-%02d" % (y, m)

def next_month(date):
    m = re_month.match(date)
    if not m:
        return None
    y, m = m.group(1, 2)
    y = int(y)
    m = int(m) + 1
    if m > 12:
        m = 1
        y += 1
    return "%04d-%02d" % (y, m)

def prev_date(date):
    date = parse_date(date)
    if date is None:
        return None
    date = date + datetime.timedelta(days=-1)
    return date.strftime("%Y-%m-%d")

def next_date(date):
    date = parse_date(date)
    if date is None:
        return None
    date = date + datetime.timedelta(days=1)
    return date.strftime("%Y-%m-%d")

def next_second(time):
    time = parse_date(time)
    time += datetime.timedelta(seconds=1)
    return time.strftime("%Y-%m-%d %H:%M:%S")

def datetime_to_human(str):
    m = re_datetime.match(str)
    if not m:
        return None
    y, m, d, hh, mm, ss = m.group(1, 2, 3, 4, 5, 6)
    return "%02d.%02d.%04d %02d:%02d:%02d" % (int(d), int(m), int(y), int(hh), int(mm), int(ss))

def time_to_human(str):
    m = re_datetime.match(str)
    if not m:
        return None
    y, m, d, hh, mm, ss = m.group(1, 2, 3, 4, 5, 6)
    return "%02d:%02d:%02d" % (int(hh), int(mm), int(ss))

def date_to_human(str):
    m = re_date.match(str)
    if not m:
        return None
    y, m, d = m.group(1, 2, 3)
    return "%02d.%02d.%04d" % (int(d), int(m), int(y))

def date_from_human(str):
    m = re_human_time.match(str)
    if not m:
        return None
    d, m, y, t = m.group(1, 2, 3, 4)
    return "%04d-%02d-%02d %s" % (int(y), int(m), int(d), t if t else "00:00:00")

def nn(num):
    if num is None:
        return 0
    if type(num) == int:
        return num
    if type(num) == float:
        num = '%f' % num
    num = str(num)
    if re_frac_part.search(num) or re_exp_format.match(num):
        return float(num)
    return int(re_remove_frac.sub('', num))

class curry:
    def __init__(self, fun, *args, **kwargs):
        self.fun = fun
        self.pending = args[:]
        self.kwargs = kwargs.copy()

    def __call__(self, *args, **kwargs):
        if kwargs and self.kwargs:
            kw = self.kwargs.copy()
            kw.update(kwargs)
        else:
            kw = kwargs or self.kwargs

        return self.fun(*(self.pending + args), **kw)

def quotestr(s):
    return re_dblquote.sub('\\"', re_backslash.sub('\\\\', s))

def unquotestr(s):
    return re_backslashed.sub(r'\1', s)
