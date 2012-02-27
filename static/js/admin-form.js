var form_id = 0;

Form = Ext.extend(AdminResponsePanel, {
	constructor: function(data) {
		Form.superclass.constructor.call(this, {
		});
		this.conditions = new Array();
		form_id++;
		var upload = data.upload;
		var next_elem_id = 0;
		var rows = new Array();
		if (data.title) {
			rows.push({
				border: false,
				html: '<div class="text"><h1>' + data.title + '</h1></div>'
			});
		}
		if (data.menu && data.menu.length) {
			var menu_entries = new Array();
			for (var i = 0; i < data.menu.length; i++) {
				var ent = data.menu[i];
				var html = ent.text;
				if (ent.hook) {
					html = '<a href="/admin?_nd=' + Math.random() + '#' + ent.hook + '" onclick="adm(\'' + ent.hook + '\'); return false">' + html + '</a>';
				}
				menu_entries.push(html);
			}
			rows.push({
				border: false,
				html: '<div class="admin-actions">' + menu_entries.join(' / ') + '</div>'
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
					html: '<h1 class="admin-form-header">' + it.html + '</h1>'
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
					height: it.height,
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
					elt.listWidth = 600;
				} else if (elt.xtype == 'password') {
					elt.xtype = 'textfield';
					elt.inputType = 'password';
				} else if (elt.xtype == 'htmleditor') {
					elt.plugins = Ext.form.HtmlEditor.plugins();
					elt.selectImage = function(image) {
						(new Ext.Window({
							id: 'image-upload-win',
							title: gt.gettext('Upload file'),
							resizable: false,
							modal: true,
							items: {
								xtype: 'form',
								id: 'image-upload-form',
								bodyStyle: 'padding: 10px',
								border: false,
								waitTitle: gt.gettext('Please wait...'),
								labelAlign: 'top',
								layout: 'auto',
								fileUpload: true,
								animate: true,
								width: 300,
								autoHeight: true,
								items: [{
									border: false,
									layout: 'form',
									autoHeight: true,
									items: {
										width: 200,
										fieldLabel: gt.gettext('Upload image'),
										xtype: 'fileuploadfield',
										name: 'image',
										height: 30,
										border: false
									}
								}, {
									border: false,
									layout: 'form',
									autoHeight: true,
									items: {
										width: 200,
										xtype: 'textfield',
										fieldLabel: gt.gettext('Or provide image URL'),
										name: 'url',
										height: 30,
										border: false
									}
								}, {
									border: false,
									items: {
										xtype: 'button',
										text: gt.gettext('Upload'),
										handler: function() {
											Ext.getCmp('image-upload-form').getForm().submit({
												url: '/admin-image/upload',
												waitMsg: gt.gettext('Uploading data...'),
												success: function(f, action) {
													var res = Ext.util.JSON.decode(Ext.util.Format.htmlDecode(action.response.responseText));
													if (res) {
														image.insertImage({
															src: res.uri
														});
														Ext.getCmp('image-upload-win').close();
													}
												},
												failure: function(f, action) {
													if (action.failureType === Ext.form.Action.SERVER_INVALID) {
														if (action.result && action.result.errormsg) {
															Ext.Msg.alert(gt.gettext('Error'), action.result.errormsg);
														}
													} else if (action.failureType === Ext.form.Action.CONNECT_FAILURE) {
														Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Server error: %s'), action.response.status + ' ' + action.response.statusText));
													}
												}
											});
										}
									}
								}]
							}
						})).show();
					};
				}
				if (elt.fieldLabel == undefined)
					elt.hideLabel = true;
				if (elt.fieldLabel == '&nbsp;' || it.remove_label_separator)
					elt.labelSeparator = '';
				if (elt.xtype != 'textarea' && elt.xtype != 'combo' && elt.xtype != 'htmleditor') {
					elt.listeners.specialkey = (function(field, e) {
						if (e.getKey() == e.ENTER) {
							var form = Ext.getCmp('admin-form-' + this.form_id);
							form.ownerCt.custom_submit(form.url);
						}
					}).createDelegate(this);
				}
				elt.listeners.select = elt.listeners.change = elt.listeners.check = (function(field, newval, oldval) {
					var form = Ext.getCmp('admin-form-' + this.form_id);
					form.ownerCt.enforce_conditions();
					if (form.changeHandler)
						form.changeHandler();
				}).createDelegate(this);
				if (elt.xtype == 'textarea' || elt.xtype == 'textfield') {
					elt.enableKeyEvents = true;
					elt.listeners.change = elt.listeners.keyup = (function() {
						var form = Ext.getCmp('admin-form-' + this.form_id);
						form.ownerCt.enforce_conditions();
						if (form.changeHandler)
							form.changeHandler();
					}).createDelegate(this);
				}
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
			var elem_id;
			if (it.id || it.name) {
				elem_id = 'elem_' + (it.id || it.name);
			} else {
				next_elem_id++;
				it.id = 'auto_' + next_elem_id;
				elem_id = 'elem_' + it.id;
			}
			row.push({
				id: elem_id,
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
		for (var i = 0; i < data.buttons.length; i++) {
			var btn_config = data.buttons[i];
			if (btn_config.xtype) {
				buttons.push(btn_config);
			} else {
				var btn = new Ext.Button({
					text: btn_config.text,
					url: btn_config.url ? btn_config.url : data.url,
					form_id: form_id,
					autoHeight: true
				});
				btn.on('click', function(btn, e) {
					var form = Ext.getCmp('admin-form-' + btn.form_id);
					form.ownerCt.custom_submit(btn.url);
				}, btn);
				buttons.push(btn);
			}
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
			method: 'POST',
			form_id: form_id,
			changeHandler: data.changeHandler,
			successHandler: data.successHandler
		});
		this.add(form);
		this.enforce_conditions(true);
		this.form_cmp = form;
		this.form_id = form_id;
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
			if (!cmp) {
				Ext.Msg.alert(gt.gettext('Error'), 'Missing component ' + cond.id);
				continue;
			}
			if (cmp.isVisible() != visible || force) {
				cmp.setVisible(visible);
				changed = true;
			}
		}
		if (changed)
			this.doLayout();
	},
	custom_submit: function(url) {
		var saved = Ext.query('.admin-saved', admincontent.dom);
		for (var i = 0; i < saved.length; i++) {
			saved[i].style.display = 'none';
		}
		var form = Ext.getCmp('admin-form-' + this.form_id);
		form.getForm().submit({
			url: url,
			waitMsg: gt.gettext('Sending data...'),
			success: function(f, action) {
				if (f.successHandler) {
					f.successHandler(f, action);
				} else {
					if (form.fileUpload) {
						adm_success_json(action.response, {
							func: url.replace(/(^\/admin-|\/$)/g, '')
						});
					} else {
						adm_success(action.response, {
							func: url.replace(/(^\/admin-|\/$)/g, '')
						});
					}
				}
			},
			failure: function(f, action) {
				if (action.failureType === Ext.form.Action.SERVER_INVALID) {
					var txt = action.result.errormsg || action.result.errmsg || action.result.error;
					if (txt) {
						Ext.Msg.alert(gt.gettext('Error'), txt);
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

