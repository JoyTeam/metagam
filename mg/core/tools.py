import urllib
import string

def urldecode(str):
    if str is None:
        return ""
    return urllib.unquote(str).decode("utf-8")

def urlencode(str):
    if str is None:
        return ""
    if type(str) != unicode:
        str = unicode(str, "utf-8")
    return urllib.quote(str)

def intz(str):
    try:
        return int(str)
    except:
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

