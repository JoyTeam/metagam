var Combat = {};

Combat.state_marker = function(pkt) {
    this.call(pkt.combat, 'stateMarker', pkt.marker);
};

Combat.combat_params = function(pkt) {
    this.call(pkt.combat, 'combatParamsChanged', pkt.params);
};

Combat.member_params = function(pkt) {
    this.call(pkt.combat, 'memberParamsChanged', pkt.member, pkt.params);
};

/* Call combat method */
Combat.call = function (combat_id, method) {
    try {
        var iframe = Ext.getCmp('main-iframe');
        if (iframe) {
            var win = iframe.el.dom.contentWindow || window.frames['main-iframe'];
            if (win) {
                var doc = win.document;
                if (doc) {
                    var combat = doc['combatObject' + combat_id];
                    if (combat) {
                        combat.callMethod(method, Array.prototype.slice(arguments, 2));
                    }
                }
            }
        }
    } catch (e) {
        this.error(gt.gettext('Exception'), e);
    }
};

wait(['realplexor-stream'], function() {
    Stream.stream_handler('combat', Combat);
    loaded('combat-stream');
});
