import mg
import datetime
import re

class Date(mg.Module):
    def __init__ (self, app):
        mg.Module.__init__(self, app, fqn = "mg.core.date.Date")

    def script_attr(self, attr, handle_exceptions=True):
        re_utc_attr_prefix = re.compile(r'^utc_')
        if re_utc_attr_prefix.match(attr):
            now = datetime.datetime.utcnow()
            attr = re_utc_attr_prefix.sub('', attr)
        else:
            now = self.call('l10n.now_local')
            
        map = {
            "year": "%Y",
            "month": "%m",
            "day": "%d",
            "hour": "%H",
            "minute": "%M",
            "second": "%S",
        }
        
        if attr in map:
            return now.strftime(map[attr])
        
        raise AttributeError(attr)
