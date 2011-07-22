var Chat = {
	channels: new Array(),
	channels_by_id: new Array(),
	chat_filters: new Array(),
	classes: ['auth', 'move'],
	chatbox_limit: 1000
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
		autoScroll: true
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
			this.scroll_bottom();
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
	return this.msg_list({messages: [pkt]})[0];
};

/* Receive message list */
Chat.msg_list = function(pkt) {
	var messages = pkt.messages;
	var divs = new Array();
	var fragments = new Array();
	var scroll = false;
	for (var mi = 0; mi < messages.length; mi++) {
		var msg = messages[mi];
		if (this.mode != 0) {
			var ch = this.channels_by_id[msg.channel];
			if (!ch)
				continue;
		}
		/* message divs are joined into fragments to speed up rendering */
		var fragment_id;
		if (this.mode == 1) {
			fragment_id = ch.id;
		} else {
			fragment_id = '_main';
		}
		var fragment = fragments[fragment_id];
		if (!fragment) {
			fragment = document.createDocumentFragment();
			fragments[fragment_id] = fragment;
		}
		/* formatting message */
		var ctspan = document.createElement('span');
		if (msg.cls) {
			ctspan.className = 'chat-msg-' + msg.cls;
		}
		if (msg.cls && this.chat_filters[msg.cls] === false) {
			ctspan.style.display = 'none';
		}
		ctspan.innerHTML = msg.html;
		var div = document.createElement('div');
		div.className = 'chat-msg';
		if (msg.id)
			div.id = msg.id;
		div.appendChild(ctspan);
		div.className = div.className + ' cmc-' + ch.id;
		if (msg.priv)
			div.className = div.className + ' chat-private';
		/* storing message */
		fragment.appendChild(div);
		if (this.mode == 1) {
			if (ch.id == this.active_channel) {
				scroll = true;
			} else if (ch.btn && msg.hl) {
				ch.btn.el.dom.src = ch.button_image + '-new.png';
			}
		} else if (this.mode == 2) {
			div.style.display = ch.visible ? 'block' : 'none';
			if (ch.visible) {
				scroll = true;
			} else if (ch.btn && msg.hl) {
				ch.btn.el.dom.src = ch.button_image + '-new.png';
			}
		} else if (this.mode == 0) {
			scroll = true;
		}
		divs.push(div);
	}
	/* adding fragments to the chatbox */
	for (var i = 0; i < this.channels.length; i++) {
		var ch = this.channels[i];
		var fragment = fragments[ch.id];
		if (fragment) {
			var container = ch.box_content.el.dom;
			container.appendChild(fragment);
			while (container.childNodes.length > this.chatbox_limit) {
				container.removeChild(container.firstChild);
			}
		}
	}
	var fragment = fragments['_main'];
	if (fragment) {
		var container = this.box_content.el.dom;
		container.appendChild(fragment);
		while (container.childNodes.length > this.chatbox_limit) {
			container.removeChild(container.firstChild);
		}
	}
	if (!pkt.scroll_disable) {
		if (pkt.scroll_bottom) {
			this.scroll_bottom();
		} else if (scroll) {
			this.box_content.el.scroll('down', 1000000, true);
		}
	}
	return divs;
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
		this.scroll_bottom();
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
	if (this.transl) {
		var tokens = this.parse_input(val);
		tokens.text = tokens.text.replace(/([bvgdhzjklmnprstfc])'/g, '$1ь');
		tokens.text = tokens.text.replace(/([BVGDHZJKLMNPRSTFC])'/g, '$1Ь');
		tokens.text = tokens.text.replace(/e'/g, 'э');
		tokens.text = tokens.text.replace(/E'/g, 'Э');
		tokens.text = tokens.text.replace(/sch/g, 'щ');
		tokens.text = tokens.text.replace(/tsh/g, 'щ');
		tokens.text = tokens.text.replace(/S[cC][hH]/g, 'Щ');
		tokens.text = tokens.text.replace(/T[sS][hH]/g, 'Щ');
		tokens.text = tokens.text.replace(/jo/g, 'ё');
		tokens.text = tokens.text.replace(/ju/g, 'ю');
		tokens.text = tokens.text.replace(/ja/g, 'я');
		tokens.text = tokens.text.replace(/yo/g, 'ё');
		tokens.text = tokens.text.replace(/yu/g, 'ю');
		tokens.text = tokens.text.replace(/ya/g, 'я');
		tokens.text = tokens.text.replace(/J[oO]/g, 'Ё');
		tokens.text = tokens.text.replace(/J[uU]/g, 'Ю');
		tokens.text = tokens.text.replace(/J[aA]/g, 'Я');
		tokens.text = tokens.text.replace(/Y[oO]/g, 'Ё');
		tokens.text = tokens.text.replace(/Y[uU]/g, 'Ю');
		tokens.text = tokens.text.replace(/Y[aA]/g, 'Я');
		tokens.text = tokens.text.replace(/zh/g, 'ж');
		tokens.text = tokens.text.replace(/kh/g, 'х');
		tokens.text = tokens.text.replace(/ts/g, 'ц');
		tokens.text = tokens.text.replace(/ch/g, 'ч');
		tokens.text = tokens.text.replace(/sh/g, 'ш');
		tokens.text = tokens.text.replace(/Z[hH]/g, 'Ж');
		tokens.text = tokens.text.replace(/K[hH]/g, 'Х');
		tokens.text = tokens.text.replace(/T[sS]/g, 'Ц');
		tokens.text = tokens.text.replace(/C[hH]/g, 'Ч');
		tokens.text = tokens.text.replace(/S[hH]/g, 'Ш');
		tokens.text = tokens.text.replace(/a/g, 'а');
		tokens.text = tokens.text.replace(/b/g, 'б');
		tokens.text = tokens.text.replace(/v/g, 'в');
		tokens.text = tokens.text.replace(/w/g, 'в');
		tokens.text = tokens.text.replace(/g/g, 'г');
		tokens.text = tokens.text.replace(/d/g, 'д');
		tokens.text = tokens.text.replace(/e/g, 'е');
		tokens.text = tokens.text.replace(/z/g, 'з');
		tokens.text = tokens.text.replace(/i/g, 'и');
		tokens.text = tokens.text.replace(/j/g, 'й');
		tokens.text = tokens.text.replace(/k/g, 'к');
		tokens.text = tokens.text.replace(/l/g, 'л');
		tokens.text = tokens.text.replace(/m/g, 'м');
		tokens.text = tokens.text.replace(/n/g, 'н');
		tokens.text = tokens.text.replace(/o/g, 'о');
		tokens.text = tokens.text.replace(/p/g, 'п');
		tokens.text = tokens.text.replace(/r/g, 'р');
		tokens.text = tokens.text.replace(/s/g, 'с');
		tokens.text = tokens.text.replace(/t/g, 'т');
		tokens.text = tokens.text.replace(/u/g, 'у');
		tokens.text = tokens.text.replace(/f/g, 'ф');
		tokens.text = tokens.text.replace(/h/g, 'х');
		tokens.text = tokens.text.replace(/x/g, 'х');
		tokens.text = tokens.text.replace(/y/g, 'ы');
		tokens.text = tokens.text.replace(/c/g, 'ц');
		tokens.text = tokens.text.replace(/A/g, 'А');
		tokens.text = tokens.text.replace(/B/g, 'Б');
		tokens.text = tokens.text.replace(/V/g, 'В');
		tokens.text = tokens.text.replace(/W/g, 'В');
		tokens.text = tokens.text.replace(/G/g, 'Г');
		tokens.text = tokens.text.replace(/D/g, 'Д');
		tokens.text = tokens.text.replace(/E/g, 'Е');
		tokens.text = tokens.text.replace(/Z/g, 'З');
		tokens.text = tokens.text.replace(/I/g, 'И');
		tokens.text = tokens.text.replace(/J/g, 'Й');
		tokens.text = tokens.text.replace(/K/g, 'К');
		tokens.text = tokens.text.replace(/L/g, 'Л');
		tokens.text = tokens.text.replace(/M/g, 'М');
		tokens.text = tokens.text.replace(/N/g, 'Н');
		tokens.text = tokens.text.replace(/O/g, 'О');
		tokens.text = tokens.text.replace(/P/g, 'П');
		tokens.text = tokens.text.replace(/R/g, 'Р');
		tokens.text = tokens.text.replace(/S/g, 'С');
		tokens.text = tokens.text.replace(/T/g, 'Т');
		tokens.text = tokens.text.replace(/U/g, 'У');
		tokens.text = tokens.text.replace(/F/g, 'Ф');
		tokens.text = tokens.text.replace(/H/g, 'Х');
		tokens.text = tokens.text.replace(/X/g, 'Х');
		tokens.text = tokens.text.replace(/Y/g, 'Ы');
		tokens.text = tokens.text.replace(/C/g, 'Ц');
		val = this.generate_input(tokens);
	}
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

/* Update chat filters */
Chat.filters = function(pkt) {
	this.chat_filters = pkt;
	for (var i = 0; i < this.classes.length; i++) {
		var els = Ext.query('.chat-msg-' + this.classes[i]);
		var cls = this.chat_filters[this.classes[i]] ? 'block' : 'none';
		for (var j = 0; j < els.length; j++) {
			els[j].style.display = cls;
		}
	}
};

/* Update chat message about current location */
Chat.current_location = function(pkt) {
	this.last_location_msg = this.msg_list({
		messages: [{
			id: 'msg-current-location',
			channel: 'loc',
			html: pkt.html,
			cls: 'your-location'
		}],
		scroll_disable: pkt.scroll_disable
	});
};

/* Clear all messages in the loc channel */
Chat.clear_loc = function(pkt) {
	Ext.each(Ext.query('.cmc-loc'), function(el) { el.parentNode.removeChild(el); })
};

/* Scroll screen to the bottom */
Chat.scroll_bottom = function(pkt) {
	this.box_content.el.stopFx();
	this.box_content.el.scroll('down', 1000000, false);
};

/* Activate default channel after loading */
Chat.open_default_channel = function(pkt) {
	if (this.mode == 1) {
		this.tab_open('loc', true);
	}
	if (this.channel_control_element) {
		this.channel_control_element.value = 'loc';
	}
};

Chat.clear = function() {
	if (this.box_content) {
		var container = this.box_content.el.dom;
		while (container.lastChild) {
			container.removeChild(container.lastChild);
		}
	}
	for (var i = 0; i < this.channels.length; i++) {
		var ch = this.channels[i];
		if (ch.box_content) {
			var container = ch.box_content.el.dom;
			while (container.lastChild) {
				container.removeChild(container.lastChild);
			}
		}
	}
}

Chat.translit = function() {
	var btn = Game.buttons['roster-translit'];
	if (!btn)
		return;
	this.transl = !this.transl;
	var src = this.transl ? btn.image2 : btn.image;
	if (src) {
		Ext.each(Ext.query('.btn-roster-translit'), function(el) { el.src = src; });
	}
};

wait(['realplexor-stream'], function() {
	loaded('chat');
});
