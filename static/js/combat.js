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
        if (self._queryStateInProgress) {
            return;
        }
        self._queryStateInProgress = true;
        if (self._queryStateReq) {
            Ext.Ajax.abort(self._queryStateReq);
        }
        var failure = function () {
            setTimeout(function () {
                self._queryStateInProgress = false;
                self.queryState();
            }, self.queryStateRetry);
        };
        self._queryStateReq = Ext.Ajax.request({
            url: '/combat/state/' + self.id + self.randSuffix(),
            timeout: self.queryStateTimeout,
            success: function (response, opts) {
                delete self._queryStateReq;
                if (!response || !response.getResponseHeader) {
                    return failure();
                }
                if (!response.getResponseHeader("Content-Type").match(/json/)) {
                    return failure();
                }
                self._queryStateInProgress = false;
                self.applyState(Ext.util.JSON.decode(response.responseText));
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
    }
});
