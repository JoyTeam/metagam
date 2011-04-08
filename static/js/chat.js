var Chat = {};

Chat.input = new Ext.BoxComponent({
	applyTo: 'chat-input-control'
});

//Ext.get('chat-box-content').dom.innerHTML = '';

Chat.content = new Ext.BoxComponent({
	applyTo: 'chat-box-content',
	autoScroll: true,
	style: {
		height: '100%'
	}
});

Chat.msg = function(pkt) {
	var div = document.createElement('div');
	div.innerHTML = pkt.html;
	Chat.content.el.dom.appendChild(div);
	Chat.content.el.scroll('down', 1000000, true);
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

Chat.focus= function() {
	this.input.focus();
}

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
