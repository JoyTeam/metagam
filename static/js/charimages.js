var CharImages = {
	lst: new Array(),
	cur: 0,
	layers: new Array(),
	layer_cur: new Array()
};

CharImages.select = function(id) {
	var img = this.lst[id];
	try { document.getElementById('charimgsel-input').value = img.id } catch (e) {}
	try { document.getElementById('charimgsel-image').src = img.image } catch (e) {}
	try { document.getElementById('charimgsel-name').innerHTML = img.name } catch (e) {}
	try { document.getElementById('charimgsel-description').innerHTML = img.description } catch(e) {}
	try { document.getElementById('charimgsel-price').innerHTML = img.price } catch(e) {}
	this.cur = id;
};

CharImages.reset_error = function() {
	try { var err = document.getElementById('charimgsel-error'); err.parentNode.removeChild(err); } catch(e) {}
};

CharImages.prev = function() {
	this.reset_error();
	this.select((this.cur + this.lst.length - 1) % this.lst.length);
};

CharImages.next = function() {
	this.reset_error();
	this.select((this.cur + 1) % this.lst.length);
};

CharImages.find = function(id) {
	for (var i = 0; i < this.lst.length; i++) {
		if (this.lst[i].id == id)
			return this.select(i);
	}
	this.select(0);
};

CharImages.layer = function(layer_id) {
	for (var i = 0; i < this.layers.length; i++) {
		var lay = this.layers[i];
		if (lay.id == layer_id)
			return lay;
	}
	return undefined;
};

CharImages.layer_select = function(layer_id, id) {
	var lay = this.layer(layer_id);
	var img = lay.images[id];
	try { document.getElementById('charimgsel-layer-' + lay.id).style.backgroundImage = 'url(' + img.image + ')' } catch (e) {}
	try { document.getElementById('charimgsel-input-' + lay.id).value = img.id } catch (e) {}
	this.layer_cur[layer_id] = id;
};

CharImages.layer_prev = function(layer_id) {
	var lay = this.layer(layer_id);
	this.reset_error();
	this.layer_select(layer_id, (this.layer_cur[layer_id] + lay.images.length - 1) % lay.images.length);
};

CharImages.layer_next = function(layer_id) {
	var lay = this.layer(layer_id);
	this.reset_error();
	this.layer_select(layer_id, (this.layer_cur[layer_id] + 1) % lay.images.length);
};

CharImages.layer_find = function(layer_id, id) {
	var lay = this.layer(layer_id);
	for (var i = 0; i < lay.images.length; i++) {
		if (lay.images[i].id == id)
			return this.layer_select(layer_id, i);
	}
	this.layer_select(layer_id, 0);
};

loaded('charimages');
