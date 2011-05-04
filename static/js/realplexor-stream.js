var Stream = {}

Stream.stream_handlers = new Array();

Stream.run_realplexor = function(marker) {
	this.marker = marker;
	this.personal_channel = 'id_' + Ext.util.Cookies.get('mgsess-' + Game.app);
	this.realplexor = new Dklab_Realplexor('http://rpl.' + Game.domain + '/rpl', Game.app + '_');
	this.realplexor.setCursor(this.personal_channel, 0);
	this.realplexor.subscribe(this.personal_channel, this.stream_command.createDelegate(this));
	this.realplexor.execute();
};

Stream.stream_command = function(cmd, id)
{
	if (this.initialized) {
		if (cmd.marker) {
			this.initialized = false;
			Ext.MessageBox.show({
				title: gt.gettext('Error'),
				msg: gt.gettext('Connection terminated'),
				buttons: Ext.MessageBox.OK,
				icon: Ext.MessageBox.ERROR,
				fn: function() {
					Game.close();
				}
			});
			return;
		}
	} else {
		if (cmd.marker == this.marker) {
			this.initialized = true;
			Ext.TaskMgr.start({
				interval: 600000,
				run: this.ping.createDelegate(this)
			});
			var cursor = this.realplexor._map[this.personal_channel].cursor;
			this.realplexor.setCursor('global', cursor);
			this.realplexor.subscribe('global', this.stream_command.createDelegate(this));
		}
		return;
	}
	if (cmd.packets) {
		for (var pack_i = 0; pack_i < cmd.packets.length; pack_i++)
			this.packet_received(cmd.packets[pack_i]);
	}
};

Stream.ping = function() {
	Ext.Ajax.request({
		url: '/stream/ready',
		method: 'POST',
		success: function (response, opts) {
			if (response && response.getResponseHeader) {
				var res = Ext.util.JSON.decode(response.responseText);
				if (res.ok) {
					return;
				}
			}
			Game.close();
		},
	});
};

Stream.packet_received = function(pkt) {
	var handler = this.stream_handlers[pkt.cls];
	if (!handler)
		return;
	var method = handler[pkt.method];
	if (!method)
		return;
	try {
		(method.createDelegate(handler))(pkt);
	} catch (e) {
		Game.error(gt.gettext('Exception'), e);
	}
};

Stream.stream_handler = function(tag, cls) {
	this.stream_handlers[tag] = cls;
};

Stream.stream_handler('stream', Stream);
Stream.stream_handler('game', Game);

wait(['realplexor'], function() {
	loaded('realplexor-stream');
});
