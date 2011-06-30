var admin_root = '';
var Game = {
	app: '[%app%]',
	domain: '[%domain%]',
	character: '[%character%]',
	panels: {
		[%+ foreach panel in panels%]'[%panel.id%]': {
			blocks: [
				[%foreach blk in panel.blocks%]{
					id: '[%blk.id%]',
					tp: '[%blk.tp%]',
					cls: '[%blk.cls%]'
					[%if blk.width%], width: [%blk.width%][%end%]
					[%if blk.flex%], flex: [%blk.flex%][%end%]
					[%if blk.buttons%], buttons: [
						[%foreach btn in blk.buttons%]
						{
							image: '[%btn.image%]',
							title: '[%btn.title%]'
							[%if btn.href%], href: '[%btn.href%]'[%end%]
							[%if btn.target%], target: '[%btn.target%]'[%end%]
							[%if btn.onclick%], onclick: '[%btn.onclick%]'[%end%]
						}[%unless btn.lst%],[%end%]
					    	[%end%]
					][%end%]
				}[%unless blk.lst%], [%end%]
			    	[%end%]
			]
		}[%unless panel.lst%], [%+ end%]
		[%end +%]
	}
};

Game.fixupContentEl = function(el) {
	var def = Ext.get('default-' + el.contentEl);
	if (!def) {
		Ext.alert('Missing element: default-' + el.contentEl);
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
//		container_options.height = undefined;
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
				width: block.width,
				flex: block.flex
			};
			if (block.cls) {
				block_el.cls = 'block-' + block.cls;
			}
			if (block.tp == 'empty') {
			} else if (block.tp == 'buttons') {
				block_el.html = '';
				[%if design_root%]
				block_el.html += '<img src="[%design_root%]/' + block.cls + '-' + (options.vertical ? 'top' : 'left') + '.png" alt="" />';
				[%end%]
				if (block.buttons) {
					var att = '';
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
						var img = '<img src="' + btn.image + '" alt="" title="' + btn.title + '"' + att + (btn.onclick ? ' onclick="' + btn.onclick + '" class="btn-clickable"' : '') + ' />';
						if (btn.href && !btn.onclick) {
							img = '<a href="' + btn.href + '" target="' + btn.target + '">' + img + '</a>';
						}
						block_el.html += img;
					}
				}
				[%if design_root%]
				block_el.html += '<img src="[%design_root%]/' + block.cls + '-' + (options.vertical ? 'bottom' : 'right') + '.png" alt="" />';
				[%end%]
			} else {
				block_el.html = block.tp;
			}
			el.items.push(block_el);
		}
	}
	var panel = this.element('panel-' + id, cel, el);
	return panel;
};

Game.setup_game_layout = function() {
	var panel_top;
	[%if layout.panel_top%]
     	panel_top = this.panel('top');
	[%else%]
	panel_top = {
		id: 'panel-top',
		xtype: 'box'
	};
	[%end%]
	var chat = this.element('chat-frame');
	var chat_frame_items = new Array();
	[%if layout.chat_channels%]
	if (Ext.get('chat-channel-buttons')) {
		var channel_buttons;
		if (Ext.get('chat-channel-buttons').hasClass('layout-left')) {
			channel_buttons = this.element('chat-channel-buttons', {region: 'west'}, {vertical: true, layout: 'auto'});
			channel_buttons.height = undefined;
			chat.region = 'center';
			chat = {
				id: 'chat-buttons-and-frame',
				xtype: 'container',
				layout: 'border',
				region: 'center',
				items: [
					channel_buttons,
					chat
				]
			};
		} else {
			channel_buttons = this.element('chat-channel-buttons', {region: 'north'});
			channel_buttons.region = 'north';
			channel_buttons.width = undefined;
			chat_frame_items.push(channel_buttons);
		}
	}
	[%end%]
	chat_frame_items.push(this.element('chat-box', {region: 'center'}));
	chat_frame_items.push(this.element('chat-input', {loadHeight: true, region: 'south'}));
	Ext.getCmp('chat-frame-content').add({
		id: 'chat-frame-layout',
		xtype: 'container',
		layout: 'border',
		items: chat_frame_items
	});
	var roster = this.element('chat-roster');
	Ext.getCmp('chat-roster-content').add({
		id: 'chat-roster-layout',
		xtype: 'container',
		layout: 'border',
		items: [
			[%if layout.chat_channels%]this.element('chat-roster-header', {region: 'north', loadHeight: true}),[%end%]
			this.element('chat-roster-characters', {region: 'center'}),
			this.element('chat-roster-buttons', {region: 'south', loadHeight: true})
		]
	});
	var main = this.fixupContentEl({
		id: 'main-container',
		xtype: 'container',
		contentEl: 'main',
		onLayout: function(shallow, forceLayout) {
			if (shallow !== true) {
				Ext.getCmp('main-layout').doLayout(false, forceLayout);
			}
		}
	});
	new Ext.Container({
		id: 'main-layout',
		applyTo: 'main-content',
		layout: 'vbox',
		layoutConfig: {
			align: 'stretch'
		},
		items: [{
			id: 'main-iframe',
			xtype: 'mif',
			border: false,
			defaultSrc: '[%main_init%]',
			margins: this.loadMargins('main-content'),
			flex: 1,
			frameConfig: {
				name: 'main-iframe'
			}
		}]
	});
	[%if layout.panel_main_left or layout.panel_main_right%]
		main.region = 'center';
		main = {
			id: 'main-panel-group',
			xtype: 'container',
			layout: 'border',
			items: [
				[%if layout.panel_main_left%]this.panel('main-left', {region: 'west', vertical: true}),[%end%]
				main
				[%if layout.panel_main_right%], this.panel('main-right', {region: 'east', vertical: true})[%end%]
			]
		};
	[%end%]
	[%if layout.scheme == 1%]
	panel_top.region = 'north';
	chat.region = 'center';
	chat.minWidth = 200;
	roster.region = 'east';
	roster.split = true;
	roster.width = 300;
	roster.minSize = 300;
	main.region = 'center';
	main.minHeight = 200;
	var content = new Ext.Container({
		id: 'page-content',
		layout: 'border',
		items: [
			panel_top,
			{
				id: 'chat-and-roster',
				xtype: 'container',
				region: 'south',
				height: 250,
				minHeight: 100,
				layout: 'border',
				split: true,
				items: [chat, roster]
			},
			main
		]
	});
	[%elsif layout.scheme == 2%]
	panel_top.region = 'north';
	roster.region = 'east';
	roster.width = 300;
	roster.minSize = 300;
	roster.split = true;
	chat.region = 'south';
	chat.split = true;
	chat.height = 250;
	chat.minHeight = 100;
	main.region = 'center';
	main.minHeight = 200;
	var content = new Ext.Container({
		id: 'page-content',
		layout: 'border',
		items: [
			panel_top,
			roster,
			{
				id: 'main-and-chat',
				xtype: 'container',
				region: 'center',
				minWidth: 300,
				layout: 'border',
				items: [main, chat]
			}
		]
	});
	[%elsif layout.scheme == 3%]
	panel_top.region = 'north';
	main.region = 'center';
	main.minWidth = 300;
	roster.region = 'center';
	roster.minHeight = 100;
	chat.region = 'south';
	chat.minHeight = 100;
	chat.height = 300;
	chat.split = true;
	var content = new Ext.Container({
		id: 'page-content',
		layout: 'border',
		items: [
			panel_top,
			main,
			{
				id: 'roster-and-chat',
				xtype: 'container',
				region: 'east',
				width: 300,
				minWidth: 300,
				layout: 'border',
				split: true,
				items: [roster, chat]
			}
		]
	});
	[%else%]
	var content = new Ext.Container({
		id: 'page-content',
		html: gt.gettext('Misconfigured layout scheme')
	});
	[%end%]
	var margins = new Array();
	[%if layout.marginleft%]
	margins.push(this.fixupContentEl({
		xtype: 'box',
		width: [%layout.marginleft%],
		region: 'west',
		contentEl: 'margin-left'
	}));
	[%end%]
	[%if layout.marginright%]
	margins.push(this.fixupContentEl({
		xtype: 'box',
		width: [%layout.marginright%],
		region: 'east',
		contentEl: 'margin-right'
	}));
	[%end%]
	[%if layout.margintop%]
	margins.push(this.fixupContentEl({
		xtype: 'box',
		height: [%layout.margintop%],
		region: 'north',
		contentEl: 'margin-top'
	}));
	[%end%]
	[%if layout.marginbottom%]
	margins.push(this.fixupContentEl({
		xtype: 'box',
		height: [%layout.marginbottom%],
		region: 'south',
		contentEl: 'margin-bottom'
	}));
	[%end%]
	if (margins.length) {
		content.region = 'center';
		margins.push(content);
		new Ext.Viewport({
			id: 'game-viewport',
			layout: 'border',
			items: margins
		});
	} else {
		new Ext.Viewport({
			id: 'game-viewport',
			layout: 'fit',
			items: content
		});
	}
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

Ext.onReady(function() {
	Ext.QuickTips.init();
	Ext.form.Field.prototype.msgTarget = 'under';
	wait([[%foreach module in js_modules%]'[%module.name%]'[%unless module.lst%],[%end%][%end%]], function() {
		[%+ foreach statement in js_init%][%statement +%]
		[%+ end%]
	});
});
