var LocObjectsManager, LocObjects, LocObject;
var LocCanvas = {};
var is_chrome = window.chrome;

function createImage()
{
    if (is_chrome) {
        return document.createElement('image');
    } else {
        return new Image();
    }
}

LocCanvas.resize = function () {
    var w = Loc.window_w - Loc.margin_x;
    var h = Loc.window_h - Loc.margin_y;
    if (!Loc.stretching) {
        return;
    }
    var el = document.getElementById('location-canvas');
    if (!el) {
        return;
    }
    if (w < 10) {
        w = 10;
    }
    if (h < 10) {
        h = 10;
    }
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

wait(['location', 'objects', 'hints'], function () {
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
            if (!self.canvas) {
                return;
            }
            if (!LocCanvas.width) {
                LocCanvas.width = self.canvas.width;
                LocCanvas.height = self.canvas.height;
                LocCanvas.scale = 1.0;
            }
            self.canvasEl = Ext.get(self.canvas);
            try { G_vmlCanvasManager.initElement(canvas); } catch (e) {}
            self.ctx = self.canvas.getContext('2d');
            self.paintDelay = 0;
            self.tipOffsetX = 10;
            self.tipOffsetY = 15;
            self.canvasEl.addListener('mousedown', function (ev) {
                self.onMouseEvent('onMouseDown', ev);
            });
            self.canvasEl.addListener('mouseup', function (ev) {
                self.onMouseEvent('onMouseUp', ev);
            });
            self.canvasEl.addListener('mousemove', function (ev) {
                self.onMouseEvent('onMouseMove', ev);
            });
            self.canvasEl.addListener('mouseout', function (ev) {
                self.onMouseEvent('onMouseOut', ev);
            });
            self.canvasEl.addListener('contextmenu', function (ev) {
                self.onMouseEvent('onContextMenu', ev);
            });
        },

        /*
         * Handle mouse event
         */
        onMouseEvent: function (handlerName, ev) {
            var self = this;
            ev.stopEvent();
            if (self.requestSort) {
                self.sortObjects();
            }
            var coo = ev.getXY();
            var elCoo = self.canvasEl.getXY();
            self[handlerName].call(self, ev,
                    (coo[0] - elCoo[0]) / LocCanvas.scale,
                    (coo[1] - elCoo[1]) / LocCanvas.scale);
        },

        /*
         * Sort objects based on their Y coordinate (actually z-index)
         */
        sortObjects: function () {
            var self = this;
            self.requestSort = false;
            self.objects.sort(function (a, b) {
                if (!a.position || !b.position) {
                    return 0;
                }
                if (a.position.y < b.position.y) {
                    return -1;
                }
                if (a.position.y > b.position.y) {
                    return 1;
                }
                return 0;
            });
        },

        /*
         * Set background image
         */
        setBackgroundImage: function (uri) {
            var self = this;
            var img = createImage();
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
            if (self.requestSort) {
                self.sortObjects();
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
        },

        /*
         * Find object with given point inside its active zone
         */
        findObj: function (x, y) {
            var self = this;
            for (var i = self.objects.length - 1; i >= 0; i--) {
                var obj = self.objects[i];
                if (obj.visible && obj.visible > 0 && obj.hasPoint(x, y)) {
                    return obj;
                }
            }
            return undefined;
        },

        /*
         * Handle mouse move event
         */
        onMouseMove: function (ev, x, y) {
            var self = this;
            var obj = self.findObj(x, y);
            if (obj) {
                self.canvas.style.cursor = 'pointer';
            } else {
                self.canvas.style.cursor = 'default';
            }
            if (obj && !obj.hint) {
                obj = undefined;
            }
            if (self.tipObject && self.tipObject !== obj) {
                self.tipObject = undefined;
                self.tipElement.destroy();
                self.tipElement = undefined;
            }
            if (!obj) {
                return;
            }
            var xy = ev.getXY();
            if (obj && obj !== self.tipObject) {
                self.tipObject = obj;
                self.tipElement = new Ext.Tip({
                    html: obj.hint
                });
                self.tipElement.showAt([0, 0]);
            }
            if (self.tipElement) {
                self.tipElement.setPagePosition(xy[0] + self.tipOffsetX, xy[1] + self.tipOffsetY);
            }
        },

        /*
         * Handle mouse out event
         */
        onMouseOut: function (ev) {
            var self = this;
        },

        /*
         * Handle context menu event
         */
        onContextMenu: function (ev) {
            var self = this;
        },

        /*
         * Handle mouse down event
         */
        onMouseDown: function (ev, x, y) {
            var self = this;
            if (ev.button !== 0) {
                return;
            }
            var obj = self.findObj(x, y);
            if (!obj) {
                return;
            }
            if (obj.click.action === 'move') {
                Locations.move(obj.click.loc);
            } else if (obj.click.action === 'event') {
                Game.qevent(obj.click.ev);
            } else if (obj.click.action === 'globfunc') {
                Game.main_open('/globfunc/' + obj.click.globfunc);
            } else if (obj.click.action === 'specfunc') {
                Game.main_open('/location/' + obj.click.specfunc);
            } else if (obj.click.action === 'open') {
                Game.main_open(obj.click.url);
            }
        },

        /*
         * Handle mouse up event
         */
        onMouseUp: function (ev) {
            var self = this;
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
            self.addParam(new LocObjectPosition(self, 1, new DynamicValue(info.position)));
            self.addParam(new LocObjectVisibility(self, 2, new DynamicValue(info.visible)));
            /* Hint */
            if (info.hint) {
                self.hint = info.hint;
            } else if (info.click.loc) {
                self.hint = Hints.getTransition(info.click.loc);
            }
            /* Click handler */
            self.click = info.click;
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
                var img = createImage();
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
            if (!self.image || !self.position || self.position.x === undefined ||
                    self.position.y === undefined || self.position.z === undefined) {
                return;
            }
            if (!self.visible || self.visible <= 0) {
                return;
            }
            self.manager.touchPoint(
                    (self.position.x - self.imageWidth / 2) * LocCanvas.scale,
                    (self.position.z - self.imageHeight / 2) * LocCanvas.scale);
            self.manager.touchPoint(
                    (self.position.x + self.imageWidth / 2) * LocCanvas.scale,
                    (self.position.z + self.imageHeight / 2) * LocCanvas.scale);
        },

        /*
         * Draw object on the canvas context
         */
        paint: function (ctx) {
            var self = this;
            if (self.image && self.visible && self.visible > 0) {
                if (self.visible < 1) {
                    var alpha = ctx.globalAlpha;
                    ctx.globalAlpha = self.visible;
                }
                ctx.drawImage(self.image,
                        (self.position.x - self.imageWidth / 2) * LocCanvas.scale,
                        (self.position.z - self.imageHeight / 2) * LocCanvas.scale,
                        self.imageWidth * LocCanvas.scale,
                        self.imageHeight * LocCanvas.scale);
                if (self.visible < 1) {
                    ctx.globalAlpha = alpha;
                }
            }
        },

        /*
         * Check whether given point is inside the active zone
         */
        hasPoint: function (x, y) {
            var self = this;
            if (!self.position) {
                return false;
            }
            x -= self.position.x;
            y -= self.position.z;
            var poly = self.polygon;
            for (var c = false, i = -1, l = poly.length, j = l - 1; ++i < l; j = i) {
                ((poly[i].y <= y && y < poly[j].y) || (poly[j].y <= y && y < poly[i].y))
                && (x < (poly[j].x - poly[i].x) * (y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)
                && (c = !c);
            }
            return c;
        }
    });

    /*
     * Parameter altering position of the object
     */
    LocObjectPosition = Ext.extend(GenericObjectParam, {
        applyValue: function (val) {
            var self = this;
            var oldPos = self.obj.position;
            self.obj.touch();
            self.obj.position = val;
            self.obj.touch();
            if (val && (!oldPos || val.y != oldPos.y)) {
                self.obj.manager.requestSort = true;
            }
            self.obj.manager.eventualPaint();
        }
    });

    /*
     * Parameter altering visibility of the object
     */
    LocObjectVisibility = Ext.extend(GenericObjectParam, {
        applyValue: function (val) {
            var self = this;
            self.obj.touch();
            self.obj.visible = val;
            self.obj.touch();
            self.obj.manager.eventualPaint();
        }
    });

    LocObjects = new LocObjectsManager();
    loaded('loccanvas');
});
