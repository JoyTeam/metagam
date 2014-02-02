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

from concurrence import *
from concurrence.io import Socket, Buffer, BufferedReader, BufferedWriter
from concurrence.dns import *
import re
import random
import pywhois

re_exact_match = re.compile(r'\.(com)$', re.IGNORECASE)
re_registrar = re.compile(r'(^registrar:|^registrant id:)', re.IGNORECASE | re.MULTILINE)
re_not_found = re.compile(r'(^not[\s\-\_]*found|^No entries found|^No match for|- available$|is currently restricted|^No match\.)', re.IGNORECASE | re.MULTILINE)
re_tld = re.compile(r'\.([a-z]+)$', re.IGNORECASE)
re_tld_whois = re.compile(r'^whois:\s*(\S+)', re.MULTILINE)

class NICClient(pywhois.NICClient):
    def __init__(self, *args, **kwargs):
        pywhois.NICClient.__init__(self, *args, **kwargs)
        self._tld_whois_cache = {}

    def whois(self, query, hostname, flags):
        """Perform initial lookup with TLD whois server
        then, if the quick flag is false, search that result 
        for the region-specifc whois server and do a lookup
        there for contact details
        """
        response = ''
        engine = QueryEngine()
        result = engine.asynchronous(hostname, adns.rr.ADDR)
        if len(result[3]):
            ips = [rr[1] for rr in result[3]]
            ip = random.choice(ips)
            try:
                s = Socket.connect((ip, 43))
                writer = BufferedWriter(s, Buffer(1024))
                reader = BufferedReader(s, Buffer(1024))
                if (hostname == NICClient.GERMNICHOST):
                    writer.write_bytes("-T dn,ace -C US-ASCII " + query + "\r\n")
                else:
                    writer.write_bytes(query + "\r\n")
                writer.flush()
                while True:
                    try:
                        d = reader.read_bytes_available()
                    except EOFError:
                        break
                    response += d
                    if not d:
                        break
            except IOError:
                pass
        nhost = None
        if (flags & NICClient.WHOIS_RECURSE and nhost == None):
            nhost = self.findwhois_server(response, hostname)
        if (nhost != None):
            response += self.whois(query, nhost, 0)
        return response

    def tld_whois(self, tld):
        try:
            return self._tld_whois_cache[tld]
        except KeyError:
            pass
        whois_server = None
        # querying TLD.whois-servers.net
        engine = QueryEngine()
        result = engine.asynchronous("%s.whois-servers.net" % tld, adns.rr.ADDR)
        if len(result[3]):
            whois_server = "%s.whois-servers.net" % tld
        # querying whois.iana.org
        if not whois_server:
            tld_text = self.whois_lookup({"whoishost": "whois.iana.org"}, tld, 0)
            m = re_tld_whois.search(tld_text)
            if m:
                whois_server = m.groups()[0]
        self._tld_whois_cache[tld] = whois_server
        return whois_server

    def registered(self, domain):
        m = re_tld.search(domain)
        if not m:
            raise RuntimeError("Invalid domain name")
        tld = m.groups()[0]
        # looking for TLD whois server
        whois_server = self.tld_whois(tld)
        # problem
        if not whois_server:
            raise RuntimeError("Error fetching TLD %s whois" % tld)
        # querying domain itself
        text = self.whois_lookup({"whoishost": whois_server}, ("=%s" % domain) if re_exact_match.search(domain) else domain, 0).strip()
        if len(text) == 0:
            return None
        if re_registrar.search(text):
            return True
        not_found = re_not_found.search(text)
        if len(text) <= 100 or not_found:
            return False
        else:
            return True
