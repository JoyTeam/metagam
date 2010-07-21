Form = Ext.extend(AdminResponse, {
	constructor: function(data) {
		Form.superclass.constructor.call(this, {});
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
		var buttons = new Array();
		for (i = 0; i < data.buttons.length; i++) {
			var btn = data.buttons[i];
			buttons.push({
				text: btn.text,
				type: 'submit'
			});
		}
		var form = new Ext.FormPanel({
			width: 1000,
			labelWidth: 150,
			url: data.url,
			frame: true,
			items: items,
			buttons: buttons
		});
		this.add(form);
	}
});

loaded('admin/form.js');

