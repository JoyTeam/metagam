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

loaded('game-interface');
