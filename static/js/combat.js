function Combat(id)
{
    var self = this;
    self.id = id;
    self.members = [];
    self.initConstants();
}

Ext.override(Combat, {
    /*
     * Run combat interface (query current combat state and subscribe to events
     */
    run: function () {
        var self = this;
        document['combatObject' + self.id] = self;
        self.queryState();
    },
    
    /*
     * Initialize interface constants
     */
    initConstants: function () {
        var self = this;
        self.queryStateTimeout = 10000;
        self.queryStateRetry = 3000;
    },

    /*
     * Generate ?rand=<rand> string
     */
    randSuffix: function () {
        return '?rand=' + Math.random();
    },

    /*
     * Ask combat server for complete state of current combat
     */
    queryState: function () {
        var self = this;
        if (self._queryStateMarker) {
            return;
        }
        var marker = '';
        for (var i = 0; i < 10; i++) {
            marker += Math.floor(Math.random() * 10);
        }
        self._queryStateMarker = marker;
        self._callsBlocked = true;
        if (self._queryStateReq) {
            Ext.Ajax.abort(self._queryStateReq);
        }
        var failure = function () {
            setTimeout(function () {
                delete self._queryStateMarker;
                self.queryState();
            }, self.queryStateRetry);
        };
        self._queryStateReq = Ext.Ajax.request({
            url: '/combat/state/' + self.id + '?marker=' + marker,
            timeout: self.queryStateTimeout,
            success: function (response, opts) {
                delete self._queryStateReq;
                if (!response || !response.getResponseHeader) {
                    return failure();
                }
                if (!response.getResponseHeader("Content-Type").match(/json/)) {
                    return failure();
                }
                delete self._queryStateMarker;
            },
            failure: function (response, opts) {
                delete self._queryStateReq;
                if (response.status == 404 || response.status == 403) {
                    self.abort();
                } else {
                    failure();
                }
            }
        });
    },

    /*
     * If combat received initial state, call the method immediately. 
     * Otherwise enqueue it.
     */
    callMethod: function (method, args) {
        var self = this;
        /* Block all incoming calls before receiving valid stateMarker */
        if (method == 'stateMarker') {
            if (self._callsBlocked && args[0] == self._queryStateMarker) {
                self._callsBlocked = false;
            }
            return;
        }
        if (self._callsBlocked) {
            return;
        }
        /* Look for method by its name */
        method = self[method];
        if (!method) {
            return;
        }
        /* If combat is already received its full state then
         * call the method immediately. Otherwise enqueue it */
        method.apply(self, args);
    },

    /*
     * Combat aborted
     */
    abort: function () {
        var self = this;
        window.location = '/location';
    },

    /*
     * Combat state loaded. Apply it to the interface
     */
    applyState: function (state) {
        var self = this;
        self.cleanup();
        state.members.forEach(function (member) {
            self.addMember(member);
        });
    },

    /*
     * Wipe all data
     */
    cleanup: function () {
        var self = this;
        self.members = [];
    },

    /*
     * Add a member to the combat
     */
    addMember: function (member) {
        var self = this;
        self.members.push(member);
    },

    /*
     * Called when listed combat parameters changed
     * Format: map(key => value)
     */
    combatParamsChanged: function (params) {
        var self = this;
    },

    /*
     * Called when listed member parameters changed
     * Format: map(key => value)
     */
    memberParamsChanged: function (member_id, params) {
        var self = this;
        console.log(member_id, params);
    }
});
