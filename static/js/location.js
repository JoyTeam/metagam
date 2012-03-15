var Loc = {};

Loc.init = function() {
	this.multiimages = new Array();
	this.margin_x = 200;
	this.margin_y = 80;
};

Loc.multiimage = function(img) {
	this.multiimages.push(img);
};

Loc.run = function() {
	if (this.multiimages.length || this.stretching) {
		this.run_resize_checks();
	} else {
		var el = document.getElementById('location-static-image');
		if (el) {
			el.style.visibility = 'visible';
		}
	}
};

Loc.run_resize_checks = function() {
	this.check_resize();
	window.setInterval(function() { Loc.check_resize() }, 1000);
};

Loc.check_resize = function() {
	var size = this.window_size();
	if (size.w != this.window_w || size.h != this.window_h) {
		this.window_w = size.w;
		this.window_h = size.h;
		this.resize();
	}
};

Loc.resize = function() {
	var w = this.window_w - this.margin_x;
	var h = this.window_h - this.margin_y;
	if (this.multiimages.length) {
		// selecting maximal image fitting in (w, h). if neither match select 0th
		var best = this.multiimages[0]
		for (var i = 1; i < this.multiimages.length; i++) {
			var img = this.multiimages[i];
			if (img.width <= w && img.height <= h) {
				best = img;
			} else {
				break;
			}
		}
		for (var i = 0; i < this.multiimages.length; i++) {
			var img = this.multiimages[i];
			var el = document.getElementById('multiimage-' + img.id);
			if (el)
				el.style.display = (img.id == best.id) ? 'block' : 'none';
		}
	} else if (this.stretching) {
		var el = document.getElementById('location-static-image');
		if (el) {
			var iw = this.img_width;
			var ih = this.img_height;
			// resizing to fit width exactly
			ih = ih * w * 1.0 / iw;
			iw = w;
			// checking vertical overflow
			if (ih > h) {
				iw = iw * h * 1.0 / ih;
				ih = h;
			}
			// applying
			el.style.width = Math.round(iw) + 'px';
			el.style.height = Math.round(ih) + 'px';
			el.style.visibility = 'visible';
			// resizing areas
			var scale = iw / this.img_width;
			for (var i = 0; i < this.map_areas.length; i++) {
				var area = this.map_areas[i];
				var coords = new Array();
				for (var j = 0; j < area.coords.length; j++) {
					coords.push(Math.round(area.coords[j] * scale));
				}
				area.el.coords = coords.join(',');
			}
		}
	}
};

Loc.window_size = function() {
	var w = 0, h = 0;
	if (typeof(window.innerWidth) == 'number') {
		// Non-IE
		w = window.innerWidth;
		h = window.innerHeight;
	} else if (document.documentElement && (document.documentElement.clientWidth || document.documentElement.clientHeight)) {
		// IE 6+ in 'standards compliant mode'
		w = document.documentElement.clientWidth;
		h = document.documentElement.clientHeight;
	} else if (document.body && (document.body.clientWidth || document.body.clientHeight)) {
		// IE 4 compatible
		w = document.body.clientWidth;
		h = document.body.clientHeight;
	}
	return {
		w: w,
		h: h
	};
};

Loc.margins = function(x, y) {
	this.margin_x = x;
	this.margin_y = y;
};

Loc.stretch = function(w, h) {
	this.stretching = true;
	this.img_width = w;
	this.img_height = h;
	this.map_areas = new Array();
	var els = Ext.query('area.location-area');
	for (var i = 0; i < els.length; i++) {
		var el = els[i];
		var coords = el.coords.split(',');
		var int_coords = new Array();
		for (var j = 0; j < coords.length; j++) {
			int_coords.push(parseInt(coords[j]));
		}
		this.map_areas.push({
			el: el,
			coords: int_coords
		});
	}
};

loaded('location');
