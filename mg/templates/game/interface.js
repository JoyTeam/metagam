Ext.onReady(function() {
	Ext.QuickTips.init();
	Ext.form.Field.prototype.msgTarget = 'under';

	var topmenu = {
		xtype: 'box',
		height: 40,
		autoEl: {
			tag: 'div',
			html: 'TOPMENU'
		}
	};
	var chat = {
		xtype: 'box',
		autoEl: {
			tag: 'div',
			html: 'CHAT'
		}
	};
	var roster = {
		xtype: 'box',
		autoEl: {
			tag: 'div',
			html: 'ROSTER'
		}
	};
	var main = {
		xtype: 'iframepanel',
		border: false,
		defaultSrc: 'http://www.kaluga-comfort.ru',
		frameConfig: {
			name: 'main'
		}
	};

	[%if layout.scheme == 1%]
	topmenu.region = 'north';
	chat.region = 'center';
	chat.minWidth = 200;
	roster.region = 'east';
	roster.split = true;
	roster.width = 300;
	roster.minSize = 300;
	main.region = 'center';
	main.minHeight = 200;
	new Ext.Viewport({
		layout: 'border',
		items:[
			topmenu,
			{
				region: 'south',
				height: 250,
				minHeight: 100,
				layout: 'border',
				split: true,
				border: false,
				items: [chat, roster]
			},
			main
		]
	});
	[%else%]
	new Ext.Viewport({
		html: 'Misconfigured layout scheme'
	});
	[%end%]
});
