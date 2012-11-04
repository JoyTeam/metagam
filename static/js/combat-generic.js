var GenericCombat = Ext.extend(Combat, {
    constructor: function (id) {
        var self = this;
        GenericCombat.superclass.constructor.call(self, id);
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
        self.myAvatarComponent = new Ext.Container({
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
        self.enemyAvatarComponent = new Ext.Container({
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
        self.logComponent = new Ext.Container({
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
                        region: 'north',
                        layout: 'border',
                        height: self.combatHeight,
                        border: false,
                        split: self.logResize,
                        items: viewportItems
                    },
                    {
                        region: 'center',
                        border: false,
                        autoScroll: true,
                        items: self.logComponent
                    }
                ];
            } else if (self.logLayout == 1) {
                viewportItems.push({
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
            id: 'combat-viewport',
            items: self.viewportItems()
        });
    }
});
