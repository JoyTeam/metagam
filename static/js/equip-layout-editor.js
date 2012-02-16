EquipLayoutItem = function(x, y, width, height) {
	this.x = x;
	this.y = y;
	this.width = width;
	this.height = height;
};

EquipLayoutItem.prototype.has = function(pt) {
	return pt.x >= this.x && pt.x <= this.x + this.width && pt.y >= this.y && pt.y <= this.y + this.height;
};

EquipLayoutSlot = Ext.extend(EquipLayoutItem, {
	constructor: function(id, name, x, y, width, height) {
		EquipLayoutSlot.superclass.constructor.call(this, x, y, width, height);
		this.id = id;
		this.name = name;
	},
	paint: function(ctx) {
		// rect
		ctx.beginPath();
		ctx.rect(this.x + 0.5, this.y + 0.5, this.width, this.height);
		ctx.strokeStyle = '#000000';
		ctx.fillStyle = (this == EquipLayoutEditor.highlighted_item) ? '#ffffff' : '#f8f8f8';
		ctx.lineWidth = 1;
		ctx.fill();
		ctx.stroke();
		// text
		ctx.save();
		ctx.beginPath();
		ctx.rect(this.x + 1, this.y + 1, this.width - 3, this.height - 3);
		ctx.clip();
		ctx.textBaseline = 'top';
		ctx.fillStyle = '#000000';
		ctx.fillText(this.name, this.x + 3, this.y + 3);
		ctx.fillText(this.id, this.x + 3, this.y + 15);
		ctx.restore();
	},
	coords: function() {
		return 'slot-' + this.id + ':' + this.x + ',' + this.y;
	}
});

EquipLayoutCharImage = Ext.extend(EquipLayoutItem, {
	paint: function(ctx) {
		// rect
		ctx.beginPath();
		ctx.rect(this.x + 0.5, this.y + 0.5, this.width, this.height);
		ctx.fillStyle = (this == EquipLayoutEditor.highlighted_item) ? '#f8f8ff' : '#f0f0ff';
		ctx.lineWidth = 1;
		ctx.fill();
		ctx.stroke();
		// text
		ctx.save();
		ctx.beginPath();
		ctx.rect(this.x + 1, this.y + 1, this.width - 3, this.height - 3);
		ctx.clip();
		ctx.textBaseline = 'top';
		ctx.fillStyle = '#000000';
		ctx.fillText(gt.gettext('Character image'), this.x + 3, this.y + 3);
		ctx.restore();
	},
	coords: function() {
		return 'charimage:' + this.x + ',' + this.y;
	}
});

EquipLayoutEditor = {};

EquipLayoutEditor.cleanup = function() {
	this.uninstall_global_events();
	var admin_main = Ext.getCmp('admin-main');
/*	this.width = admin_main.getWidth() - 80;
	this.height = admin_main.getHeight() - 100;
	if (this.width < 1000)
		this.width = 1000;
	if (this.height < 1000)
		this.height = 1000;*/
	this.width = 1000;
	this.height = 1000;
	this.handler_size = 5;
	this.handler_size = 5;
	this.clip_x1 = undefined;
	this.clip_x2 = undefined;
	this.clip_y1 = undefined;
	this.clip_y2 = undefined;
	this.grid_size = 10;
	this.items = new Array();
	this.highlighted_item = undefined;
	this.drag_item = undefined;
};

EquipLayoutEditor.uninstall_global_events = function() {
	if (this.global_events) {
		Ext.get('admin-viewport').un('mousedown', this.mouse_down, this);
		Ext.get('admin-viewport').un('mouseout', this.mouse_out, this);
		Ext.get('admin-viewport').un('mousemove', this.mouse_move, this);
		Ext.get('admin-viewport').un('mouseup', this.mouse_up, this);
		Ext.get('admin-viewport').un('contextmenu', this.context_menu, this);
		this.global_events = false;
	}
};

EquipLayoutEditor.init = function(submit_url, grid_size) {
	this.cleanup();
	this.grid_size = grid_size;
	/* creating canvas */
	var canvas = document.createElement('canvas');
	canvas.id = 'equip-layout-canvas';
	canvas.width = this.width;
	canvas.height = this.height;
	try {
		G_vmlCanvasManager.initElement(canvas);
		Ext.getDom('equip-layout-ie-warning').style.display = 'block';
	} catch (e) {}
	Ext.getDom('equip-layout-div').appendChild(canvas);
	this.ctx = canvas.getContext('2d');
	this.canvas = Ext.get(canvas);
	/* creating form */
	var th = this;
	this.form = new Form({
		url: submit_url,
		fields: [
			{type: 'hidden', name: 'coords', value: ''},
			{type: 'checkbox', name: 'grid', checked: (this.grid_size > 0), 'label': gt.gettext('Enable grid')},
			{name: 'grid_size', value: this.grid_size || 10, 'label': gt.gettext('Grid size'), inline: true, condition: "form_value('grid')"}
		],
		buttons: [{text: gt.gettext('Save')}],
		changeHandler: function() {
			th.form_changed();
		}
	});
};

EquipLayoutEditor.mouse_out = function(ev, target) {
	ev.stopEvent();
	this.mouse = {
		x: -1000,
		y: -1000
	};
	var repaint = false;
	if (this.update_highlighted()) {
		repaint = true;
	}
	if (repaint)
		this.paint();
};

EquipLayoutEditor.form_changed = function() {
	var new_grid_size = 0;
	if (form_value('grid')) {
		try {
			new_grid_size = parseInt(form_value('grid_size'));
		} catch (e) {
		}
	}
	if (!new_grid_size || new_grid_size < 0) {
		new_grid_size = 0;
	} else if (new_grid_size > 50) {
		new_grid_size = 50;
	}
	if (new_grid_size != this.grid_size) {
		this.grid_size = new_grid_size;
		this.paint(true);
	}
};

EquipLayoutEditor.touch_highlighted_item = function(poly) {
	this.touch_item(this.highlighted_item);
};

EquipLayoutEditor.cancel = function() {
	if (this.drag_item) {
		this.touch_highlighted_item();
		this.highlighted_item.x = this.drag_item.start_x;
		this.highlighted_item.y = this.drag_item.start_y;
		this.touch_highlighted_item();
		this.drag_item = undefined;
	} else if (this.highlighted_item) {
		this.touch_highlighted_item();
		this.highlighted_item = undefined;
	}
};

EquipLayoutEditor.mouse_down = function(ev, target) {
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
		if (this.highlighted_item) {
			this.touch_highlighted_item();
			this.drag_item = {
				start_x: this.highlighted_item.x, start_y: this.highlighted_item.y,
				mouse_start_x: this.mouse.x, mouse_start_y: this.mouse.y
			};
			repaint = true;
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

EquipLayoutEditor.mouse_move = function(ev, target) {
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
	if (this.drag_item) {
		this.touch_highlighted_item();
		var delta_x = pt.x - this.drag_item.mouse_start_x;
		var delta_y = pt.y - this.drag_item.mouse_start_y;
		this.highlighted_item.x = this.grid_size ? Math.floor((this.drag_item.start_x + delta_x) * 1.0 / this.grid_size + 0.5) * this.grid_size : this.drag_item.start_x + delta_x;
		this.highlighted_item.y = this.grid_size ? Math.floor((this.drag_item.start_y + delta_y) * 1.0 / this.grid_size + 0.5) * this.grid_size : this.drag_item.start_y + delta_y;
		this.touch_highlighted_item();
		repaint = true;
	}
	if (repaint)
		this.paint();
};

EquipLayoutEditor.mouse_up = function(ev, target) {
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
	if (this.drag_item) {
		this.drag_item = undefined;
		this.touch_highlighted_item();
		repaint = true;
		this.store_data();
	}
	if (repaint)
		this.paint();
};

EquipLayoutEditor.context_menu = function(ev, target) {
	ev.stopEvent();
};

EquipLayoutEditor.key_down = function(ev, target) {
	if (!this.canvas.dom || this.canvas.dom != Ext.getDom('equip-layout-canvas')) {
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
	}
};

EquipLayoutEditor.store_data = function() {
	var tokens = new Array();
	for (var i = 0; i < this.items.length; i++)
		tokens.push(this.items[i].coords());
	var coords = tokens.join(';');
	Ext.getCmp('form-field-coords').setValue(coords);
};

EquipLayoutEditor.run = function() {
	this.paint(true);
	this.form.enforce_conditions(true);
	this.store_data();
	this.form.render('equip-layout-form');
	this.canvas.on('mousedown', this.mouse_down, this);
	this.canvas.on('mouseout', this.mouse_out, this);
	this.canvas.on('mousemove', this.mouse_move, this);
	this.canvas.on('mouseup', this.mouse_up, this);
	this.canvas.on('contextmenu', this.context_menu, this);
	Ext.get('admin-viewport').on('keydown', this.key_down, this);
};

EquipLayoutEditor.paint = function(force) {
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
	// grid
	if (this.grid_size) {
		this.ctx.beginPath();
		this.ctx.strokeStyle = '#d0d0d0';
		this.ctx.lineWidth = 1;
		for (var x = 0; x < this.width; x += this.grid_size) {
			if (this.clip_x1 == undefined || x >= this.clip_x1 && x <= this.clip_x2) {
				this.ctx.moveTo(x + 0.5, 0);
				this.ctx.lineTo(x + 0.5, this.height);
			}
		}
		for (var y = 0; y < this.height; y += this.grid_size) {
			if (this.clip_y1 == undefined || y >= this.clip_y1 && y <= this.clip_y2) {
				this.ctx.moveTo(0, y + 0.5);
				this.ctx.lineTo(this.width, y + 0.5);
			}
		}
		this.ctx.stroke();
	}
	// items
	for (var i = 0; i < this.items.length; i++)
		this.items[i].paint(this.ctx);
	// commit
	this.ctx.restore();
	this.clip_x1 = undefined;
	this.clip_y1 = undefined;
	this.clip_x2 = undefined;
	this.clip_y2 = undefined;
};

EquipLayoutEditor.add = function(item) {
	this.items.push(item);
};

EquipLayoutEditor.touch_item = function(item) {
	if (item) {
		this.touch({x: item.x, y: item.y});
		this.touch({x: item.x + item.width, y: item.y + item.height});
	}
};

EquipLayoutEditor.touch = function(pt) {
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

EquipLayoutEditor.update_highlighted = function() {
	if (this.drag_item)
		return false;
	var old_highlighted_item = this.highlighted_item;
	if (this.highlighted_item) {
		if (this.highlighted_item.has(this.mouse)) {
			return false;
		}
	}
	this.highlighted_item = undefined;
	for (var i = 0; i < this.items.length; i++) {
		var item = this.items[i];
		if (item.has(this.mouse)) {
			this.highlighted_item = item;
		}
	}
	var modified = false;
	if (this.highlighted_item != old_highlighted_item) {
		this.touch_item(this.highlighted_item);
		this.touch_item(old_highlighted_item);
		modified = true;
	}
	return modified;
};

wait(['admin-form'], function() {
	loaded('equip-layout-editor');
});
