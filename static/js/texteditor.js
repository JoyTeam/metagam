var img_win;

function add_code(id, btn, opentag, closetag, immed)
{
	var textarea = document.getElementById(id)

	var st = textarea.scrollTop;

	var done = false;

	var sel = document.selection;

	if (sel && sel.createRange) {

		if (sel.type == 'Text' && immed != 2) {

			var rng = sel.createRange();

			if (rng && rng.text && rng.text.length > 0) {

				rng.text = opentag + rng.text + closetag;

				done = true;
			}
		}

	} else if (!done && (textarea.selectionStart || textarea.selectionStart == '0')) {

		var startPos = textarea.selectionStart;
		var endPos = textarea.selectionEnd;

		textarea.value = textarea.value.substring(0, startPos) + opentag + textarea.value.substring(startPos, endPos) + closetag + textarea.value.substring(endPos, textarea.value.length);

		textarea.selectionStart = startPos + opentag.length;
		textarea.selectionEnd = endPos + opentag.length;

		done = true;
	}

	if (!done && immed) {
		
		var len = textarea.value.length;

		textarea.value += opentag + closetag;
		done = true;

		try {
			textarea.selectionStart = len + opentag.length;
			textarea.selectionEnd = len + opentag.length;
		} catch (e) {
		}
	}

	if (!done) {

		var re = /\*$/;

		if (re.test(btn.value)) {

			btn.value = btn.value.substr(0, btn.value.length - 1);
			textarea.value += closetag;	    

		} else {

			btn.value += '*';
			textarea.value += opentag;	    
		}
	}

	textarea.scrollTop = st;
	textarea.focus();
}

function translit(id)
{
	var element = document.getElementById(id);

	var data = element.value;
	var re;

	data = data.replace(/([bvgdhzjklmnprstfc])'/g, '$1ь');
	data = data.replace(/([BVGDHZJKLMNPRSTFC])'/g, '$1Ь');
	data = data.replace(/e'/g, 'э');
	data = data.replace(/E'/g, 'Э');

	data = data.replace(/sch/g, 'щ');
	data = data.replace(/tsh/g, 'щ');

	data = data.replace(/S[cC][hH]/g, 'Щ');
	data = data.replace(/T[sS][hH]/g, 'Щ');

	data = data.replace(/jo/g, 'ё');
	data = data.replace(/ju/g, 'ю');
	data = data.replace(/ja/g, 'я');
	data = data.replace(/yo/g, 'ё');
	data = data.replace(/yu/g, 'ю');
	data = data.replace(/ya/g, 'я');

	data = data.replace(/J[oO]/g, 'Ё');
	data = data.replace(/J[uU]/g, 'Ю');
	data = data.replace(/J[aA]/g, 'Я');
	data = data.replace(/Y[oO]/g, 'Ё');
	data = data.replace(/Y[uU]/g, 'Ю');
	data = data.replace(/Y[aA]/g, 'Я');

	data = data.replace(/zh/g, 'ж');
	data = data.replace(/kh/g, 'х');
	data = data.replace(/ts/g, 'ц');
	data = data.replace(/ch/g, 'ч');
	data = data.replace(/sh/g, 'ш');
	data = data.replace(/ae/g, 'э');

	data = data.replace(/Z[hH]/g, 'Ж');
	data = data.replace(/K[hH]/g, 'Х');
	data = data.replace(/T[sS]/g, 'Ц');
	data = data.replace(/C[hH]/g, 'Ч');
	data = data.replace(/S[hH]/g, 'Ш');
	data = data.replace(/A[eE]/g, 'Э');

	data = data.replace(/a/g, 'а');
	data = data.replace(/b/g, 'б');
	data = data.replace(/v/g, 'в');
	data = data.replace(/w/g, 'в');
	data = data.replace(/g/g, 'г');
	data = data.replace(/d/g, 'д');
	data = data.replace(/e/g, 'е');
	data = data.replace(/z/g, 'з');
	data = data.replace(/i/g, 'и');
	data = data.replace(/j/g, 'й');
	data = data.replace(/k/g, 'к');
	data = data.replace(/l/g, 'л');
	data = data.replace(/m/g, 'м');
	data = data.replace(/n/g, 'н');
	data = data.replace(/o/g, 'о');
	data = data.replace(/p/g, 'п');
	data = data.replace(/r/g, 'р');
	data = data.replace(/s/g, 'с');
	data = data.replace(/t/g, 'т');
	data = data.replace(/u/g, 'у');
	data = data.replace(/f/g, 'ф');
	data = data.replace(/h/g, 'х');
	data = data.replace(/x/g, 'х');
	data = data.replace(/y/g, 'ы');
	data = data.replace(/c/g, 'ц');

	data = data.replace(/A/g, 'А');
	data = data.replace(/B/g, 'Б');
	data = data.replace(/V/g, 'В');
	data = data.replace(/W/g, 'В');
	data = data.replace(/G/g, 'Г');
	data = data.replace(/D/g, 'Д');
	data = data.replace(/E/g, 'Е');
	data = data.replace(/Z/g, 'З');
	data = data.replace(/I/g, 'И');
	data = data.replace(/J/g, 'Й');
	data = data.replace(/K/g, 'К');
	data = data.replace(/L/g, 'Л');
	data = data.replace(/M/g, 'М');
	data = data.replace(/N/g, 'Н');
	data = data.replace(/O/g, 'О');
	data = data.replace(/P/g, 'П');
	data = data.replace(/R/g, 'Р');
	data = data.replace(/S/g, 'С');
	data = data.replace(/T/g, 'Т');
	data = data.replace(/U/g, 'У');
	data = data.replace(/F/g, 'Ф');
	data = data.replace(/H/g, 'Х');
	data = data.replace(/X/g, 'Х');
	data = data.replace(/Y/g, 'Ы');
	data = data.replace(/C/g, 'Ц');

	element.value = data;
}

function add_img(id)
{
	try {
		if (img_win)
			img_win.close();

	} catch (e) {
	}

	img_win = window.open('/socio/image/' + id, '_blank', 'width=750,height=380,toolbar=0,location=0,directories=0,menubar=0,scrollbars=1,resizable=1,status=0');
}

function add_rt(id)
{
	try {
		if (img_win)
			img_win.close();

	} catch (e) {
	}

	img_win = window.open('/socio/rutube/' + id, '_blank', 'width=350,height=700,toolbar=0,location=0,directories=0,menubar=0,scrollbars=1,resizable=1,status=0');
}

function smile_category(id, cat_id)
{
	document.getElementById(id + '_smiles').innerHTML = document.getElementById('smiles_' + id + '_' + cat_id).innerHTML;
}

