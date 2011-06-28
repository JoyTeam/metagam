var form_id = 0;

Form = Ext.extend(AdminResponse, {
	constructor: function(data) {
		Form.superclass.constructor.call(this, {
		});
		this.conditions = new Array();
		var upload = data.upload;
		var rows = new Array();
		if (data.title) {
			rows.push({
				border: false,
				html: '<div class="text"><h1>' + data.title + '</h1></div>'
			});
		}
		var row = undefined;
		var flex_total = 0;
		for (var i = 0; i < data.fields.length; i++) {
			var it = data.fields[i];
			if (!row)
				row = new Array();
			var elem;
			if (it.type == 'fileuploadfield')
				upload = true;
			if (it.type == 'empty') {
				elem = {
					border: false
				};
			} else if (it.type == 'header') {
				elem = {
					border: false,
					cls: 'text',
					html: '<h1>' + it.html + '</h1>'
				};
			} else if (it.type == 'html') {
				elem = {
					border: false,
					cls: 'text',
					html: it.html
				};
			} else if (it.type == 'label') {
				elem = {
					border: false,
					cls: 'x-form-item-label',
					html: it.label
				};
			} else if (it.type == 'button') {
				elem = {
					border: false,
					layout: 'form',
					items: {
						xtype: 'button',
						border: false,
						text: it.text,
						action: it.action,
						fieldLabel: it.label,
						hideLabel: (it.label == undefined) ? true : false,
						handler: function(btn) {
							adm(btn.action);
						}
					}
				};
				if (it.label == '&nbsp;')
					elem.items.labelSeparator = '';
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
					msgTarget: 'side',
					listeners: {},
					boxLabel: it.boxLabel,
					width: it.width,
					disabled: it.disabled
				};
				if (it.name)
					elt.id = 'form-field-' + (it.id || it.name);
				if (elt.xtype == 'checkbox') {
					elt.fieldLabel = it.desc;
					elt.boxLabel = it.label;
				} else if (elt.xtype == 'radio') {
					elt.value = undefined;
					elt.inputValue = it.value;
				} else if (elt.xtype == 'combo') {
					elt.store = it.values;
					elt.forceSelection = true;
					elt.triggerAction = 'all';
					elt.hiddenName = 'v_' + elt.name;
					elt.hiddenValue = elt.value;
					elt.allowBlank = it.allow_blank;
					elt.listWidth = 600;
				} else if (elt.xtype == 'password') {
					elt.xtype = 'textfield';
					elt.inputType = 'password';
				}
				if (elt.fieldLabel == undefined)
					elt.hideLabel = true;
				if (elt.fieldLabel == '&nbsp;' || it.remove_label_separator)
					elt.labelSeparator = '';
				if (elt.xtype != 'textarea' && elt.xtype != 'combo') {
					elt.listeners.specialkey = function(field, e) {
						if (e.getKey() == e.ENTER) {
							var form = Ext.getCmp('admin-form-' + form_id);
							form.ownerCt.custom_submit(form.url);
						}
					};
				}
				elt.listeners.select = elt.listeners.change = elt.listeners.check = function(field, newval, oldval) {
					var form = Ext.getCmp('admin-form-' + form_id);
					form.ownerCt.enforce_conditions();
				};
				elem = {
					border: false,
					autoHeight: true,
					layout: 'form',
					items: elt
				};
			}
			if (!it.width && !it.flex)
				it.flex = 1;
			if (it.flex)
				flex_total += it.flex;
			row.push({
				id: (id.id || it.name) ? ('elem_' + (it.id || it.name)) : undefined,
				autoHeight: true,
				flex: it.flex,
				width: it.width,
				border: false,
				items: elem
			});
			if (it.condition)
				this.conditions.push({id: 'elem_' + (it.id || it.name), condition: it.condition});
			if (i == data.fields.length - 1 || !data.fields[i + 1].inline) {
				for (var j = 0; j < row.length; j++) {
					if (row[j].flex)
						row[j].columnWidth = row[j].flex / flex_total;
					row[j].flex = undefined;
				}
				flex_total = 0;
				rows.push({
					border: false,
					layout: 'column',
					autoHeight: true,
					defaults: {
						autoHeight: true
					},
					items: row
				});
				/* single column rows */
				if (row.length == 1) {
					rows[rows.length - 1].id = row[0].id;
					row[0].id = undefined;
				}
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
		for (var i = 0; i < data.buttons.length; i++) {
			var btn_config = data.buttons[i];
			var btn = new Ext.Button({
				text: btn_config.text,
				url: btn_config.url ? btn_config.url : data.url,
				form_id: form_id,
				autoHeight: true
			});
			btn.on('click', function(btn, e) {
				var form = Ext.getCmp('admin-form-' + form_id);
				form.ownerCt.custom_submit(btn.url);
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
			layout: 'auto',
			fileUpload: upload,
			url: data.url,
			method: 'POST'
		});
		this.add(form);
		this.enforce_conditions(true);
	},
	enforce_conditions: function(force) {
		var changed = false;
		for (var i = 0; i < this.conditions.length; i++) {
			var cond = this.conditions[i];
			var visible = false;
			try {
				visible = eval(cond.condition);
			} catch (e) {
			}
			var cmp = Ext.getCmp(cond.id);
			if (cmp.isVisible() != visible || force) {
				cmp.setVisible(visible);
				changed = true;
			}
		}
		if (changed)
			this.doLayout();
	},
	custom_submit: function(url) {
		var form = Ext.getCmp('admin-form-' + form_id);
		form.getForm().submit({
			url: url,
			waitMsg: gt.gettext('Sending data...'),
			success: function(f, action) {
				if (form.fileUpload) {
					adm_success_json(action.response, {
						func: url.replace(/(^\/admin-|\/$)/g, '')
					});
				} else {
					adm_success(action.response, {
						func: url.replace(/(^\/admin-|\/$)/g, '')
					});
				}
			},
			failure: function(f, action) {
				if (action.failureType === Ext.form.Action.SERVER_INVALID) {
					if (action.result.errormsg) {
						Ext.Msg.alert(gt.gettext('Error'), action.result.errormsg);
					}
				} else if (action.failureType === Ext.form.Action.CONNECT_FAILURE) {
					Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Server error: %s'), action.response.status + ' ' + action.response.statusText + '<br />' + url));
				}
			}
		});
	}
});

function form_value(id)
{
	var cmp = Ext.getCmp('form-field-' + id);
	return cmp.getValue();
}

loaded('admin-form');

