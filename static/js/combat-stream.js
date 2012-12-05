var Combat = {};

Combat.state_marker = function(pkt) {
    this.call(pkt.combat, 'stateMarker', pkt.marker);
};

Combat.combat_params = function(pkt) {
    this.call(pkt.combat, 'combatParamsChanged', pkt.params);
};

Combat.member_joined = function(pkt) {
    this.call(pkt.combat, 'memberJoined', pkt.member);
};

Combat.member_params = function(pkt) {
    this.call(pkt.combat, 'memberParamsChanged', pkt.member, pkt.params);
};

Combat.myself = function(pkt) {
    this.call(pkt.combat, 'setMyself', pkt.member);
};

/* Call combat method */
Combat.call = function (combat_id, method) {
    var args = Array.prototype.slice.call(arguments, 2);
    try {
        var iframe = Ext.getCmp('main-iframe');
        if (iframe) {
            var win = iframe.el.dom.contentWindow || window.frames['main-iframe'];
            if (win) {
                var doc = win.document;
                if (doc) {
                    var combat = doc['combatObject' + combat_id];
                    if (combat) {
                        combat.callMethod(method, args);
                    }
                }
            }
        }
    } catch (e) {
        Game.error(gt.gettext('Exception'), e);
    }
};

wait(['realplexor-stream'], function() {
    Stream.stream_handler('combat', Combat);
    loaded('combat-stream');
});
