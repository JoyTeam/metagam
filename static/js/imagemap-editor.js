ImageMapZone = function(id) {
	this.id = id;
	this.poly = new Array();
};

ImageMapZone.prototype.render = function(form) {
	this.form = form;
	var enforce_conditions = form.enforce_conditions.createDelegate(form);
	this.cmp = form.form_cmp.add({
		title: gt.gettext('Zone') + ' ' + this.id,
		collapsible: true,
		collapsed: true,
		layout: 'form',
		autoHeight: true,
		bodyStyle: 'padding: 10px',
		style: 'margin: 0 0 10px 0',
		items: {
			border: false,
			autoHeight: true,
			defaults: {
				layout: 'form',
				labelAlign: 'top',
				autoHeight: true,
				border: false
			},
			items: [
				{
					id: 'elem_polygon-' + this.id,
					items: { 
						id: 'form-field-polygon-' + this.id,
						fieldLabel: gt.gettext('Polygon vertices'),
						name: 'polygon-' + this.id,
						value: this.getPolygonStr(),
						xtype: 'textfield',
						allowBlank: true,
						msgTarget: 'side',
						anchor: '-30',
						autoHeight: true
					},
				},
				{
					id: 'elem_hint-' + this.id,
					items: {
						id: 'form-field-hint-' + this.id,
						fieldLabel: gt.gettext('Mouse over hint'),
						name: 'hint-' + this.id,
						value: this.hint,
						xtype: 'textfield',
						allowBlank: true,
						msgTarget: 'side',
						anchor: '-30',
						autoHeight: true
					}
				},
				{
					id: 'elem_action-' + this.id,
					items: {
						id: 'form-field-action-' + this.id,
						fieldLabel: gt.gettext('Click action'),
						name: 'action-' + this.id,
						value: this.action,
						xtype: 'combo',
						allowBlank: true,
						msgTarget: 'side',
						anchor: '-30',
						autoHeight: true,
						store: ImageMapEditor.actions,
						forceSelection: true,
						triggerAction: 'all',
						hiddenName: 'v_action-' + this.id,
						hiddenValue: this.action,
						value: this.action,
						listWidth: 600,
						listeners: {
							select: enforce_conditions,
							change: enforce_conditions
						}
					}
				},
				{
					id: 'elem_location-' + this.id,
					items: {
						id: 'form-field-location-' + this.id,
						fieldLabel: gt.gettext('Target location'),
						name: 'location-' + this.id,
						value: this.action,
						xtype: 'combo',
						allowBlank: true,
						msgTarget: 'side',
						anchor: '-30',
						autoHeight: true,
						store: ImageMapEditor.locations,
						forceSelection: true,
						triggerAction: 'all',
						hiddenName: 'v_location-' + this.id,
						hiddenValue: this.loc,
						value: this.loc,
						listWidth: 600,
						listeners: {
							select: enforce_conditions,
							change: enforce_conditions
						}
					}
				}
			]
		}
	});
	this.form.conditions.push({
		id: 'elem_location-' + this.id,
		condition: "form_value('action-" + this.id + "')=='move'"
	});
};

ImageMapZone.prototype.activate = function() {
	this.cmp.addClass('im');
	this.cmp.expand(false);
};

ImageMapZone.prototype.deactivate = function() {
	this.cmp.removeClass('im');
	this.cmp.collapse(false);
};

ImageMapZone.prototype.cleanup = function() {
	this.uninstall_global_events();
	this.form.form_cmp.remove(this.cmp);
	for (var ci = this.form.conditions.length - 1; ci >= 0; ci--) {
		if (this.form.conditions[ci].id == 'elem_location-' + this.id) {
			this.form.conditions.splice(ci, 1);
			break;
		}
	}
};

ImageMapZone.prototype.getPolygonStr = function() {
	var tokens = new Array();
	for (var i = 0; i < this.poly.length - 1; i++) {
		var pt = this.poly[i];
		tokens.push(pt.x + ',' + pt.y);
	}
	/* last point is copy of the first. so in normal closed polygon it is not necessary to show it */
	if (this.open && this.poly.length > 0) {
		var pt = this.poly[this.poly.length - 1];
		tokens.push(pt.x + ',' + pt.y);
	}
	return tokens.join(',');
};

ImageMapZone.prototype.setPolygonStr = function(str) {
	var tokens = str.split(',');
	if (tokens.length % 2) {
		Game.error(gt.gettext('Number of corrdinates must not be odd'))
		return;
	}
	if (tokens.length < 6) {
		Game.error(gt.gettext('Minimal number of vertices - 3'))
		return;
	}
	for (var i = 0; i < tokens.length; i++) {
		var token = tokens[i];
		if (!token.match(/^-?[0-9]+$/)) {
			Game.error(gt.gettext('Invalid non-integer coordinate encountered'));
			return;
		}
	}
	this.poly = new Array();
	for (var i = 0; i < tokens.length; i += 2) {
		this.poly.push({x: parseInt(tokens[i]), y: parseInt(tokens[i + 1])});
	}
	this.poly.push(this.poly[0]);
};

ImageMapZone.prototype.update_polygon_str = function() {
	Ext.get('form-field-polygon-' + this.id).dom.value = this.getPolygonStr();
};

ImageMapEditor = {};

ImageMapEditor.cleanup = function() {
	this.zones = new Array();
	this.mouse = new Array();
	this.handler_size = 8;
	this.active_zone = undefined;
	this.mode = undefined;
	this.active_handler = undefined;
	this.highlighted_handler = undefined;
	this.highlighted_segment = undefined;
	this.highlighted_zone = undefined;
	this.drag_handler = undefined;
	this.drag_zone = undefined;
	this.clip_x1 = undefined;
	this.clip_x2 = undefined;
	this.clip_y1 = undefined;
	this.clip_y2 = undefined;
	this.zone_id = 0;
	this.actions = new Array();
	this.locations = new Array();
};

ImageMapEditor.init = function(submit_url, width, height) {
	this.cleanup();
	this.width = width;
	this.height = height;
	/* creating canvas */
	var canvas = document.createElement('canvas');
	canvas.id = 'imagemap-canvas';
	canvas.width = width;
	canvas.height = height;
	try {
		G_vmlCanvasManager.initElement(canvas);
		Ext.getDom('imagemap-ie-warning').style.display = 'block';
	} catch (e) {}
	Ext.getDom('imagemap-div').appendChild(canvas);
	this.ctx = canvas.getContext('2d');
	this.canvas = Ext.get(canvas);
	/* creating form */
	this.form = new Form({
		url: submit_url,
		fields: [],
		buttons: [{text: gt.gettext('Save')}]
	});
};

ImageMapEditor.run = function() {
	this.paint(true);
	this.form.enforce_conditions(true);
	this.form.render('imagemap-form');
	this.canvas.on('mousedown', this.mouse_down, this);
	this.canvas.on('mousemove', this.mouse_move, this);
	this.canvas.on('mouseup', this.mouse_up, this);
	this.canvas.on('contextmenu', this.context_menu, this);
	Ext.get('admin-viewport').on('keydown', this.key_down, this);
};

ImageMapEditor.point_in_poly = function(pt, poly) {
	for (var c = false, i = -1, l = poly.length, j = l - 1; ++i < l; j = i) {
		((poly[i].y <= pt.y && pt.y < poly[j].y) || (poly[j].y <= pt.y && pt.y < poly[i].y))
		&& (pt.x < (poly[j].x - poly[i].x) * (pt.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)
		&& (c = !c);
	}
	if (c) {
		return true;
	}
	for (var i = 0; i < poly.length; i++) {
		var vx = poly[i].x - pt.x;
		var vy = poly[i].y - pt.y;
		if (vx * vx + vy * vy < this.handler_size * this.handler_size)
			return true;
	}
	return false;
};

ImageMapEditor.paint_handler = function(pt) {
	this.ctx.save();
	if (this.active_handler == pt && this.highlighted_handler == pt) {
		this.ctx.fillStyle = '#ff8080';
		this.ctx.strokeStyle = '#804040';
	} else if (this.active_handler == pt) {
		this.ctx.fillStyle = '#ffc0c0';
		this.ctx.strokeStyle = '#804040';
	} else if (this.highlighted_handler == pt) {
		this.ctx.fillStyle = '#ffffff';
		this.ctx.strokeStyle = '#000000';
	} else {
		this.ctx.fillStyle = '#808080';
		this.ctx.strokeStyle = '#404040';
	}
	this.ctx.fillRect(pt.x + 0.5 - this.handler_size / 2, pt.y + 0.5 - this.handler_size / 2, this.handler_size, this.handler_size);
	this.ctx.strokeRect(pt.x + 0.5 - this.handler_size / 2, pt.y + 0.5 - this.handler_size / 2, this.handler_size, this.handler_size);
	this.ctx.restore();
};

ImageMapEditor.paint_segment = function(pt1, pt2) {
	this.ctx.save();
	this.ctx.beginPath();
	this.ctx.moveTo(pt1.x + 0.5, pt1.y + 0.5);
	this.ctx.lineTo(pt2.x + 0.5, pt2.y + 0.5);
	this.ctx.strokeStyle = '#c0c0c0';
	this.ctx.lineWidth = 2;
	this.ctx.stroke();
	this.ctx.restore();
};

ImageMapEditor.update_highlighted = function() {
	if (this.drag_handler || this.drag_zone)
		return false;
	var old_highlighted_zone = this.highlighted_zone;
	var old_highlighted_handler = this.highlighted_handler;
	var old_highlighted_segment = this.highlighted_segment;
	this.highlighted_handler = undefined;
	this.highlighted_segment = undefined;
	this.highlighted_zone = undefined;
	if (this.active_zone) {
		var best_dist = undefined;
		for (var j = 0; j < this.active_zone.poly.length - 1; j++) {
			var pt = this.active_zone.poly[j];
			var pv = {x: pt.x - this.mouse.x, y: pt.y - this.mouse.y};
			var dist = Math.sqrt(pv.x * pv.x + pv.y * pv.y);
			if (dist < this.handler_size * 2) {
				if (best_dist == undefined || dist < best_dist) {
					best_dist = dist;
					this.highlighted_handler = pt;
					this.highlighted_zone = this.active_zone;
				}
			}
		}
		if (!this.active_zone.open) {
			for (var j = 0; j < this.active_zone.poly.length - 1; j++) {
				var pt1 = this.active_zone.poly[j];
				var pt2 = this.active_zone.poly[j + 1];
				if (this.mouse.x >= pt1.x && this.mouse.x <= pt2.x || this.mouse.x <= pt1.x && this.mouse.x >= pt2.x) {
					if (this.mouse.y >= pt1.y && this.mouse.y <= pt2.y || this.mouse.y <= pt1.y && this.mouse.y >= pt2.y) {
						/* distance from segment (pt1, pt2) to the mouse cursor */
						var v12 = {x: pt2.x - pt1.x, y: pt2.y - pt1.y};
						var l12 = Math.sqrt(v12.x * v12.x + v12.y * v12.y);
						if (l12 < 1) l12 = 1;
						var u12 = {x: v12.x / l12, y: v12.y / l12};
						var n12 = {x: -u12.y, y: u12.x};
						var vm = {x: this.mouse.x - pt1.x, y: this.mouse.y - pt1.y};
						var dist = Math.abs(vm.x * n12.x + vm.y * n12.y) + this.handler_size;
						if (dist < this.handler_size * 3) {
							if (best_dist == undefined || dist < best_dist) {
								best_dist = dist;
								this.highlighted_segment = j;
								this.highlighted_handler = undefined;
								this.highlighted_zone = this.active_zone;
							}
						}
					}
				}
			}
		}
	}
	if (!this.highlighted_zone) {
		for (var i = 0; i < this.zones.length; i++) {
			if (this.point_in_poly(this.mouse, this.zones[i].poly)) {
				this.highlighted_zone = this.zones[i];
				break;
			}
		}
	}
	var modified = false;
	if (this.highlighted_handler != old_highlighted_handler) {
		this.touch_active_zone();
		modified = true;
	}
	if (this.highlighted_segment != old_highlighted_segment) {
		this.touch_active_zone();
		modified = true;
	}
	if (this.highlighted_zone != old_highlighted_zone) {
		this.touch_zone(this.highlighted_zone);
		this.touch_zone(old_highlighted_zone);
		modified = true;
	}
	return modified;
};

ImageMapEditor.paint = function(force) {
	if (this.clip_x1 == undefined && !force)
		return;
	this.ctx.save();
	var clipping = true;
	try {
		if (G_vmlCanvasManager) {
			clipping = false;
		}
	} catch (e) {
	}
	if (clipping && !force) {
		this.ctx.beginPath();
		this.ctx.rect(this.clip_x1, this.clip_y1, this.clip_x2 - this.clip_x1 + 1, this.clip_y2 - this.clip_y1 + 1);
		this.ctx.clip();
	}
	this.ctx.clearRect(0, 0, this.width, this.height);
	for (var i = 0; i < this.zones.length; i++) {
		var zone = this.zones[i];
		this.ctx.save();
		this.ctx.beginPath();
		this.ctx.moveTo(zone.poly[0].x, zone.poly[0].y);
		for (var j = 1; j < zone.poly.length; j++) {
			this.ctx.lineTo(zone.poly[j].x + 0.5, zone.poly[j].y + 0.5);
		}
		if (!zone.open) {
			if (this.highlighted_zone == zone && this.active_zone == zone) {
				this.ctx.fillStyle = '#ff8080';
			} else if (this.active_zone == zone) {
				this.ctx.fillStyle = '#ffc0c0';
			} else if (this.highlighted_zone == zone) {
				this.ctx.fillStyle = '#ffffff';
			} else {
				this.ctx.fillStyle = '#c0c0c0';
			}
			this.ctx.globalAlpha = 0.3;
			this.ctx.lineTo(zone.poly[0].x + 0.5, zone.poly[0].y + 0.5);
			this.ctx.closePath();
			this.ctx.fill();
		}
		this.ctx.globalAlpha = 1;
		if (this.highlighted_zone == zone) {
			this.ctx.strokeStyle = '#000000';
		} else {
			this.ctx.strokeStyle = '#404040';
		}
		this.ctx.stroke();
		this.ctx.restore();
		/* handlers */
		if (zone == this.active_zone) {
			if (this.highlighted_segment != undefined) {
				this.paint_segment(zone.poly[this.highlighted_segment], zone.poly[this.highlighted_segment + 1]);
			}
			if (zone.open) {
				this.paint_handler(zone.poly[0]);
			} else {
				for (var j = 0; j < zone.poly.length - 1; j++) {
					this.paint_handler(zone.poly[j]);
				}
			}
		}
	}
	this.ctx.restore();
	this.clip_x1 = undefined;
	this.clip_y1 = undefined;
	this.clip_x2 = undefined;
	this.clip_y2 = undefined;
};

ImageMapEditor.new_zone = function() {
	var zone = new ImageMapZone(++this.zone_id);
	this.zones.push(zone);
	return zone;
};

ImageMapEditor.mouse_down = function(ev, target) {
	ev.stopEvent();
	var page_coo = ev.getXY();
	var pt = {
		x: page_coo[0] - this.canvas.getLeft(),
		y: page_coo[1] - this.canvas.getTop()
	};
	this.mouse = pt;
	var repaint = false;
	if (this.update_highlighted()) {
		repaint = true;
	}
	if (ev.button == 0) {
		if (this.mode == 'new-zone') {
			var last_pt = this.active_zone.poly[this.active_zone.poly.length - 1];
			if (this.highlighted_handler) {
				/* closing polygon */
				if (this.active_zone.poly.length >= 4) {
					this.active_zone.poly[this.active_zone.poly.length - 1] = this.active_zone.poly[0];
					this.active_zone.open = false;
					this.mode = undefined;
					repaint = true;
					this.touch_active_zone();
					this.active_zone.update_polygon_str();
				}
			} else {
				/* adding new point to the polygon */
				last_pt.x = pt.x;
				last_pt.y = pt.y;
				this.active_zone.poly.push(pt);
				this.touch_active_zone();
				repaint = true;
				this.active_zone.update_polygon_str();
			}
		} else if (this.highlighted_handler) {
			/* activating handler */
			this.active_handler = this.highlighted_handler;
			this.drag_handler = {
				start_x: this.active_handler.x, start_y: this.active_handler.y,
				mouse_start_x: this.mouse.x, mouse_start_y: this.mouse.y
			};
			this.touch_active_zone();
			repaint = true;
		} else if (this.highlighted_segment != undefined) {
			/* splitting segment into 2 segments */
			this.active_handler = pt;
			this.active_zone.poly.splice(this.highlighted_segment + 1, 0, pt);
			this.drag_handler = {
				start_x: this.active_handler.x, start_y: this.active_handler.y,
				mouse_start_x: this.mouse.x, mouse_start_y: this.mouse.y
			};
			this.highlighted_segment = undefined;
			this.touch_active_zone();
			repaint = true;
		} else if (this.highlighted_zone) {
			this.touch_active_zone();
			if (this.active_zone)
				this.active_zone.deactivate();
			this.active_zone = this.highlighted_zone;
			this.active_zone.activate();
			this.active_handler = undefined;
			this.active_segment = undefined;
			this.drag_zone = {
				offset_x: 0, offset_y: 0,
				mouse_last_x: this.mouse.x, mouse_last_y: this.mouse.y
			};
			this.touch_active_zone();
			repaint = true;
		} else if (this.active_zone) {
			this.touch_active_zone();
			this.active_zone.deactivate();
			this.active_zone = undefined;
			this.active_handler = undefined;
			this.active_segment = undefined;
			repaint = true;
		} else {
			this.active_zone = this.new_zone();
			this.active_zone.render(this.form);
			this.form.enforce_conditions(true);
			this.form.doLayout();
			this.active_zone.activate();
			this.active_zone.open = true;
			this.active_zone.poly.push(pt);
			this.active_zone.poly.push({x: pt.x, y: pt.y})
			this.mode = 'new-zone';
			repaint = true;
			this.touch_active_zone();
		}
	} else if (ev.button == 2) {
		this.cancel();
		repaint = true;
	}
	if (repaint) {
		this.paint();
	}
	if (!this.global_events) {
		Ext.get('admin-viewport').on('mousemove', this.mouse_move, this);
		Ext.get('admin-viewport').on('mouseup', this.mouse_up, this);
		Ext.get('admin-viewport').on('contextmenu', this.context_menu, this);
		this.global_events = true;
	}
};

ImageMapEditor.touch_active_zone = function(poly) {
	this.touch_zone(this.active_zone);
};

ImageMapEditor.touch_zone = function(zone) {
	if (zone)
		this.touch_poly(zone.poly);
};

ImageMapEditor.touch_poly = function(poly) {
	for (var pi = 0; pi < poly.length; pi++) {
		this.touch(poly[pi]);
	}
};

ImageMapEditor.touch = function(pt) {
	if (this.clip_x1 == undefined) {
		this.clip_x1 = pt.x;
		this.clip_x2 = pt.x;
		this.clip_y1 = pt.y;
		this.clip_y2 = pt.y;
	} else {
		if (pt.x - this.handler_size < this.clip_x1)
			this.clip_x1 = pt.x - this.handler_size;
		if (pt.x + this.handler_size > this.clip_x2)
			this.clip_x2 = pt.x + this.handler_size;
		if (pt.y - this.handler_size < this.clip_y1)
			this.clip_y1 = pt.y - this.handler_size;
		if (pt.y + this.handler_size > this.clip_y2)
			this.clip_y2 = pt.y + this.handler_size;
	}
};

ImageMapEditor.cancel = function() {
	if (this.mode == 'new-zone') {
		for (var i = 0; i < this.zones.length; i++) {
			if (this.zones[i] == this.active_zone) {
				this.active_zone.cleanup();
				this.zones.splice(i, 1);
				this.touch_active_zone();
				this.active_zone = undefined;
				this.highlighted_zone = undefined;
				this.highlighted_handler = undefined;
				this.active_handler = undefined;
				this.active_segment = undefined;
				this.highlighted_segment = undefined;
				this.mode = undefined;
			}
		}
	} else if (this.drag_handler) {
		this.touch_active_zone();
		this.active_handler.x = this.drag_handler.start_x;
		this.active_handler.y = this.drag_handler.start_y;
		this.touch_active_zone();
		this.drag_handler = undefined;
		this.active_zone.update_polygon_str();
	} else if (this.drag_zone) {
		this.touch_active_zone();
		for (var i = 0; i < this.active_zone.poly.length - 1; i++) {
			var pt = this.active_zone.poly[i];
			pt.x -= this.drag_zone.offset_x;
			pt.y -= this.drag_zone.offset_y;
		}
		this.touch_active_zone();
		this.drag_zone = undefined;
		this.active_zone.update_polygon_str();
	} else if (this.active_zone) {
		this.touch_active_zone();
		this.active_zone.deactivate();
		this.active_zone = undefined;
		this.active_handler = undefined;
		this.active_segment = undefined;
	}
};

ImageMapEditor.mouse_move = function(ev, target) {
	ev.stopEvent();
	var page_coo = ev.getXY();
	var pt = {
		x: page_coo[0] - this.canvas.getLeft(),
		y: page_coo[1] - this.canvas.getTop()
	};
	this.mouse = pt;
	var repaint = false;
	if (this.update_highlighted()) {
		repaint = true;
	}
	if (this.mode == 'new-zone') {
		this.touch_active_zone();
		var last_pt = this.active_zone.poly[this.active_zone.poly.length - 1];
		last_pt.x = pt.x;
		last_pt.y = pt.y;
		this.touch_active_zone();
		repaint = true;
		this.active_zone.update_polygon_str();
	} else if (this.drag_handler) {
		this.touch_active_zone();
		this.active_handler.x = pt.x - this.drag_handler.mouse_start_x + this.drag_handler.start_x;
		this.active_handler.y = pt.y - this.drag_handler.mouse_start_y + this.drag_handler.start_y;
		this.touch_active_zone();
		repaint = true;
		this.active_zone.update_polygon_str();
	} else if (this.drag_zone) {
		this.touch_active_zone();
		var delta_x = pt.x - this.drag_zone.mouse_last_x;
		var delta_y = pt.y - this.drag_zone.mouse_last_y;
		this.drag_zone.mouse_last_x = pt.x;
		this.drag_zone.mouse_last_y = pt.y;
		this.drag_zone.offset_x += delta_x;
		this.drag_zone.offset_y += delta_y;
		for (var i = 0; i < this.active_zone.poly.length - 1; i++) {
			var pt = this.active_zone.poly[i];
			pt.x += delta_x;
			pt.y += delta_y;
		}
		this.touch_active_zone();
		repaint = true;
		this.active_zone.update_polygon_str();
	}
	if (repaint)
		this.paint();
};

ImageMapEditor.uninstall_global_events = function() {
	if (this.global_events) {
		Ext.get('admin-viewport').un('mousemove', this.mouse_move, this);
		Ext.get('admin-viewport').un('mouseup', this.mouse_up, this);
		Ext.get('admin-viewport').un('contextmenu', this.context_menu, this);
		this.global_events = false;
	}
};

ImageMapEditor.mouse_up = function(ev, target) {
	this.uninstall_global_events();
	ev.stopEvent();
	var page_coo = ev.getXY();
	var pt = {
		x: page_coo[0] - this.canvas.getLeft(),
		y: page_coo[1] - this.canvas.getTop()
	};
	this.mouse = pt;
	var repaint = false;
	if (this.update_highlighted()) {
		repaint = true;
	}
	if (this.drag_handler) {
		this.drag_handler = undefined;
		this.touch_active_zone();
		repaint = true;
	}
	if (this.drag_zone) {
		this.drag_zone = undefined;
		this.touch_active_zone();
		repaint = true;
	}
	if (repaint)
		this.paint();
};

ImageMapEditor.context_menu = function(ev, target) {
	ev.stopEvent();
};

ImageMapEditor.key_down = function(ev, target) {
	if (!this.canvas.dom || this.canvas.dom != Ext.getDom('imagemap-canvas')) {
		// editor closed. uninstalling
		Ext.get('admin-viewport').un('keydown', this.key_down, this);
		this.cleanup();
		return;
	}
	var key = ev.getKey();
	if (key == ev.ESC) {
		ev.stopEvent();
		this.cancel();
		this.paint();
	} else if (key == ev.ENTER) {
		ev.stopEvent();
		this.cancel();
		this.paint();
		this.form.custom_submit(this.form.form_cmp.url);
	} else if (key == ev.DELETE) {
		ev.stopEvent();
		if (this.active_handler && !this.mode) {
			/* removing vertex */
			this.touch_active_zone();
			for (var i = 0; i < this.active_zone.poly.length; i++) {
				if (this.active_zone.poly[i] == this.active_handler) {
					this.active_zone.poly.splice(i, 1);
					if (i == 0) {
						/* first point removed */
						this.active_zone.poly[this.active_zone.poly.length - 1] = this.active_zone.poly[0];
					}
					this.active_handler = this.active_zone.poly[i];
					this.active_zone.update_polygon_str();
					break;
				}
			}
			if (this.active_zone.poly.length < 4) {
				/* removing zone */
				for (var i = 0; i < this.zones.length; i++) {
					if (this.zones[i] == this.active_zone) {
						this.active_zone.cleanup();
						this.zones.splice(i, 1);
						break;
					}
				}
				this.active_zone = undefined;
				this.active_handler = undefined;
				this.active_segment = undefined;
			}
			this.drag_handler = undefined;
			this.update_highlighted();
			this.paint();
		} else if (!this.active_handler && !this.highlighted_handler && this.active_zone) {
			/* removing zone */
			this.touch_active_zone();
			for (var i = 0; i < this.zones.length; i++) {
				if (this.zones[i] == this.active_zone) {
					this.active_zone.cleanup();
					this.zones.splice(i, 1);
					break;
				}
			}
			this.mode = undefined;
			this.active_zone = undefined;
			this.drag_handler = undefined;
			this.active_handler = undefined;
			this.active_segment = undefined;
			this.update_highlighted();
			this.paint();
		}
	}
};

wait(['admin-form'], function() {
	loaded('imagemap-editor');
});
