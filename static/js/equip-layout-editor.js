EquipLayoutItem = function(x, y, width, height) {
	this.order = 0;
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
		this.order = 20;
		this.id = id;
		this.name = name;
	},
	paint: function(ctx) {
		// rect
		ctx.beginPath();
		ctx.rect(this.x, this.y, this.width, this.height);
		ctx.fillStyle = (this == EquipLayoutEditor.highlighted_item) ? '#9dd9f7' : '#e5f1f7';
		ctx.fill();
		// border
		var border = EquipLayoutEditor.slot_border;
		if (border) {
			ctx.save();
			ctx.beginPath();
			ctx.rect(this.x - border / 2.0, this.y - border / 2.0, this.width + border, this.height + border);
			ctx.lineWidth = border;
			ctx.strokeStyle = '#000000';
			ctx.stroke();
			ctx.restore()
		}
		// text
		ctx.save();
		ctx.beginPath();
		ctx.rect(this.x + 1, this.y + 1, this.width - 3, this.height - 3);
		ctx.clip();
		ctx.textBaseline = 'top';
		ctx.fillStyle = '#000000';
		if (ctx.fillText) {
			ctx.fillText(this.name, this.x + 3, this.y + 3);
			ctx.fillText(this.id, this.x + 3, this.y + 15);
		}
		ctx.restore();
		return true;
	},
	coords: function() {
		return 'slot-' + this.id + ':' + this.x + ',' + this.y + ',' + this.width + ',' + this.height;
	},
	border: function() {
		return EquipLayoutEditor.slot_border;
	}
});

EquipLayoutCharImage = Ext.extend(EquipLayoutItem, {
	constructor: function(x, y, width, height) {
		EquipLayoutCharImage.superclass.constructor.call(this, x, y, width, height);
		this.order = 10;
	},
	paint: function(ctx) {
		// rect
		ctx.beginPath();
		ctx.rect(this.x, this.y, this.width, this.height);
		ctx.fillStyle = (this == EquipLayoutEditor.highlighted_item) ? '#ea9e70' : '#f8decd';
		ctx.fill();
		// border
		var border = EquipLayoutEditor.charimage_border;
		if (border) {
			ctx.save();
			ctx.beginPath();
			ctx.rect(this.x - border / 2.0, this.y - border / 2.0, this.width + border, this.height + border);
			ctx.lineWidth = border;
			ctx.strokeStyle = '#000000';
			ctx.stroke();
			ctx.restore()
		}
		// text
		ctx.save();
		ctx.beginPath();
		ctx.rect(this.x + 1, this.y + 1, this.width - 3, this.height - 3);
		ctx.clip();
		ctx.textBaseline = 'top';
		ctx.fillStyle = '#000000';
		if (ctx.fillText)
			ctx.fillText(gt.gettext('Character image'), this.x + 3, this.y + 3);
		ctx.restore();
		return true;
	},
	coords: function() {
		return 'charimage:' + this.x + ',' + this.y + ',' + this.width + ',' + this.height;
	},
	border: function() {
		return EquipLayoutEditor.charimage_border;
	}
});

EquipLayoutStaticImage = Ext.extend(EquipLayoutItem, {
	constructor: function(uuid, uri, x, y, width, height) {
		EquipLayoutStaticImage.superclass.constructor.call(this, x, y, width, height);
		this.order = 0;
		this.uuid = uuid;
		this.uri = uri;
		var img = document.createElement('IMG');
		img.src = uri;
		this.img = img;
		this.deletable = true;
	},
	paint: function(ctx) {
		var img_ok = this.img.width && this.img.height;
		if (img_ok) {
			// image
			ctx.drawImage(this.img, this.x, this.y, this.width, this.height);
		} else {
			// rect
			ctx.beginPath();
			ctx.rect(this.x + 0.5, this.y + 0.5, this.width - 1, this.height - 1);
			ctx.strokeStyle = '#000000';
			ctx.lineWidth = 1;
			ctx.stroke();
			// text
			ctx.save();
			ctx.beginPath();
			ctx.rect(this.x + 1, this.y + 1, this.width - 3, this.height - 3);
			ctx.clip();
			ctx.textBaseline = 'top';
			ctx.fillStyle = '#000000';
			if (ctx.fillText)
				ctx.fillText(this.uri, this.x + 3, this.y + 3);
			ctx.restore();
		}
		// highlight
		if (this == EquipLayoutEditor.highlighted_item) {
			ctx.beginPath();
			ctx.rect(this.x + 0.5, this.y + 0.5, this.width - 1, this.height - 1);
			ctx.strokeStyle = '#ff0000';
			ctx.lineWidth = 1;
			ctx.stroke();
		}
		return img_ok;
	},
	coords: function() {
		return 'staticimage-' + this.uuid + '(' + this.uri + '):' + this.x + ',' + this.y + ',' + this.width + ',' + this.height;
	},
	border: function() {
		return 0;
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
	this.slot_border = 1;
	this.charimage_border = 1;
	this.items = new Array();
	this.highlighted_item = undefined;
	this.drag_item = undefined;
	this.last_item_id = 0;
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

EquipLayoutEditor.init = function(submit_url, grid_size, slot_border, charimage_border) {
	this.cleanup();
	this.grid_size = grid_size;
	this.slot_border = slot_border;
	this.charimage_border = charimage_border;
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
			{name: 'grid_size', value: this.grid_size || 10, 'label': gt.gettext('Grid size'), inline: true, condition: "form_value('grid')"},
			{name: 'slot_border', value: this.slot_border, 'label': gt.gettext('Slot border'), inline: true},
			{name: 'charimage_border', value: this.charimage_border, 'label': gt.gettext('Character image border'), inline: true}
		],
		buttons: [
			{text: gt.gettext('Save')},
			{
				text: gt.gettext('Add arbitrary image'),
				xtype: 'button',
				icon: '/st-mg/icons/image.gif',
				listeners: {
					click: function() {
						th.add_arbitrary_image();
					}
				}
			}
		],
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
	if (repaint) {
		this.paint();
	}
};

EquipLayoutEditor.parseInt = function(name, min, max) {
	var new_val = 0;
	if (form_value(name)) {
		try {
			new_val = parseInt(form_value(name));
		} catch (e) {
		}
	}
	if (!new_val || new_val < min) {
		new_val = min;
	} else if (new_val > max) {
		new_val = max;
	}
	return new_val;
};

EquipLayoutEditor.form_changed = function() {
	var new_grid_size = form_value('grid') ? this.parseInt('grid_size', 0, 50) : 0;
	var new_slot_border = this.parseInt('slot_border', 0, 50);
	var new_charimage_border = this.parseInt('charimage_border', 0, 50);
	if (new_grid_size != this.grid_size || new_slot_border != this.slot_border || new_charimage_border != this.charimage_border) {
		this.grid_size = new_grid_size;
		this.slot_border = new_slot_border;
		this.charimage_border = new_charimage_border;
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
		this.fix_item(this.highlighted_item);
		this.touch_highlighted_item();
		repaint = true;
	}
	if (repaint) {
		this.paint();
	}
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
	if (repaint) {
		this.paint();
	}
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
	} else if (key == ev.DOWN) {
		if (this.highlighted_item) {
			ev.stopEvent();
			this.touch_highlighted_item();
			this.highlighted_item.y++;
			this.touch_highlighted_item();
			this.store_data();
			this.paint();
		}
	} else if (key == ev.UP) {
		if (this.highlighted_item) {
			ev.stopEvent();
			this.touch_highlighted_item();
			this.highlighted_item.y--;
			this.touch_highlighted_item();
			this.store_data();
			this.paint();
		}
	} else if (key == ev.LEFT) {
		if (this.highlighted_item) {
			ev.stopEvent();
			this.touch_highlighted_item();
			this.highlighted_item.x--;
			this.touch_highlighted_item();
			this.store_data();
			this.paint();
		}
	} else if (key == ev.RIGHT) {
		if (this.highlighted_item) {
			ev.stopEvent();
			this.touch_highlighted_item();
			this.highlighted_item.x++;
			this.touch_highlighted_item();
			this.store_data();
			this.paint();
		}
	} else if (key == ev.DELETE) {
		if (this.highlighted_item) {
			ev.stopEvent();
			if (this.highlighted_item.deletable) {
				this.touch_highlighted_item();
				for (var i = 0; i < this.items.length; i++) {
					if (this.items[i] == this.highlighted_item) {
						this.items.splice(i, 1);
						this.highlighted_item = undefined;
						break;
					}
				}
			}
			this.store_data();
			this.paint();
		}
	}
};

EquipLayoutEditor.store_data = function() {
	var tokens = new Array();
	for (var i = 0; i < this.items.length; i++)
		tokens.push(this.items[i].coords());
	var coords = tokens.join(';');
	Ext.getCmp('form-field-coords').setValue(coords);
};

EquipLayoutEditor.cmp_items = function(a, b) {
	if (a.order < b.order)
		return -1;
	if (a.order > b.order)
		return 1;
	if (a.item_id < b.item_id)
		return -1;
	if (a.item_id > b.item_id)
		return 1;
	return 0;
};

EquipLayoutEditor.sort_items = function() {
	this.items.sort(this.cmp_items);
};

EquipLayoutEditor.run = function() {
	this.sort_items();
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
			this.ctx.moveTo(x + 0.5, 0);
			this.ctx.lineTo(x + 0.5, this.height);
		}
		for (var y = 0; y < this.height; y += this.grid_size) {
			this.ctx.moveTo(0, y + 0.5);
			this.ctx.lineTo(this.width, y + 0.5);
		}
		this.ctx.stroke();
	}
	// items
	var failed = false;
	for (var i = 0; i < this.items.length; i++) {
		if (!this.items[i].paint(this.ctx))
			failed = true;
	}
	// commit
	this.ctx.restore();
	this.clip_x1 = undefined;
	this.clip_y1 = undefined;
	this.clip_x2 = undefined;
	this.clip_y2 = undefined;
	// handling failures
	if (failed) {
		if (this.fail_timer) {
			this.fail_timer *= 2;
			if (this.fail_timer > 10000) {
				this.fail_timer = 0;
			}
		} else {
			this.fail_timer = 100;
		}
	} else {
		this.fail_timer = 0;
	}
	if (this.fail_timer)
		window.setTimeout((function() { this.paint(true) }).createDelegate(this), this.fail_timer);
};

EquipLayoutEditor.fix_item = function(item) {
	if (item.x < 0)
		item.x = 0;
	if (item.y < 0)
		item.y = 0;
	if (item.x + item.width > this.width)
		item.x = this.width - item.width;
	if (item.y + item.height > this.height)
		item.y = this.height - item.height;
};

EquipLayoutEditor.add = function(item) {
	item.item_id = ++this.last_item_id;
	this.fix_item(item);
	this.items.push(item);
};

EquipLayoutEditor.touch_item = function(item) {
	if (item) {
		var border = item.border();
		this.touch({x: item.x - border, y: item.y - border});
		this.touch({x: item.x + item.width + border, y: item.y + item.height + border});
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
/*	if (this.highlighted_item) {
		if (this.highlighted_item.has(this.mouse)) {
			return false;
		}
	}*/
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

EquipLayoutEditor.add_arbitrary_image = function() {
	if (this.storage_unavailable)
		return Ext.Msg.alert(gt.gettext('Error'), this.storage_unavailable);
	var th = this;
	var win = new Ext.Window({
		id: 'upload-window',
		modal: true,
		title: gt.gettext('Add arbitrary image'),
		width: 500,
		autoHeight: true,
		padding: '20px 0 20px 20px',
		items: [
			new Form({
				url: '/admin-storage/static/new',
				fields: [
					{type: 'hidden', name: 'image', 'value': '1'},
					{type: 'hidden', name: 'group', 'value': 'equip-layout'},
					{type: 'fileuploadfield', name: 'ob', 'label': gt.gettext('Image file')}
				],
				buttons: [
					{text: gt.gettext('Upload')}
				],
				successHandler: function(f, action) {
					var cmp = Ext.getCmp('upload-window');
					if (cmp)
						cmp.close();
					var res = Ext.util.JSON.decode(action.response.responseText);
					th.add(new EquipLayoutStaticImage(res.uuid, res.uri, 0, 0, res.width, res.height));
					th.sort_items();
					th.store_data();
					th.paint(true);
				}
			})
		]
	});
	win.show();
};

wait(['admin-form', 'FileUploadField'], function() {
	loaded('equip-layout-editor');
});
