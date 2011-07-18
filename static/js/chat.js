var Chat = {
	channels: new Array(),
	channels_by_id: new Array()
};

Chat.initialize = function() {
	this.input_control = Ext.get('chat-input-control');
	this.channel_control_element = Ext.getDom('chat-channel-control');
	this.buttons_content = Ext.get('chat-channel-buttons-content');
	this.roster_header_element = Ext.get('chat-roster-header-content');
	this.roster_chars_element = Ext.get('chat-roster-characters-content');
	Stream.stream_handler('chat', this);
	this.input_control.on('keypress', function(e, t, o) {
		if (e.getKey() == 13) {
			e.preventDefault();
			Chat.submit();
		}
	});
	this.box_content = new Ext.BoxComponent({
		applyTo: 'chat-box-content',
		autoScroll: true,
		style: {
			height: '100%'
		}
	});
};

/* Create channel: chat tab, channel button, roster tab, channel selection option */
Chat.channel_create = function(ch) {
	if (this.channels_by_id[ch.id])
		return;
	this.channels.push(ch);
	this.channels_by_id[ch.id] = ch;
	if (ch.roster) {
		this.roster_tab_create(ch);
	}
	if (this.mode == 1) {
		if (ch.chatbox) {
			this.channel_button_create(ch);
		}
		this.channel_tab_create(ch);
	}
	if (this.mode == 2 && ch.switchable) {
		ch.visible = true;
		this.channel_button_create(ch);
	}
	if (ch.writable && this.channel_control_element) {
		var opt = document.createElement('option');
		opt.value = ch.id;
		opt.innerHTML = htmlescape(ch.title);
		ch.channel_control_opt = opt;
		this.channel_control_element.appendChild(opt);
	}
};

/* Destroy channel and everything related */
Chat.channel_destroy = function(ch) {
	var channels_by_id= new Array();
	var channels = new Array();
	for (var i = 0; i < this.channels.length; i++) {
		var c = this.channels[i];
		if (c.id != ch.id) {
			channels.push(c);
			channels_by_id[c.id] = c;
		}
	}
	this.channels = channels;
	this.channels_by_id = channels_by_id;
	if (ch.roster) {
		this.roster_tab_destroy(ch);
	}
	if (this.mode == 1) {
		this.channel_tab_destroy(ch);
		if (ch.chatbox) {
			this.channel_button_destroy(ch);
		}
	}
	if (this.mode == 2 && ch.switchable) {
		this.channel_button_destroy(ch);
	}
	if (ch.channel_control_opt) {
		this.channel_control_element.removeChild(ch.channel_control_opt);
		ch.channel_control_opt = undefined;
	}
	if (this.mode == 1 && this.active_channel == ch.id) {
		this.open_first_tab();
	}
};

/* Create roster tab */
Chat.roster_tab_create = function(ch) {
	if (!this.roster_chars_element)
		return;
	ch.roster_characters = new Array();
	ch.roster_characters_by_id = new Array();
	if (this.roster_chars_element) {
		ch.roster_chars = new Ext.BoxComponent({
			renderTo: this.roster_chars_element,
			hidden: true,
			cls: 'chat-roster-characters-content2'
		});
	}
	if (!this.active_roster_channel) {
		this.active_roster_channel = ch.id;
		if (ch.roster_chars) {
			ch.roster_chars.show();
		}
	}
	this.roster_header_update();
};

/* Remove all characters from the roster */
Chat.roster_clear = function(ch) {
	if (!this.roster_chars_element)
		return;
	for (var i = 0; i < ch.roster_characters.length; i++) {
		var c = ch.roster_characters[i];
		if (c.element) {
			c.element.destroy()
		}
	}
	ch.roster_characters = new Array();
	ch.roster_characters_by_id = new Array();
};

/* Destroy roster tab */
Chat.roster_tab_destroy = function(ch) {
	if (!this.roster_chars_element)
		return;
	if (ch.roster_chars) {
		ch.roster_chars.destroy();
		ch.roster_chars = undefined;
	}
	if (this.active_roster_channel == ch.id) {
		if (this.channels.length) {
			var c = this.channels[0]
			this.active_roster_channel = c.id;
			if (c.roster_chars) {
				c.roster_chars.show();
			}
		} else {
			this.active_roster_channel = undefined;
		}
	}
	this.roster_header_update();
	this.channel_button_destroy(ch);
};

/* Update roster menu */
Chat.roster_header_update = function() {
	if (!this.roster_header_element)
		return;
	var tokens = new Array();
	for (var i = 0; i < this.channels.length; i++) {
		var ch = this.channels[i];
		if (ch.roster) {
			var html = htmlescape(ch.title);
			if (ch.id != this.active_roster_channel) {
				html = '<span class="chat-roster-channel chat-roster-channel-clickable" onclick="Chat.roster_tab(\'' + ch.id + '\')">' + html + '</span>';
			} else {
				html = '<span class="chat-roster-channel">' + html + '</span>';
			}
			tokens.push(html);
		}
	}
	this.roster_header_element.update(tokens.join('&nbsp;| '));
};

/* Open specified roster tab */
Chat.roster_tab = function(id) {
	if (this.active_roster_channel) {
		var ch = this.channels_by_id[this.active_roster_channel];
		if (ch && ch.roster_chars) {
			ch.roster_chars.hide();
		}
	}
	this.active_roster_channel = id;
	this.roster_header_update();
	var ch = this.channels_by_id[id];
	if (ch && ch.roster_chars) {
		ch.roster_chars.show();
	}
};

/* Create channel tab - element containing channel messages */
Chat.channel_tab_create = function(ch) {
	ch.box_content = new Ext.BoxComponent({
		autoEl: {
			tag: 'div',
			cls: 'chat-channel-content'
		},
		renderTo: this.box_content.el,
		hidden: true
	});
};

/* Destroy channel tab */
Chat.channel_tab_destroy = function(ch) {
	if (ch.box_content) {
		ch.box_content.destroy();
		ch.box_content = undefined;
	}
};

/* Create channel button */
Chat.channel_button_create = function(ch) {
	var state;
	var onclick;
	if (this.mode == 1) {
		state = (this.active_channel == ch.id);
		onclick = 'return Chat.tab_open(\'' + ch.id + '\', true);';
	} else if (this.mode == 2) {
		state = ch.visible;
		onclick = 'return Chat.channel_toggle(\'' + ch.id + '\');';
	}
	ch.btn = new Ext.BoxComponent({
		autoEl: {
			tag: 'img',
			src: ch.button_image + (state ? '-on.png' : '-off.png'),
			onclick: onclick,
			cls: 'chat-button',
			title: htmlescape(ch.title)
		},
		renderTo: this.buttons_content
	});
};

/* Destroy channel button */
Chat.channel_button_destroy = function(ch) {
	if (ch.btn) {
		ch.btn.destroy();
		ch.btn = undefined;
	}
};

/* Open chatbox tab with given id */
Chat.tab_open = function(id, change_write_selector) {
	if (id != this.active_channel) {
		var ch = this.channels_by_id[id];
		if (ch && ch.chatbox) {
			if (this.active_channel) {
				var old_ch = this.channels_by_id[this.active_channel];
				if (old_ch) {
					old_ch.box_content.hide();
					if (this.mode == 1 && old_ch.btn) {
						old_ch.btn.el.dom.src = old_ch.button_image + '-off.png';
					}
				}
			}
			this.active_channel = id;
			ch.box_content.show();
			this.box_content.el.scroll('down', 1000000, false);
			if (this.mode == 1 && ch.btn) {
				ch.btn.el.dom.src = ch.button_image + '-on.png';
			}
		}
		if (ch && change_write_selector && this.channel_control_element) {
			this.channel_control_element.value = id;
		}
	}
	this.focus();
};

/* Give focus to the chat input control */
Chat.focus = function() {
	var cht = Ext.getDom('chat-input-control');
	if (cht)
		cht.focus();
};

/* Receive message from the server */
Chat.msg = function(pkt) {
	if (this.mode != 0) {
		var ch = this.channels_by_id[pkt.channel];
		if (!ch)
			return;
	}
	var div = document.createElement('div');
	div.innerHTML = pkt.html;
	if (this.mode == 1) {
		ch.box_content.el.dom.appendChild(div);
		if (ch.id == this.active_channel) {
			this.box_content.el.scroll('down', 1000000, true);
		} else if (ch.btn) {
			ch.btn.el.dom.src = ch.button_image + '-new.png';
		}
	} else if (this.mode == 2) {
		div.className = 'cmc-' + ch.id;
		div.style.display = ch.visible ? 'block' : 'none';
		this.box_content.el.dom.appendChild(div);
		if (ch.visible) {
			this.box_content.el.scroll('down', 1000000, true);
		} else if (ch.btn) {
			ch.btn.el.dom.src = ch.button_image + '-new.png';
		}
	} else if (this.mode == 0) {
		this.box_content.el.dom.appendChild(div);
		this.box_content.el.scroll('down', 1000000, true);
	}
};

/* Toggle chatbox tab visibility */
Chat.channel_toggle = function(id) {
	var ch = this.channels_by_id[id];
	if (ch) {
		if (ch.visible) {
			this.channel_hide(id);
		} else {
			this.channel_show(id);
		}
		this.box_content.el.scroll('down', 1000000, false);
	}
	this.focus();
};

/* Show chatbox tab */
Chat.channel_show = function(id) {
	var ch = this.channels_by_id[id];
	if (ch && !ch.visible) {
		if (this.mode == 2 && ch.btn) {
			ch.btn.el.dom.src = ch.button_image + '-on.png';
		}
		Ext.each(Ext.query('.cmc-' + ch.id), function(el) { el.style.display = 'block'; })
		ch.visible = true;
	}
};

/* Hide chatbox tab */
Chat.channel_hide = function(id) {
	var ch = this.channels_by_id[id];
	if (ch && ch.visible) {
		if (this.mode == 2 && ch.btn) {
			ch.btn.el.dom.src = ch.button_image + '-off.png';
		}
		Ext.each(Ext.query('.cmc-' + ch.id), function(el) { el.style.display = 'none'; })
		ch.visible = false;
	}
};

/* Submit chat message to the server */
Chat.submit = function() {
	if (this.submit_locked)
		return;
	var val = this.input_control.dom.value;
	if (!val)
		return;
	this.submit_locked = true;
	this.input_control.dom.onkeypress = function() { return false; }
	var channel = this.active_channel;
	if (this.channel_control_element && this.channel_control_element.value) {
		channel = this.channel_control_element.value;
	} else if (this.mode == 1) {
		channel = this.active_channel;
	}
	if (this.mode == 1) {
		this.tab_open(channel);
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
			this.input_control.dom.onkeypress = function() { return true; }
			if (response && response.getResponseHeader) {
				var res = Ext.util.JSON.decode(response.responseText);
				this.focus();
				if (res.ok) {
					this.input_control.dom.value = '';
					if (this.mode == 1) {
						this.tab_open(res.channel);
					} else if (this.mode == 2) {
						this.channel_show(res.channel);
					}
				} else if (res.error) {
					Game.error(res.hide_title ? '' : gt.gettext('Error'), res.error);
				}
			}
		}).createDelegate(this),
		failure: (function (response, opts) {
			this.submit_locked = false;
			this.input_control.dom.onkeypress = function() { return true; }
			this.focus();
			Game.error(gt.gettext('Error'), gt.gettext('Couldn\'t deliver message to the server'));
		}).createDelegate(this)
	});
};

/* Click on the character nick
 * names - list of character names
 * priv - true if clicked on private message and false otherwise
 */
Chat.click = function(names, priv) {
	if (this.submit_locked)
		return false;
	var tokens = this.parse_input(this.input_control.dom.value);
	/* ensure all names are in the list */
	var existing = new Array();
	for (var i = 0; i < tokens.recipients.length; i++) {
		existing[tokens.recipients[i].name] = true;
	}
	var anybody_added = false;
	for (var i = 0; i < names.length; i++) {
		if (!existing[names[i]]) {
			anybody_added = true;
			tokens.recipients.push({name: names[i]});
		}
	}
	/* if anybody added to the list - apply original 'priv' setting.
	 * otherwise invert current private selection */
	if (!anybody_added) {
		priv = !tokens.recipients[0].priv
	}
	for (var i = 0; i < tokens.recipients.length; i++) {
		tokens.recipients[i].priv = priv;
	}
	this.focus();
	this.input_control.dom.value = this.generate_input(tokens);
	return false;
};

/* Parse chat input string and return parsed structure */
Chat.parse_input = function(val) {
	var tokens = {
		commands: [],
		recipients: [],
		text: val
	};
	/* extracting commands */
	while (true) {
		var res = /^\s*\/(\S+)\s*(.*)/.exec(tokens.text);
		if (!res)
			break;
		tokens.commands.push(res[1]);
		tokens.text = res[2];
	}
	/* extracting recipients */
	while (true) {
		var res = /^\s*(to|private)\s*\[([^\]]+)\]\s*(.*)/.exec(tokens.text);
		if (!res)
			break;
		tokens.recipients.push({
			priv: res[1] == 'private',
			name: res[2]
		});
		tokens.text = res[3];
	}
	return tokens;
};

/* Generate chat input string based on the given structure */
Chat.generate_input = function(tokens) {
	var res = '';
	for (var i = 0; i < tokens.commands.length; i++) {
		res += '/' + tokens.commands[i] + ' ';
	}
	for (var i = 0; i < tokens.recipients.length; i++) {
		var rec = tokens.recipients[i];
		res += (rec.priv ? 'private' : 'to') + ' [' + rec.name + '] ';
	}
	res += tokens.text;
	return res;
};

/* Add a new character to the roster tab */
Chat.roster_add = function(pkt) {
	var ch = this.channels_by_id[pkt.channel];
	if (!ch)
		return;
	var char_info = pkt.character;
	var character = ch.roster_characters_by_id[char_info.id];
	if (character) {
		character.html = char_info.html;
		character.name = char_info.name;
		if (character.element) {
			character.element.el.update(char_info.html);
		}
		return;
	}
	var character = char_info;
	if (ch.roster_chars) {
		character.element = new Ext.BoxComponent({
			renderTo: ch.roster_chars.el,
			html: '<span class="chat-roster-char chat-clickable" onclick="return Chat.click([\'' + jsencode(char_info.name) + '\']);">' + htmlescape(char_info.name) + '</span>'
		});
	}
	ch.roster_characters.push(character);
	ch.roster_characters_by_id[character.id] = character;
};

/* Remove a character from the roster tab */
Chat.roster_remove = function(pkt) {
	var ch = this.channels_by_id[pkt.channel];
	if (!ch)
		return;
	var character = ch.roster_characters_by_id[pkt.character];
	if (!character)
		return;
	var characters = new Array();
	var characters_by_id = new Array();
	for (var i = 0; i < ch.roster_characters.length; i++) {
		var c = ch.roster_characters[i];
		if (c.id != character.id) {
			characters.push(c);
			characters_by_id[c.id] = c;
		}
	}
	ch.roster_characters = characters;
	ch.roster_characters_by_id = characters_by_id;
	if (character.element) {
		character.element.destroy();
		character.element = undefined;
	}
	if (character.id == Game.character) {
		if (ch.permanent) {
			this.roster_clear(ch);
		} else {
			this.channel_destroy(ch);
		}
	}
};

/* Supply full of channels to the client. Client must synchronize existing channels with received ones */
Chat.reload_channels = function(pkt) {
	var remaining = new Array();
	for (var i = 0; i < pkt.channels.length; i++) {
		var ch = pkt.channels[i];
		this.channel_create(ch);
		remaining[ch.id] = true;
	}
	for (var i = this.channels.length - 1; i >= 0; i--) {
		var ch = this.channels[i];
		if (!remaining[ch.id]) {
			this.channel_destroy(ch);
		}
	}
	if (this.mode == 1 && !this.active_channel) {
		this.open_first_tab();
	}
};

/* Open the first tab with chatbox */
Chat.open_first_tab = function() {
	if (this.channels.length) {
		for (var i = 0; i < this.channels.length; i++) {
			var ch = this.channels[i];
			if (ch.chatbox) {
				this.tab_open(ch.id, true);
				return;
			}
		}
	}
	this.active_channel = undefined;
};

Chat.clear = function() {
	alert('Clearing chat');
}

Chat.translit = function() {
	alert('Switching translit');
}

wait(['realplexor-stream'], function() {
	loaded('chat');
});
