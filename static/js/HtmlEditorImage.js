Ext.form.HtmlEditor.Image = Ext.extend(Ext.util.Observable, {
    urlSizeVars: ['width','height'],
    init: function(cmp){
        this.cmp = cmp;
        this.cmp.on('render', this.onRender, this);
        this.cmp.on('initialize', this.onInit, this, {delay:100, single: true});
	this.cmp.insertImage = this.insertImage.createDelegate(this);
    },
    onEditorMouseUp : function(e){
        Ext.get(e.getTarget()).select('img').each(function(el){
            var w = el.getAttribute('width'), h = el.getAttribute('height'), src = el.getAttribute('src')+' ';
            src = src.replace(new RegExp(this.urlSizeVars[0]+'=[0-9]{1,5}([&| ])'), this.urlSizeVars[0]+'='+w+'$1');
            src = src.replace(new RegExp(this.urlSizeVars[1]+'=[0-9]{1,5}([&| ])'), this.urlSizeVars[1]+'='+h+'$1');
            el.set({src:src.replace(/\s+$/,"")});
        }, this);
        
    },
    onInit: function(){
        Ext.EventManager.on(this.cmp.getDoc(), {
		'mouseup': this.onEditorMouseUp,
		buffer: 100,
		scope: this
	});
    },
    onRender: function() {
        var btn = this.cmp.getToolbar().addButton({
            iconCls: 'x-edit-pictures',
            handler: this.cmp.selectImage ? this.cmp.selectImage.createCallback(this) : Ext.emptyFn,
            scope: this,
            tooltip: gt.gettext('Insert Image')
        });
    },
    insertImage: function(img) {
	this.cmp.updateToolbar();
        this.cmp.insertAtCursor('<img src="' + img.src + '" alt="" />');
    }
});

wait(['FileUploadField'], function() {
	loaded('HtmlEditorImage');
});
