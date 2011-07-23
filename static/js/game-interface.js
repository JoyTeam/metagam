Game.progress = new Array();

Game.now = function() {
	return (new Date()).getTime();
};

Game.reload = function() {
	Stream.initialized = false;
	var frm = document.createElement('form');
	frm.method = 'post';
	frm.action = '/';
	var inp = document.createElement('input');
	inp.type = 'hidden';
	inp.name = 'session';
	inp.value = Ext.util.Cookies.get('mgsess-' + Game.app);
	frm.appendChild(inp);
	Ext.getBody().dom.appendChild(frm);
	frm.submit();
};

Game.close = function() {
	Stream.initialized = false;
	document.location = 'http://' + Game.domain;
};

Game.logout = function() {
	Stream.initialized = false;
	document.location = 'http://' + Game.domain + '/auth/logout';
};

Game.msg = function(title, str, add_cls) {
	if (!this.msgCt){
		this.msgCt = Ext.DomHelper.insertFirst(document.body, {id: 'msg-div'}, true);
	}
	var m = Ext.DomHelper.append(this.msgCt, '<div class="msg' + (add_cls ? ' ' + add_cls : '') + '">' + (title ? '<h3>' + title + '</h3>' : '') + '<p>' + str + '</p></div>', true);
	m.hide();
	m.slideIn('t').pause(3).ghost('t', {remove: true});
};

Game.info = function(title, str) {
	this.msg(title, str, 'msg-info');
};

Game.error = function(title, str) {
	this.msg(title, str, 'msg-error');
};

Game.main_open = function(uri) {
	try {
		var iframe = Ext.getCmp('main-iframe');
		var win = iframe.el.dom.contentWindow || window.frames['main-iframe'];
		win.location.href = uri;
	} catch (e) {
		this.error(gt.gettext('Exception'), e);
	}
};

Game.progress_stop = function(id) {
	if (this.progress[id] && this.progress[id].timer) {
		window.clearInterval(this.progress[id].timer);
		this.progress[id].timer = undefined;
	}
};

Game.progress_set = function(id, ratio) {
	this.progress_stop(id);
	this.progress_show(id, ratio);
};

Game.progress_show = function(id, ratio) {
	if (ratio < 0)
		ratio = 0;
	if (ratio > 1)
		ratio = 1;
	var progress = this.progress[id];
	if (!progress) {
		progress = {};
		this.progress[id] = progress;
	}
	progress.ratio = ratio;
	var els = Ext.query('.progress-' + id);
	for (var i = 0; i < els.length; i++) {
		var el = Ext.get(els[i]);
		if (el.hasClass('progress-indicator-horizontal')) {
			if (el.content_width == undefined) {
				el.content_width = el.parent().getWidth(true);
			}
			el.dom.style.width = Math.floor(ratio * el.content_width) + 'px';
		} else if (el.hasClass('progress-indicator-vertical')) {
			if (el.content_height == undefined) {
				el.content_height = el.parent().getHeight(true);
			}
			el.dom.style.height = Math.floor(ratio * el.content_height) + 'px';
		} else {
			continue;
		}
		if (!el.hasClass(id + '-notfull')) {
			if (ratio < 1) {
				el.removeClass(id + '-full');
				el.addClass(id + '-notfull');
			}
		}
		if (!el.hasClass(id + '-full')) {
			if (ratio >= 1) {
				el.removeClass(id + '-notfull');
				el.addClass(id + '-full');
			}
		}
	}
};

Game.progress_run = function(id, start_ratio, end_ratio, time_till_end) {
	this.progress_set(start_ratio);
	if (time_till_end > 0) {
		var now = this.now();
		this.progress[id] = {
			timer: window.setInterval(this.progress_tick.createDelegate(this, [id]), 30),
			start_ratio: start_ratio,
			end_ratio: end_ratio,
			start_time: now,
			end_time: now + time_till_end
		};
	}
};

Game.progress_tick = function(id) {
	try {
		var progress = this.progress[id];
		if (progress && progress.timer) {
			var now = this.now();
			if (now >= progress.end_time) {
				this.progress_show(id, 1);
				this.progress_stop(id);
			} else {
				var ratio = (now - progress.start_time) * (progress.end_ratio - progress.start_ratio) / (progress.end_time - progress.start_time) + progress.start_ratio;
				this.progress_show(id, ratio);
			}
		}
	} catch (e) {
		this.progress_stop(id);
		this.error(gt.gettext('Exception'), e);
	}
};

Game.onLayout = function() {
	for (var id in this.progress) {
		var progress = this.progress[id];
		if (progress.ratio == undefined)
			continue;
		var els = Ext.query('.progress-' + id);
		for (var i = 0; i < els.length; i++) {
			var el = Ext.get(els[i]);
			if (el.content_width != undefined) {
				el.content_width = undefined;
				el.dom.style.width = '0px';
			}
			if (el.content_height != undefined) {
				el.content_height = undefined;
				el.dom.style.height = '0px';
			}
		}
		this.progress_show(id, progress.ratio);
	}
};

Game.main_frame_document = function() {
	try {
		return Ext.getCmp('main-iframe').getFrameDocument();
	} catch (e) {
		this.error(gt.gettext('Exception'), e);
	}
	return undefined;
};

Game.fixupContentEl = function(el) {
	var def = Ext.get('default-' + el.contentEl);
	if (!def) {
		Ext.Msg.alert('Missing element: default-' + el.contentEl);
		return el;
	}
	if (Ext.getDom(el.contentEl)) {
		Ext.get(def.id).remove();
		if (el.loadWidth)
			el.width = Ext.get(el.contentEl).getWidth();
		if (el.loadHeight)
			el.height = Ext.get(el.contentEl).getHeight();
	} else {
		if (el.loadWidth)
			el.width = def.getWidth();
		if (el.loadHeight)
			el.height = def.getHeight();
		def.id = el.contentEl;
		def.dom.id = el.contentEl;
	}
	return el;
};

Game.loadMargins = function(el) {
	el = Ext.fly(el);
	if (!el)
		return undefined;
	var margins = el.dom.style.margin;
	if (!margins)
		return undefined;
	el.dom.style.margin = '';
	return margins;
};

Game.element = function(eid, cel, el) {
	/* creating container element */
	cel = cel || {};
	cel.id = eid;
	cel.xtype = cel.xtype || 'container';
	cel.contentEl = eid;
	cel.onLayout = function(shallow, forceLayout) {
		if (shallow !== true) {
			Ext.getCmp(eid + '-content-container').doLayout(false, forceLayout);
		}
	};
	cel = this.fixupContentEl(cel);
	cel.id = eid + '-container';
	Ext.get(eid).dom.style.height = '100%';
	/* creating content element */
	el = el || {};
	var content = Ext.get(eid + '-content');
	el.margins = content.dom.style.margin;
	/* save static content items */
	var children = new Array();
	var childNodes = content.dom.childNodes;
	for (var i = childNodes.length - 1; i >= 0; i--) {
		var node = childNodes[i];
		content.dom.removeChild(node);
		children.push(node);
	}
	el.html = content.dom.innerHTML;
	/* 'content' is the innermost container. Remove it and create a new element
	 * at the same place. */
	var content_parent = content.parent();
	var insert_here = content_parent.dom.insertBefore(document.createElement('div'), content.dom);
	content.remove();
	el.id = eid + '-content';
	el.xtype = el.xtype || 'container';
	el.flex = 1;
	el.layout = el.layout || 'fit';
	insert_here.id = eid + '-content-container';
	var container_options = {
		id: eid + '-content-container',
		applyTo: insert_here,
		height: '100%',
		layout: 'vbox',
		layoutConfig: {
			align: 'stretch'
		},
		items: [el]
	};
	if (el.vertical) {
		el.vertical = undefined;
		container_options.width = '100%';
		container_options.layout = 'auto';
		container_options.layoutConfig = undefined;
	}
	var container = new Ext.Container(container_options);
	/* restore static content items */
	var dom = Ext.get(eid + '-content').dom;
	for (var i = children.length - 1; i >= 0; i--) {
		dom.appendChild(children[i]);
	}
	return cel;
};

Game.panel = function(id, options) {
	var cel = {};
	var el = {
		layoutConfig: {
			align: 'stretch'
		}
	};
	options = options || {};
	if (options.vertical) {
		cel.loadWidth = true;
		el.vertical = true;
		el.layout = 'vbox';
		el.height = '100%';
	} else {
		cel.loadHeight = true;
		el.layout = 'hbox';
	}
	if (options.region) {
		cel.region = options.region;
	}
	el.items = [];
	var panel_info = this.panels[id];
	if (panel_info) {
		for (var i = 0; i < panel_info.blocks.length; i++) {
			var block = panel_info.blocks[i];
			var block_el = {
				xtype: 'box',
				flex: block.flex
			};
			if (options.vertical) {
				block_el.height = block.width;
			} else {
				block_el.width = block.width;
			}
			if (block.cls) {
				block_el.cls = 'block-' + block.cls;
			}
			if (block.tp == 'empty') {
			} else if (block.tp == 'buttons') {
				block_el.html = '';
				if (this.design_root) {
					if (options.vertical) {
						if (block.buttons_top) {
							block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-top.png" alt="" />';
						}
					} else {
						if (block.buttons_left) {
							block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-left.png" alt="" />';
						}
					}
				}
				var hints = Ext.getDom('block-hints-' + block.cls);
				hints = hints ? hints.innerHTML.split(',') : undefined;
				if (options.vertical) {
					if (hints) {
						block_el.height = parseInt(hints[0]) * block.buttons.length + parseInt(hints[1]);
					} else {
						block_el.height = 32 * block.buttons.length + 32;
					}
				} else {
					if (hints) {
						block_el.width = parseInt(hints[0]) * block.buttons.length + parseInt(hints[1]);
					} else {
						block_el.width = 32 * block.buttons.length + 32;
					}
				}
				for (var j = 0; j < block.buttons.length; j++) {
					var btn = block.buttons[j];
					block_el.html += this.render_button(btn);
				}
				if (this.design_root) {
					if (options.vertical) {
						if (block.buttons_bottom) {
							block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-bottom.png" alt="" />';
						}
					} else {
						if (block.buttons_right) {
							block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-right.png" alt="" />';
						}
					}
				}
			} else if (block.tp == 'html') {
				block_el.html = block.html;
			} else if (block.tp == 'header') {
				var cls = 'panel-header-' + (options.vertical ? 'vertical' : 'horizontal');
				block_el.html = '<div class="' + cls + '"><div class="' + cls + '-1"><div class="' + cls + '-2"><div class="' + cls + '-3"><div class="' + cls + '-4"><div class="' + cls + '-5"><div class="' + cls + '-6"><div class="' + cls + '-7"><div class="' + cls + '-8"><div class="panel-header-horizontal-margin"></div><table class="' + cls + '-9"><tr><td class="' + cls + '-10">' + block.html + '</td></tr></table></div></div></div></div></div></div></div></div></div>';
			} else if (block.tp == 'progress') {
				var cls = 'progress-' + (options.vertical ? 'vertical' : 'horizontal');
				var bars;
				if (block.progress_types.length) {
					if (options.vertical) {
						bars = '<table class="progress-bars-vertical"><tr>';
						var width = Math.floor(100 / block.progress_types.length);
						for (var j = 0; j < block.progress_types.length; j++) {
							bars += '<td class="progress-bars-vertical-td" style="width: ' + width + '%"><div class="progress-indicator progress-indicator-vertical progress-' + block.progress_types[j] + '" style="height: 0px"></div></td>';
						}
						bars += '</tr></table>';
					} else {
						bars = '<div class="progress-bars-horizontal-margin"></div><table class="progress-bars-horizontal">';
						var height = Math.floor(100 / block.progress_types.length);
						for (var j = 0; j < block.progress_types.length; j++) {
							bars += '<tr style="height: ' + height + '%"><td class="progress-bars-horizontal-td"><div class="progress-indicator progress-indicator-horizontal progress-' + block.progress_types[j] + '" style="width: 0px"></div></td></tr>';
						}
						bars += '</table>';
					}
				} else {
					bars = '';
				}
				block_el.html = '<div class="' + cls + '"><div class="' + cls + '-1"><div class="' + cls + '-2"><div class="' + cls + '-3"><div class="' + cls + '-4"><div class="' + cls + '-5"><div class="' + cls + '-6"><div class="' + cls + '-7"><div class="' + cls + '-8"><div class="' + cls + '-9">' + bars + '</div></div></div></div></div></div></div></div></div></div>';
			} else {
				block_el.html = block.tp;
			}
			el.items.push(block_el);
		}
	}
	var panel = this.element('panel-' + id, cel, el);
	return panel;
};

Game.setup_cabinet_layout = function() {
	new Ext.Viewport({
		id: 'cabinet-viewport',
		layout: 'fit',
		items: this.fixupContentEl({
			xtype: 'box',
			contentEl: 'cabinet-content'
		})
	});
};

Game.get_btn_id = function() {
	if (this.btn_id != undefined)
		return ++this.btn_id;
	this.btn_id = 1;
	return 1;
};

Game.render_button = function(btn) {
	var att = '';
	var btn_id = this.get_btn_id();
	var classes = new Array();
	if (btn.onclick) {
		att += ' onclick="' + btn.onclick + '"';
		classes.push('clickable');
	} else if (btn.popup) {
		att += ' onclick="Game.popup(\'panel-btn-' + btn_id + '\', \'' + btn.popup + '\');"';
		classes.push('clickable');
	}
	classes.push('btn-' + btn.id);
	att += ' class="' + classes.join(' ') + '"';
	var img = '<img id="panel-btn-' + btn_id + '" src="' + btn.image + '" alt="" title="' + btn.title + '"' + att + ' />';
	if (btn.href && !btn.onclick) {
		img = '<a href="' + btn.href + '" target="' + btn.target + '">' + img + '</a>';
	}
	this.buttons[btn.id] = btn;
	return img;
};

Game.popup = function(btn_id, popup_id, parent_menu) {
	var btn_el = Ext.get(btn_id);
	if (!btn_el)
		return;
	var popup = this.popups[popup_id];
	if (!popup)
		return;
	var menu = new Ext.menu.Menu({
	});
	for (var i = 0; i < popup.buttons.length; i++) {
		var btn = popup.buttons[i];
		var btn_id = 'panel-btn-' + this.get_btn_id();
		menu.addMenuItem({
			id: btn_id,
			icon: btn.image,
			text: btn.title,
			href: btn.href,
			hrefTarget: btn.target,
			hideOnClick: btn.popup ? false : true,
			listeners: {
				click: (function(btn_el, e, btn, menu, btn_id) {
					if (btn.onclick) {
						eval(btn.onclick);
					} else if (btn.popup) {
						this.popup(btn_id, btn.popup, menu);
					}
				}).createDelegate(this, [btn, menu, btn_id], true)
			}
		});
	}
	menu.show(btn_el, 'tl-bl', parent_menu);
	if (!parent_menu) {
		Ext.ux.ManagedIFrame.Manager.showShims();
		menu.addListener('hide', function() {
			Ext.ux.ManagedIFrame.Manager.hideShims();
		});
	}
};

loaded('game-interface');
