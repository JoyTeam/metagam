from mg import *
from mg.core.whois_client import *
from mg.core.money_classes import MemberMoney
import re
from concurrence import Timeout, TimeoutError
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from mg.constructor.common import Domain, DomainList

re_price_value = re.compile(r'^(\d+|\d+\.\d{1,2})$')
re_person_r = re.compile(r'^\w+( \w+)+$', re.UNICODE)
re_person = re.compile(r'^[A-Z][a-z]*( [A-Z][a-z]*)+$')
re_birth_date = re.compile(r'^\d\d\.\d\d\.\d\d\d\d$')
re_phone = re.compile(r'^\+\d[ \d]+$')
re_i7_response = re.compile(r'^<html><body>(\S*):\s*(\d*)\s+(\S*)\s+(\S*)(,\s*in progress|)</body></html>$')
re_domain = re.compile(r'^[a-z0-9][a-z0-9\-]*(\.[a-z0-9][a-z0-9\-]*)+$')
re_double_dash = re.compile(r'--')

class DNSCheckError(Exception):
    pass

class Domains(Module):
    def register(self):
        self.rhook("domains.tlds", self.tlds)
        self.rhook("domains.prices", self.prices)
        self.rhook("domains.assign", self.assign)
        self.rhook("domains.validate_new", self.validate_new)
        self.rhook("admin-game.recommended-actions", self.recommended_actions)

    def tlds(self, tlds):
        tlds.extend(['ru', 'su', 'com', 'net', 'org', 'biz', 'info', 'mobi', 'name', 'ws', 'in', 'cc', 'tv', 'mn', 'me', 'tel', 'asia', 'us'])

    def get_prices(self):
        prices = self.main_app().config.get("domains.prices")
        if prices is not None:
            return prices
        return {
            "ru": 7,
            "su": 18,
            "com": 13,
            "net": 13,
            "org": 13,
            "biz": 13,
            "info": 13,
            "mobi": 27,
            "name": 15,
            "ws": 15,
            "in": 30,
            "cc": 40,
            "tv": 50,
            "mn": 70,
            "me": 40,
            "tel": 25,
            "asia": 25,
            "us": 15,
        }

    def prices(self, prices):
        for tld, price in self.get_prices().iteritems():
            if price != "":
                prices[tld] = price

    def assign(self, domain):
        project = self.app().project
        self.info("Assigning domain %s to the project %s", domain, project.uuid)
        rec = self.main_app().obj(Domain, domain, silent=True)
        rec.set("user", project.get("owner"))
        rec.set("project", self.app().project.uuid)
        rec.set("created", self.now())
        rec.store()
        project.set("domain", domain)
        project.store()
        self.app().store_config_hooks()

    def validate_new(self, domain, errors):
        try:
            rec = self.main_app().obj(Domain, domain)
        except ObjectNotFoundException:
            pass
        else:
            if rec.get("project"):
                if self.app().project.uuid == rec.get("project"):
                    return
                else:
                    errors["domain"] = self._("This domain is already bound to another MMO Constructor project")
            elif rec.get("registered") == "pending":
                errors["domain"] = self._("This domain is a subject to the manual check. This may take up to 3 days")
            elif rec.get("registered") == "yes" and rec.get("user") != self.app().project.get("owner"):
                errors["domain"] = self._("This domain was not registered by you. You can't use for your project")
            if len(errors):
                return
        try:
            servers = self.dns_servers(domain)
        except DNSCheckError as e:
            errors["domain"] = unicode(e)
            return
        ns1 = self.main_app().config.get("dns.ns1")
        ns2 = self.main_app().config.get("dns.ns2")
        if ns1 not in servers or ns2 not in servers or len(servers) != 2:
            errors["domain"] = self._("Domain servers for {0} are: {1}. Setup your zone correctly: DNS servers must be {2} and {3}").format(domain, ", ".join(servers), ns1, ns2)

    def dns_servers(self, domain):
        main = self.main_app()
        ns1 = main.config.get("dns.ns1")
        ns2 = main.config.get("dns.ns2")
        domains = domain.split(".")
        if "www" in domains:
            raise DNSCheckError(self._("Domain name can't contain 'www'"))
        domains.reverse()
        game_domain = domains.pop()
        checkdomain = None
        configtext = None
        dnsservers = None
        not_found = self._("Domain {0} was not found by {1}. Either domain is not registered yet or DNS data was not updated yet. If the domain was registered recently, it is normal situation. It may take several hours (about 6) for NS servers to update. Try again later, please")
        for domain in domains:
            checkdomain = domain + "." + checkdomain if checkdomain else domain
            engine = QueryEngine(configtext=configtext)
            result = engine.asynchronous(checkdomain + ".", adns.rr.NS)
            ips = []
            names = []
            self.debug("Querying %s about domain %s: %s", configtext, checkdomain, [result])
            for rr in result[3]:
                names.append(rr[0])
                if rr[2]:
                    for rr_a in rr[2]:
                        ips.append(rr_a[1])
                elif rr[0]:
                    engine = QueryEngine()
                    result = engine.asynchronous(checkdomain + ".", adns.rr.ADDR)
                    self.debug("Querying main DNS about domain %s: %s", rr[0], [result])
                    for rr in result[3]:
                        ips.append(rr[1])
            if not len(ips):
                result = engine.asynchronous(checkdomain + ".", adns.rr.ADDR)
                if len(result[3]):
                    raise DNSCheckError(self._("Domain {0} has A records but no NS records. Configure your zone correctly").format(checkdomain))
                elif dnsservers:
                    raise DNSCheckError(not_found.format(checkdomain, ", ".join(dnsservers)))
                else:
                    raise DNSCheckError(self._("Domain {0} was not found by the root nameservers").format(checkdomain))
            configtext = "\n".join(["nameserver %s" % ip for ip in ips])
            dnsservers = names
            if ns1 in names or ns2 in names:
                raise DNSCheckError(self._("{0} is already configured for the project. You may not use its subdomains").format(checkdomain))
        checkdomain = game_domain + "." + checkdomain
        engine = QueryEngine(configtext=configtext)
        result = engine.asynchronous(checkdomain + ".", adns.rr.NSraw)
        servers = result[3]
        if not len(servers):
            result = engine.asynchronous(checkdomain + ".", adns.rr.ADDR)
            if len(result[3]):
                raise DNSCheckError(self._("Domain {0} has A records but no NS records. Configure your zone correctly").format(checkdomain))
            else:
                raise DNSCheckError(not_found.format(checkdomain, ", ".join(dnsservers)))
        return [ns.lower() for ns in servers]

    def recommended_actions(self, recommended_actions):
        project = self.app().project
        req = self.req()
        if not project.get("domain") and req.has_access("project.admin"):
            recommended_actions.append({"icon": "/st/img/applications-internet.png", "content": u'%s <hook:admin.link href="game/domain" title="%s" />' % (self._("Your game is currently available under the temporary domain %s only. You have to assign it a normal domain name before game launch.") % self.app().canonical_domain, self._("Assign a domain name")), "order": 100, "before_launch": True})

class DomainRegWizard(Wizard):
    def new(self, target=None, redirect_fail=None, **kwargs):
        super(DomainRegWizard, self).new(**kwargs)
        if target is None:
            raise RuntimeError("DomainRegWizard target not specified")
        if redirect_fail is None:
            raise RuntimeError("DomainRegWizard redirect_fail not specified")
        self.config.set("tag", "domain-reg")
        self.config.set("target", target)
        self.config.set("redirect_fail", redirect_fail)

    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Domain registration wizard"), "leaf": True, "order": 20, "icon": "/st-mg/menu/wizard.png"})

    def request(self, cmd):
        req = self.req()
        tlds = []
        self.call("domains.tlds", tlds)
        prices = {}
        self.call("domains.prices", prices)
        tlds = [tld for tld in tlds if prices.get(tld)]
        if cmd == "abort":
            self.abort()
            self.call("admin.redirect", self.config.get("redirect_fail"))
        elif cmd == "check" or cmd == "register":
            domain_name = req.param("domain_name").lower()
            tld = req.param("tld").lower()
            errors = {}
            if not re.match(r'^[a-z0-9][a-z0-9\-]*$', domain_name):
                errors["domain_name"] = self._("Invalid domain name. It must begin with letter a-z or digit 0-9 and contain letters, digits and '-' sign")
            elif re_double_dash.search(domain_name):
                errors["domain_name"] = self._("Domain name can't contain double dash ('--'). International domain names are not supported")
            if not tld in tlds:
                errors["tld"] = self._("Select top level domain")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors, "stage": "check"})
            domain = str("%s.%s" % (domain_name, tld))
            # locked operations
            with self.main_app().lock(["DomainReg.%s" % domain], patience=190, delay=3, ttl=185):
                try:
                    rec = self.main_app().obj(Domain, domain)
                except ObjectNotFoundException:
                    pass
                else:
                    if rec.get("user") != self.app().project.get("owner"):
                        errors["domain_name"] = self._("This domain is already registered by another user of the MMO Constructor")
                    elif rec.get("registered") == "pending":
                        errors["domain_name"] = self._("This domain is in the pending state. We don't know the result of the registration. Please contact MMO Constructor administration to get more details. registrar_id=%s") % rec.get("registrar_id")
                    elif rec.get("project"):
                        errors["domain_name"] = self._("This domain is already assigned to a project")
                    else:
                        errors["domain_name"] = self.call("web.parse_inline_layout", '%s. <hook:admin.link href="wizard/call/%s/abort" title="%s" /> %s' % (self._("This domain is registered by you but not assigned to a project"), self.uuid, self._("Go to the domain checker"), self._("to assign the domain")), {})
                if not len(errors):
                    self.config.set("domain_name", domain_name)
                    self.config.set("tld", tld)
                    self.config.store()
                    whois = NICClient()
                    reg = whois.registered(domain)
                    if reg is None:
                        errors["domain_name"] = self._("%s registry is temporarily unavailable. Try again later") % tld.upper()
                    elif reg:
                        errors["domain_name"] = self._("This domain name is occupied already. Choose another one")
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors, "stage": "check"})
                price = float(prices[tld])
                balance = self.user_money_available()
                if cmd == "check":
                    self.call("web.response_json", {"success": True, "stage": "register", "domain_name": domain, "price": price, "price_text": self._("%(price).2f MM$ (approx %(price).2f USD)") % {"price": price}, "balance": balance, "balance_text": "%.2f" % balance})
                owner = req.param("owner")
                main_config = self.main_app().config
                if owner == "admin":
                    person_r = main_config.get("domains.person-r")
                    person = main_config.get("domains.person")
                    passport = main_config.get("domains.passport")
                    birth_date = main_config.get("domains.birth-date")
                    address_r = main_config.get("domains.address-r")
                    p_addr = main_config.get("domains.p-addr")
                    phone = main_config.get("domains.phone")
                elif owner == "user":
                    person_r = req.param("person-r").strip()
                    person = req.param("person").strip()
                    passport = req.param("passport").strip()
                    birth_date = req.param("birth-date").strip()
                    address_r = req.param("address-r").strip()
                    p_addr = req.param("p-addr").strip()
                    phone = req.param("phone").strip()
                    if not re_person_r.match(person_r):
                        errors["person-r"] = self._("Invalid field format")
                    if not re_person.match(person):
                        errors["person"] = self._("Invalid field format")
                    if passport == "":
                        errors["passport"] = self._("Enter your passport number, issuer and issue date")
                    if not re_birth_date.match(birth_date):
                        errors["birth-date"] = self._("Enter birthday in format DD.MM.YYYY")
                    if address_r == "":
                        errors["address-r"] = self._("Enter valid address")
                    if p_addr == "":
                        errors["p-addr"] = self._("Enter valid address")
                    if not re_phone.match(phone):
                        errors["phone"] = self._("Invalid phone format. Look at the example")
                    if len(errors):
                        self.call("web.response_json", {"success": False, "stage": "register", "domain_name": domain, "price": price, "price_text": self._("%(price).2f MM$ (approx %(price).2f USD)") % {"price": price}, "balance": balance, "balance_text": "%.2f" % balance, "errors": errors})
                else:
                    self.call("web.response_json", {"success": False, "errormsg": self._("Select an owner of the domain")})
                # Registration request
                params = []
                params.append(("action", "NEW"))
                params.append(("login", main_config.get("domains.login")))
                params.append(("passwd", main_config.get("domains.password")))
                params.append(("domain", domain))
                params.append(("state", "DELEGATED"))
                params.append(("nserver", main_config.get("dns.ns1")))
                params.append(("nserver", main_config.get("dns.ns2")))
                params.append(("person", person))
                params.append(("person-r", person_r))
                params.append(("passport", passport))
                params.append(("birth-date", birth_date))
                params.append(("address-r", address_r))
                params.append(("p-addr", p_addr))
                params.append(("phone", phone))
                params.append(("e-mail", main_config.get("domains.email")))
                params.append(("private-whois", "yes"))
                self.info("Querying registrar: %s", params)
                params_url = "&".join(["%s=%s" % (key, urlencode(unicode(val).encode("koi8-r", "replace"))) for key, val in params])
                error = None
                try:
                    with Timeout.push(180):
                        rec = self.main_app().obj(Domain, domain, data={})
                        rec.set("user", self.app().project.get("owner"))
                        rec.set("registered", "pending")
                        rec.set("created", self.now())
                        rec.set("person", person)
                        rec.set("person-r", person_r)
                        rec.set("passport", passport)
                        rec.set("birth-date", birth_date)
                        rec.set("address-r", address_r)
                        rec.set("p-addr", p_addr)
                        rec.set("phone", phone)
                        # Connecting
                        cnn = HTTPConnection()
                        try:
                            cnn.connect(("my.i7.ru", 80))
                        except IOError as e:
                            self.call("web.response_json", {"success": False, "errormsg": self._("Error connecting to the registrar. Try again please")})
                        # Locking money
                        money = self.user_money()
                        lock = money.lock(price, "MM$", "domain-reg", domain=domain)
                        if not lock:
                            self.call("web.response_json", {"success": False, "errormsg": self._("You have not enough money"), "balance": balance, "balance_text": "%.2f" % balance})
                        # Storing domain record
                        rec.set("money_lock", lock.uuid)
                        rec.store()
                        try:
                            self.info("Registrar request: %s", params)
                            request = cnn.get("/c/registrar?%s" % params_url)
                            request.add_header("Connection", "close")
                            response = cnn.perform(request)
                            #class Response(object):
                            #    pass
                            #response = Response()
                            #response.status_code = 200
                            #response.body = '<html><body>NEW:10 done cause</body></html>'
                            if response.status_code != 200:
                                self.error("Registrar response: %s", response.status)
                                error = self._("Error getting response from the registrar. Your request was not processed")
                                self.main_app().hooks.call("domains.money_unlock", rec)
                                rec.remove()
                            else:
                                m = re_i7_response.match(response.body)
                                if not m:
                                    self.error("Invalid response from the registrar: %s", urlencode(response.body))
                                    error = self._("Invalid response from the registrar. We don't know whether your request was processed, so we remain payment for the domain in the locked state. Result of the operation will be checked by the technical support manually.")
                                else:
                                    action, id, state, cause, inprogress = m.groups()
                                    inprogress = True if len(inprogress) else False
                                    self.info("Registrar response: action=%s, id=%s, state=%s, cause=%s, inprogress=%s", action, id, state, cause, inprogress)
                                    if state == "done" or state == "dns_check":
                                        rec.set("registered", "yes")
                                        rec.set("registrar_id", id)
                                        self.main_app().hooks.call("domains.money_charge", rec)
                                        rec.store()
                                        target = self.config.get("target")
                                        self.result(domain)
                                        self.finish()
                                        msg1 = self._("You have successfully registered domain <strong>%s</strong>")
                                        if target[0] == "wizard":
                                            self.call("admin.response", "%s. %s." % ((msg1 % domain), (self._('Now <hook:admin.link href="wizard/call/%s" title="check your domain settings" />') % target[1])), {})
                                        else:
                                            self.call("admin.response", "%s." % msg1, {})
                                    elif state == "money_wait" or state == "tc_wait" or inprogress:
                                        rec.set("registrar_id", id)
                                        rec.set("registrar_state", state)
                                        rec.set("registrar_cause", cause)
                                        rec.set("registrar_inprogress", inprogress)
                                        rec.store()
                                        error = self._("Your domain was not registered due to temporary problems. We don't know whether your request was processed, so we remain payment for the domain in the locked state. Result of the operation will be checked by the technical support manually.")
                                    else:
                                        error = self._("Error registering domain: %s" % cause)
                                        self.main_app().hooks.call("domains.money_unlock", rec)
                                        rec.remove()
                        finally:
                            cnn.close()
                except TimeoutError:
                    self.error("Timeout querying registrar")
                    error = self._("Request to the registrar timed out. We don't know whether your request was processed, so we remain payment for the domain in the locked state. Result of the operation will be checked by the technical support manually.")
                if error:
                    self.call("web.response_json", {"success": False, "errormsg": self._(error), "stage": "check"})
                self.call("web.response_json", {"success": False, "errormsg": self._("Registering for the name: %s" % person_r)})
        elif cmd == "balance":
            balance = self.user_money_available()
            self.call("web.response_json", {"success": True, "balance": balance, "balance_text": "%.2f" % balance})
        elif cmd == "":
            tlds_store = [{"code": tld, "value": "." + tld} for tld in tlds]
            if len(tlds_store):
                tlds_store[-1]["lst"] = True
            vars = {
                "DomainWizard": self._("Domain registration wizard"),
                "DomainName": self._("Domain name"),
                "wizard": self.uuid,
                "EnterDomain": self._("Enter domain name"),
                "domain_name": self.config.get("domain_name"),
                "tld": self.config.get("tld", "ru"),
                "tlds": tlds_store,
                "DomainAvailable": self._("Domain %s is available for registration"),
                "RegistrationPrice": self._("for %s"),
                "yourBalanceIs": self._("your current balance is %s MM$"),
                "HereYouCan": self._("Here you can register a domain"),
                "RegisterDomain": self._("Register this domain"),
                "UpdateBalance": self._("Update balance"),
                "MakeMeTheOwner": self._("You will be the owner of the domain (in this case provide your personal data)"),
                "BeOwnerYourself": self._("MMO Constructor will be the owner of the domain"),
                "PersonR": self._("Your name (in your language). For example: <strong>John A Smith</strong>"),
                "Person": self._("Your name (in English). For example: <strong>John A Smith</strong>"),
                "Passport": self._("Your passport number, issuer and issue date"),
                "BirthDate": self._("Your birthday in DD.MM.YYYY format. For example: <strong>31.12.1980</strong>"),
                "AddressR": self._("Your official registration address (in your language)"),
                "PAddr": self._("Your postal address (in your language)"),
                "Phone": self._("Your phone number in the international format. For example: <strong>+1 800 5555555</strong>"),
                "CheckingAvailability": self._("Checking domain availability..."),
                "UpdatingBalance": self._("Updating balance..."),
                "RegisteringDomain": self._("Registering domain. It may take several minutes. Be patient please..."),
            }
            self.call("admin.response_template", "constructor/setup/domain-wizard.html", vars)

    def user_money(self):
        return self.main_app().hooks.call("money.member-money", self.app().project.get("owner"))

    def user_money_available(self):
        return self.user_money().available("MM$")

class DomainsAdmin(Module):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("money-description.domain-reg", self.money_description_domain_reg)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-domains.index", self.menu_domains_index)
        self.rhook("ext-admin-domains.dns", self.ext_dns, priv="domains.dns")
        self.rhook("ext-admin-domains.prices", self.ext_prices, priv="domains.prices")
        self.rhook("ext-admin-domains.personal-data", self.ext_personal_data, priv="domains.personal-data")
        self.rhook("ext-admin-domains.pending", self.ext_pending, priv="domains")
        self.rhook("domains.money_unlock", self.money_unlock)
        self.rhook("domains.money_charge", self.money_charge)
        self.rhook("auth.user-tables", self.user_tables)
        self.rhook("ext-admin-domains.unassign", self.ext_unassign, priv="domains.unassign")

    def permissions_list(self, perms):
        perms.append({"id": "domains", "name": self._("Domains: administration")})
        perms.append({"id": "domains.dns", "name": self._("Domains: DNS settings")})
        perms.append({"id": "domains.prices", "name": self._("Domains: registration prices")})
        perms.append({"id": "domains.personal-data", "name": self._("Domains: administrator's personal data")})
        perms.append({"id": "domains.unassign", "name": self._("Domains: unassigning")})

    def money_description_domain_reg(self):
        return {
            "args": ["domain"],
            "text": self._("Domain registration: {domain}"),
        }

    def objclasses_list(self, objclasses):
        objclasses["Domain"] = (Domain, DomainList)

    def menu_root_index(self, menu):
        menu.append({"id": "domains.index", "text": self._("Domains"), "order": 15})

    def menu_domains_index(self, menu):
        req = self.req()
        if req.has_access("domains"):
            menu.append({"id": "domains/pending", "text": self._("List of pending domains"), "leaf": True})
        if req.has_access("domains.prices"):
            menu.append({"id": "domains/prices", "text": self._("Registration prices"), "leaf": True})
        if req.has_access("domains.personal-data"):
            menu.append({"id": "domains/personal-data", "text": self._("Administrator's personal data"), "leaf": True})
        if req.has_access("domains.dns"):
            menu.append({"id": "domains/dns", "text": self._("DNS settings"), "leaf": True})

    def ext_dns(self):
        req = self.req()
        main = self.main_app()
        ns1 = req.param("ns1")
        ns2 = req.param("ns2")
        if req.param("ok"):
            config = main.config_updater()
            config.set("dns.ns1", ns1)
            config.set("dns.ns2", ns2)
            config.store()
            self.call("admin.response", self._("DNS settings stored"), {})
        else:
            ns1 = main.config.get("dns.ns1")
            ns2 = main.config.get("dns.ns2")
        fields = [
            {"name": "ns1", "label": self._("DNS server 1"), "value": ns1},
            {"name": "ns2", "label": self._("DNS server 2"), "value": ns2},
        ]
        self.call("admin.form", fields=fields)

    def ext_prices(self):
        req = self.req()
        tlds = []
        self.call("domains.tlds", tlds)
        prices = {}
        for tld in tlds:
            prices[tld] = req.param("price_%s" % tld)
        if req.param("ok"):
            errors = {}
            for tld in tlds:
                if prices[tld] != "" and not re_price_value.match(prices[tld]):
                    errors["price_%s" % tld] = self._("Invalid price format")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config = self.app().config_updater()
            config.set("domains.prices", prices)
            config.store()
            self.call("admin.response", self._("Domain registration prices stored"), {})
        else:
            prices = {}
            self.call("domains.prices", prices)
        fields = []
        n = 0
        for tld in tlds:
            fields.append({"name": "price_%s" % tld, "label": tld, "value": prices.get(tld), "inline": n % 5})
            n += 1
        self.call("admin.form", fields=fields)

    def ext_personal_data(self):
        req = self.req()
        person_r = req.param("person-r")
        person = req.param("person")
        passport = req.param("passport")
        birth_date = req.param("birth-date")
        address_r = req.param("address-r")
        p_addr = req.param("p-addr")
        phone = req.param("phone")
        email = req.param("email")
        login = req.param("login")
        password = req.param("password")
        if req.param("ok"):
            config = self.app().config_updater()
            config.set("domains.person-r", person_r)
            config.set("domains.person", person)
            config.set("domains.passport", passport)
            config.set("domains.birth-date", birth_date)
            config.set("domains.address-r", address_r)
            config.set("domains.p-addr", p_addr)
            config.set("domains.phone", phone)
            config.set("domains.email", email)
            config.set("domains.login", login)
            config.set("domains.password", password)
            config.store()
            self.call("admin.response", self._("Personal data saved"), {})
        else:
            person_r = self.conf("domains.person-r")
            person = self.conf("domains.person")
            passport = self.conf("domains.passport")
            birth_date = self.conf("domains.birth-date")
            address_r = self.conf("domains.address-r")
            p_addr = self.conf("domains.p-addr")
            phone = self.conf("domains.phone")
            email = self.conf("domains.email")
            login = self.conf("domains.login")
            password = self.conf("domains.password")
        fields = []
        fields.append({"name": "person-r", "label": self._("Person name (in the native language)"), "value": person_r})
        fields.append({"name": "person", "label": self._("Person name (in English)"), "value": person})
        fields.append({"name": "passport", "label": self._("Passport number"), "value": passport})
        fields.append({"name": "birth-date", "label": self._("Birthday"), "value": birth_date})
        fields.append({"name": "address-r", "label": self._("Registration address"), "value": address_r})
        fields.append({"name": "p-addr", "label": self._("Postal address"), "value": p_addr})
        fields.append({"name": "phone", "label": self._("Phone"), "value": phone})
        fields.append({"name": "email", "label": self._("E-mail address"), "value": email})
        fields.append({"name": "login", "label": self._("Registrar login"), "value": login})
        fields.append({"name": "password", "label": self._("Registrar password"), "value": password, "type": "password"})
        self.call("admin.form", fields=fields)

    def ext_pending(self):
        req = self.req()
        m = re.match(r'(confirm|cancel|recheck)/(\S+)$', req.args)
        if m:
            action, domain = m.groups()
            try:
                rec = self.obj(Domain, domain)
            except ObjectNotFoundException:
                pass
            else:
                if action == "cancel":
                    self.call("domains.money_unlock", rec)
                    rec.remove()
                elif action == "confirm":
                    self.call("domains.money_charge", rec)
                    rec.store()
                elif action == "recheck":
                    requestid = rec.get("registrar_id")
                    if requestid:
                        params = []
                        params.append(("action", "REQUEST"))
                        params.append(("login", self.conf("domains.login")))
                        params.append(("passwd", self.conf("domains.password")))
                        params.append(("requestid", requestid))
                        self.info("Querying registrar: %s", params)
                        params = "&".join(["%s=%s" % (key, urlencode(unicode(val).encode("koi8-r", "replace"))) for key, val in params])
                        try:
                            with Timeout.push(180):
                                cnn = HTTPConnection()
                                try:
                                    cnn.connect(("my.i7.ru", 80))
                                except IOError as e:
                                    self.error("Error coonecting to the registrar")
                                try:
                                    request = cnn.get("/c/registrar?%s" % params)
                                    request.add_header("Connection", "close")
                                    response = cnn.perform(request)
                                    if response.status_code != 200:
                                        self.error("Registrar response: %s", response.status)
                                    else:
                                        m = re_i7_response.match(response.body)
                                        if not m:
                                            self.error("Invalid response from the registrar: %s", response.body)
                                        else:
                                            action, id, state, cause, inprogress = m.groups()
                                            inprogress = True if len(inprogress) else False
                                            self.info("Registrar response: action=%s, id=%s, state=%s, cause=%s, inprogress=%s", action, id, state, cause, inprogress)
                                            rec.set("registrar_state", state)
                                            rec.set("registrar_cause", cause)
                                            rec.set("registrar_inprogress", inprogress)
                                            rec.store()
                                finally:
                                    cnn.close()
                        except TimeoutError:
                            self.error("Connection to the registrar timed out")
                self.call("admin.redirect", "domains/pending")
        domains = self.objlist(DomainList, query_index="registered", query_equal="pending")
        domains.load(silent=True)
        vars = {
            "Domain": self._("Domain"),
            "Created": self._("Created"),
            "RegistrarID": self._("Request"),
            "RegistrarState": self._("State"),
            "RegistrarCause": self._("Cause"),
            "RegistrarInProgress": self._("In&nbsp;progress"),
            "Confirm": self._("Confirm"),
            "Cancel": self._("Cancel"),
            "confirm": self._("confirm"),
            "cancel": self._("cancel"),
            "Recheck": self._("Recheck"),
            "recheck": self._("recheck"),
            "domains": domains.data(),
        }
        self.call("admin.response_template", "admin/constructor/domains-pending.html", vars)

    def money_unlock(self, domain):
        money_lock = domain.get("money_lock")
        if money_lock is None:
            return None
        money = self.call("money.member-money", domain.get("user"))
        lock = money.unlock(money_lock)
        if lock:
            domain.delkey("money_lock")
            return lock
        else:
            return None

    def money_charge(self, domain):
        money = self.call("money.member-money", domain.get("user"))
        lock = self.money_unlock(domain)
        if not lock:
            return
        domain.delkey("money_lock")
        money.force_debit(float(lock.get("amount")), lock.get("currency"), "domain-reg", domain=domain.uuid)
        domain.set("registered", "yes")

    def user_tables(self, user, tables):
        if self.req().has_access("domains"):
            domains = self.objlist(DomainList, query_index="user", query_equal=user.uuid)
            domains.load(silent=True)
            if len(domains):
                status = {
                    "ext": self._("external"),
                    "yes": self._("completed"),
                    "pending": self._("pending"),
                }
                tables.append({
                    "type": "domains",
                    "title": self._("Domains"),
                    "order": 40,
                    "header": [self._("Domain"), self._("Registration"), self._("Project")],
                    "rows": [(d.uuid, status.get(d.get("registered", "ext"), self._("unknown")), d.get("project")) for d in domains]
                })

    def ext_unassign(self):
        req = self.req()
        try:
            project = self.int_app().obj(Project, req.args)
        except ObjectNotFoundException:
            self.call("web.not_found")
        domain = project.get("domain")
        if domain:
            try:
                obj = self.main_app().obj(Domain, domain)
            except ObjectNotFoundException:
                self.call("web.not_found")
            project.delkey("domain")
            obj.remove()
            project.store()
        self.call("admin.redirect", "constructor/project-dashboard/%s" % project.uuid)

class DomainWizard(Wizard):
    def new(self, **kwargs):
        super(DomainWizard, self).new(**kwargs)
        self.config.set("state", "main")
        self.config.set("tag", "domain")
        self.config.set("redirect_fail", kwargs["redirect_fail"])
        
    def menu(self, menu):
        menu.append({"id": "wizard/call/%s" % self.uuid, "text": self._("Domain wizard"), "leaf": True, "order": 20, "icon": "/st-mg/menu/wizard.png"})

    def domain_registered(self, domain, arg):
        self.config.set("domain", domain)
        self.config.set("registered", True)
        self.config.store()
    
    def request(self, cmd):
        req = self.req()
        state = self.config.get("state")
        project = self.app().project
        if state == "main":
            if cmd == "cancel":
                wizs = self.call("wizards.find", "domain-reg")
                for wiz in wizs:
                    wiz.abort()
                self.abort()
                self.call("admin.redirect", self.config.get("redirect_fail"))
            elif cmd == "check":
                domain = req.param("domain").strip().lower()
                self.config.set("domain", domain)
                self.config.store()
                errors = {}
                if domain == "":
                    errors["domain"] = self._("Specify your domain name")
                elif not re_domain.match(domain):
                    errors["domain"] = self._("Invalid domain name")
                elif re_double_dash.search(domain):
                    errors["domain"] = self._("Domain name can't contain double dash ('--'). International domain names are not supported")
                elif len(domain) > 63:
                    errors["domain"] = self._("Domain name is too long")
                if not len(errors):
                    self.call("domains.validate_new", domain, errors)
                if len(errors):
                    self.call("web.response_json", {"success": False, "errors": errors})
                wizs = self.call("wizards.find", "domain-reg")
                for wiz in wizs:
                    wiz.abort()
                # saving wizard data
                self.call("domains.assign", domain)
                for wiz in wizs:
                    wiz.finish()
                self.finish()
                self.call("admin.response", self._('You have assigned domain name <strong>{0}</strong> to your game. Now you can enter the game only via this domain. It may take several hours for your local DNS server to make your domain available. Please be patient. <a href="//{1}/cabinet" target="_top">Return to the cabinet</a>').format(domain, self.main_app().canonical_domain), {})
            elif cmd == "register":
                wizs = self.call("wizards.find", "domain-reg")
                if len(wizs):
                    self.call("admin.redirect", "wizard/call/%s" % wizs[0].uuid)
                wiz = self.call("wizards.new", "mg.constructor.domains.DomainRegWizard", target=["wizard", self.uuid, "domain_registered", ""], redirect_fail="wizard/call/%s" % self.uuid)
                self.call("admin.redirect", "wizard/call/%s" % wiz.uuid)
            ns1 = self.main_app().config.get("dns.ns1")
            ns2 = self.main_app().config.get("dns.ns2")
            vars = {
                "Disclaimer": self._("<p>We don't offer a free domain name &mdash; you have to register it manually. You may take domain of any level you want: 2nd-level domain (yourgame.com), 3rd-level (game.yourdomain.com) or any other (game.project.person.company.com)</p>"),
                "IHaveADomain": self._("If you have a domain name already"),
                "IdLikeToRegister": self._("If you would like to register a new domain now"),
                "DomainSettings": self._("If you want to assign the entire domain (for example: <strong>blahblahgame.com</strong>) to the game, supply the following settings to your domain registrar:<ul><li>DNS server 1: {0}</li><li>DNS server 2: {1}</li></ul>If you want to assign a subdomain (for example: <strong>blahblahgame.example.com</strong>) to the game go to the <strong>example.com</strong> domain control panel (or edit domain zone configuration) and add subdomain records:<ul><li><strong>blahblahgame</strong> IN NS {0}.</li><li><strong>blahblahgame</strong> IN NS {1}.</li></ul>").format(ns1, ns2),
                "LaunchWizard": self._("Launch domain registration wizard"),
                "wizard": self.uuid,
                "DomainName": self._("Domain name (without www)"),
                "CheckDomain": self._("Check domain and assign it to the game"),
                "CheckingDomain": self._("Checking domain..."),
                "domain_name": jsencode(self.config.get("domain")),
            }
            if self.config.get("domain"):
                if self.config.get("registered"):
                    vars["expanded"] = 2
                else:
                    vars["expanded"] = 1
            self.call("admin.response_template", "constructor/setup/domain.html", vars)
        else:
            raise RuntimeError("Invalid DomainWizard state: %s" % state)
