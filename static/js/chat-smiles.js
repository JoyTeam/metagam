var Smiles = {
	win: new Ext.Window({
		id: 'smiles-window',
		modal: true,
		closeAction: 'hide',
		width: 400,
		height: 300,
		header: false,
		closable: false,
		items: Game.element('smiles', {}, {autoScroll: true})
	})
};

Smiles.show = function() {
	this.win.show();
	if (!this.initialized) {
		var screen = Ext.getBody().getViewSize();
		this.win_x = screen.width - 500;
		this.win_y = screen.height - 400;
		this.win.mon(this.win, 'beforehide', function() {
			var pos = this.win.getPosition();
			this.win_x = pos[0];
			this.win_y = pos[1];
		}, this);
		this.win.mon(this.win.mask, 'click', function() {
			this.win.hide();
		}, this);
		this.win.mon(this.win, 'resize', function() {
			Ext.getCmp('smiles-container').doLayout();
		}, this);
		var km = this.win.getKeyMap();
		km.on(27, this.win.onEsc, this.win);
		km.enable();
		if (this.smiles) {
			var html = '';
			for (var i = 0; i < this.smiles.length; i++) {
				var smile = this.smiles[i];
				html += '<img src="' + smile.image + '" alt="" onclick="Smiles.add(\'' + smile.code + '\')" class="clickable" /> ';
			}
			Ext.get('smiles-content').update(html);
		}
		Ext.getCmp('smiles-container').doLayout();
		this.initialized = true;
	}
	this.win.setPosition(this.win_x, this.win_y);
};

Smiles.add = function(code) {
	var input = Chat.input_control.dom;
	var inputtext = new String(input.value);
	input.focus();
	input.value = inputtext + ((inputtext.length == 0 || inputtext.substr(inputtext.length - 1, 1) == ' ') ? '' : ' ') + code + ' ';
	this.win.hide();
};

loaded('chat-smiles');
