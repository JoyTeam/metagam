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
var leftmenu;
var topmenu;
var ver_suffix = '-' + Math.round(Math.random() * 100000000);
ver = ver + ver_suffix;

function adm_response(res)
{
	if (res.ver)
		ver = res.ver + ver_suffix;
	if (res.menu)
		update_menu(res.menu);
	if (res.redirect) {
		if (res.redirect == '_self')
			adm(current_page);
		else
			adm(res.redirect);
	} else if (res.redirect_top) {
		window.location.href = res.redirect_top;
	} else if (res.script) {
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
	} else if (res.content) {
		var panel = new AdminResponse({
			border: false,
			html: res.content,
			autoScroll: true,
			bodyStyle: 'padding: 10px'
		});
		adminmain.removeAll();
		adminmain.add(panel);
		adminmain.doLayout();
	}
}

function adm_success(response, opts)
{
	current_page = opts.func;
	if (response.getResponseHeader("Content-Type").match(/json/)) {
		var res = Ext.util.JSON.decode(response.responseText);
		adm_response(res);
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

function button_handler(btn)
{
	if (btn.href)
		window.location.href = btn.href;
	else if (btn.id)
		adm(btn.id);
}

function update_menu(menu)
{
	leftmenu.setRootNode(menu.left);
	topmenu.removeAll();
	topmenu.add({
		id: 'projecttitle',
		xtype: 'tbtext',
		text: menu.title,
	}, '->');
	for (var i = 0; i < menu.top.length; i++) {
		ent = menu.top[i];
		topmenu.add({id: ent.id, href: ent.href, text: ent.text, tooltip: ent.tooltip, handler: button_handler});
	}
	topmenu.doLayout();
}

Ext.onReady(function() {
	Ext.QuickTips.init();
	Ext.form.Field.prototype.msgTarget = 'side';
	adminmain = new Ext.Container({
		autoDestroy: true,
		layout: 'fit'
	});
	leftmenu = new Ext.tree.TreePanel({
		id: 'leftmenu',
		useArrows: true,
		autoScroll: true,
		animate: true,
		containerScroll: true,
		border: false,
		rootVisible: false,
		root: {},
	});
	topmenu = new Ext.Toolbar({
		id: 'topmenu',
		border: false,
	});
	var viewport = new Ext.Viewport({
		layout: 'border',
		items: [
/*			{
				region: 'north',
				height: 30,
				border: false,
				autoScroll: false,
				layout: 'hbox',
				layoutConfig: {
					align: 'stretchmax',
					pack: 'start'
				},
				items: [{
					id: 'toptitle',
					html: 'Project ABC',
					border: false
				}, {
					flex: 1,
					border: false,
					layout: 'fit',
					items: [topmenu]
				}],
			},*/
			{
				region: 'north',
				height: 30,
				autoScroll: false,
				layout: 'fit',
				border: false,
				items: topmenu
			},
			{
				region: 'west',
				split: true,
				width: 200,
				minSize: 175,
				maxSize: 400,
				border: false,
				autoScroll: true,
				items: leftmenu
			},
			{
				region: 'east',
				split: true,
				width: 400,
				border: false,
				autoScroll: true,
			},
			{
				region: 'center',
				border: false,
				layout: 'fit',
				items: adminmain
			}
		]
	});
	leftmenu.getSelectionModel().on({
		'beforeselect' : function(sm, node) {
			if (node && node.isLeaf())
				button_handler(node);
			else
				adm(undefined);
			return false;
		},
		scope: leftmenu
	});
	update_menu(admin_menu);
	if (!default_page)
		default_page = find_default_page(admin_menu.left.children)
	if (default_page)
		adm(default_page);
});
