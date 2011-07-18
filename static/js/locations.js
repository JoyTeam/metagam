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
					Game.main_open('/location');
				} else if (res.error) {
					Game.error(res.hide_title ? '' : gt.gettext('Error'), res.error);
				}
			}
		}).createDelegate(this),
		failure: (function (response, opts) {
			this.submit_locked = false;
			Game.error(gt.gettext('Error'), gt.gettext('Couldn\'t send command to the server'));
		}).createDelegate(this)
	});
};

loaded('locations');
