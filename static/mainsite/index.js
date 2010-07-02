Ext.BLANK_IMAGE_URL = '/st/ext/resources/images/default/s.gif';
Ext.onReady(function() {
	var tabPanel = new Ext.TabPanel({
		region: 'center',
		deferredRender: false,
		autoScroll: true, 
		margins: '0 4 4 0',
		activeTab: 0,
		items:[{
			title: 'Login',
			html: 'Login form'
		}, {
			title: 'Register',
			html: 'Register form'
		}]
	});
	tabPanel.render('cent')
});
