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
					Game.progress_run('location-movement', 0, 1, res.delay * 1000);
					this.moved(res);
					Game.main_open('/location');
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

Locations.moved = function(loc) {
	var els = Ext.query('.location-name');
	for (var i = 0; i < els.length; i++) {
		els[i].innerHTML = loc.name;
	}
	var els = Ext.query('.location-name-w');
	for (var i = 0; i < els.length; i++) {
		els[i].innerHTML = loc.name_w;
	}
};

loaded('locations');
