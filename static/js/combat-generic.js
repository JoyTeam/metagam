var GenericCombat = Ext.extend(Combat, {
    constructor: function (combatId) {
        var self = this;
        GenericCombat.superclass.constructor.call(self, combatId);
        self.createMain();
    },

    /*
     * Initialize interface constants
     */
    initConstants: function () {
        var self = this;
        GenericCombat.superclass.initConstants.call(self);
        self.logHeight = 50;
        self.aboveAvatarParams = [];
        self.belowAvatarParams = [];
    },

    /*
     * Create containter for player's avatar
     */
    createMyAvatar: function () {
        var self = this;
        self.myAvatarComponent = new Ext.BoxComponent({
            id: 'combat-myavatar',
            border: false,
            autoWidth: true,
            html: 'My Avatar'
        });
    },

    /*
     * Create containter for enemy's avatar
     */
    createEnemyAvatar: function () {
        var self = this;
        self.enemyAvatarComponent = new Ext.BoxComponent({
            id: 'combat-enemyavatar',
            border: false,
            autoWidth: true,
            html: 'Enemy Avatar'
        });
    },

    /*
     * Create containter for combat log
     */
    createLog: function () {
        var self = this;
        self.logComponent = new Ext.BoxComponent({
            id: 'combat-log',
            border: false,
            autoWidth: true,
            html: 'Combat log'
        });
    },

    /*
     * Create containter for main interface
     */
    createMain: function () {
        var self = this;
        self.mainComponent = new Ext.BoxComponent({
            id: 'combat-main',
            border: false,
            autoWidth: true,
            html: 'Main content'
        });
    },

    /*
     * Generate list of viewport items
     */
    viewportItems: function () {
        var self = this;
        var viewportItems = [];
        if (self.myAvatarComponent) {
            viewportItems.push({
                xtype: 'container',
                region: 'west',
                width: self.myAvatarWidth,
                autoScroll: false,
                layout: 'fit',
                border: false,
                split: self.myAvatarResize,
                items: self.myAvatarComponent
            });
        }
        if (self.enemyAvatarComponent) {
            viewportItems.push({
                xtype: 'container',
                region: 'east',
                width: self.enemyAvatarWidth,
                autoScroll: false,
                layout: 'fit',
                border: false,
                split: self.enemyAvatarResize,
                items: self.enemyAvatarComponent
            });
        }
        if (self.mainComponent) {
            viewportItems.push({
                xtype: 'container',
                region: 'center',
                border: false,
                autoScroll: true,
                bodyCfg: {
                    cls: 'x-panel-body combat-main'
                },
                items: self.mainComponent
            });
        }
        if (self.logComponent) {
            if (self.logLayout == 0) {
                viewportItems = [
                    {
                        xtype: 'container',
                        region: 'north',
                        layout: 'border',
                        height: self.combatHeight,
                        border: false,
                        split: self.logResize,
                        items: viewportItems
                    },
                    {
                        xtype: 'container',
                        region: 'center',
                        border: false,
                        autoScroll: true,
                        items: self.logComponent
                    }
                ];
            } else if (self.logLayout == 1) {
                viewportItems.push({
                    xtype: 'container',
                    region: 'south',
                    height: self.logHeight,
                    autoScroll: true,
                    layout: 'fit',
                    border: false,
                    split: self.logResize,
                    items: self.logComponent
                });
            }
        }
        return viewportItems;
    },

    /*
     * Show all widgets required to display user interface
     */
    render: function () {
        var self = this;
        self.viewportComponent = new Ext.Viewport({
            layout: 'border',
            items: self.viewportItems()
        });
    },

    /*
     * Method for creating new members. Usually it's overriden
     * by combat implementations.
     */
    newMember: function (memberId) {
        var self = this;
        return new GenericCombatMember(self, memberId);
    },

    /*
     * React to "set myself" event
     */
    setMyself: function (memberId) {
        var self = this;
        GenericCombat.superclass.setMyself.call(self, memberId);
        self.myAvatarComponent.update(self.myself.renderAvatarHTML());
    },

    /*
     * For every element with class "c-<cls>"
     * run callback provided.
     */
    forEachElement: function (cls, callback) {
        var self = this;
        Ext.getBody().query('.c-' + cls).forEach(callback);
    }
});

var GenericCombatMember = Ext.extend(CombatMember, {
    constructor: function (combat, memberId) {
        var self = this;
        GenericCombatMember.superclass.constructor.call(self, combat, memberId);
        self.avatarDeps = {};
    },

    /*
     * Set member parameter "key" to value "value"
     */
    setParam: function (key, value) {
        var self = this;
        GenericCombatMember.superclass.setParam.call(self, key, value);
        self.renderChangedParam(key, value);
    },

    /*
     * Apply changed parameter value to currently
     * displayed interface
     */
    renderChangedParam: function (key, value) {
        var self = this;
        if (key === 'image') {
            self.forEachElement('image', function (el) {
                el.src = value;
            });
        }
    },

    /*
     * For every element with class "c-m-<memberId>-<cls>"
     * run callback provided.
     */
    forEachElement: function (cls, callback) {
        var self = this;
        self.combat.forEachElement('m-' + self.id + '-' + cls, callback);
    },

    /*
     * Generate HTML for rendering member's avatar
     * Side effects: reset dependencies
     */
    renderAvatarHTML: function () {
        var self = this;
        self.avatarDeps = {};
        self.avatarDepCnt = 0;
        var html = '<div class="combat-member-avatar">';
        for (var i = 0; i < self.combat.aboveAvatarParams.length; i++) {
            html += self.renderAvatarParamHTML(self.combat.aboveAvatarParams[i]);
        }
        html += self.renderImageHTML();
        for (var i = 0; i < self.combat.belowAvatarParams.length; i++) {
            html += self.renderAvatarParamHTML(self.combat.belowAvatarParams[i]);
        }
        html += '</div>';
        return html;
    },

    /*
     * Generate HTML for rendering member's image
     */
    renderImageHTML: function () {
        var self = this;
        var image = self.params.image;
        if (!image) {
            return '';
        }
        return '<div class="combat-member-image"><img class="c-m-' + self.id + '-image" src="' + image + '" alt="" /></div>';
    },

    /*
     * Parse syntax tree provided and register dependencies between "member" parameters and
     * CSS classes of displayed expressions.
     */
    registerAvatarParamDeps: function (cls, type, val) {
        var self = this;
        var deps = MMOScript.dependencies(val);
        for (var i = 0; i < deps.length; i++) {
            var dep = deps[i];
            if (dep.length >= 2 && dep[0] == 'member') {
                var param = dep[1];
                if (!self.avatarDeps[param]) {
                    self.avatarDeps[param] = {};
                }
                self.avatarDeps[param][cls] = [type, val];
            }
        }
    },

    /*
     * Generate HTML code for avatar parameter.
     * Side effects: register dependencies
     */
    renderAvatarParamHTML: function (param) {
        var self = this;
        var env = {
            globs: {
                combat: self.combat,
                member: self,
                viewer: self.combat.myself
            }
        };
        var html = '';
        var val = MMOScript.evaluate(param.visible, env);
        var id = ++self.avatarDepCnt;
        html += '<div class="c-m-' + self.id + '-ap-' + id + '" style="display: ' + (val ? 'block' : 'none') + '">';
        self.registerAvatarParamDeps('ap-' + id, 'visibility', param.visible);
        if (param.type == 'tpl') {
            for (var i = 0; i < param.tpl.length; i++) {
                var ent = param.tpl[i];
                if (typeof(ent) == 'string') {
                    html += ent;
                } else {
                    var id = ++self.avatarDepCnt;
                    html += '<span class="c-m-' + self.id + '-ap-' + id + '">';
                    var val = MMOScript.toString(MMOScript.evaluate(ent, env));
                    html += val;
                    html += '</span>';
                    self.registerAvatarParamDeps('ap-' + id, 'html', ent);
                }
            }
        }
        html += '</div>';
        return html;
    },

    /*
     * Called when member parameters changed
     * Format: map(key => value)
     */
    paramsChanged: function (params) {
        var self = this;
        GenericCombatMember.superclass.paramsChanged.call(self, params);
        // prepare list of avatar parameters that may be affected by
        // parameters change
        var affectedClasses;
        for (var key in params) {
            if (params.hasOwnProperty(key)) {
                var deps = self.avatarDeps[key];
                for (var dkey in deps) {
                    if (deps.hasOwnProperty(dkey)) {
                        if (!affectedClasses) {
                            affectedClasses = {};
                        }
                        affectedClasses[dkey] = deps[dkey];
                    }
                }
            }
        }
        // for every "possibly changed" parameter evaluate its value
        if (affectedClasses) {
            var env = {
                globs: {
                    combat: self.combat,
                    member: self,
                    viewer: self.combat.myself
                }
            };
            for (var cls in affectedClasses) {
                if (affectedClasses.hasOwnProperty(cls)) {
                    var ent = affectedClasses[cls];
                    var type = ent[0];
                    var script = ent[1];
                    var val = MMOScript.evaluate(script, env);
                    if (type == 'visibility') {
                        self.forEachElement(cls, function (el) {
                            el.style.display = val ? 'block' : 'none';
                        });
                    } else if (type == 'html') {
                        val = MMOScript.toString(val);
                        self.forEachElement(cls, function (el) {
                            el.innerHTML = val;
                        });
                    }
                }
            }
        }
    }
});
