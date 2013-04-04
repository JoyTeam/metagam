var Characters = {
    params: {},
    names: {},
    context_menu: []
};

Characters.set_params = function (id, params) {
    params.id = id;
    this.params[id] = params;
    this.names[params.name] = id;
};

Characters.params_by_name = function (name) {
    var id = this.names[name];
    if (!id)
        return undefined;
    return this.params[id];
};

Characters.menu = function (el) {
    var params = this.params_by_name(el.innerHTML);
    if (!params) {
        return;
    }
    var link_el = Ext.get(el);
    var menu = new Ext.menu.Menu({});
    var env = {
        globs: {
            'char': params,
            'viewer': this.params[Game.character]
        }
    };
    var anyItems = false;
    var cmenu = this.context_menu;
    for (var i = 0; i < cmenu.length; i++) {
        var ent = cmenu[i];
        (function (ent) {
            if (MMOScript.evaluate(ent.visible, env)) {
                if (ent.href) {
                    menu.addMenuItem({
                        icon: ent.image,
                        text: MMOScript.evaluateText(ent.title, env),
                        href: MMOScript.evaluateText(ent.href, env),
                        hrefTarget: '_blank',
                        hideOnClick: true
                    });
                } else {
                    menu.addMenuItem({
                        icon: ent.image,
                        text: MMOScript.evaluateText(ent.title, env),
                        hideOnClick: true,
                        listeners: {
                            click: function () {
                                if (ent.onclick) {
                                    eval(MMOScript.evaluateText(ent.onclick, env));
                                } else if (ent.qevent) {
                                    Game.qevent(ent.qevent, {
                                        targetchar: params.id
                                    });
                                }
                            }
                        }
                    });
                }
                anyItems = true;
            }
        })(ent);
    }
    if (anyItems) {
        menu.show(link_el, 'tl-bl');
        Ext.ux.ManagedIFrame.Manager.showShims();
        menu.addListener('hide', function () {
            Ext.ux.ManagedIFrame.Manager.hideShims();
        });
    }
};

wait(['mmoscript'], function () {
    loaded('characters');
});
