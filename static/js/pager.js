function Pager(pager_list, page_prefix)
{
	this.pager_list = pager_list;
	this.page_prefix = page_prefix;
	this.pages = [];
	this.active_page = undefined;
	this.id = ++Pager.pager_last_id;
	Pager.pagers[this.id] = this;
}

Pager.pagers = [];
Pager.pager_last_id = 0;

Pager.prototype.add = function(page_id, page_title, visible) {
	if (visible) {
		this.hide_active();
		this.active_page = page_id;
	}
	this.pages.push({
		id: page_id,
		title: page_title
	});
};

Pager.prototype.update = function() {
	var tokens = [];
	for (var i = 0; i < this.pages.length; i++) {
		var page = this.pages[i];
		var title = page.title;
		if (page.id == this.active_page) {
			title = '<span class="page-selected">' + title + '</span>';
		} else {
			var onclick = 'Pager.pagers[' + this.id + '].click(\'' + page.id + '\'); return false';
			title = '<a class="page-notselected" href="javascript:void(0)" onclick="' + onclick + '">' + title + '</a>';
		}
		tokens.push(title);
	}
	document.getElementById(this.pager_list).innerHTML = tokens.join('&nbsp;| ');
	var el = document.getElementById('form-page');
	if (el) {
		el.value = this.active_page;
	}
};

Pager.prototype.hide_active = function() {
	if (this.active_page) {
		var el = document.getElementById(this.page_prefix + this.active_page);
		if (el)
			el.style.display = 'none';
		this.active_page = undefined;
	}
};

Pager.prototype.click = function(page_id) {
	this.hide_active();
	var el = document.getElementById(this.page_prefix + page_id);
	if (el)
		el.style.display = 'block';
	this.active_page = page_id;
	this.update();
};

loaded('pager');
