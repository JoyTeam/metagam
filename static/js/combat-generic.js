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
        self.goButtonText = 'Go';
        self.avatarWidth = 120;
        self.avatarHeight = 220;
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
            html: ''
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
            html: ''
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
        self.mainComponent = new Ext.Container({
            id: 'combat-main',
            layout: 'fit',
            border: false,
            autoWidth: true,
            items: []
        });
    },

    /*
     * Generate viewport parameters
     */
    viewportParams: function () {
        var self = this;

        // myAvatar, mainComponent, enemyAvatar
        var topItems = [];
        if (self.myAvatarComponent) {
            topItems.push({
                xtype: 'container',
                width: self.myAvatarWidth,
                autoScroll: false,
                border: false,
                split: self.myAvatarResize,
                items: self.myAvatarComponent
            });
        }
        if (self.mainComponent) {
            topItems.push({
                xtype: 'container',
                border: false,
                autoScroll: true,
                bodyCfg: {
                    cls: 'x-panel-body combat-main'
                },
                flex: 1,
                items: self.mainComponent
            });
        }
        if (self.enemyAvatarComponent) {
            topItems.push({
                xtype: 'container',
                width: self.enemyAvatarWidth,
                autoScroll: false,
                border: false,
                split: self.enemyAvatarResize,
                items: self.enemyAvatarComponent
            });
        }
        var viewportParams = {
            xtype: 'container',
            border: false,
            layout: 'hbox',
            layoutConfig: {
                align: 'middle'
            },
            items: topItems
        };

        if (self.logComponent) {
            if (self.logLayout == 0) {
                viewportParams.region = 'north';
                viewportParams.height = self.combatHeight;
                viewportParams.split = self.logResize;
                viewportParams = {
                    xtype: 'container',
                    layout: 'border',
                    border: false,
                    items: [
                        viewportParams,
                        {
                            xtype: 'container',
                            region: 'center',
                            border: false,
                            autoScroll: true,
                            layout: 'fit',
                            items: self.logComponent
                        }
                    ]
                };
            } else if (self.logLayout == 1) {
                viewportParams.region = 'center';
                viewportParams = {
                    xtype: 'container',
                    layout: 'border',
                    border: false,
                    items: [
                        viewportParams,
                        {
                            xtype: 'container',
                            region: 'south',
                            height: self.logHeight,
                            border: false,
                            autoScroll: true,
                            layout: 'fit',
                            split: self.logResize,
                            items: self.logComponent
                        }
                    ]
                };
            }
        }

        return viewportParams;
    },

    /*
     * Show all widgets required to display user interface
     */
    render: function () {
        var self = this;
        self.viewportComponent = new Ext.Viewport(self.viewportParams());
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
    },

    /*
     * Notify combat that its controlled member
     * got right of turn
     */
    turnGot: function () {
        var self = this;
        GenericCombat.superclass.turnGot.call(self);
        self.showActionSelector();
    },

    /*
     * Notify combat that its controlled member
     * lost right of turn
     */
    turnLost: function () {
        var self = this;
        GenericCombat.superclass.turnLost.call(self);
        self.hideActionSelector();
    },

    /*
     * Show interface where player can choose an action
     */
    showActionSelector: function () {
        var self = this;
        if (!self.myself) {
            return;
        }
        if (!self.actionSelector) {
            self.actionSelector = self.newActionSelector();
        }
        self.actionSelector.show();
        self.viewportComponent.doLayout();
    },

    /*
     * Hide interface where player can choose an action
     */
    hideActionSelector: function () {
        var self = this;
        if (!self.actionSelector) {
            return;
        }
        self.actionSelector.hide();
        self.viewportComponent.doLayout();
    },

    /*
     * Create new action selector (override to use another class)
     */
    newActionSelector: function () {
        var self = this;
        return new GenericCombatActionSelector(self);
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
        return '<div class="combat-member-image"><img class="c-m-' +
            self.id + '-image" src="' + image + '" alt="" style="width: ' +
            self.combat.avatarWidth + 'px; height: ' + self.combat.avatarHeight + 'px" /></div>';
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

var GenericCombatActionSelector = Ext.extend(Object, {
    constructor: function (combat) {
        var self = this;
        self.combat = combat;
        self.shown = false;
        self.myself = combat.myself;
    },

    /*
     * Show action selector
     */
    show: function () {
        var self = this;
        if (self.shown) {
            self.hide();
        }
        self.action = null;
        self.actionInfo = null;
        self.actionItems = self.newActionItems();
        self.cmp = new Ext.Container({
            xtype: 'container',
            layout: 'hbox',
            border: false,
            layoutConfig: {
                align: 'middle'
            },
            items: [
                self.actionItems
            ]
        });
        self.combat.mainComponent.removeAll(true);
        self.combat.mainComponent.add(self.cmp);

        /* Display preselected target member */
        if (self.combat.enemyAvatarComponent) {
            var targets = self.myself.params.targets;
            if (targets != 'selectable') {
                if (targets) {
                    // targets == [1, 2, 3]
                    var targetId = targets[0];
                    if (targetId) {
                        var target = self.combat.members[targetId];
                        if (target) {
                            self.combat.enemyAvatarComponent.update(target.renderAvatarHTML());
                        }
                    }
                } else {
                    // targets == null
                    self.combat.enemyAvatarComponent.update('');
                }
            } else {
                // targets are to be selected by player
                self.combat.enemyAvatarComponent.update('');
            }
        }

        self.combat.viewportComponent.doLayout();
        self.shown = true;
    },

    /*
     * Hide action selector
     */
    hide: function () {
        var self = this;
        if (!self.shown) {
            return;
        }
        self.shown = false;
        // Destroy all other items
        self.actionItems = undefined;
        self.targetItems = undefined;
        self.combat.mainComponent.removeAll(true);
        self.combat.viewportComponent.doLayout();
        delete self.cmp;
    },

    /*
     * Create action selector component
     */
    newActionItems: function () {
        var self = this;
        var items = [];
        for (var i = 0; i < self.combat.availableActions.length; i++) {
            var ent = self.combat.availableActions[i];
            var act = self.combat.actions[ent.action];
            if (!act) {
                continue;
            }
            (function (ent, act) {
                var cmp = new Ext.BoxComponent({
                    id: 'combat-action-id-' + act.code,
                    cls: 'combat-action-selector combat-item-deselected combat-action-deselected',
                    autoHeight: true,
                    style: {
                        padding: '10px'
                    },
                    html: act.name,
                    listeners: {
                        render: function () {
                            this.getEl().on('click', function () {
                                self.selectAction(ent, act);
                            });
                        }
                    }
                });
                items.push(cmp);
            })(ent, act);
        }
        return new Ext.Container({
            id: 'combat-actions-box',
            items: items,
            flex: 1,
            style: {
                paddingRight: '40px'
            },
            border: false
        });
    },

    /*
     * Select specified action and show prompt to the user to choose action attributes
     */
    selectAction: function(act, actInfo) {
        var self = this;
        Ext.select('.combat-action-selected', self.actionItems).
            removeClass('combat-item-selected').
            removeClass('combat-action-selected').
            addClass('combat-item-deselected').
            addClass('combat-action-deselected');
        self.action = act;
        self.actionInfo = actInfo;
        if (act) {
            Ext.select('#combat-action-id-' + actInfo.code).
                removeClass('combat-item-deselected').
                removeClass('combat-action-deselected').
                addClass('combat-item-selected').
                addClass('combat-action-selected');
            if (self.myself.params.targets == 'selectable') {
                if (act.targets_max > 0) {
                    self.showTargets();
                } else {
                    self.hideTargets();
                }
                self.hideGoButton();
            } else {
                self.hideTargets();
                self.showGoButton();
            }
            self.combat.viewportComponent.doLayout();
        }
    },

    /*
     * Show targets selector
     */
    showTargets: function () {
        var self = this;
        if (self.targetItems) {
            self.hideTargets();
        }
        self.targetItems = self.newTargetItems();
        self.cmp.add(self.targetItems);
        // TODO: show/hide specific targets
    },

    /*
     * Hide targets selector
     */
    hideTargets: function () {
        var self = this;
        if (self.targetItems) {
            self.targetItems.ownerCt.remove(self.targetItems, true);
            self.targetItems = undefined;
        }
    },

    /*
     * Create action selector component.
     */
    newTargetItems: function () {
        var self = this;
        var items = [];
        for (var memberId in self.combat.members) {
            if (!self.combat.members.hasOwnProperty(memberId)) {
                continue;
            }
            (function (memberId) {
                var member = self.combat.members[memberId];
                var cmp = new Ext.BoxComponent({
                    html: member.params.name,
                    autoHeight: true,
                    style: {
                        padding: '10px'
                    },
                    listeners: {
                        render: function () {
                            this.getEl().on('click', function () {
                                self.toggleTarget(member);
                            });
                            this.getEl().on('mouseover', function () {
                                self.showEnemy(member);
                            });
                        }
                    }
                });
                member.targetCmp = cmp;
                items.push(cmp);
            })(memberId);
        }
        return new Ext.Container({
            id: 'combat-targets-box',
            items: items,
            border: false,
            flex: 1,
            style: {
                paddingRight: '40px'
            },
            listeners: {
                render: function () {
                    for (var memberId in self.combat.members) {
                        if (!self.combat.members.hasOwnProperty(memberId)) {
                            continue;
                        }
                        self.selectTarget(self.combat.members[memberId], false);
                    }
                }
            }
        });
    },

    /*
     * Select/deselect action target
     */
    selectTarget: function (member, state) {
        var self = this;
        if (self.myself.params.targets != 'selectable') {
            return;
        }
        member.targeted = state;
        if (member.targetCmp) {
            if (state) {
                member.targetCmp.removeClass('combat-item-deselected');
                member.targetCmp.removeClass('combat-target-deselected');
                member.targetCmp.addClass('combat-item-selected');
                member.targetCmp.addClass('combat-target-selected');
            } else {
                member.targetCmp.removeClass('combat-item-selected');
                member.targetCmp.removeClass('combat-target-selected');
                member.targetCmp.addClass('combat-item-deselected');
                member.targetCmp.addClass('combat-target-deselected');
            }
        }
        // Display "Go" button
        var anyTargeted = false;
        for (var memberId in self.combat.members) {
            if (!self.combat.members.hasOwnProperty(memberId)) {
                continue;
            }
            if (self.combat.members[memberId].targeted) {
                anyTargeted = true;
                break;
            }
        }
        if (anyTargeted) {
            self.showGoButton();
        } else {
            self.hideGoButton();
        }
        self.combat.viewportComponent.doLayout();
    },

    /*
     * Show "Go" button
     */
    showGoButton: function () {
        var self = this;
        if (!self.goButton) {
            self.goButton = self.newGoButton();
            self.cmp.add(self.goButton);
        }
    },

    /*
     * Hide "Go" button
     */
    hideGoButton: function () {
        var self = this;
        if (self.goButton) {
            self.goButton.ownerCt.remove(self.goButton, true);
            self.goButton = undefined;
        }
    },

    /*
     * Toggle "selected" state for given member
     */
    toggleTarget: function (member) {
        var self = this;
        self.selectTarget(member, !member.targeted);
    },

    /*
     * Show enemy avatar
     */
    showEnemy: function (member) {
        var self = this;
        if (self.combat.enemyAvatarComponent) {
            self.combat.enemyAvatarComponent.update(member.renderAvatarHTML());
            self.combat.viewportComponent.doLayout();
        }
    },

    /*
     * Create go button component.
     */
    newGoButton: function () {
        var self = this;
        return new Ext.Container({
            id: 'combat-go-box',
            items: [{
                xtype: 'button',
                text: self.combat.goButtonText,
                width: 100,
                height: 40
            }],
            border: false,
            flex: 1
        });
    }
});
