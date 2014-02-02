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

import mg
import datetime
import re
from mg.core.tools import *

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
            return intz(now.strftime(map[attr]))
        
        raise AttributeError(attr)
