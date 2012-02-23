var admin_root = '';
var Game = {
	app: '[%app%]',
	domain: '[%domain%]',
	base_domain: '[%base_domain%]',
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
							[%if btn.qevent%], qevent: '[%btn.qevent%]'[%end%]
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
					[%if btn.qevent%], qevent: '[%btn.qevent%]'[%end%]
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
			channel_buttons = this.element('chat-channel-buttons', {region: 'west'}, {vertical: true, layout: 'auto', no_height: true});
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
			this.element('chat-roster-header', {region: 'north', loadHeight: true}),
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
			cls: 'main-iframe',
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
				[%if layout.panel_main_right%], this.panel('main-right', {region: 'east', vertical: true, right: true})[%end%]
			]
		};
	[%end%]
	[%if layout.scheme == 1%]
	chat.region = [%if layout.chat_width%]'west'[%else%]'center'[%end%];
	chat.minWidth = 200;
	[%if layout.chat_width%]chat.width = [%layout.chat_width%];[%end%]
	roster.region = [%if layout.chat_width%]'center'[%else%]'east'[%end%];
	[%if layout.chat_width%]chat[%else%]roster[%end%].split = true;
	[%if layout.roster_width%]roster.width = [%layout.roster_width%];[%end%]
	roster.minWidth = 300;
	main.region = [%if layout.main_frame_height%]'north'[%else%]'center'[%end%];
	main.minHeight = 200;
	main.split = true;
	[%if layout.main_frame_height%]main.height = [%layout.main_frame_height%];[%end%]
	var content = new Ext.Container({
		id: 'page-content',
		layout: 'border',
		items: [
			{
				id: 'chat-and-roster',
				xtype: 'container',
				region: [%if layout.chat_height%]'south'[%else%]'center'[%end%],
				[%if layout.chat_height%]height: [%layout.chat_height%],[%end%]
				minHeight: 100,
				layout: 'border',
				split: true,
				items: [chat, roster]
			},
			main
		]
	});
	[%elsif layout.scheme == 2%]
	roster.region = [%if layout.roster_width%]'east'[%else%]'center'[%end%];
	[%if layout.roster_width%]roster.width = [%layout.roster_width%];[%end%]
	roster.minWidth = 300;
	roster.split = true;
	chat.region = [%if layout.chat_height%]'south'[%else%]'center'[%end%];
	chat.split = true;
	chat.height = 250;
	chat.minHeight = 100;
	main.region = [%if layout.main_frame_height%]'north'[%else%]'center'[%end%];
	[%if layout.main_frame_height%]main.height = [%layout.main_frame_height%];[%end%]
	main.minHeight = 200;
	main.split = true;
	var content = new Ext.Container({
		id: 'page-content',
		layout: 'border',
		items: [
			roster,
			{
				id: 'main-and-chat',
				xtype: 'container',
				region: [%if layout.main_frame_width%]'west'[%else%]'center'[%end%],
				[%if layout.main_frame_width%]width: [%layout.main_frame_width%],[%end%]
				minWidth: 300,
				split: true,
				layout: 'border',
				items: [main, chat]
			}
		]
	});
	[%elsif layout.scheme == 3%]
	main.region = [%if layout.main_frame_width%]'west'[%else%]'center'[%end%];
	[%if layout.main_frame_width%]main.width = [%layout.main_frame_width%];[%end%]
	main.split = true;
	main.minWidth = 300;
	roster.region = [%if layout.roster_height%]'south'[%else%]'center'[%end%];
	[%if layout.roster_height%]roster.height = [%layout.roster_height%];[%end%]
	roster.minHeight = 100;
	roster.split = true;
	chat.region = [%if layout.chat_height%]'north'[%else%]'center'[%end%];
	chat.minHeight = 100;
	[%if layout.chat_height%]chat.height = [%layout.chat_height%];[%end%]
	chat.split = true;
	var content = new Ext.Container({
		id: 'page-content',
		layout: 'border',
		items: [
			main,
			{
				id: 'roster-and-chat',
				xtype: 'container',
				region: [%if layout.roster_width%]'east'[%else%]'center'[%end%],
				[%if layout.roster_width%]width: [%layout.roster_width%],[%end%]
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
	panel_top.region = 'north';
	content.region = 'center';
	content = {
		id: 'page-content-2',
		xtype: 'container',
		layout: 'border',
		items: [
			panel_top,
			content
		]
	};
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

try { debug_log('interface: waiting for extjs'); } catch(e) {}

Ext.onReady(function() {
	try { debug_log('interface: extjs ready'); } catch(e) {}
	Ext.QuickTips.init();
	Ext.form.Field.prototype.msgTarget = 'under';
	try { debug_log('interface: extjs initialized'); } catch(e) {}
	wait(['game-interface'], function() {
		wait([[%foreach module in js_modules%]'[%module.name%]'[%unless module.lst%],[%end%][%end%]], function() {
			try { debug_log('js: all modules loaded'); } catch(e) {}
			[%+ foreach ent in js_init%]
				try { debug_log('js: [%ent.js_cmd%]'); } catch(e) {}
				try { [%+ ent.cmd +%] } catch (e) { try { debug_log('js: exception in [%ent.js_cmd%]: ' + e); } catch(e) {} Game.error(gt.gettext('Exception'), e) }
			[%+ end%]
			try { debug_log('js: init complete'); } catch(e) {}
		});
	});
});
