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
        self.myAvatarComponent.update(self.myself.getAvatarHTML());
    },

    /*
     * For every element with class "combat-<cls>"
     * run callback provided.
     */
    forEachElement: function (cls, callback) {
        var self = this;
        Ext.getBody().query('.combat-' + cls).forEach(callback);
    }
});

var GenericCombatMember = Ext.extend(CombatMember, {
    constructor: function (combat, memberId) {
        var self = this;
        GenericCombatMember.superclass.constructor.call(self, combat, memberId);
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
     * For every element with class "combat-member-<memberId>-<cls>"
     * run callback provided.
     */
    forEachElement: function (cls, callback) {
        var self = this;
        self.combat.forEachElement('member-' + self.id + '-' + cls, callback);
    },

    /*
     * Generate HTML for rendering member's avatar
     */
    getAvatarHTML: function () {
        var self = this;
        var html = '<div class="combat-member-avatar">';
        html += self.getImageHTML();
        html += '</div>';
        return html;
    },

    /*
     * Generate HTML for rendering member's image
     */
    getImageHTML: function () {
        var self = this;
        var image = self.params.image;
        if (!image) {
            return '';
        }
        return '<div class="combat-member-image"><img class="combat-member-' + self.id + '-image" src="' + image + '" alt="" /></div>';
    }
});
