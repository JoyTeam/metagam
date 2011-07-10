Ext.form.HtmlEditor.plugins = function(){
    return [
        new Ext.form.HtmlEditor.Image()
    ];
};

wait(['HtmlEditorImage'], function() {
	loaded('HtmlEditorPlugins');
});
