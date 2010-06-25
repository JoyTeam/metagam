copyright="Alexander Lourier <aml@rulezz.ru>"
package_name="Metagam"
package_version="0.1"

all: pot po mo
.PHONY: pot po mo
	
sources=$(shell find . -name '*.py')
server_mo_files = $(wildcard mg/locale/*/LC_MESSAGES/*.mo)
server_po_files = $(wildcard mg/locale/server/*.po)

pot: mg/locale/mg_server.pot
mg/locale/mg_server.pot: $(sources)
	find . -name '*.py' > .src-files
	xgettext -d mg_server -f .src-files -L Python --copyright-holder=$(copyright) \
		--package-name=$(package_name) --package-version=$(package_version)
	rm .src-files
	mv mg_server.po mg/locale/mg_server.pot
	mkdir -p mg/locale/server

po: $(server_po_files)
$(server_po_files): mg/locale/mg_server.pot
	make -C mg/locale/server po

mo: $(server_mo_files)
$(server_mo_files): $(server_po_files)
	make -C mg/locale/server mo

test:
	for i in mg/test/*.py ; do echo $$i ; python2.6 $$i ; done
