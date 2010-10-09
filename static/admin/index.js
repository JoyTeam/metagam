AdminResponse = Ext.extend(Ext.Panel, {
	border: false,
	region: 'center',
});

var base_url = document.URL;
var default_page;
var i = base_url.indexOf('#');
if (i >= 0) {
	default_page = base_url.substr(i + 1);
	base_url = base_url.substr(0, i);
}

var admin_ajax_trans;
var adminmain;
var current_page;
var ver_suffix = '-' + Math.round(Math.random() * 100000000);
ver = ver + ver_suffix;

function adm_success(response, opts)
{
	current_page = opts.func;
	if (response.getResponseHeader("Content-Type").match(/json/)) {
		var res = Ext.util.JSON.decode(response.responseText);
		if (res.redirect) {
			adm(res.redirect);
			return;
		} else if (res.redirect_top) {
			window.location.href = res.redirect_top;
			return;
		}
		ver = res.ver + ver_suffix;
		wait([res.script], function() {
			adminmain.removeAll();
			var obj = new (eval(res.cls))(res.data);
			obj = new Ext.Container({
				autoScroll: true,
				items: [{
					border: false,
					autoHeight: true,
					html: '<div id="headmenu">' + res.headmenu + '</div>',
					bodyStyle: 'padding: 10px 10px 0px 10px'
				}, {
					border: false,
					items: obj,
					bodyStyle: 'padding: 0px 10px 10px 10px'
				}]
			});
			adminmain.add(obj);
			adminmain.doLayout();
		});
	} else {
		var panel = new AdminResponse({
			border: false,
			html: response.responseText,
			autoScroll: true,
			bodyStyle: 'padding: 10px'
		});
		adminmain.removeAll();
		adminmain.add(panel);
		adminmain.doLayout();
	}
}

function adm_failure(response, opts)
{
	var panel = new AdminResponse({
		border: false,
		html: sprintf('%h: <strong>%h</strong>', opts.func, response.status + ' ' + response.statusText),
		autoScroll: true,
		bodyStyle: 'padding: 10px'
	});
	adminmain.removeAll();
	adminmain.add(panel);
	adminmain.doLayout();
}

function adm(node_id)
{
	if (admin_ajax_trans)
		Ext.Ajax.abort(admin_ajax_trans);
	if (node_id) {
		document.location.replace(base_url + '#' + node_id);
		admin_ajax_trans = Ext.Ajax.request({
			url: '/admin-' + node_id + '/ver' + ver,
			func: node_id,
			success: function(response, opts) {
				adm_success(response, opts);
			},
			failure: function(response, opts) {
				adm_failure(response, opts);
			}
		});
	} else {
		document.location.replace(base_url + '#');
		adminmain.removeAll();
	}
}

function find_default_page(menu)
{
	var i;
	for (i = 0; i < menu.length; i++) {
		var ent = menu[i];
		if (ent.admin_index)
			return ent.id;
		if (ent.children) {
			var id = find_default_page(ent.children);
			if (id)
				return id;
		}
	}
	return undefined;
}

Ext.onReady(function() {
	Ext.QuickTips.init();
	Ext.form.Field.prototype.msgTarget = 'side';
	adminmain = new Ext.Container({
		autoDestroy: true,
		layout: 'fit'
	});
	var menu = new Ext.tree.TreePanel({
		useArrows: true,
		autoScroll: true,
		animate: true,
		containerScroll: true,
		border: false,
		rootVisible: false,
		root: admin_menu,
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
			if (node && node.isLeaf())
				adm(node.id);
			else
				adm(undefined);
			return false;
		},
		scope: menu
	});
	if (!default_page)
		default_page = find_default_page(admin_menu.children)
	if (default_page)
		adm(default_page);
});
