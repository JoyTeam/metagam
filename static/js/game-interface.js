Game.progress = new Array();

Game.now = function() {
	return (new Date()).getTime();
};

Game.reload = function() {
	Stream.initialized = false;
	var frm = document.createElement('form');
	frm.method = 'post';
	frm.action = '/';
	var inp = document.createElement('input');
	inp.type = 'hidden';
	inp.name = 'session';
	inp.value = Ext.util.Cookies.get('mgsess-' + Game.app);
	frm.appendChild(inp);
	Ext.getBody().dom.appendChild(frm);
	frm.submit();
};

Game.close = function() {
	Stream.initialized = false;
	document.location = 'http://' + Game.domain;
};

Game.logout = function() {
	Stream.initialized = false;
	document.location = 'http://' + Game.domain + '/auth/logout';
};

Game.msg = function(title, str, add_cls) {
	if (!this.msgCt){
		this.msgCt = Ext.DomHelper.insertFirst(document.body, {id: 'msg-div'}, true);
	}
	var m = Ext.DomHelper.append(this.msgCt, '<div class="msg' + (add_cls ? ' ' + add_cls : '') + '">' + (title ? '<h3>' + title + '</h3>' : '') + '<p>' + str + '</p></div>', true);
	m.hide();
	m.slideIn('t').pause(3).ghost('t', {remove: true});
};

Game.info = function(title, str) {
	this.msg(title, str, 'msg-info');
};

Game.error = function(title, str) {
	this.msg(title, str, 'msg-error');
};

Game.main_open = function(uri) {
	try {
		var iframe = Ext.getCmp('main-iframe');
		var win = iframe.el.dom.contentWindow || window.frames['main-iframe'];
		win.location.href = uri;
	} catch (e) {
		this.error(gt.gettext('Exception'), e);
	}
};

Game.progress_stop = function(id) {
	if (this.progress[id] && this.progress[id].timer) {
		window.clearInterval(this.progress[id].timer);
		this.progress[id].timer = undefined;
	}
};

Game.progress_set = function(id, ratio) {
	this.progress_stop(id);
	this.progress_show(id, ratio);
};

Game.progress_show = function(id, ratio) {
	if (ratio < 0)
		ratio = 0;
	if (ratio > 1)
		ratio = 1;
	var progress = this.progress[id];
	if (!progress) {
		progress = {};
		this.progress[id] = progress;
	}
	progress.ratio = ratio;
	var els = Ext.query('.progress-' + id);
	for (var i = 0; i < els.length; i++) {
		var el = Ext.get(els[i]);
		if (el.hasClass('progress-indicator-horizontal')) {
			if (el.content_width == undefined) {
				el.content_width = el.parent().getWidth(true);
			}
			el.dom.style.width = Math.floor(ratio * el.content_width) + 'px';
		} else if (el.hasClass('progress-indicator-vertical')) {
			if (el.content_height == undefined) {
				el.content_height = el.parent().getHeight(true);
			}
			el.dom.style.height = Math.floor(ratio * el.content_height) + 'px';
		} else {
			continue;
		}
		if (!el.hasClass(id + '-notfull')) {
			if (ratio < 1) {
				el.removeClass(id + '-full');
				el.addClass(id + '-notfull');
			}
		}
		if (!el.hasClass(id + '-full')) {
			if (ratio >= 1) {
				el.removeClass(id + '-notfull');
				el.addClass(id + '-full');
			}
		}
	}
};

Game.progress_run = function(id, start_ratio, end_ratio, time_till_end) {
	this.progress_set(start_ratio);
	if (time_till_end > 0) {
		var now = this.now();
		this.progress[id] = {
			timer: window.setInterval(this.progress_tick.createDelegate(this, [id]), 30),
			start_ratio: start_ratio,
			end_ratio: end_ratio,
			start_time: now,
			end_time: now + time_till_end
		};
	}
};

Game.progress_tick = function(id) {
	try {
		var progress = this.progress[id];
		if (progress && progress.timer) {
			var now = this.now();
			if (now >= progress.end_time) {
				this.progress_show(id, 1);
				this.progress_stop(id);
			} else {
				var ratio = (now - progress.start_time) * (progress.end_ratio - progress.start_ratio) / (progress.end_time - progress.start_time) + progress.start_ratio;
				this.progress_show(id, ratio);
			}
		}
	} catch (e) {
		this.progress_stop(id);
		this.error(gt.gettext('Exception'), e);
	}
};

Game.onLayout = function() {
	for (var id in this.progress) {
		var progress = this.progress[id];
		if (progress.ratio == undefined)
			continue;
		var els = Ext.query('.progress-' + id);
		for (var i = 0; i < els.length; i++) {
			var el = Ext.get(els[i]);
			if (el.content_width != undefined) {
				el.content_width = undefined;
				el.dom.style.width = '0px';
			}
			if (el.content_height != undefined) {
				el.content_height = undefined;
				el.dom.style.height = '0px';
			}
		}
		this.progress_show(id, progress.ratio);
	}
};

Game.main_frame_document = function() {
	try {
		return Ext.getCmp('main-iframe').getFrameDocument();
	} catch (e) {
		this.error(gt.gettext('Exception'), e);
	}
	return undefined;
};

loaded('game-interface');
