var Locations = {
};

Locations.move = function(loc_id) {
	if (this.submit_locked)
		return;
	this.submit_locked = false;
	Ext.Ajax.request({
		url: '/location/move',
		method: 'POST',
		params: {
			'location': loc_id
		},
		success: (function (response, opts) {
			this.submit_locked = false;
			if (response && response.getResponseHeader) {
				var res = Ext.util.JSON.decode(response.responseText);
				if (res.ok) {
					eval(res.update_script);
					Game.main_open('/location?noupdate=1');
				} else if (res.error) {
					Game.error(res.hide_title ? '' : gt.gettext('Error'), res.error);
				}
			}
		}).createDelegate(this),
		failure: (function (response, opts) {
			this.submit_locked = false;
			Game.error(undefined, gt.gettext('Error connecting to the server'));
		}).createDelegate(this)
	});
};

Locations.update = function(name, name_w) {
	var els = Ext.query('.location-name');
	for (var i = 0; i < els.length; i++) {
		els[i].innerHTML = name;
	}
	var els = Ext.query('.location-name-w');
	for (var i = 0; i < els.length; i++) {
		els[i].innerHTML = name_w;
	}
};

loaded('locations');
