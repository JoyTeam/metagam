/*
 * jQuery plugin: fieldSelection - v0.2.3 - last cange: 2006-12-20
 * (c) 2006 Alex Brem <alex@0xab.cd> - http://blog.0xab.cd
 */

(function() {

	var rx_newline = /(\u000d\u000a|\u000a|\u000d|\u0085\u2028|\u2029)/gm;

	var fieldSelection = {
		
		getSelection: function() {

			var e = (this.jquery) ? this[0] : this;
			
			return (

				/* mozilla / dom 3.0 */
				('selectionStart' in e && function() {
					var l = e.selectionEnd - e.selectionStart;
					
					var range = { start: e.selectionStart, end: e.selectionEnd, length: l, text: e.value.substr(e.selectionStart, l) };

					if (e.tagName.toLowerCase() == 'textarea') {
						var col = range.row = 0;
						e.value.substr(0, range.start).replace(rx_newline, function() { range.row++; col = arguments[2] });
						range.col = (col) ? range.start - col - 1 : range.start;
					}

					return range;

				}) ||

				/* exploder */
				(document.selection && function() {

					e.focus();

					var r = document.selection.createRange();
					if (r === null) {
						return { start: 0, end: 0, length: 0 }
					}
					
					var re = e.createTextRange();
					var rc = re.duplicate();
					re.moveToBookmark(r.getBookmark());
					rc.setEndPoint('EndToStart', re);

					var range = { start: rc.text.length, end: rc.text.length + r.text.length, length: r.text.length, text: r.text };

					if (e.tagName.toLowerCase() == 'textarea') {
						var col = row = 0;

						e.value.substr(0, range.start).replace(rx_newline, function() { row++; col = arguments[2] });

						range.row = row;
						range.col = (col) ? range.start - col - 2 : range.start;
						
						/*
							see! this browser is stupid to such an extend. simply unbelievable.
							
							we need a fix because of IE getting the newline-thing wrong.
							IE counts \r\n  but they are under the cursor when the new line starts
							and so we do not get an carent/key event for this character (WTF!?)

							(update) hooray. I've hacked a solution.
							
							(update2) argh! HOLY SHIT! this crap works only until the 2nd line break.
							hey IE developers! no insulting, but did you code IE while you were on drugs?
							
							conclusion: the CR/LF handling of textareas is completely fucked up!
							
							try for yourself: disable the next code block, clear the textarea and
							enter just some newlines.. then move the caret up and down and watch
							the positions together with the hex dump.
							
							to be continued... *sigh*
						 */

						var rl = rc.duplicate();
						var bm = rc.getBookmark();
						// is there a preceding CR
						if (rl.findText("\r", 0, 536870912 + 131072)) { // \n is mysteriously undetectable!
							// yes. now set range from found CR to selection/caret
							rl.setEndPoint('EndToStart', re);
							if (rl.text == '') {
								// hooray! we're at the beginning of a new column
								// IE is stupid, so we have to zero col and inc row
								// but strangely this only works after the first CR/LF
								range.col = 0;
								range.row++;
							}

						}
					
					}
					
					return range;

				}) ||

				/* browser not supported */
				function() { return null }

			)();

		},

		setSelection: function() {
			
			var e = (this.jquery) ? this[0] : this;
			
			var index = (arguments.length > 0) && ( // -1 means don't change index
									( typeof arguments[0] == 'string') && (
													((arguments[0] == ''  || arguments[0] == 'none'   ) && [   -1,    0]) // unselect all
											||	((arguments[0] == '*' || arguments[0] == 'all'    ) && [    0,   -1]) // select all
											||	((arguments[0] == '<' || arguments[0] == 'tostart') && [    0, null]) // select start to current
											||	((arguments[0] == '>' || arguments[0] == 'toend'  ) && [  null,   -1]) // select current to end
											||	((arguments[0] == '^' || arguments[0] == 'start'  ) && [    0,    0]) // cursor to start
											||	((arguments[0] == '$' || arguments[0] == 'end'    ) && [   null, -1]) // cursor to end
											||	((arguments[0] == '|' || arguments[0] == 'center' ) && [  '|',  '|']) // select word under cursor
										) ||
										( typeof arguments[0] == 'object') && (
													(('start' in arguments[0] || 'end' in arguments[0]) && [arguments[0]['start'] || null, arguments[0]['end'] || null]) // json {start: n, end: n}
											||	('pos' in arguments[0] && [arguments[0]['pos'], arguments[0]['pos']] || null) // json {pos: n}
											||	((typeof arguments[0][0] != 'undefined' && typeof arguments[0][1] != 'undefined') && arguments[0]) // array [start, end]
										) || ( arguments.length == 2) && [arguments[0], arguments[1]] // 2 parameters (start, end)
									)		|| [null, null];

			var named = { 'current': null, 'start': 0, 'end': -1 };
			if (typeof index[0] == 'string') { index[0] = (index[0] in named) ? named[index[0]] : null }
			if (typeof index[1] == 'string') { index[1] = (index[1] in named) ? named[index[1]] : null }
			
			return (
				
				/* mozilla / dom 3.0 */
				('selectionStart' in e && function() {
					e.focus();

					// note: we could use setSelectionRange as a substitute
					e.selectionStart = (index[0] === null) ? e.selectionStart : index[0];
					e.selectionEnd = (index[1] === null) ? e.selectionEnd : ((index[1] == -1) ? e.value.length : index[1]);
					
					return jQuery(e);
				}) ||

				/* exploder */
				(document.selection && function() {
					var range = jQuery(e).getSelection();
					var start = (index[0] === null) ? range.start : index[0];
					var end = (index[1] === null) ? range.end : ((index[1] == -1) ? e.value.length : index[1]);

					var r = document.selection.createRange();
					var re = e.createTextRange();
					re.moveStart('character', (index[0] === null) ? range.start : index[0]);
					re.moveEnd('character', (index[1] === null) ? -(e.value.length - range.end) : ((index[1] == -1) ? 0 : -(e.value.length - index[1])));
					r.moveToBookmark(re.getBookmark());
					r.select();

					return jQuery(e);
				}) ||

				/* browser not supported */
				function() { return jQuery(e) }
				
			)();
			
		},

		replaceSelection: function() {

			var e = (this.jquery) ? this[0] : this;
			var text = arguments[0] || '';
			var select_new = arguments[1] || false;

			return (

				/* mozilla / dom 3.0 */
				('selectionStart' in e && function() {
					e.focus();
					var start = e.selectionStart;
					e.value = e.value.substr(0, e.selectionStart) + text + e.value.substr(e.selectionEnd, e.value.length);
					if (select_new) {
						e.setSelectionRange(start, start + text.length);
					}
					return jQuery(e);
				}) ||

				/* exploder */
				(document.selection && function() {
					e.focus();
					var r = document.selection.createRange();
					r.text = text;
					if (!select_new) { // to make IE behave nicely we must use reverse psychology ;)
						r.collapse(false);
						r.select();
					}
					return jQuery(e);
				}) ||

				/* browser not supported */
				function() {
					e.value += text;
					return jQuery(e);
				}

			)();

		}

	};

	jQuery.each(fieldSelection, function(i) { jQuery.fn[i] = this; });

})();
