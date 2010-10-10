Form = Ext.extend(AdminResponse, {
	constructor: function(data) {
		Form.superclass.constructor.call(this, {
		});
		var i;
		var rows = new Array();
		var row = undefined;
		for (i = 0; i < data.fields.length; i++) {
			var it = data.fields[i];
			if (!row)
				row = new Array();
			var elem;
			if (it.type == 'empty') {
				elem = {
				};
			} else if (it.type == 'button') {
				elem = {
					layout: 'border',
					items: [{
						height: 31,
						region: 'south',
						split: false,
						layout: 'anchor',
						items: [{
							xtype: 'button',
							text: it.text,
							height: 23,
							anchor: '-30',
							action: it.action,
							handler: function(btn) {
								adm(btn.action);
							},
						}],
					}, {
						region: 'center',
					}],
				};
			} else {			
				var elt = {
					fieldLabel: it.label,
					name: (it.name != undefined) ? it.name : '',
					allowBlank: true,
					value: it.value,
					checked: it.checked,
					xtype: (it.type == undefined) ? 'textfield' : it.type,
					anchor: '-30',
				};
				if (elt.xtype == 'checkbox') {
					elt.fieldLabel = it.desc;
					elt.boxLabel = it.label;
				} else if (elt.xtype == 'combo') {
					elt.store = it.values;
					elt.forceSelection = true;
					elt.triggerAction = 'all';
					elt.hiddenName = 'v_' + elt.name;
					elt.hiddenValue = elt.value;
					elt.allowBlank = it.allow_blank;
				}
				if (elt.fieldLabel == undefined)
					elt.hideLabel = true;
				elem = {
					layout: 'form',
					items: [elt],
				};
			}
			if (!it.width && !it.flex)
				it.flex = 1;
			row.push({
				flex: it.flex,
				width: it.width,
				layout: 'fit',
				items: [elem],
			});
			if (i == data.fields.length - 1 || !data.fields[i + 1].inline) {
				rows.push({
					layout: 'hbox',
					layoutConfig: {
						align: 'stretchmax',
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
							adm_success(action.response, {
								func: data.url
							});
						},
						failure: function(f, action) {
							if (action.failureType === Ext.form.Action.SERVER_INVALID) {
								if (action.result.errormsg) {
									Ext.Msg.alert(gt.gettext('Error'), action.result.errormsg);
								}
							} else if (action.failureType === Ext.form.Action.CONNECT_FAILURE) {
								Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Server error: %s'), action.response.status + ' ' + action.response.statusText + '<br />' + data.url));
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

