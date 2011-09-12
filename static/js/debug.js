var debug_records = new Array();
function debug_log(str)
{
	var now = new Date();
	debug_records.push('<div><span style="font-weight: bold">' + now.getHours() + ':' + now.getMinutes() + ':' + now.getSeconds() + '</span>: ' + str + '</div>');
}
function debug_keydown(e)
{
	if (!e)
		e = window.event;
	var keycode = e.keyCode ? e.keyCode : e.which;
	if (keycode == 120 || keycode == 113 || keycode == 119) {
		if (document.getElementById('debug-log')) {
			debug_close();
		} else {
			var div = document.createElement('div');
			div.id = 'debug-log';
			div.style.position = 'absolute';
			div.style.left = 40 + 'px';
			div.style.top = 40 + 'px';
			div.style.width = 800 + 'px';
			div.style.height = 400 + 'px';
			div.style.border = 'solid 1px #000000';
			div.style.background = '#ffffff';
			div.style.overflow = 'auto';
			div.style.padding = '20px';
			div.style.zIndex = 100000;
			div.innerHTML = debug_records.join('') + '<form style="padding-top: 20px"><input type="submit" value="Dismiss" onclick="return debug_close();" /></form>';
			document.getElementsByTagName('body')[0].appendChild(div);
		}
		return false;
	}
	return true;
}
function debug_close()
{
	var div = document.getElementById('debug-log');
	if (div)
		div.parentNode.removeChild(div);
}
try {
	document.addEventListener('keydown', debug_keydown, false);
} catch (e) {
	try {
		document.onkeydown = debug_keydown;
	} catch (e) {
	}
}
debug_log('debug loaded');
