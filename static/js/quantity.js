function q_find(id)
{
	return document.getElementById(id);
}

function q_img(id, src)
{
	 var el = q_find(id);
	 if (el)
		 el.src = src;
}

function q_add(id, delta, min, max)
{
	var input = q_find(id);
	var old_val = parseInt(input.value);
	if (!old_val)
		old_val = 0;
	if (old_val > max)
		old_val = max;
	if (old_val < min)
		old_val = min;
	var new_val = old_val + delta;
	if (new_val > max)
		new_val = max;
	if (new_val < min)
		new_val = min;
	input.value = new_val;
	q_update(id, min, max);
}

function q_update(id, min, max)
{
	var input = q_find(id);
	var val = parseInt(input.value);
	if (val > min) {
		q_img('m_' + id, '/st-mg/form/minus.gif');
		q_img('mm_' + id, '/st-mg/form/minusmax.gif');
	} else {
		q_img('m_' + id, '/st-mg/form/minusd.gif');
		q_img('mm_' + id, '/st-mg/form/minusmaxd.gif');
	}
	if (val < max) {
		q_img('p_' + id, '/st-mg/form/plus.gif');
		q_img('pm_' + id, '/st-mg/form/plusmax.gif');
	} else {
		q_img('p_' + id, '/st-mg/form/plusd.gif');
		q_img('pm_' + id, '/st-mg/form/plusmaxd.gif');
	}
}

loaded('quantity');
