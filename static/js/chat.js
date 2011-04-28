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

Chat.input = new Ext.BoxComponent({
	applyTo: 'chat-input-control'
});

Chat.channel_new = function(ch) {
	this.channels.push(ch);
	this.channels_by_id[ch.id] = ch;
	ch.content = new Ext.BoxComponent({
		autoEl: {
			tag: 'div'
		},
		renderTo: 'chat-box-content',
		html: 'Initial content for channel ' + ch.id,
		hidden: true
	});
	ch.btn = Ext.get('chat-channel-button-' + ch.id);
};

Chat.tab_open = function(id) {
	if (id == this.active_channel)
		return;
	var ch = this.channels_by_id[id];
	if (!ch)
		return;
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
};

Chat.msg = function(pkt) {
	var ch = this.channels_by_id[pkt.channel];
	if (!ch)
		ch = this.channels_by_id['main'];
	var div = document.createElement('div');
	div.innerHTML = pkt.html;
	ch.content.el.dom.appendChild(div);
	this.content.el.scroll('down', 1000000, true);
};

Chat.submit = function() {
	var val = this.input.el.dom.value;
	if (!val)
		return;
	this.input.disable();
	Ext.Ajax.request({
		url: '/chat/post',
		method: 'POST',
		params: {
			text: val
		},
		success: (function (response, opts) {
			this.input.enable();
			if (response && response.getResponseHeader) {
				var res = Ext.util.JSON.decode(response.responseText);
				if (res.ok) {
					this.input.el.dom.value = '';
				}
			}
			this.input.focus();
		}).createDelegate(this),
		failure: (function (response, opts) {
			this.input.enable();
			this.input.focus();
		}).createDelegate(this)
	});
};

Chat.focus = function() {
	this.input.focus();
};

wait(['realplexor-stream'], function() {

	Stream.stream_handler('chat', Chat);

	Chat.input.el.on('keypress', function(e, t, o) {
		if (e.getKey() == 13) {
			e.preventDefault();
			Chat.submit();
		}
	});

	loaded('chat');
});
