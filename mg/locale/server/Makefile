languages = ru
po_objects = $(foreach lang,$(languages),$(lang).po)
mo_objects = $(foreach lang,$(languages),../$(lang)/LC_MESSAGES/mg_server.mo)

all: po mo

po: $(po_objects)
%.po: ../mg_server.pot
	msgmerge -U $@ ../mg_server.pot

mo: $(mo_objects)
../%/LC_MESSAGES/mg_server.mo: %.po
	msgfmt -o $@ $<
