/* includes */
[%foreach file in includes%]
[%process $file%]
[%end%]

/* common variables */
var last_request_id = 0;
var in_dialog = false;
var in_report = false;

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
	img.className = 'report-overlay';
	img.src = 'http://www.[%main_host%]/st-mg/img/dark.png';
	$$('body')[0].appendChild(img);

	var table = document.createElement('table');
	table.style.position = 'absolute';
	table.style.left = (viewport.left + 10) + 'px';
	table.style.top = (viewport.top + 10) + 'px';
	table.style.width = (viewport.width - 20) + 'px';
	table.style.height = (viewport.height - 20) + 'px';
	table.style.zIndex = 2001;
	table.className = 'report-overlay';
	var tbody = document.createElement('tbody');
	var tr = document.createElement('tr');
	var td = document.createElement('td');
	td.className = 'report-overlay-td';
	td.innerHTML = '<table class="message-window"><tr><td class="message-window-td"><table class="message-text"><tr><td class="message-text-td">' + text + '</td></tr></table>' + '<div class="message-button"><a href="javascript:void(0)" onclick="return report_close();">Закрыть</a></div>' + '</td></tr></table>';
	tr.appendChild(td);
	tbody.appendChild(tr);
	table.appendChild(tbody);
	$$('body')[0].appendChild(table);

	in_report = true;
}

function report_close()
{
	in_report = false;
	var lst = $$('.report-overlay');
	for (var i = 0; i < lst.length; i++) {
		var msg = lst[i];
		msg.parentNode.removeChild(msg);
	}
	return false;
}

function dialog(text)
{
	var viewport = get_viewport();
	var img = document.createElement('img');
	img.style.position = 'absolute';
	img.style.left = viewport.left + 'px';
	img.style.top = viewport.top + 'px';
	img.style.width = viewport.width + 'px';
	img.style.height = viewport.height + 'px';
	img.style.zIndex = 2000;
	img.className = 'dialog-overlay';
	img.src = 'http://www.[%main_host%]/st-mg/img/dark.png';
	$$('body')[0].appendChild(img);

	var table = document.createElement('table');
	table.style.position = 'absolute';
	table.style.left = (viewport.left + 10) + 'px';
	table.style.top = (viewport.top + 10) + 'px';
	table.style.width = (viewport.width - 20) + 'px';
	table.style.height = (viewport.height - 20) + 'px';
	table.style.zIndex = 2001;
	table.className = 'dialog-overlay';
	var tbody = document.createElement('tbody');
	var tr = document.createElement('tr');
	var td = document.createElement('td');
	td.className = 'dialog-overlay-td';
	td.innerHTML = '<table class="message-window"><tr><td class="message-window-td"><table class="message-text"><tr><td class="message-text-td">' + text + '</td></tr></table>' + '<div class="message-button"><a href="javascript:void(0)" onclick="return dialog_close();">Закрыть</a></div>' + '</td></tr></table>';
	tr.appendChild(td);
	tbody.appendChild(tr);
	table.appendChild(tbody);
	$$('body')[0].appendChild(table);

	in_dialog = true;
}

function dialog_close()
{
	in_dialog = false;
	var lst = $$('.dialog-overlay');
	for (var i = 0; i < lst.length; i++) {
		var msg = lst[i];
		msg.parentNode.removeChild(msg);
	}
	return false;
}

function htmlencode(s)
{
	if (s == undefined)
		return '';
	s = s.replace(/\046/g, '\&amp;');
	s = s.replace(/\074/g, '\&lt;');
	s = s.replace(/\076/g, '\&gt;');
	s = s.replace(/\012/g, '\&quot;');
	return s;
}

function auth_login()
{
	if (in_dialog || in_report)
		return false;
	if ((document.location + '').match('^file://')) {
		report_failure(gt.gettext('Server is in the local mode'));
		return false;
	}
	new Ajax.Request('/player/login', {
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
				report_failure(gt.gettext('Server is temporarily unavailable'));
			}
		}
	});
	return false;
}

var register_fields = new Array();
var fld_index = 0;
[%+ foreach fld in register_fields%]
register_fields.push({'prompt': '[%fld.prompt%]', 'code': '[%fld.code%]', 'type': '[%fld.type%]'[%if fld.type == 1%], 'values': [[%foreach v in fld.values%]['[%v.0%]', '[%v.1%]'][%unless v.2%], [%end%][%end%]][%end%]});
[%+ end%]

function auth_register()
{
	if (in_dialog || in_report)
		return false;
	var html = '<form action="/" method="post" id="registerform" name="registerform" onsubmit="return auth_register_next();"><div id="registerform-content"></div><div id="field-submit"><a id="field-submit-a" href="/" onclick="return auth_register_next();">' + gt.gettext('Next >') + '</a></div><input type="image" src="/st-mg/[%ver%]/img/null.gif" /></form>';
	dialog(html);
	auth_register_field(0);
	return false;
}

function auth_register_field(i)
{
	fld_index = i;
	var fld = register_fields[fld_index];
	var inp_html;
	if (fld.type == 1) {
		inp_html = '<div class="field-input-div"><select id="field-input">';
		for (var i = 0; i < fld.values.length; i++) {
			inp_html += '<option value="' + fld.values[i][0] + '"' + (fld.value == fld.values[i][0] ? ' selected="selected"' : '') + '>' + fld.values[i][1] + '</option>';
		}
		inp_html += '</select></div>';
	} else if (fld.type == 2) {
		inp_html = '<div class="field-input-div"><textarea id="field-input" class="field-edit">' + htmlencode(fld.value) + '</textarea></div>';
	} else if (fld.code == 'password') {
		inp_html = '<div class="field-input-div"><input id="field-input" type="password" class="field-edit" /></div>';
		inp_html += '<div class="field-input-div"><input id="field-input2" type="password" class="field-edit" /></div>';
	} else if (fld.code == 'captcha') {
		inp_html = '<div class="field-input-div"><img id="captcha" src="/auth/captcha?rnd=' + Math.random() + '" alt="" /></div>';
		inp_html += '<div class="field-input-div"><input id="field-input" type="captcha" class="field-edit" /></div>';
	} else {
		inp_html = '<div class="field-input-div"><input id="field-input" value="' + htmlencode(fld.value) + '" class="field-edit" /></div>';
	}
	var html = '<div id="field-prompt">' + fld['prompt'] + '</div>' + inp_html + '<div id="field-error">' + (fld.error ? fld.error : '') + '</div>';
	fld.error = undefined;
	$('field-submit-a').innerHTML = (fld_index < register_fields.length - 1) ? gt.gettext('Next >') : gt.gettext('Register');
	$('registerform-content').innerHTML = html;
	$('field-input').focus();
}

function auth_register_next()
{
	var val = $('field-input').value;
	if (!val) {
		$('field-error').innerHTML = gt.gettext('This field may not be empty');
		$('field-input').focus();
		return false;
	}
	var fld = register_fields[fld_index];
	if (fld.code == 'password') {
		var val2 = $('field-input2').value;
		if (!val2) {
			$('field-error').innerHTML = gt.gettext('Type your password twice');
			$('field-input2').focus();
			return false;
		} else if (val != val2) {
			$('field-error').innerHTML = gt.gettext('Passwords don\'t match');
			$('field-input').value = '';
			$('field-input2').value = '';
			$('field-input').focus();
			return false;
		}
	}
	fld.value = val;

	if (fld_index < register_fields.length - 1)
		auth_register_field(fld_index + 1);
	else {
		if ((document.location + '').match('^file://')) {
			report_failure(gt.gettext('Server is in the local mode'));
			return false;
		}
		var params = {};
		for (var i = 0; i < register_fields.length; i++) {
			var fld = register_fields[i];
			params[fld.code] = fld.value;
		}
		new Ajax.Request('/player/register', {
			'method': 'post',
			request_id: ++last_request_id,
			parameters: params,
			onSuccess: function(response) {
				if (response.request.options.request_id == last_request_id) {
					var json = response.responseText.evalJSON();
					if (json.error) {
						report_failure(json.error);
					} else if (json.errors) {
						var index = -1;
						for (var i = 0; i < register_fields.length; i++) {
							var fld = register_fields[i];
							if (json.errors[fld.code]) {
								if (index < 0)
									index = i;
								fld.error = json.errors[fld.code];
							}
						}
						if (index < 0) {
							report_failure(gt.gettext('Error during registration'));
						} else {
							auth_register_field(index);
						}
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
					report_failure(gt.gettext('Server is temporarily unavailable'));
				}
			}
		});
	}

	return false;
}

function auth_remind()
{
}
