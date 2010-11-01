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
var admincontent;
var current_page;
var leftmenu;
var topmenu;
var advicecontent;
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
	} else {
		adminmain.removeAll();
		admincontent = new Ext.Container({
			hidden: true,
			cls: 'admin-content',
		});
		if (res.headmenu)
			admincontent.add({
				border: false,
				autoHeight: true,
				html: res.headmenu,
				cls: 'admin-headmenu',
			});
		adminmain.add(admincontent);
		adminmain.doLayout();
		if (res.script) {
			wait([res.script], function() {
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
				cls: 'admin-body',
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
				cls: 'advice-banner',
			});
			for (var i = 0; i < res.advice.length; i++) {
				var adv = res.advice[i];
				advicecontent.add({
					collapsible: true,
					title: adv.title,
					html: adv.content,
					cls: 'advice',
					bodyCssClass: 'advice-body',
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
				border: false,
				collapsed: !div.is('.expanded'),
				titleCollapse: true
			});
		}
	}
}

function adm_success(response, opts)
{
	current_page = opts.func;
	expand_menu(current_page);
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
	var panel = new AdminResponse({
		border: false,
		html: sprintf('<div class="text">%s</div>', response.responseText),
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
	leftmenu.animate = false;
	leftmenu.setRootNode(menu.left);
	leftmenu.expandAll();
	leftmenu.collapseAll();
	expand_menu(current_page);
	leftmenu.animate = true;
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
	Ext.form.Field.prototype.msgTarget = 'side';
	adminmain = new Ext.Container({
		autoDestroy: true,
		cls: 'admin-main',
	});
	leftmenu = new Ext.tree.TreePanel({
		id: 'leftmenu',
		useArrows: true,
		border: false,
		rootVisible: false,
		root: {},
	});
	topmenu = new Ext.Toolbar({
		id: 'topmenu',
		border: false,
	});
	advicecontent = new Ext.Panel({
		id: 'advicecontent',
		border: false,
		autoDestroy: true,
	});
	var viewport = new Ext.Viewport({
		layout: 'border',
		items: [
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
				maxSize: 400,
				border: false,
				autoScroll: true,
				items: leftmenu,
			},
			{
				region: 'east',
				split: true,
				width: 200,
				border: false,
				autoScroll: true,
				layout: 'fit',
				items: advicecontent,
			},
			{
				region: 'center',
				border: false,
				autoScroll: true,
				items: adminmain,
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
