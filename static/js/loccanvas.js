var LocObjectsManager, LocObjects, LocObject;
var LocCanvas = {};

LocCanvas.resize = function () {
    var w = Loc.window_w - Loc.margin_x;
    var h = Loc.window_h - Loc.margin_y;
    if (!Loc.stretching)
        return;
    var el = document.getElementById('location-canvas');
    if (!el)
        return;
    var iw = Loc.img_width;
    var ih = Loc.img_height;
    // resize to fit width exactly
    ih = ih * w * 1.0 / iw;
    iw = w;
    // check vertical overflow
    if (ih > h) {
        iw = iw * h * 1.0 / ih;
        ih = h;
    }
    // round
    iw = Math.round(iw);
    ih = Math.round(ih);
    // apply
    el.style.width = iw + 'px';
    el.style.height = ih + 'px';
    el.style.visibility = 'visible';
    el.width = iw;
    el.height = ih;
    LocCanvas.width = iw;
    LocCanvas.height = ih;
    LocCanvas.scale = LocCanvas.width * 1.0 / Loc.img_width;
    if (LocObjects) {
        LocObjects.paint(true);
    }
};

wait(['location', 'objects'], function () {
    Loc.resize = LocCanvas.resize;

    /*
     * Collection of objects on the location
     */
    LocObjectsManager = Ext.extend(ObjectsManager, {
        init: function () {
            var self = this;
            LocObjectsManager.superclass.constructor.call(self);
            self.clear();
            self.canvas = document.getElementById('location-canvas');
            try { G_vmlCanvasManager.initElement(canvas); } catch (e) {}
            self.ctx = self.canvas.getContext('2d');
            self.paintDelay = 10;
        },

        /*
         * Set background image
         */
        setBackgroundImage: function (uri) {
            var self = this;
            var img = new Image();
            self.backgroundImageLoading = img;
            img.onload = function () {
                if (self.backgroundImageLoading != img)
                    return;
                self.backgroundImageLoading = undefined;
                self.backgroundImage = img;
                self.paint(true);
            };
            img.src = uri;
        },

        /*
         * Add static location object
         */
        addStaticObject: function (info) {
            var self = this;
            var obj = new LocObject(self, info);
            self.addObject(obj);
        },

        /*
         * Extend clipping area to fit specified point
         */
        touchPoint: function (x, y) {
            var self = this;
            if (self.clip_x1 === undefined) {
                self.clip_x1 = x - 1;
                self.clip_x2 = x + 1;
                self.clip_y1 = y - 1;
                self.clip_y2 = y + 1;
            } else {
                if (x - 1 < self.clip_x1) {
                    self.clip_x1 = x - 1;
                }
                if (y - 1 < self.clip_y1) {
                    self.clip_y1 = y - 1;
                }
                if (x + 1 > self.clip_x2) {
                    self.clip_x2 = x + 1;
                }
                if (y + 1 > self.clip_y2) {
                    self.clip_y2 = y + 1;
                }
            }
        },

        /*
         * Paint all objects
         */
        paint: function (force) {
            var self = this;
            self.paintPlanned = false;
            if (self.clip_x1 === undefined && !force) {
                return;
            }
            self.ctx.save();
            /* Setup clipping */
            var clipping;
            if (force) {
                clipping = false;
            } else {
                clipping = true;
                try {
                    if (G_vmlCanvasManager) {
                        clipping = false;
                    }
                } catch (e) {
                }
            }
            if (clipping) {
                self.ctx.beginPath();
                self.ctx.rect(self.clip_x1, self.clip_y1,
                        self.clip_x2 - self.clip_x1 + 1,
                        self.clip_y2 - self.clip_y1 + 1);
                self.ctx.clip();
            }
            /* Draw background */
            if (self.backgroundImage) {
                self.ctx.drawImage(self.backgroundImage, 0, 0, LocCanvas.width, LocCanvas.height);
            }
            /* Draw objects */
            for (var i = 0; i < self.objects.length; i++) {
                self.objects[i].paint(self.ctx);
            }
            /* Restore everything and reset clipping rectangle */
            self.ctx.restore();
            self.clip_x1 = undefined;
            self.clip_y1 = undefined;
            self.clip_x2 = undefined;
            self.clip_y2 = undefined;
        },

        /* Paint at the next convenient time */
        eventualPaint: function () {
            var self = this;
            if (self.paintPlanned) {
                return;
            }
            self.paintPlanned = true;
            setTimeout(function () {
                self.paint();
            }, self.paintDelay);
        },

        /*
         * Run timer to update objects
         */
        run: function () {
            var self = this;
            LocObjectsManager.superclass.run.call(self);
            self.paint(true);
        }
    });

    /*
     * Object that can be placed on the location
     */
    LocObject = Ext.extend(GenericObject, {
        /*
         * Create an object. info is a dictionary with object description
         */
        constructor: function (manager, info) {
            var self = this;
            LocObject.superclass.constructor.call(self, manager, info.id);
            /* Object position */
            self.addParam(new LocObjectPosition(self, 1, info.position));
            /* Object active zone polygon */
            var poly = info.polygon.split(',');
            self.polygon = [];
            for (var i = 0; i < poly.length; i += 2) {
                var x = parseInt(poly[i]);
                var y = parseInt(poly[i + 1]);
                self.polygon.push({
                    x: x,
                    y: y
                });
            }
            /* Object image */
            if (info.image) {
                self.imageWidth = info.width;
                self.imageHeight = info.height;
                var img = new Image();
                img.onload = function () {
                    self.image = img;
                    self.touch();
                    self.manager.eventualPaint();
                };
                img.src = info.image;
            }
        },

        touch: function () {
            var self = this;
            if (!self.image || !self.position || self.position[0] === undefined ||
                    self.position[1] === undefined || self.position[2] === undefined) {
                return;
            }
            self.manager.touchPoint(
                    (self.position[0] - self.imageWidth / 2) * LocCanvas.scale,
                    (self.position[2] - self.imageHeight / 2) * LocCanvas.scale);
            self.manager.touchPoint(
                    (self.position[0] + self.imageWidth / 2) * LocCanvas.scale,
                    (self.position[2] + self.imageHeight / 2) * LocCanvas.scale);
        },

        /*
         * Draw object on the canvas context
         */
        paint: function (ctx) {
            var self = this;
            if (self.image) {
                ctx.drawImage(self.image,
                        (self.position[0] - self.imageWidth / 2) * LocCanvas.scale,
                        (self.position[2] - self.imageHeight / 2) * LocCanvas.scale,
                        self.imageWidth * LocCanvas.scale,
                        self.imageHeight * LocCanvas.scale);
            }
        }
    });

    /*
     * Parameter altering position of the object
     */
    LocObjectPosition = Ext.extend(GenericObjectParam, {
        applyValue: function (val) {
            var self = this;
            self.obj.touch();
            self.obj.position = val;
            self.obj.touch();
        }
    });
    LocObjects = new LocObjectsManager();
    loaded('loccanvas');
});
