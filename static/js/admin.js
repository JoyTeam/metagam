var AdminResponse = Ext.extend(Ext.BoxComponent, {
	border: false,
	autoWidth: true,
	region: 'center'
});

var AdminResponsePanel = Ext.extend(Ext.Panel, {
	border: false,
	region: 'center'
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
var admincontent;
var current_page;
var leftmenu;
var topmenu;
var advicecontent;
var ver_suffix = '-' + Math.round(Math.random() * 100000000);
ver = ver + ver_suffix;
var headmenu;

function adm_response(res)
{
	if (res.ver)
		ver = res.ver + ver_suffix;
	if (res.menu)
		update_menu(res.menu);
	if (res.redirect) {
		if (res.redirect == '_self')
			adm(current_page, res.parameters);
		else
			adm(res.redirect, res.parameters);
	} else if (res.redirect_top) {
		window.location = res.redirect_top;
	} else {
		adminmain.removeAll();
		admincontent = new Ext.Container({
			hidden: true,
			cls: 'admin-content'
		});
		if (res.headmenu) {
			headmenu = res.headmenu;
			var tokens = new Array();
			for (var i = 0; i < headmenu.length; i++) {
				var html = headmenu[i].html;
				var href = headmenu[i].href;
				if (href) {
					html = '<a href="/admin?_nd=' + Math.random() + '#' + href + '" onclick="adm(\'' + href + '\'); return false;">' + html + '</a>';
					expand_menu(href);
				}
				tokens.push(html);
			}
			admincontent.add({
				border: false,
				autoHeight: true,
				html: tokens.join(' / '),
				cls: 'admin-headmenu'
			});
		} else {
			headmenu = undefined;
		}
		adminmain.add(admincontent);
		adminmain.doLayout();
		if (res.script) {
			var wait_modules = res.data.modules;
			if (!wait_modules)
				wait_modules = new Array();
			wait_modules.push(res.script);
			wait(wait_modules, function() {
				var obj = new (eval(res.cls))(res.data);
				admincontent.add({
					border: false,
					cls: 'admin-body',
					items: obj
				});
				admincontent.doLayout();
				adminmain.doLayout();
				admincontent.show()
			});
		} else if (res.content) {
			var panel = new AdminResponse({
				border: false,
				cls: 'admin-body'
			});
			admincontent.add(panel);
			admincontent.doLayout();
			admincontent.show();
			panel.update(res.content, true);
		}
		advicecontent.removeAll()
		if (res.advice && res.advice.length) {
			advicecontent.add({
				html: gt.gettext('Guru advice'),
				border: false,
				bodyCfg: {
					cls: 'admin-advice-header'
				}
			});
			for (var i = 0; i < res.advice.length; i++) {
				var adv = res.advice[i];
				advicecontent.add({
					title: adv.title,
					html: '<h1>' + adv.title + '</h1>' + adv.content,
					bodyCfg: {
						cls: adv.lst ? 'admin-advice-body-last' : 'admin-advice-body'
					},
					headerCfg: {
						cls: 'admin-advice-title'
					}
				});
			}
		}
		advicecontent.doLayout();
		var auto_panels = Ext.query('div.auto-panel', admincontent.dom);
		for (var i = 0; i < auto_panels.length; i++) {
			var div = new Ext.Element(auto_panels[i]);
			var content = div.dom.innerHTML;
			var title = div.dom.title;
			div.dom.innerHTML = '';
			div.dom.title = '';
			var panel = new Ext.Panel({
				title: title,
				html: content,
				collapsible: true,
				renderTo: div,
				collapsed: !div.is('.expanded'),
				titleCollapse: true
			});
		}
	}
}

function adm_success_json(response, opts)
{
	current_page = opts.func;
	expand_menu(current_page);
	if (!response.responseText) {
		Ext.Msg.alert(gt.gettext('Error'), gt.gettext('Error parsing server response'));
	} else {
		var res = Ext.util.JSON.decode(response.responseText);
		adm_response(res);
	}
}

function adm_success(response, opts)
{
	Ext.get('admin-logo-image').dom.src = '/st-mg/constructor/admin/top-left-logo.gif';
	if (!response || !response.getResponseHeader)
		return;
	if (opts.func) {
		current_page = opts.func;
		expand_menu(current_page);
	}
	if (response.getResponseHeader("Content-Type").match(/json/)) {
		var res = Ext.util.JSON.decode(response.responseText);
		adm_response(res);
	} else {
		var panel = new AdminResponse({
			border: false,
			html: response.responseText,
			bodyStyle: 'padding: 10px'
		});
		adminmain.removeAll();
		adminmain.add(panel);
		adminmain.doLayout();
	}
}

function adm_failure(response, opts)
{
	Ext.get('admin-logo-image').dom.src = '/st-mg/constructor/admin/top-left-logo.gif';
	var panel = new AdminResponse({
		border: false,
		html: sprintf('<div class="text">%s</div>', response.responseText),
		bodyStyle: 'padding: 10px'
	});
	adminmain.removeAll();
	adminmain.add(panel);
	adminmain.doLayout();
}

function adm(node_id, parameters)
{
	if (admin_ajax_trans)
		Ext.Ajax.abort(admin_ajax_trans);
	if (node_id) {
		document.location.replace(base_url + '#' + node_id);
		var args_res = /^(.*?)\?(.*)$/.exec(node_id);
		if (args_res) {
			var args = args_res[2].split('&');
			node_id = args_res[1];
			parameters = parameters || {};
			for (var i = 0; i < args.length; i++) {
				var res = /^(.*?)=(.*)$/.exec(args[i]);
				if (res) {
					parameters[res[1]] = res[2];
				}
			}
		}
		admin_ajax_trans = Ext.Ajax.request({
			url: '/admin-' + node_id + '/ver' + ver,
			params: parameters,
			func: node_id,
			timeout: 120000,
			success: adm_success,
			failure: adm_failure
		});
		Ext.get('admin-logo-image').dom.src = '/st-mg/constructor/admin/top-left-logo-anim.gif';
	} else {
		document.location.replace(base_url + '#');
		adminmain.removeAll();
	}
}

function find_default_page(menu)
{
	if (!menu)
		return undefined;
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
		window.location = btn.href;
	else if (btn.id)
		adm(btn.id);
}

function update_menu(menu)
{
	leftmenu.animate = false;
	leftmenu.setRootNode(menu.left);
	leftmenu.expandAll();
	leftmenu.collapseAll();
	expand_menu(current_page);
	leftmenu.animate = true;
	topmenu.removeAll();
	topmenu.add({
		id: 'admin-logo',
		xtype: 'tbtext',
		text: '<a href="' + constructor_index_page + '"><img id="admin-logo-image" src="' + admin_root + '/st-mg/constructor/admin/top-left-logo.gif" alt="" title="' + gt.gettext('To the main page') + '" /></a>'
	});
	topmenu.add({
		id: 'admin-project-title',
		xtype: 'tbtext',
		text: menu.title
	}, '->');
	for (var i = 0; i < menu.top.length; i++) {
		ent = menu.top[i];
		topmenu.add({
			xtype: 'tbtext',
			text: (ent.href ? '<a href="' + ent.href + '" title="' + ent.tooltip + '">' : '<a href="javascript:void(0)" title="' + ent.tooltip + '" onclick="adm(\'' + ent.id + '\'); return 0;">') + ent.text + '</a>'
		});
	}
	topmenu.doLayout();
}

function expand_menu(page)
{
	expand_node(leftmenu.getRootNode(), page)
}

function expand_node(node, id)
{
	if (node.id == id) {
		node.expand();
		return true;
	}
	for (var i = 0; i < node.childNodes.length; i++)
		if (expand_node(node.childNodes[i], id)) {
			node.expand();
			return true;
		}

}

Ext.onReady(function() {
	Ext.QuickTips.init();
	Ext.form.Field.prototype.msgTarget = 'under';
	adminmain = new Ext.Container({
		autoDestroy: true
	});
	leftmenu = new Ext.tree.TreePanel({
		useArrows: true,
		border: false,
		rootVisible: false,
		id: 'admin-leftmenu-tree',
		root: {}
	});
	topmenu = new Ext.Toolbar({
		id: 'admin-topmenu',
		border: false,
		height: 45,
		autoWidth: true
	});
	advicecontent = new Ext.Panel({
		id: 'admin-advicecontent',
		border: false,
		autoDestroy: true,
		autoScroll: true,
		bodyCfg: {
			cls: 'admin-advicecontent'
		}
	});
	var viewport = new Ext.Viewport({
		layout: 'border',
		id: 'admin-viewport',
		items: [
			{
				region: 'north',
				height: 45,
				autoScroll: false,
				layout: 'fit',
				border: false,
				items: topmenu
			},
			{
				id: 'admin-leftmenu',
				region: 'west',
				split: true,
				width: '20%',
				maxSize: 400,
				border: false,
				layout: 'fit',
				bodyCfg: {
					cls: 'admin-leftmenu'
				},
				items: {
					autoScroll: true,
					border: false,
					items: leftmenu
				}
			},
			{
				id: 'admin-advicecontent1',
				border: false,
				items: advicecontent,
				region: 'east',
				split: true,
				width: '25%',
				layout: 'fit',
				bodyCfg: {
					cls: 'admin-advicecontent1'
				}
			},
			{
				region: 'center',
				border: false,
				id: 'admin-main',
				autoScroll: true,
				bodyCfg: {
					cls: 'x-panel-body admin-main'
				},
				items: adminmain
			}
		]
	});
	leftmenu.getSelectionModel().on({
		'beforeselect' : function(sm, node) {
			if (node) {
		       		if (node.isLeaf())
					button_handler(node);
				else if (node.isExpanded())
					node.collapse(true, true);
				else
					node.expand(false, true);
			} else
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
