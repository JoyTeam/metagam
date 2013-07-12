/*
 * Objects Manager
 */
var ObjectsManager = Ext.extend(Object, {
    constructor: function () {
        var self = this;
        self.timerInterval = 10;
        self.clear();
    },

    /*
     * Remove all objects and reinitialize
     */
    clear: function () {
        var self = this;
        self.markNeedUpdate();
        self.objects = [];
        self.objectsById = {};
    },

    /*
     * Get current time in milliseconds
     */
    getTime: function () {
        return TimeSync.getTime();
    },

    /*
     * Register new object
     */
    addObject: function (obj) {
        var self = this;
        self.markNeedUpdate();
        self.objects.push(obj);
        self.objectsById[obj.id] = obj;
    },

    /*
     * Destroy object by id
     */
    destroyObject: function (objId) {
        var self = this;
        self.markNeedUpdate();
        delete self.objectsById[obj.id];
        for (var i = 0; i < self.objects.length; i++) {
            var obj = self.objects[i];
            if (obj.id == objId) {
                self.objects.splice(i, 1);
                obj.destroy();
                break;
            }
        }
    },

    /*
     * Get object by its identifier
     */
    getObject: function (id) {
        var self = this;
        return self.objectsById[id];
    },

    /*
     * Run timer to update objects
     */
    run: function () {
        var self = this;
        if (self.running) {
            return;
        }
        self.running = true;
        self.timerTick();
    },

    /*
     * Process timer event
     */
    timerTick: function () {
        var self = this;
        try {
            var now = self.getTime();
            self.update(now);
        } catch (e) {
            try { Game.error(gt.gettext('Exception'), e); } catch (e2) {}
        }
        setTimeout(function () {
            self.timerTick();
        }, self.timerInterval);
    },

    /*
     * Update all objects
     */
    update: function (now) {
        var self = this;
        if (!self.needUpdate) {
            return;
        }
        self.needUpdate = false;
        for (var i = 0; i < self.objects.length; i++) {
            var obj = self.objects[i];
            obj.update(now);
            if (obj.needUpdate) {
                self.needUpdate = true;
            }
        }
    },

    /*
     * If something changed in the object manager, and it needs update
     */
    markNeedUpdate: function () {
        var self = this;
        self.needUpdate = true;
    }
});

/*
 * Generic Object
 */
var GenericObject = Ext.extend(Object, {
    constructor: function (manager, id) {
        var self = this;
        self.manager = manager;
        self.id = id;
        self.params = [];
        self.paramsById = {};
        self.needUpdate = true;
    },

    /*
     * Register new parameter for the object
     */
    addParam: function (param) {
        var self = this;
        self.params.push(param);
        self.paramsById[param.id] = param
    },

    /*
     * Get a parameter by its id
     */
    getParam: function (id) {
        var self = this;
        return self.paramsById[id];
    },

    /*
     * Update object
     */
    update: function (now) {
        var self = this;
        if (!self.needUpdate) {
            return;
        }
        self.needUpdate = false;
        for (var i = 0; i < self.params.length; i++) {
            var param = self.params[i];
            param.update(now);
            if (param.needUpdate) {
                self.needUpdate = true;
            }
        }
    },

    /*
     * Destroy object
     */
    destroy: function () {
        var self = this;
        self.markNeedUpdate();
    },

    /*
     * If something changed in the object, and it needs update
     */
    markNeedUpdate: function () {
        var self = this;
        self.needUpdate = true;
        self.manager.markNeedUpdate();
    }
});

function deepEquals(a, b)
{
    if (typeof(a) != typeof(b)) {
        return false;
    }

    if (typeof(a) == 'object') {
        if (a === b) {
            return true;
        }
        if (a.constructor !== b.constructor) {
            return false;
        }
        for (var p in a) {
            if (!b.hasOwnProperty(p)) {
                return false;
            }
            if (!deepEquals(a[p], b[p])) {
                return false;
            }
        }
        for (var p in b) {
            if (!a.hasOwnProperty(p)) {
                return false;
            }
        }
        return true;
    } else {
        return (a === b) ? true : false;
    }
}

/*
 * Generic Object Parameter
 */
var GenericObjectParam = Ext.extend(Object, {
    constructor: function (obj, id, value) {
        var self = this;
        self.obj = obj;
        self.id = id;
        self.value = value;
        self.needUpdate = true;
    },

    /*
     * Update object parameter
     */
    update: function (now) {
        var self = this;
        if (!self.needUpdate) {
            return;
        }
        self.needUpdate = false;
        var val;
        if (self.value instanceof DynamicValue) {
            val = self.value.evaluateAndForget(now);
            if (self.value.dynamic) {
                self.needUpdate = true;
            }
        } else {
            val = self.value;
        }
        if (!deepEquals(val, self.oldVal)) {
            self.oldVal = val;
            self.applyValue(val);
        }
    },

    /*
     * Set value (DynamicValue is possible)
     */
    setValue: function (val) {
        var self = this;
        self.value = val;
        self.markNeedUpdate();
    },

    /*
    * Apply parameter value
    */
    applyValue: function (val) {
    },

    /*
     * If something changed in the parameter, and it needs update
     */
    markNeedUpdate: function () {
        var self = this;
        self.needUpdate = true;
        self.obj.markNeedUpdate();
    },

    /*
     * Smoothly slide from current value to target one
     * in specified number of seconds.
     */
    slideTo: function (toValue, time) {
        var self = this;
        if (!time || time <= 0) {
            return self.setValue(toValue);
        }
        var now = self.obj.manager.getTime();
        var fromValue;
        if (self.value instanceof DynamicValue) {
            fromValue = self.value.evaluate(now);
        } else {
            fromValue = self.value;
        }
        var val = new DynamicValue([
            '+',
            fromValue,
            [
                '*',
                [
                    '/',
                    [
                        '-',
                        ['glob', 't'],
                        now
                    ],
                    time
                ],
                MMOScript.evaluate(['-', toValue, fromValue], {})
            ]
        ]);
        val.setTill(now + time);
        self.setValue(val);
    }
});

loaded('objects');
