AdminResponse = Ext.extend(Ext.Panel, {
	bodyStyle: 'padding: 10',
	border: false
});

Ext.onReady(function() {
	Ext.QuickTips.init();
	var ver_suffix = '-' + Math.round(Math.random() * 100000000);
	ver = ver + ver_suffix;
	var admin_ajax_trans;
	var adminmain = new Ext.Container({
		autoDestroy: true,
		layout: 'fit'
	});
	var menu = new Ext.tree.TreePanel({
		useArrows: true,
		autoScroll: true,
		animate: true,
		containerScroll: true,
		border: false,
		dataUrl: '/admin/menu/' + ver,
		rootVisible: false,
		root: {
			nodeType: 'async',
			text: 'Root',
			id: 'root'
		},
		onSuccess: function(response, opts) {
			var res = Ext.util.JSON.decode(response.responseText);
			ver = res.ver + ver_suffix;
			wait([res.script], function() {
				var obj = new (eval(res.cls))(res.data);
				adminmain.removeAll();
				adminmain.add(obj);
				adminmain.doLayout();
			});
		},
		onFailure: function(response, opts) {
			var panel = new Ext.Panel({
				bodyStyle: 'padding: 10',
				border: false,
				html: sprintf(gt.gettext('Error loading %s: %s'), opts.func, response.status + ' ' + response.statusText)
			});
			adminmain.removeAll();
			adminmain.add(panel);
			adminmain.doLayout();
		}
	});
	var viewport = new Ext.Viewport({
		layout: 'border',
		items: [
			{
				region: 'west',
				split: true,
				width: 200,
				minSize: 175,
				maxSize: 400,
				border: false,
				autoScroll: true,
				items: menu
			},
			{
				region: 'center',
				border: false,
				layout: 'fit',
				items: adminmain
			}
		]
	});
	menu.getSelectionModel().on({
		'beforeselect' : function(sm, node) {
		},
		'selectionchange' : function(sm, node) {
			Ext.Ajax.abort(admin_ajax_trans);
			if (node && node.isLeaf()) {
				admin_ajax_trans = Ext.Ajax.request({
					url: '/admin/' + node.id + '/' + ver,
					func: node.id,
					success: menu.onSuccess,
					failure: menu.onFailure,
					scope: menu
				});
			} else {
				adminmain.removeAll();
			}
		},
		scope: menu
	});
});
