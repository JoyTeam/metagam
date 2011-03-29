var form_presets;

FormPresets = Ext.extend(AdminResponse, {
	constructor: function(data) {
		FormPresets.superclass.constructor.call(this, {
		});
		var form = new Form(data);
		if (data.presets) {
			var presets = new Array();
			if (data.presets.length) {
				presets.push('<div class="x-form-item-label">' + gt.gettext('Presets:') + '</div>');
				for (var i = 0; i < data.presets.length; i++) {
					var preset = data.presets[i];
					presets.push('<a href="javascript:void(0)" onclick="form_preset(' + i + '); return false">' + preset.title + '</a>');
				}
			}
			form_presets = data.presets;
			var panel = new Ext.Panel({
				border: false,
				layout: 'column',
				items: [{
					border: false,
					columnWidth: 1,
					items: form
				}, {
					width: 150,
					border: false,
					html: presets.join('<br />')
				}]
			});
			this.add(panel);
		} else {
			this.add(form);
		}
		form.doLayout();
	}
});

function form_preset(i)
{
	var preset = form_presets[i];
	for (var j = 0; j < preset.fields.length; j++) {
		var field = preset.fields[j];
		var cmp = Ext.getCmp('form-field-' + field.name);
		if (cmp)
			cmp.setValue(field.value);
	}
}

wait(['admin-form'], function() {
	loaded('admin-form-presets');
});

