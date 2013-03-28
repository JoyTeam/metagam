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

Combat.action = function(pkt) {
    this.call(pkt.combat, 'actionInfo', pkt.action);
};

Combat.available_actions = function(pkt) {
    this.call(pkt.combat, 'setAvailableActions', pkt.actions);
};

Combat.turn_got = function(pkt) {
    this.call(pkt.combat, 'turnGot');
};

Combat.turn_lost = function(pkt) {
    this.call(pkt.combat, 'turnLost');
};

Combat.turn_timeout = function(pkt) {
    this.call(pkt.combat, 'turnTimeout');
};

Combat.log = function(pkt) {
    this.call(pkt.combat, 'log', pkt.entries);
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
        Game.error(sprintf(gt.gettext('Exception in %s'), 'combat.' + method), e);
        if (e.stack) {
            try {
                debug_log('<b>Exception: ' + e + '</b>' + e.stack);
            } catch (e) {
            }
        }
    }
};

wait(['realplexor-stream'], function() {
    Stream.stream_handler('combat', Combat);
    loaded('combat-stream');
});
