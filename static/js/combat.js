var Combat = Ext.extend(Object, {
    constructor: function (combatId) {
        var self = this;
        self.id = combatId;
        self.initConstants();
        self.cleanup();
    },

    /*
     * Run combat interface (query current combat state and subscribe to events)
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
        self.submitActionTimeout = 10000;
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
                if (self.consoleLog) {
                    console.log('combat.init');
                }
            }
            return;
        }
        if (self._callsBlocked) {
            return;
        }
        if (self.consoleLog) {
            if (args.length) {
                console.log('combat.' + method, Ext.util.JSON.encode(args));
            } else {
                console.log('combat.' + method);
            }
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
     * Wipe all data
     */
    cleanup: function () {
        var self = this;
        self.members = {};
        self.params = {};
        self.actions = {};
        self.availableActions = [];
    },

    /*
     * Set combat parameter "key" to value "value"
     * Old value is passed in oldValue argument.
     */
    setParam: function (key, value, oldValue) {
    },

    /*
     * Called when combat parameters changed
     * Format: map(key => value)
     */
    combatParamsChanged: function (params) {
        var self = this;
        var oldvals = [];
        for (var key in params) {
            if (params.hasOwnProperty(key)) {
                oldvals[key] = self.params[key];
                self.params[key] = params[key];
            }
        }
        for (var key in params) {
            if (params.hasOwnProperty(key)) {
                self.setParam(key, params[key], oldvals[key]);
            }
        }
    },

    /*
     * Called when a new member joins combat
     * Format: map(key => value)
     */
    memberJoined: function (memberId) {
        var self = this;
        if (!self.members[memberId]) {
            self.members[memberId] = self.newMember(memberId);
        }
    },

    /*
     * Method for creating new members. Usually it's overriden
     * by combat implementations.
     */
    newMember: function (memberId) {
        var self = this;
        return new CombatMember(self, memberId);
    },

    /*
     * Called when listed member parameters changed
     * Format: map(key => value)
     */
    memberParamsChanged: function (memberId, params) {
        var self = this;
        var member = self.members[memberId];
        if (!member) {
            return;
        }
        member.paramsChanged(params);
    },

    /*
     * Called when server notifies client about member
     * controller by this client
     */
    setMyself: function (memberId) {
        var self = this;
        self.myself = self.members[memberId];
    },

    /*
     * Get attribute value from script
     */
    scriptAttr: function (key) {
        var self = this;
        var m = key.match(/^p_([a-zA-Z0-9]+)$/);
        if (m) {
            return self.params[m[1]];
        }
        return undefined;
    },

    /*
     * Called when server sends action description
     * to the client
     */
    actionInfo: function (action) {
        var self = this;
        self.actions[action.code] = action;
    },

    /*
     * Called every time when server notifies client
     * about its controlled member may perform listed
     * actions
     */
    setAvailableActions: function (actions) {
        var self = this;
        self.availableActions = actions;
    },

    /*
     * Called when client gets turn right
     */
    turnGot: function () {
        var self = this;
    },

    /*
     * Called when client loses turn right
     */
    turnLost: function () {
        var self = this;
    },

    /*
     * Called when client times out
     */
    turnTimeout: function () {
    },

    /*
     * Submit action selected by the player to the server.
     * data - structure to be sent to the server
     * callback - is a function reference that will be called with single arg:
     *   null - when the request has been sent successfully
     *   errcode - when an error occurred:
     *     "sendInProgress" - previous request hasn't been completed yet
     *     "combatTerminated" - combat was terminated by some reason
     *     "serverError" - response from server is not valid JSON
     *     "Text error description" - all other values are explicit error messages
     */
    submitAction: function (data, callback) {
        var self = this;
        if (self._submitActionReq) {
            callback('sendInProgress');
            return;
        }
        self._submitActionReq = Ext.Ajax.request({
            url: '/combat/action/' + self.id,
            method: 'POST',
            params: {
                data: Ext.util.JSON.encode(data)
            },
            timeout: self.submitActionTimeout,
            success: function (response, opts) {
                delete self._submitActionReq;
                if (!response || !response.getResponseHeader) {
                    callback('serverError');
                    return;
                }
                if (!response.getResponseHeader("Content-Type").match(/json/)) {
                    callback('serverError');
                    return;
                }
                var res = Ext.util.JSON.decode(response.responseText);
                if (!res) {
                    callback('serverError');
                    return;
                }
                if (res.error) {
                    callback(res.error);
                    return;
                }
                callback(null);
            },
            failure: function (response, opts) {
                delete self._submitActionReq;
                if (response.status == 404 || response.status == 403) {
                    callback('combatTerminated');
                    self.abort();
                } else {
                    callback('serverError');
                }
            }
        });
    },

    /*
     * Called when new log entries arrived from the server
     */
    log: function (entries) {
    }
});

var CombatMember = Ext.extend(Object, {
    constructor: function (combat, memberId) {
        var self = this;
        self.combat = combat;
        self.id = memberId;
        self.params = {};
    },

    /*
     * Set member parameter "key" to value "value".
     * Old value is passed in oldValue argument.
     */
    setParam: function (key, value, oldvalue) {
    },

    /*
     * Called when member parameters changed
     * Format: map(key => value)
     */
    paramsChanged: function (params) {
        var self = this;
        var oldvals = [];
        for (var key in params) {
            if (params.hasOwnProperty(key)) {
                oldvals[key] = self.params[key];
                self.params[key] = params[key];
            }
        }
        for (var key in params) {
            if (params.hasOwnProperty(key)) {
                self.setParam(key, params[key], oldvals[key]);
            }
        }
    },

    /*
     * Get attribute value from script
     */
    scriptAttr: function (key) {
        var self = this;
        if (key == 'id') {
            return self.id;
        }
        return self.params[key];
    }
});
