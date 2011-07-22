var admin_root = '';
var Game = {
	app: '[%app%]',
	domain: '[%domain%]',
	character: '[%character%]',
	design_root: '[%design_root%]',
	panels: {
		[%+ foreach panel in panels%]'[%panel.id%]': {
			blocks: [
				[%foreach blk in panel.blocks%]{
					id: '[%blk.id%]',
					tp: '[%blk.tp%]',
					cls: '[%blk.cls%]',
					html: '[%blk.html%]'
					[%if blk.width%], width: [%blk.width%][%end%]
					[%if blk.buttons_left%], buttons_left: true[%end%]
					[%if blk.buttons_right%], buttons_right: true[%end%]
					[%if blk.buttons_top%], buttons_top: true[%end%]
					[%if blk.buttons_bottom%], buttons_bottom: true[%end%]
					[%if blk.flex%], flex: [%blk.flex%][%end%]
					[%if blk.buttons%], buttons: [
						[%foreach btn in blk.buttons%]
						{
							id: '[%btn.id%]',
							image: '[%btn.image%]',
							title: '[%btn.title%]'
							[%if btn.image2%], image2: '[%btn.image2%]'[%end%]
							[%if btn.href%], href: '[%btn.href%]'[%end%]
							[%if btn.target%], target: '[%btn.target%]'[%end%]
							[%if btn.onclick%], onclick: '[%btn.onclick%]'[%end%]
							[%if btn.popup%], popup: '[%btn.popup%]'[%end%]
						}[%unless btn.lst%],[%end%]
					    	[%end%]
					][%end%]
					[%if blk.progress_types%], progress_types: [
						[%foreach pt in blk.progress_types%]'[%pt.id%]'[%unless pt.lst%],[%end%][%end%]
					][%end%]
				}[%unless blk.lst%], [%end%]
			    	[%end%]
			]
		}[%unless panel.lst%], [%+ end%]
		[%end +%]
	},
	popups: {
		[%+ foreach popup in popups%]'[%popup.id%]': {
			buttons: [
				[%foreach btn in popup.buttons%]
				{
					id: '[%btn.id%]',
					image: '[%btn.image%]',
					title: '[%btn.title%]'
					[%if btn.image2%], image2: '[%btn.image2%]'[%end%]
					[%if btn.href%], href: '[%btn.href%]'[%end%]
					[%if btn.target%], target: '[%btn.target%]'[%end%]
					[%if btn.onclick%], onclick: '[%btn.onclick%]'[%end%]
					[%if btn.popup%], popup: '[%btn.popup%]'[%end%]
				}[%unless btn.lst%],[%end%]
				[%end%]
			]
		}[%unless popup.lst%], [%+ end%]
		[%end +%]
	},
	buttons: new Array()
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
			channel_buttons = this.element('chat-channel-buttons', {region: 'north', loadHeight: true});
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
			this.panel('roster-buttons', {region: 'south'})
		]
	});
	var main = this.fixupContentEl({
		id: 'main-container',
		xtype: 'container',
		contentEl: 'main',
		onLayout: function(shallow, forceLayout) {
			if (shallow !== true) {
				Ext.getCmp('main-layout').doLayout(false, forceLayout);
				Game.onLayout();
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

Ext.onReady(function() {
	Ext.QuickTips.init();
	Ext.form.Field.prototype.msgTarget = 'under';
	wait(['game-interface'], function() {
		wait([[%foreach module in js_modules%]'[%module.name%]'[%unless module.lst%],[%end%][%end%]], function() {
			[%+ foreach statement in js_init%][%statement +%]
			[%+ end%]
		});
	});
});
