var Stream = {}

Stream.stream_handlers = new Array();

Stream.run_realplexor = function(marker, cursor) {
	try { debug_log('realplexor: initializing http://' + Game.base_domain + '/rpl; prefix=' + Game.app + '_' + '; marker=' + marker + '; cursor=' + cursor); } catch(e) {}
	this.marker = marker;
	this.personal_channel = 'id_' + Ext.util.Cookies.get('mgsess-' + Game.app);
	this.realplexor = new Dklab_Realplexor('http://' + Game.base_domain + '/rpl', Game.app + '_');
	this.realplexor.setCursor(this.personal_channel, cursor);
	this.realplexor.subscribe(this.personal_channel, this.stream_command.createDelegate(this));
	this.realplexor.execute();
	try { debug_log('realplexor: running'); } catch(e) {}
};

Stream.stream_command = function(cmd, id) {
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
			var cursor = this.realplexor._map[this.personal_channel].cursor;
			try { debug_log('realplexor: marker found'); } catch(e) {}
			this.initialized = true;
			Ext.TaskMgr.start({
				interval: 600000,
				run: this.ping.createDelegate(this)
			});
			this.realplexor.setCursor('global', cursor);
			this.realplexor.subscribe('global', this.stream_command.createDelegate(this));
			try { debug_log('realplexor: cursor=' + cursor + '; initialized'); } catch(e) {}
		}
		return;
	}
	if (cmd.packets && cmd.packets.length) {
		var cursor = this.realplexor._map[id].cursor;
		try { debug_log('realplexor: cursor=' + cursor + '; packets=' + cmd.packets.length); } catch(e) {}
		for (var pack_i = 0; pack_i < cmd.packets.length; pack_i++) {
			this.packet_received(cmd.packets[pack_i]);
		}
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
		}
	});
};

Stream.packet_received = function(pkt) {
	try { debug_log('realplexor: received ' + pkt.method_cls + '.' + pkt.method); } catch(e) {}
	var handler = this.stream_handlers[pkt.method_cls];
	if (!handler) {
		try { debug_log('realplexor: missing class handler'); } catch(e) {}
		return;
	}
	var method = handler[pkt.method];
	if (!method) {
		try { debug_log('realplexor: missing method handler'); } catch(e) {}
		return;
	}
	try {
		(method.createDelegate(handler))(pkt);
	} catch (e) {
		try { debug_log('realplexor: exception in ' + pkt.method_cls + '.' + pkt.method + ': ' + e); } catch(e) {}
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
