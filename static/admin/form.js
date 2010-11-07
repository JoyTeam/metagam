var form_id = 0;

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
					border: false,
				};
			} else if (it.type == 'header') {
				elem = {
					border: false,
					cls: 'text',
					html: '<h1>' + it.html + '</h1>',
				};
			} else if (it.type == 'html') {
				elem = {
					border: false,
					cls: 'text',
					html: it.html,
				};
			} else if (it.type == 'button') {
				elem = {
					layout: 'border',
					border: false,
					items: [{
						height: 40,
						region: 'south',
						split: false,
						border: false,
						items: [{
							xtype: 'button',
							border: false,
							text: it.text,
							height: 23,
							action: it.action,
							handler: function(btn) {
								adm(btn.action);
							},
						}],
					}, {
						region: 'center',
						border: false,
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
					border: false,
					style: 'margin-bottom: 10px',
					msgTarget: 'side',
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
				} else if (elt.xtype == 'password') {
					elt.xtype = 'textfield';
					elt.inputType = 'password';
				}
				if (elt.fieldLabel == undefined)
					elt.hideLabel = true;
				elem = {
					border: false,
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
				border: false,
				items: [elem],
			});
			if (i == data.fields.length - 1 || !data.fields[i + 1].inline) {
				rows.push({
					border: false,
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
		form_id++;
		for (i = 0; i < data.buttons.length; i++) {
			var btn_config = data.buttons[i];
			var btn = new Ext.Button({
				text: btn_config.text,
				url: btn_config.url ? btn_config.url : data.url,
				form_id: form_id,
			});
			btn.on('click', function(btn, e) {
				var form = Ext.getCmp('admin-form-' + form_id);
				form.getForm().submit({
					url: btn.url,
					waitMsg: gt.gettext('Sending data...'),
					success: function(f, action) {
						adm_success(action.response, {
							func: btn.url
						});
					},
					failure: function(f, action) {
						if (action.failureType === Ext.form.Action.SERVER_INVALID) {
							if (action.result.errormsg) {
								Ext.Msg.alert(gt.gettext('Error'), action.result.errormsg);
							}
						} else if (action.failureType === Ext.form.Action.CONNECT_FAILURE) {
							Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Server error: %s'), action.response.status + ' ' + action.response.statusText + '<br />' + btn.url));
						}
					},
				});
			}, btn);
			buttons.push(btn);
		}
		var form = new Ext.FormPanel({
			id: 'admin-form-' + form_id,
			cls: 'admin-form',
			labelAlign: 'top',
			border: false,
			width: '100%',
			labelWidth: 150,
			items: rows,
			buttons: buttons,
			buttonAlign: 'left',
			footerStyle: 'padding: 0',
			waitTitle: gt.gettext('Please wait...'),
		});
		this.add(form);
	}
});

loaded('admin/form.js');

