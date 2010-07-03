Ext.BLANK_IMAGE_URL = '/st/ext/resources/images/default/s.gif';
Ext.QuickTips.init();
Ext.form.Field.prototype.msgTarget = 'under';
Ext.onReady(function() {

	var submitButton = new Ext.Button({
		text: gt.gettext('Subscribe'),
		handler: function() {
			this.fireEvent('submit');
		},
		listeners: {
			submit: function() {
				emailForm.getForm().submit({
					success: function(form, action) {
						Ext.Msg.alert(gt.gettext('Subscription confirmation'), gt.gettext('You have successfully subscribed to the project news'));
						emailForm.getForm().reset();
					},
					failure: function(form, action) {
						if (action.failureType == Ext.form.Action.CONNECT_FAILURE)
							Ext.Msg.alert(gt.gettext('Error'), gt.gettext('Connection to the server failed'));
					}
				});
			}
		}
	});

	var emailForm = new Ext.FormPanel({
		title: gt.gettext('Subscribe to the project news'),
		url: '/mainsite/subscribe',
		frame: true,
		bodyStyle: 'padding: 5px 5px 0',
		width: 400,
		height: 120,
		defaults: {
			width: '100%',
			enableKeyEvents: true,
			listeners: {
				specialKey: function(field, el) {
					if (el.getKey() == Ext.EventObject.ENTER) {
						submitButton.fireEvent('submit');
					}
				}
			}
		},
		defaultType: 'textfield',
		items: [{
			fieldLabel: gt.gettext('E-mail address'),
			name: 'email',
		}],
		buttons: [submitButton]
	});

	emailForm.render('emailform');
});
