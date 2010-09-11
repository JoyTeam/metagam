Ext.BLANK_IMAGE_URL = '/st/ext/resources/images/default/s.gif';
Ext.QuickTips.init();
Ext.form.Field.prototype.msgTarget = 'under';

function show_subscribe()
{
	if (Ext.isReady) {

		var emailWindow;
		
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
							emailWindow.close();
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
			url: '/constructor/subscribe',
			frame: true,
			bodyStyle: 'padding: 5px 5px 0',
			width: 400,
			height: 100,
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

		emailWindow = new Ext.Window({
			title: gt.gettext('Subsciption to the project news'),
			autoWidth: 420,
			autoHeight: true,
			modal: true,
			items: [emailForm]
		});

		emailWindow.show()
	}
}
