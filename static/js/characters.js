var Characters = {
    params: {},
    names: {},
    context_menu: [],
    progress_bars: {},
    progress_bar_deps: {},
    myparams: {}
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

Characters.progress_bar = function (id, param, param_max) {
    this.progress_bars[id] = {
        param: param,
        param_max: param_max
    };
    this.progress_bar_dep(param, id);
    this.progress_bar_dep(param_max, id);
};

Characters.progress_bar_dep = function (param, pbar) {
    if (!this.progress_bar_deps[param]) {
        this.progress_bar_deps[param] = [];
    }
    this.progress_bar_deps[param].push(pbar);
};

Characters.myparam = function (pkt) {
    var val;
    if (pkt.value && pkt.value.length == 2) {
        val = new DynamicValue(pkt.value[1]);
        if (pkt.value[0]) {
            val.setTill(pkt.value[0]);
        }
    } else {
        val = new DynamicValue(pkt.value);
    }
    val.dirty = true;
    this.myparams[pkt.param] = val;
    this.updateParams();
    var updateGame;
    try {
        updateGame = Game.on_myparam_update;
    } catch (e) {
    }
    if (updateGame) {
        updateGame(pkt.param);
    }
};

Characters.myParam = function (key) {
    var param = this.myparams[key];
    if (!param) {
        return undefined;
    }
    return param.actualValue;
};

Characters.updateParams = function () {
    var self = this;
    if (self.paramUpdaterTimer) {
        return;
    }
    var updateProgressBars = {};
    var dirty = false;
    var time = TimeSync.getTime();
    if (!time) {
        dirty = true;
    } else {
        var changes;
        for (var key in self.myparams) {
            if (self.myparams.hasOwnProperty(key)) {
                var val = self.myparams[key];
                if (val.dirty) {
                    var newVal = val.evaluateAndForget(time);
                    if (newVal !== val.actualValue) {
                        var lst = self.progress_bar_deps[key];
                        if (lst) {
                            for (var i = 0; i < lst.length; i++) {
                                updateProgressBars[lst[i]] = true;
                            }
                        }
                        val.actualValue = newVal;
                        if (!changes) {
                            changes = {};
                        }
                        changes[key] = val.actualValue;
                    }
                    if (val.dynamic) {
                        dirty = true;
                    } else {
                        val.dirty = false;
                    }
                }
            }
        }
        for (var id in updateProgressBars) {
            if (updateProgressBars.hasOwnProperty(id)) {
                var pb = self.progress_bars[id];
                var val = self.myparams[pb.param];
                var val_max = self.myparams[pb.param_max];
                if (val !== undefined && val_max !== undefined) {
                    val = val.evaluate(time);
                    val_max = val_max.evaluate(time);
                    Game.progress_show(id, val_max ? (val / val_max) : 0);
                }
            }
        }
        if (self.onParamChange && changes) {
            try {
                self.onParamChange(changes);
            } catch (e) {
                Game.error(gt.gettext('Exception'), 'Characters.onParamChange: ' + e);
            }
        }
    }
    if (dirty) {
        self.paramUpdaterTimer = setTimeout(function () {
            self.paramUpdaterTimer = undefined;
            self.updateParams();
        }, 10);
    }
};

Characters.money_changed = function (obj) {
    if (Characters.onMoneyChange) {
        try {
            Characters.onMoneyChange(obj);
        } catch (e) {
            Game.error(gt.gettext('Exception'), 'Characters.onMoneyChange: ' + e);
        }
    }
    var els = Game.dom_query('.char-money-balance-' + obj.currency);
    for (var i = 0; i < els.length; i++) {
        els[i].innerHTML = obj.balance;
    }
};

wait(['realplexor-stream', 'mmoscript', 'timesync', 'game-interface'], function () {
    Stream.stream_handler('characters', Characters);
    loaded('characters');
});
