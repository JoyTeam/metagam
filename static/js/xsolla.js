Xsolla = {};

Xsolla.paystation = function() {
	if (!this.initialized) {
		this.url = 'https://secure.xsolla.com/paystation/?projectid=' + this.project + '&id_theme=1&local=' + this.lang + '&v1=' + this.name;
		this.win = new Ext.Window({
			id: 'payment-window',
			modal: true,
			closeAction: 'hide',
			header: false,
			closable: false,
			items: Game.element('payment', {}, {
				items: {
					id: 'paystation-iframe',
					xtype: 'mif',
					border: false,
					defaultSrc: this.url,
					frameConfig: {
						name: 'paystation'
					}
				}
			})
		});
	}
	this.win.show();
	if (!this.initialized) {
		var screen = Ext.getBody().getViewSize();
		this.win_x = 50;
		this.win_y = 50;
		this.win.setWidth(screen.width - 100);
		this.win.setHeight(screen.height - 100);
		this.win.mon(this.win, 'beforehide', function() {
			var pos = this.win.getPosition();
			this.win_x = pos[0];
			this.win_y = pos[1];
		}, this);
		this.win.mon(this.win.mask, 'click', function() {
			this.win.hide();
		}, this);
		this.win.mon(this.win, 'resize', function() {
			Ext.getCmp('payment-container').doLayout();
		}, this);
		var km = this.win.getKeyMap();
		km.on(27, this.win.onEsc, this.win);
		km.enable();
		Ext.getCmp('payment-container').doLayout();
		this.initialized = true;
	} else {
		Ext.getCmp('paystation-iframe').setSrc(this.url);
	}
	this.win.setPosition(this.win_x, this.win_y);
};

loaded('xsolla');
