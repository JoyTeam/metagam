import urllib
import string
import re

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

def intz(str):
    try:
        return int(str)
    except (ValueError, TypeError):
        return 0

def jsencode(str):
    str = string.replace(str, "\\", "\\\\")
    str = string.replace(str, "'", "\\'")
    str = string.replace(str, "\r", "\\r")
    str = string.replace(str, "\n", "\\n")
    return str

def jsdecode(str):
    str = string.replace(str, "\\n", "\n")
    str = string.replace(str, "\\r", "\r")
    str = string.replace(str, "\\'", "'")
    str = string.replace(str, "\\\\", "\\")
    return str

def format_gender(gender, str):
    return re.sub(r'\[gender\?([^:\]]*):([^:\]]*)\]', lambda m: m.group(1) if gender == 1 or gender == "1" else m.group(2), str)
