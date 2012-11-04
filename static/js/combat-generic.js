var GenericCombat = Ext.extend(Combat, {
    constructor: function (id) {
        var self = this;
        GenericCombat.superclass.constructor.call(self, id);
        self.initGUI();
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
     * Create all widgets required to display user interface
     */
    initGUI: function () {
        var self = this;
        self.logControl = new Ext.Container({
            id: 'combat-log',
            border: false,
            autoWidth: true,
            html: 'Combat log'
        });
        self.combatmain = new Ext.Container({
            autoDestroy: true
        });
        self.viewport = new Ext.Viewport({
            layout: 'border',
            id: 'combat-viewport',
            items: [
                {
                    region: 'south',
                    height: self.logHeight,
                    autoScroll: false,
                    layout: 'fit',
                    border: 'false',
                    items: self.logControl
                },
                {
                    region: 'center',
                    border: false,
                    id: 'combat-main',
                    autoScroll: true,
                    bodyCfg: {
                        cls: 'x-panel-body combat-main'
                    },
                    items: self.combatmain
                }
            ]
        });
    }
});
