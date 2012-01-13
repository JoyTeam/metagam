var CharClasses = {
	lst: new Array(),
	cur: 0,
	layers: new Array(),
	layer_cur: new Array()
};

CharClasses.select = function(id) {
	var img = this.lst[id];
	try { document.getElementById('charclssel-input').value = img.id } catch (e) {}
	try { document.getElementById('charclssel-name').innerHTML = img.name } catch (e) {}
	try { document.getElementById('charclssel-description').innerHTML = img.description } catch(e) {}
	this.cur = id;
};

CharClasses.reset_error = function() {
	try { var err = document.getElementById('charclssel-error'); err.parentNode.removeChild(err); } catch(e) {}
};

CharClasses.prev = function() {
	this.reset_error();
	this.select((this.cur + this.lst.length - 1) % this.lst.length);
};

CharClasses.next = function() {
	this.reset_error();
	this.select((this.cur + 1) % this.lst.length);
};

CharClasses.find = function(id) {
	for (var i = 0; i < this.lst.length; i++) {
		if (this.lst[i].id == id)
			return this.select(i);
	}
	this.select(0);
};

loaded('charclasses');
