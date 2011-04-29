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

Game.msg = function(title, str) {
	if (!this.msgCt){
		this.msgCt = Ext.DomHelper.insertFirst(document.body, {id: 'msg-div'}, true);
	}
	var m = Ext.DomHelper.append(this.msgCt, '<div class="msg"><h3>' + title + '</h3><p>' + str + '</p></div>', true);
	m.hide();
	m.slideIn('t').pause(3).ghost('t', {remove: true});
};

loaded('game-interface');
