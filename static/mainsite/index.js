Ext.BLANK_IMAGE_URL = '/st/ext/resources/images/default/s.gif';
Ext.onReady(function() {
	var emailForm = new Ext.FormPanel({
		title: gt.gettext('Project status notifications'),
		frame: true,
		bodyStyle:'padding: 5px 5px 0',
		width: 350,
		defaults: {width: '100%'},
		defaultType: 'textfield',
		items: [{
			fieldLabel: gt.gettext('E-mail address'),
			name: 'email',
			allowBlank: false
		}],
		buttons: [{
			text: gt.gettext('Stay tuned'),
			handler: function() {
				emailForm.getForm().submit({
					clientValidation: true,
					url: '/mainsite/email',
					success: function(form, action) {
						Ext.Msg.alert('Success', action.result.msg);
					},
					failure: function(form, action) {
						switch (action.failureType) {
							case Ext.form.Action.CLIENT_INVALID:
								Ext.Msg.alert('Failure', 'Form fields may not be submitted with invalid values');
								break;
							case Ext.form.Action.CONNECT_FAILURE:
								Ext.Msg.alert('Failure', 'Ajax communication failed');
								break;
							case Ext.form.Action.SERVER_INVALID:
								Ext.Msg.alert('Failure', action.result.msg);
						}
					}
				});
			}
		}]
	});
	emailForm.render('emailform');
});
