/* includes */
[%foreach file in includes%]
[%process $file%]
[%end%]

/* common variables */
var last_request_id = 0;
var in_dialog = false;

function get_viewport()
{
	var dim = document.viewport.getDimensions();
	var scr = document.viewport.getScrollOffsets();

	return {
		'left': scr.left,
		'top': scr.top,
		'width': dim.width,
		'height': dim.height
	};
}

function report_failure(text)
{
	var viewport = get_viewport();
	var img = document.createElement('img');
	img.style.position = 'absolute';
	img.style.left = viewport.left + 'px';
	img.style.top = viewport.top + 'px';
	img.style.width = viewport.width + 'px';
	img.style.height = viewport.height + 'px';
	img.style.zIndex = 2000;
	img.className = 'message-overlay';
	img.src = 'http://www.[%main_host%]/st-mg/img/dark.png';
	$$('body')[0].appendChild(img);

	var table = document.createElement('table');
	table.style.position = 'absolute';
	table.style.left = (viewport.left + 10) + 'px';
	table.style.top = (viewport.top + 10) + 'px';
	table.style.width = (viewport.width - 20) + 'px';
	table.style.height = (viewport.height - 20) + 'px';
	table.style.zIndex = 2001;
	table.className = 'message-overlay';
	var tbody = document.createElement('tbody');
	var tr = document.createElement('tr');
	var td = document.createElement('td');
	td.className = 'message-overlay-td';
	td.innerHTML = '<table class="message-window"><tr><td class="message-window-td"><table class="message-text"><tr><td class="message-text-td">' + text + '</td></tr></table>' + '<div class="message-button"><a href="javascript:void(0)" onclick="return report_close();">Закрыть</a></div>' + '</td></tr></table>';
	tr.appendChild(td);
	tbody.appendChild(tr);
	table.appendChild(tbody);
	$$('body')[0].appendChild(table);

	in_dialog = true;
}

function report_close()
{
	in_dialog = false;
	var lst = $$('.message-overlay');
	for (var i = 0; i < lst.length; i++) {
		var msg = lst[i];
		msg.parentNode.removeChild(msg);
	}
	return false;
}

function auth_login()
{
	if (in_dialog)
		return false;
	if ((document.location + '').match('^file://')) {
		report_failure(gt.gettext('Server is in the local mode'));
		return false;
	}
	new Ajax.Request('/auth/ajax-login', {
		'method': 'post',
		request_id: ++last_request_id,
		parameters: {
			'email': $('email').value,
			'password': $('password').value
		},
		onSuccess: function(response) {
			if (response.request.options.request_id == last_request_id) {
				var json = response.responseText.evalJSON();
				if (json.error) {
					report_failure(json.error);
				} else if (json.ok) {
					var frm = document.createElement('form');
					frm.method = 'post';
					frm.action = '/';
					var inp = document.createElement('input');
					inp.type = 'hidden';
					inp.name = 'session';
					inp.value = json.session;
					frm.appendChild(inp);
					$$('body')[0].appendChild(frm);
					frm.submit();
				}
			}
		},
		onFailure: function (response) {
			if (response.request.options.request_id == last_request_id) {
				report_failure(gt.gettext('Server is unavailable'));
			}
		}
	});
	return false;
}
