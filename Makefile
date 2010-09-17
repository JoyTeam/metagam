.PHONY: all pot po mo js
all: translations
translations: pot po mo js

# ============= SETTINGS ===============
copyright="Alexander Lourier <aml@rulezz.ru>"
package_name="Metagam"
package_version="0.1"
langs := ru
mo_modules := server
js_modules := constructor

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

# ============= MODULE: constructor ===============
constructor_sources := $(shell find static/constructor static/admin -name '*.js' | egrep -v '/gettext-')
constructor_po_files := $(foreach lang,$(langs),mg/locale/constructor/$(lang).po)
constructor_js_files := $(foreach lang,$(langs),static/constructor/gettext-$(lang).js)
mg/locale/mg_constructor.pot: $(constructor_sources)
	xgettext -d mg_constructor -L Python --copyright-holder=$(copyright) --force-po \
		--package-name=$(package_name) --package-version=$(package_version) \
		-kgettext_noop \
		$(constructor_sources)
	mv mg_constructor.po mg/locale/mg_constructor.pot
	mkdir -p mg/locale/constructor
mg/locale/constructor/%.po: mg/locale/mg_constructor.pot
	msgmerge -U $@ $<
	touch $@
static/constructor/gettext-%.js: mg/locale/constructor/%.po
	(echo -n 'var gt=new Gettext({"domain": "mg_constructor", "locale_data": {"mg_constructor": '; po2json $< ; echo '}})') > $@

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

clean:
	find \( -name '*.pyc' -or -name '*~' \) -exec rm {} \;

deploy: translations
	rm -rf depl
	find -name '*.pyc' -exec rm {} \;
	bin/mg_compile .
	mkdir -p depl/bin
	for m in director reload server worker ; do cp bin/mg_$$m bin/*.sh depl/bin/ ; done
	cp -R mg static depl/
	find depl/mg \( -name '*.py' -or -name '.hg*' -or -name '*.po' -or -name '*.pot' \) -exec rm -rf {} \;
	rsync -r depl/* f0.mmoconstructor.com:/home/mg/
	ssh f0.mmoconstructor.com 'cd /home/mg;rsync -r * d0:/home/mg/'
