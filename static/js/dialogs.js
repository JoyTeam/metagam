var dialog_default_event;

function dialog_click(btn_event)
{
	document.getElementById('dialog-event').value = btn_event;
	document.getElementById('dialog-form').onsubmit = function () { return true };
	return true;
}

function dialog_keypress(e)
{
	if (!e)
		e = window.event;
	var code = e.keyCode || e.which;
	if (code == 13) {
		if (dialog_default_event) {
			document.getElementById('dialog-event').value = dialog_default_event;
			var form = document.getElementById('dialog-form');
			form.onsubmit = function () { return true };
			form.submit();
		}
		return false;
	}
	return true;
}

loaded('dialogs');
