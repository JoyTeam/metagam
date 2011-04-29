var Chat = {
	channels: new Array(),
	channels_by_id: new Array(),
	button_images: new Array()
};

Chat.content = new Ext.BoxComponent({
	applyTo: 'chat-box-content',
	autoScroll: true,
	style: {
		height: '100%'
	}
});

Chat.input_control = new Ext.BoxComponent({
	applyTo: 'chat-input-control'
});

Chat.channel_control = Ext.getDom('chat-channel-control');

Chat.channel_new = function(ch) {
	this.channels.push(ch);
	this.channels_by_id[ch.id] = ch;
	if (this.mode == 1) {
		ch.content = new Ext.BoxComponent({
			autoEl: {
				tag: 'div'
			},
			renderTo: 'chat-box-content',
			hidden: true
		});
	} else if (this.mode == 2) {
		ch.visible = true;
	}
	ch.btn = Ext.get('chat-channel-button-' + ch.id);
};

Chat.tab_open = function(id) {
	if (id != this.active_channel) {
		var ch = this.channels_by_id[id];
		if (ch) {
			if (this.active_channel) {
				var old_ch = this.channels_by_id[this.active_channel];
				if (old_ch) {
					old_ch.content.hide();
					if (this.mode == 1 && old_ch.btn)
						old_ch.btn.dom.src = this.button_images[this.active_channel] + '-off.gif';
				}
			}
			this.active_channel = id;
			ch.content.show();
			this.content.el.scroll('down', 1000000, false);
			if (this.mode == 1 && ch.btn) {
				ch.btn.dom.src = this.button_images[id] + '-on.gif';
			}
		}
	}
	this.focus();
};

Chat.focus = function() {
	var cht = Ext.getCmp('chat-input-control');
	if (cht)
		cht.focus();
};

Chat.msg = function(pkt) {
	var ch = this.channels_by_id[pkt.channel];
	if (!ch)
		ch = this.channels_by_id['main'];
	var div = document.createElement('div');
	div.innerHTML = pkt.html;
	if (this.mode == 1) {
		ch.content.el.dom.appendChild(div);
		this.content.el.scroll('down', 1000000, true);
	} else if (this.mode == 2) {
		div.className = 'cmc-' + ch.id;
		div.style.display = ch.visible ? 'block' : 'none';
		this.content.el.dom.appendChild(div);
		if (ch.visible)
			this.content.el.scroll('down', 1000000, true);
	}
};

Chat.channel_toggle = function(id) {
	var ch = this.channels_by_id[id];
	if (ch) {
		if (ch.visible)
			this.channel_hide(id);
		else
			this.channel_show(id);
		this.content.el.scroll('down', 1000000, false);
	}
};

Chat.channel_show = function(id) {
	var ch = this.channels_by_id[id];
	if (ch && !ch.visible) {
		if (this.mode == 2 && ch.btn) {
			ch.btn.dom.src = this.button_images[id] + '-on.gif';
		}
		Ext.each(Ext.query('.cmc-' + ch.id), function(el) { el.style.display = 'block'; })
		ch.visible = true;
	}
};

Chat.channel_hide = function(id) {
	var ch = this.channels_by_id[id];
	if (ch && ch.visible) {
		if (this.mode == 2 && ch.btn) {
			ch.btn.dom.src = this.button_images[id] + '-off.gif';
		}
		Ext.each(Ext.query('.cmc-' + ch.id), function(el) { el.style.display = 'none'; })
		ch.visible = false;
	}
};

Chat.submit = function() {
	if (this.submit_locked)
		return;
	var val = this.input_control.el.dom.value;
	if (!val)
		return;
	this.submit_locked = true;
	this.input_control.el.dom.onkeypress = function() { return false; }
	var channel = this.active_channel;
	if (this.channel_control) {
		channel = this.channel_control.value;
	}
	Ext.Ajax.request({
		url: '/chat/post',
		method: 'POST',
		params: {
			text: val,
			channel: channel
		},
		success: (function (response, opts) {
			this.submit_locked = false;
			this.input_control.el.dom.onkeypress = undefined;
			if (response && response.getResponseHeader) {
				var res = Ext.util.JSON.decode(response.responseText);
				if (res.ok) {
					this.input_control.el.dom.value = '';
					this.focus();
					if (this.mode == 2) {
						this.channel_show(res.channel);
					}
				} else if (res.error) {
					Game.msg(gt.gettext('Error'), res.error);
				}
			}
		}).createDelegate(this),
		failure: (function (response, opts) {
			this.submit_locked = false;
			this.input_control.el.dom.onkeypress = undefined;
			this.focus();
		}).createDelegate(this)
	});
};

wait(['realplexor-stream'], function() {

	Stream.stream_handler('chat', Chat);

	Chat.input_control.el.on('keypress', function(e, t, o) {
		if (e.getKey() == 13) {
			e.preventDefault();
			Chat.submit();
		}
	});

	loaded('chat');
});
