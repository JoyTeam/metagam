Form = Ext.extend(AdminResponse, {
	constructor: function(data) {
		Form.superclass.constructor.call(this, {
		});
		var i;
		var rows = new Array();
		var row = undefined;
		for (i = 0; i < data.fields.length; i++) {
			var it = data.fields[i];
			if (!row) {
				row = new Array();
			}
			var elt = {
				fieldLabel: it.label,
				name: (it.name != undefined) ? it.name : '',
				allowBlank: true,
				value: it.value,
				checked: it.checked,
				xtype: (it.type == undefined) ? 'textfield' : it.type,
				anchor: '-10',
			};
			if (elt.xtype == 'checkbox') {
				elt.fieldLabel = it.desc;
				elt.boxLabel = it.label;
			}
			if (!elt.fieldLabel)
				elt.hideLabel = true;
			row.push({
				items: [{
					layout: 'form',
					items: [elt]
				}]
			});
			if (i == data.fields.length - 1 || !data.fields[i + 1].inline) {
				for (var j = 0; j < row.length; j++)
					row[j].width = Math.round(100 / row.length) + '%';
				rows.push({
					flex: 1 / row.length,
					layout: 'hbox',
					layoutConfig: {
						pack: 'start',
					},
					items: row,
				});
				row = undefined;
			}
		}
		rows.push({
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
			labelAlign: 'top',
			frame: true,
			width: '100%',
			labelWidth: 150,
			items: rows,
			buttons: buttons,
			buttonAlign: 'left',
		});
		this.add(form);
	}
});

loaded('admin/form.js');

