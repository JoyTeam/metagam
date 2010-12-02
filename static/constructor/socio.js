function run_search()
{
	var frm = document.getElementById('search-form');
	var query = document.getElementById('socio-top-search').value;
	if (query != '') {
		frm.action = '/forum/search/' + encodeURIComponent(query);
		frm.submit();
	}
	return false;
}
