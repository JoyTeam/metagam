var modules_loaded;
var modules_loading;
var modules_waiting;
var depend_counter = 0;

if (!modules_loaded) {

	modules_loaded = new Array();
	modules_loading = new Array();
	modules_waiting = new Array();
}

function wait(m, c)
{
	var wait_entry = {
		modules: m,
		callback: c,
		index: ++depend_counter
	};

	if (entry_ready(wait_entry))
		entry_run(wait_entry);
	else
		modules_waiting.push(wait_entry);
}

function entry_ready(wait_entry)
{
	var all_ready = true;

	if (!wait_entry)
		return;

	for (var i = 0; i < wait_entry.modules.length; i++) {

		var module = wait_entry.modules[i];

		if (!modules_loaded[module]) {

			if (!modules_loading[module]) {

				modules_loading[module] = true;

				var hd = document.getElementsByTagName('head')[0];
				var newScript = document.createElement('script');
				newScript.type = 'text/javascript';
				newScript.src = admin_root + '/st/' + ver + '/' + module;
				hd.appendChild(newScript);
			}
		}

		if (!modules_loaded[module]) {

			all_ready = false;
		}
	}

	return all_ready;
}

function entry_run(wait_entry)
{
	if (wait_entry.callback)
		wait_entry.callback();
}

function loaded(module)
{
	modules_loaded[module] = true;

	for (var j = modules_waiting.length - 1; j >= 0; j--) {

		var wait_entry = modules_waiting[j];

		if (entry_ready(wait_entry)) {

			modules_waiting.splice(j, 1);

			entry_run(wait_entry);
		}
	}
}

try { initdeps(); } catch(e) { }
