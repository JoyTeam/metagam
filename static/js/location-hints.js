function transition_init()
{
}

function transition_hint(loc_id, hint)
{
	var els = Ext.query('.loc-tr-' + loc_id);
	for (var i = 0; i < els.length; i++) {
		new Ext.ToolTip({
			target: els[i],
			html: hint,
			anchor: 'right',
			trackMouse: true,
			showDelay: 0,
			hideDelay: 0,
			dismissDelay: 10000
		});
	}
}
