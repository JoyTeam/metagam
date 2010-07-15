ForumCategories = Ext.extend(AdminResponse, {
	constructor: function(data) {
		ForumCategories.superclass.constructor.call(this, {});
		var cm = new Ext.grid.ColumnModel({
			columns: [
				{
					id: 'name',
					header: 'Category title',
					dataIndex: 'name',
					width: 300
				}, {
					id: 'description',
					header: 'Category description',
					dataIndex: 'description'
				}
			]
		});
		var store = new Ext.data.JsonStore({
			autoDestroy: true,
			data: data,
			fields: [
				{name: 'name'},
				{name: 'description'}
			]
		});
		var grid = new Ext.grid.EditorGridPanel({
			store: store,
			cm: cm,
			autoExpandColumn: 'description',
			autoWidth: true,
			autoHeight: true,
			view: new Ext.grid.GridView({
				markDirty: false
			}),
			tbar: [
				{
					text: 'Add Employee',
					handler: function() {
						var e = new Employee({
							name: 'New Guy',
							email: 'new@exttest.com',
							start: (new Date()).clearTime(),
							salary: 50000,
							active: true
						});
						editor.stopEditing();
						store.insert(0, e);
						grid.getView().refresh();
						grid.getSelectionModel().selectRow(0);
						editor.startEditing(0);
					}
				}, {
					text: 'Remove Employee',
					disabled: true,
					handler: function(){
						editor.stopEditing();
						var s = grid.getSelectionModel().getSelections();
						for(var i = 0, r; r = s[i]; i++) {
							store.remove(r);
						}
					}
				}
			]
		});
		this.add(grid);
	}
});

wait(['js/roweditor.js'], function() {

	loaded('admin/forum/categories.js');
});
