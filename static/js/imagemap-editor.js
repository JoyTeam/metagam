ImageMapEditor = {
	zones: new Array(),
	mouse: {x: -100, y: -100 },
	handler_size: 8
};

ImageMapEditor.init = function(width, height) {
	this.width = width;
	this.height = height;
	var canvas = document.createElement('canvas');
	canvas.id = 'imagemap_canvas';
	canvas.width = width;
	canvas.height = height;
	try { G_vmlCanvasManager.initElement(canvas); } catch (e) {}
	Ext.getDom('imagemap_div').appendChild(canvas);
	this.ctx = canvas.getContext('2d');
	this.canvas = Ext.get(canvas);
	this.img = Ext.getDom('imagemap_img');
	this.init_image();
};

ImageMapEditor.init_image = function() {
	try {
		this.ctx.drawImage(this.img, 0, 0);
	} catch (e) {
		window.setTimeout(this.init_image.createDelegate(this), 100);
		return;
	}
	this.img.style.display = 'none';
	this.canvas.on('mousedown', this.mouse_down.createDelegate(this));
	this.canvas.on('mousemove', this.mouse_move.createDelegate(this));
	this.canvas.on('mouseup', this.mouse_up.createDelegate(this));
	this.canvas.on('contextmenu', this.context_menu.createDelegate(this));
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
	return this.highlighted_handler != old_highlighted_handler || this.highlighted_segment != old_highlighted_segment || this.highlighted_zone != old_highlighted_zone;
};

ImageMapEditor.paint = function() {
	this.ctx.drawImage(this.img, 0, 0);
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
};

ImageMapEditor.new_zone = function() {
	var zone = {
		poly: new Array()
	};
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
				}
			} else {
				/* adding new point to the polygon */
				last_pt.x = pt.x;
				last_pt.y = pt.y;
				this.active_zone.poly.push(pt);
				repaint = true;
			}
		} else if (this.highlighted_handler) {
			/* activating handler */
			this.active_handler = this.highlighted_handler;
			this.drag_handler = {
				start_x: this.active_handler.x, start_y: this.active_handler.y,
				mouse_start_x: this.mouse.x, mouse_start_y: this.mouse.y
			};
			repaint = true;
		} else if (this.highlighted_segment != undefined) {
			/* splitting segment into 2 segments */
			this.active_handler = pt;
			this.active_zone.poly.splice(this.highlighted_segment + 1, 0, pt);
			this.drag_handler = {
				start_x: this.active_handler.x, start_y: this.active_handler.y,
				mouse_start_x: this.mouse.x, mouse_start_y: this.mouse.y
			};
			repaint = true;
		} else if (this.highlighted_zone) {
			this.active_zone = this.highlighted_zone;
			this.active_handler = undefined;
			this.active_segment = undefined;
			this.drag_zone = {
				offset_x: 0, offset_y: 0,
				mouse_last_x: this.mouse.x, mouse_last_y: this.mouse.y
			};
			repaint = true;
		} else if (this.active_zone) {
			this.active_zone = undefined;
			this.active_handler = undefined;
			this.active_segment = undefined;
			repaint = true;
		} else {
			this.active_zone = this.new_zone();
			this.active_zone.open = true;
			this.active_zone.poly.push(pt);
			this.active_zone.poly.push({x: pt.x, y: pt.y})
			this.mode = 'new-zone';
			repaint = true;
		}
	} else if (ev.button == 2) {
		this.cancel();
		repaint = true;
	}
	if (repaint) {
		this.paint();
	}
};

ImageMapEditor.cancel = function() {
	if (this.mode == 'new-zone') {
		for (var i = 0; i < this.zones.length; i++) {
			if (this.zones[i] == this.active_zone) {
				this.zones.splice(i, 1);
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
		this.active_handler.x = this.drag_handler.start_x;
		this.active_handler.y = this.drag_handler.start_y;
		this.drag_handler = undefined;
	} else if (this.drag_zone) {
		for (var i = 0; i < this.active_zone.poly.length - 1; i++) {
			var pt = this.active_zone.poly[i];
			pt.x -= this.drag_zone.offset_x;
			pt.y -= this.drag_zone.offset_y;
		}
		this.drag_zone = undefined;
	} else if (this.active_zone) {
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
		var last_pt = this.active_zone.poly[this.active_zone.poly.length - 1];
		last_pt.x = pt.x;
		last_pt.y = pt.y;
		repaint = true;
	} else if (this.drag_handler) {
		this.active_handler.x = pt.x - this.drag_handler.mouse_start_x + this.drag_handler.start_x;
		this.active_handler.y = pt.y - this.drag_handler.mouse_start_y + this.drag_handler.start_y;
		repaint = true;
	} else if (this.drag_zone) {
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
		repaint = true;
	}
	if (repaint)
		this.paint();
};

ImageMapEditor.mouse_up = function(ev, target) {
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
		repaint = true;
	}
	if (this.drag_zone) {
		this.drag_zone = undefined;
		repaint = true;
	}
	if (repaint)
		this.paint();
};

ImageMapEditor.context_menu = function(ev, target) {
	ev.stopEvent();
};

ImageMapEditor.key_down = function(ev, target) {
	if (!this.canvas.dom || this.canvas.dom != Ext.getDom('imagemap_canvas')) {
		// editor closed. uninstalling
		Ext.get('admin-viewport').un('keydown', this.key_down, this);
		return;
	}
	var key = ev.getKey();
	if (key == ev.ESC) {
		ev.stopEvent();
		this.cancel();
		this.paint();
	} else if (key == ev.DELETE) {
		ev.stopEvent();
		if (this.active_handler && !this.mode) {
			/* removing vertex */
			for (var i = 0; i < this.active_zone.poly.length; i++) {
				if (this.active_zone.poly[i] == this.active_handler) {
					this.active_zone.poly.splice(i, 1);
					if (i == 0) {
						/* first point removed */
						this.active_zone.poly[this.active_zone.poly.length - 1] = this.active_zone.poly[0];
					}
					this.active_handler = this.active_zone.poly[i];
					break;
				}
			}
			if (this.active_zone.poly.length < 4) {
				/* removing zone */
				for (var i = 0; i < this.zones.length; i++) {
					if (this.zones[i] == this.active_zone) {
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
			for (var i = 0; i < this.zones.length; i++) {
				if (this.zones[i] == this.active_zone) {
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
		} else {
			alert(this.active_handler + ', ' + this.highlighted_handler + ', ' + this.active_zone);
		}
	}
};

loaded('imagemap-editor');
