import urllib

def urldecode(str):
    return urllib.unquote(str).decode("utf-8")

def urlencode(str):
    if type(str) != unicode:
        str = unicode(str, "utf-8")
    return urllib.quote(str)
