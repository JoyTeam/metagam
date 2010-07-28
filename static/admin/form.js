Form = Ext.extend(AdminResponse, {
	constructor: function(data) {
		Form.superclass.constructor.call(this, {
		});
		var i;
		var items = new Array();
		for (i = 0; i < data.fields.length; i++) {
			var it = data.fields[i];
			items.push({
				fieldLabel: it.label,
				name: (it.name != undefined) ? it.name : '',
				allowBlank: true,
				value: it.value,
				xtype: (it.type == undefined) ? 'textfield' : it.type,
				width: 825
			});
		}
		items.push({
			xtype: 'hidden',
			name: 'ok',
			value: '1'
		});
		var buttons = new Array();
		var form;
		for (i = 0; i < data.buttons.length; i++) {
			var btn = data.buttons[i];
			buttons.push({
				text: btn.text,
				handler: function() {
					form.getForm().submit({
						url: data.url,
						waitMsg: gt.gettext('Sending data...'),
						success: function(f, action) {
							if (action.result.redirect) {
								adm(action.result.redirect);
							} else {
								adm_success(action.response, {
									func: data.url
								});
							}
						},
						failure: function(f, action) {
							if (action.failureType === Ext.form.Action.SERVER_INVALID) {
								if (action.result.errormsg) {
									Ext.Msg.alert(gt.gettext('Error'), action.result.errormsg);
								}
							} else if (action.failureType === Ext.form.Action.CONNECT_FAILURE) {
								Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Server error: %s %s<br />%s'), action.response.status, action.response.statusText, data.url));
							}
						},
					});
				},
			});
		}
		form = new Ext.FormPanel({
			width: 1020,
			labelWidth: 150,
			frame: true,
			items: items,
			buttons: buttons,
			buttonAlign: 'left'
		});
		this.add(form);
	}
});

loaded('admin/form.js');

