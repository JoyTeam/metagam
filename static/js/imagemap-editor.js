ImageMapEditor = {};

ImageMapEditor.init = function(width, height) {
	this.width = width;
	this.height = height;
	var canvas = document.createElement('canvas');
	canvas.id = 'imagemap_canvas';
	canvas.width = width;
	canvas.height = height;
	try { G_vmlCanvasManager.initElement(canvas); } catch (e) {}
	Ext.getDom('imagemap_div').appendChild(canvas);
	this.ctx = canvas.getContext('2d');
	this.canvas = Ext.get(canvas);
	this.init_image();
};

ImageMapEditor.init_image = function() {
	this.img = Ext.getDom('imagemap_img');
	try {
		this.ctx.drawImage(this.img, 0, 0);
	} catch (e) {
		window.setTimeout(this.init_image.createDelegate(this), 100);
		return;
	}
	this.img.parentNode.removeChild(this.img);
	Ext.get('imagemap_canvas').on('click', this.click.createDelegate(this));
};

ImageMapEditor.click = function(ev, target) {
	ev.preventDefault();
	var page_coo = ev.getXY();
	var x = page_coo[0] - this.canvas.getLeft();
	var y = page_coo[1] - this.canvas.getTop();
	this.ctx.save();
	this.ctx.strokeStyle = '#000000';
	this.ctx.lineWidth = 1;
	this.ctx.strokeRect(x - 4.5, y - 4.5, 8, 8);
	this.ctx.restore();
};

loaded('imagemap-editor');
