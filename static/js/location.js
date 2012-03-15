var Loc = {};

Loc.init = function() {
	this.multiimages = new Array();
};

Loc.multiimage = function(img) {
	this.multiimages.push(img);
};

Loc.run = function() {
	if (this.multiimages.length)
		this.run_resize_checks();
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
	var w = this.window_w - 200;
	var h = this.window_h - 40;
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

loaded('location');
