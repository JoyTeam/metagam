.PHONY: all pot po mo js
all: pot po mo js

# ============= SETTINGS ===============
copyright="Alexander Lourier <aml@rulezz.ru>"
package_name="Metagam"
package_version="0.1"
langs := ru
mo_modules := server
js_modules := mainsite

# ============= MODULE: server ===============
server_sources := $(shell find . -name '*.py')
server_mo_files := $(foreach lang,$(langs),mg/locale/$(lang)/LC_MESSAGES/mg_server.mo)
server_po_files := $(foreach lang,$(langs),mg/locale/server/$(lang).po)
mg/locale/mg_server.pot: $(server_sources)
	find . -name '*.py' > .src-files
	xgettext -d mg_server -f .src-files -L Python --copyright-holder=$(copyright) \
		--package-name=$(package_name) --package-version=$(package_version) \
		--force-po -kgettext_noop
	rm .src-files
	mv mg_server.po mg/locale/mg_server.pot
	mkdir -p mg/locale/server
mg/locale/server/%.po: mg/locale/mg_server.pot
	msgmerge -U $@ $<
	touch $@
mg/locale/%/LC_MESSAGES/mg_server.mo: mg/locale/server/%.po
	msgfmt -o $@ $<

# ============= MODULE: mainsite ===============
mainsite_sources := $(shell find static/mainsite static/admin -name '*.js' | egrep -v '/gettext-')
mainsite_po_files := $(foreach lang,$(langs),mg/locale/mainsite/$(lang).po)
mainsite_js_files := $(foreach lang,$(langs),static/mainsite/gettext-$(lang).js)
mg/locale/mg_mainsite.pot: $(mainsite_sources)
	xgettext -d mg_mainsite -L Python --copyright-holder=$(copyright) --force-po \
		--package-name=$(package_name) --package-version=$(package_version) \
		-kgettext_noop \
		$(mainsite_sources)
	mv mg_mainsite.po mg/locale/mg_mainsite.pot
	mkdir -p mg/locale/mainsite
mg/locale/mainsite/%.po: mg/locale/mg_mainsite.pot
	msgmerge -U $@ $<
	touch $@
static/mainsite/gettext-%.js: mg/locale/mainsite/%.po
	(echo -n 'var gt=new Gettext({"domain": "mg_mainsite", "locale_data": {"mg_mainsite": '; po2json $< ; echo '}})') > $@

# ============= GLOBAL ===============
modules := $(mo_modules) $(js_modules)
pot: $(foreach module,$(modules),mg/locale/mg_$(module).pot)
po: $(foreach module,$(modules),$($(module)_po_files))
mo: $(foreach module,$(mo_modules),$($(module)_mo_files))
js: $(foreach module,$(js_modules),$($(module)_js_files))

test:
	for i in mg/test/*.py ; do echo $$i ; python2.6 $$i ; done

debug:
	@echo "POT Files: $(foreach module,$(modules),mg/locale/mg_$(module).pot)"
	@echo "PO Files: $(foreach module,$(modules),$($(module)_po_files))"
	@echo "MO Files: $(foreach module,$(mo_modules),$($(module)_mo_files))"
	@echo "JS Files: $(foreach module,$(js_modules),$($(module)_js_files))"
