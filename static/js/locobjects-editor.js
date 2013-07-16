VisualObject = function(id) {
    this.id = id;
    this.poly = new Array();
};

VisualObject.prototype.render = function(form) {
    this.form = form;
    var enforce_conditions = form.enforce_conditions.createDelegate(form);
    this.cmp = form.form_cmp.add({
        id: 'panel-obj-' + this.id,
        title: gt.gettext('Object') + ' ' + this.id,
        collapsible: true,
        collapsed: true,
        layout: 'form',
        autoHeight: true,
        bodyStyle: 'padding: 10px',
        style: 'margin: 0 0 10px 0',
        items: {
            border: false,
            autoHeight: true,
            defaults: {
                layout: 'form',
                labelAlign: 'top',
                autoHeight: true,
                border: false
            },
            items: [
                {
                    id: 'form-order-' + this.id,
                    xtype: 'hidden',
                    name: 'order-' + this.id
                },
                {
                    id: 'form-field-image-' + this.id,
                    xtype: 'hidden',
                    name: 'image-' + this.id,
                    value: this.image
                },
                {
                    id: 'form-field-width-' + this.id,
                    xtype: 'hidden',
                    name: 'width-' + this.id,
                    value: this.width
                },
                {
                    id: 'form-field-height-' + this.id,
                    xtype: 'hidden',
                    name: 'height-' + this.id,
                    value: this.height
                },
                {
                    id: 'elem_id-' + this.id,
                    items: { 
                        id: 'form-field-id-' + this.id,
                        fieldLabel: gt.gettext('Object identifier'),
                        name: 'id-' + this.id,
                        value: this.ident,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true
                    }
                },
                {
                    id: 'elem_x-' + this.id,
                    items: { 
                        id: 'form-field-x-' + this.id,
                        fieldLabel: gt.gettext('Center X'),
                        readOnly: true,
                        name: 'x-' + this.id,
                        value: this.x,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true
                    }
                },
                {
                    id: 'elem_y-' + this.id,
                    items: { 
                        id: 'form-field-y-' + this.id,
                        fieldLabel: gt.gettext('Center Y'),
                        readOnly: true,
                        name: 'y-' + this.id,
                        value: this.y,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true
                    }
                },
                {
                    id: 'elem_position-expr-' + this.id,
                    items: { 
                        id: 'form-field-position-expr-' + this.id,
                        fieldLabel: gt.gettext('Scripted object position'),
                        boxLabel: gt.gettext('Enable scripted position'),
                        name: 'position-expr-' + this.id,
                        checked: this.position ? true : false,
                        xtype: 'checkbox',
                        msgTarget: 'under',
                        anchor: '-30',
                        autoHeight: true,
                        listeners: {
                            check: enforce_conditions
                        }
                    }
                },
                {
                    id: 'elem_position-' + this.id,
                    items: { 
                        id: 'form-field-position-' + this.id,
                        fieldLabel: gt.gettext('Object position expression') + ' <img class="inline-icon" src="/st/icons/script.gif" alt="" />',
                        name: 'position-' + this.id,
                        value: this.position,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true
                    }
                },
                {
                    id: 'elem_polygon-' + this.id,
                    items: { 
                        id: 'form-field-polygon-' + this.id,
                        fieldLabel: gt.gettext('Active zone vertices (relative to the object pivot)'),
                        readOnly: true,
                        name: 'polygon-' + this.id,
                        value: this.getPolygonStr(),
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true
                    }
                },
                {
                    id: 'elem_visible-' + this.id,
                    items: { 
                        id: 'form-field-visible-' + this.id,
                        fieldLabel: gt.gettext('Visibility condition') + ' <img class="inline-icon" src="/st/icons/script.gif" alt="" />',
                        name: 'visible-' + this.id,
                        value: this.visible,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true
                    }
                },
                {
                    id: 'elem_action-' + this.id,
                    items: {
                        id: 'form-field-action-' + this.id,
                        fieldLabel: gt.gettext('Click action'),
                        name: 'action-' + this.id,
                        xtype: 'combo',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true,
                        store: LocObjectsEditor.actions,
                        forceSelection: true,
                        triggerAction: 'all',
                        hiddenName: 'v_action-' + this.id,
                        hiddenValue: this.action,
                        value: this.action,
                        listWidth: 600,
                        listeners: {
                            select: enforce_conditions,
                            change: enforce_conditions
                        }
                    }
                },
                {
                    id: 'elem_location-' + this.id,
                    items: {
                        id: 'form-field-location-' + this.id,
                        fieldLabel: gt.gettext('Target location'),
                        name: 'location-' + this.id,
                        xtype: 'combo',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true,
                        store: LocObjectsEditor.locations,
                        forceSelection: true,
                        triggerAction: 'all',
                        hiddenName: 'v_location-' + this.id,
                        hiddenValue: this.loc,
                        value: this.loc,
                        listWidth: 600,
                        listeners: {
                            select: enforce_conditions,
                            change: enforce_conditions
                        }
                    }
                },
                {
                    id: 'elem_url-' + this.id,
                    items: {
                        id: 'form-field-url-' + this.id,
                        fieldLabel: gt.gettext('Relative URL (starting with \'/\')'),
                        name: 'url-' + this.id,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true,
                        value: this.url
                    }
                },
                {
                    id: 'elem_event-' + this.id,
                    items: {
                        id: 'form-field-event-' + this.id,
                        fieldLabel: gt.gettext('Event identifier'),
                        name: 'event-' + this.id,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true,
                        value: this.ev
                    }
                },
                {
                    id: 'elem_globfunc-' + this.id,
                    items: {
                        id: 'form-field-globfunc-' + this.id,
                        fieldLabel: gt.gettext('Global interface'),
                        name: 'globfunc-' + this.id,
                        value: this.globfunc,
                        xtype: 'combo',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true,
                        hiddenName: 'v_globfunc-' + this.id,
                        hiddenValue: this.globfunc,
                        store: LocObjectsEditor.globfuncs,
                        listWidth: 600,
                        triggerAction: 'all',
                        forceSelection: true
                    }
                },
                {
                    id: 'elem_specfunc-' + this.id,
                    items: {
                        id: 'form-field-specfunc-' + this.id,
                        fieldLabel: gt.gettext('Special function'),
                        name: 'specfunc-' + this.id,
                        value: this.specfunc,
                        xtype: 'combo',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true,
                        hiddenName: 'v_specfunc-' + this.id,
                        hiddenValue: this.specfunc,
                        store: LocObjectsEditor.specfuncs,
                        listWidth: 600,
                        triggerAction: 'all',
                        forceSelection: true
                    }
                },
                {
                    id: 'elem_hint-' + this.id,
                    items: {
                        id: 'form-field-hint-' + this.id,
                        fieldLabel: gt.gettext('Hint on mouseover'),
                        name: 'hint-' + this.id,
                        xtype: 'textfield',
                        allowBlank: true,
                        msgTarget: 'side',
                        anchor: '-30',
                        autoHeight: true,
                        value: this.hint
                    }
                }
            ]
        }
    });
    this.form.conditions.push({
        id: 'elem_position-' + this.id,
        condition: "form_value('position-expr-" + this.id + "')"
    });
    this.form.conditions.push({
        id: 'elem_location-' + this.id,
        condition: "form_value('action-" + this.id + "')=='move'"
    });
    this.form.conditions.push({
        id: 'elem_event-' + this.id,
        condition: "form_value('action-" + this.id + "')=='event'"
    });
    this.form.conditions.push({
        id: 'elem_url-' + this.id,
        condition: "form_value('action-" + this.id + "')=='open'"
    });
    this.form.conditions.push({
        id: 'elem_globfunc-' + this.id,
        condition: "form_value('action-" + this.id + "')=='globfunc'"
    });
    this.form.conditions.push({
        id: 'elem_specfunc-' + this.id,
        condition: "form_value('action-" + this.id + "')=='specfunc'"
    });
    this.form.conditions.push({
        id: 'elem_hint-' + this.id,
        condition: "form_value('action-" + this.id + "')!='move'"
    });
};

VisualObject.prototype.activate = function() {
    this.cmp.addClass('im');
    this.cmp.expand(false);
};

VisualObject.prototype.deactivate = function() {
    this.cmp.removeClass('im');
    this.cmp.collapse(false);
};

VisualObject.prototype.cleanup = function() {
    this.form.form_cmp.remove(this.cmp);
    for (var ci = this.form.conditions.length - 1; ci >= 0; ci--) {
        var id = this.form.conditions[ci].id;
        if (id == 'elem_location-' + this.id ||
            id == 'elem_position-' + this.id ||
            id == 'elem_event-' + this.id ||
            id == 'elem_url-' + this.id ||
            id == 'elem_globfunc-' + this.id ||
            id == 'elem_hint-' + this.id ||
            id == 'elem_specfunc-' + this.id) {
            this.form.conditions.splice(ci, 1);
        }
    }
};

VisualObject.prototype.getPolygonStr = function() {
    var tokens = new Array();
    for (var i = 0; i < this.poly.length - 1; i++) {
        var pt = this.poly[i];
        tokens.push(pt.x + ',' + pt.y);
    }
    return tokens.join(',');
};

VisualObject.prototype.setPolygonStr = function(str) {
    var tokens = str.split(',');
    if (tokens.length % 2) {
        Ext.Msg.alert(gt.gettext('Error'), gt.gettext('Number of coordinates must not be odd'))
        return;
    }
    if (tokens.length < 6) {
        Ext.Msg.alert(gt.gettext('Error'), gt.gettext('Minimal number of vertices - 3'))
        return;
    }
    for (var i = 0; i < tokens.length; i++) {
        var token = tokens[i];
        if (!token.match(/^-?[0-9]+$/)) {
            Ext.Msg.alert(gt.gettext('Error'), gt.gettext('Invalid non-integer coordinate encountered'));
            return;
        }
    }
    this.poly = new Array();
    for (var i = 0; i < tokens.length; i += 2) {
        this.poly.push({x: parseInt(tokens[i]), y: parseInt(tokens[i + 1])});
    }
    this.poly.push(this.poly[0]);
};

VisualObject.prototype.update_form = function() {
    Ext.get('form-field-polygon-' + this.id).dom.value = this.getPolygonStr();
    Ext.get('form-field-x-' + this.id).dom.value = this.x;
    Ext.get('form-field-y-' + this.id).dom.value = this.y;
};

VisualObject.prototype.loadImage = function () {
    var obj = this;
    if (!obj.image) {
        return;
    }
    var img = new Image();
    img.onload = function () {
        obj.img = img;
        LocObjectsEditor.touch_object(obj);
        LocObjectsEditor.paint();
    };
    img.src = obj.image;
};

LocObjectsEditor = {};

LocObjectsEditor.cleanup = function() {
    this.uninstall_global_events();
    this.objects = new Array();
    this.mouse = new Array();
    this.handler_size = 8;
    this.active_object = undefined;
    this.active_handler = undefined;
    this.highlighted_handler = undefined;
    this.highlighted_segment = undefined;
    this.highlighted_object = undefined;
    this.drag_handler = undefined;
    this.drag_object = undefined;
    this.clip_x1 = undefined;
    this.clip_x2 = undefined;
    this.clip_y1 = undefined;
    this.clip_y2 = undefined;
    this.object_id = 0;
    this.actions = new Array();
    this.locations = new Array();
    this.globfuncs = new Array();
    this.specfuncs = new Array();
};

LocObjectsEditor.init = function(submit_url, width, height) {
    this.cleanup();
    this.width = width;
    this.height = height;
    /* creating canvas */
    var canvas = document.createElement('canvas');
    canvas.id = 'imagemap-canvas';
    canvas.width = width;
    canvas.height = height;
    try {
        G_vmlCanvasManager.initElement(canvas);
        Ext.getDom('imagemap-ie-warning').style.display = 'block';
    } catch (e) {}
    Ext.getDom('imagemap-div').appendChild(canvas);
    this.ctx = canvas.getContext('2d');
    this.canvas = Ext.get(canvas);
    /* creating form */
    this.form = new Form({
        url: submit_url,
        fields: [],
        buttons: [
            {
                text: gt.gettext('Save')
            },
            {
                text: gt.gettext('Upload visual object image'),
                xtype: 'button',
                icon: '/st-mg/icons/image.gif',
                listeners: {
                    click: function() {
                        LocObjectsEditor.add_object();
                    }
                }
            },
            {
                text: gt.gettext('Add image from the storage'),
                xtype: 'button',
                icon: '/st-mg/icons/image.gif',
                listeners: {
                    click: function() {
                        LocObjectsEditor.select_object();
                    }
                }
            },
            {
                text: gt.gettext('Add new clickable area'),
                xtype: 'button',
                icon: '/st-mg/icons/polygon.png',
                listeners: {
                    click: function() {
                        LocObjectsEditor.add_area();
                    }
                }
            }
        ],
        beforeSubmit: function () {
            for (var i = 0; i < LocObjectsEditor.objects.length; i++) {
                var obj = LocObjectsEditor.objects[i];
                Ext.get('form-order-' + obj.id).dom.value = i;
            }
        },
        errorHandler: function (form, error) {
            var fields = ['x', 'y', 'polygon', 'visible', 'action', 'location', 'url', 'id',
                    'position-expr', 'position'];
            for (var i = 0; i < LocObjectsEditor.objects.length; i++) {
                var obj = LocObjectsEditor.objects[i];
                var id = obj.id;
                for (var j = 0; j < fields.length; j++) {
                    var err = error[fields[j] + '-' + id];
                    if (err) {
                        Ext.getCmp('panel-obj-' + id).expand(false);
                        Ext.getCmp('form-field-' + fields[j] + '-' + id).markInvalid(err);
                    }
                }
            }
            return false;
        }
    });
};

LocObjectsEditor.add_object = function () {
    if (this.storage_unavailable)
        return Ext.Msg.alert(gt.gettext('Error'), this.storage_unavailable);
    var th = this;
    th.cancel();
    var win = new Ext.Window({
        id: 'upload-window',
        modal: true,
        title: gt.gettext('Add new visual object'),
        width: 500,
        autoHeight: true,
        padding: '20px 0 20px 20px',
        items: [
            new Form({
                url: '/admin-storage/static/new',
                fields: [
                    {type: 'hidden', name: 'image', 'value': '1'},
                    {type: 'hidden', name: 'group', 'value': 'location-objects'},
                    {type: 'fileuploadfield', name: 'ob', 'label': gt.gettext('Image file')}
                ],
                buttons: [
                    {text: gt.gettext('Upload')}
                ],
                successHandler: function(f, action) {
                    var cmp = Ext.getCmp('upload-window');
                    if (cmp)
                        cmp.close();
                    var res = Ext.util.JSON.decode(action.response.responseText);
                    var obj = th.new_object();
                    th.active_object = obj;
                    obj.x = Math.floor(th.width / 2 + 0.5);
                    obj.y = Math.floor(th.height / 2 + 0.5);
                    obj.width = res.width;
                    obj.height = res.height;
                    obj.image = res.uri;
                    obj.visible = '1';
                    obj.action = 'none';
                    obj.render(th.form);
                    th.form.enforce_conditions(true);
                    th.form.doLayout();
                    obj.activate();
                    obj.poly.push({x: Math.floor(-obj.width / 2), y: Math.floor(-obj.height / 2)});
                    obj.poly.push({x: Math.floor(+obj.width / 2), y: Math.floor(-obj.height / 2)});
                    obj.poly.push({x: Math.floor(+obj.width / 2), y: Math.floor(+obj.height / 2)});
                    obj.poly.push({x: Math.floor(-obj.width / 2), y: Math.floor(+obj.height / 2)});
                    obj.poly.push(obj.poly[0]);
                    th.touch_active_object();
                    th.paint();
                    obj.update_form();
                    obj.loadImage();
                }
            })
        ]
    });
    win.show();
};

LocObjectsEditor.select_object = function () {
    var th = this;
    th.cancel();
    var win = new Ext.Window({
        id: 'upload-window',
        modal: true,
        title: gt.gettext('Add new visual object from the storage'),
        width: 500,
        autoHeight: true,
        padding: '20px 0 20px 20px',
        items: [
            new Form({
                fields: [
                    {
                        type: 'textfield',
                        name: 'uri',
                        'label': gt.gettext('Object URI (only URIs from the storage are allowed)')
                    }
                ],
                buttons: [
                    {
                        text: gt.gettext('Add object'),
                    }
                ],
                submit: function () {
                    var uri = Ext.get('form-field-uri').getValue();
                    if (!uri) {
                        Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Invalid URI')));
                        return;
                    }

                    /* Load the image */
                    var img = new Image();
                    img.onload = function () {
                        var obj = th.new_object();
                        th.active_object = obj;
                        obj.x = Math.floor(th.width / 2 + 0.5);
                        obj.y = Math.floor(th.height / 2 + 0.5);
                        obj.image = uri;
                        obj.img = img;
                        obj.width = img.width;
                        obj.height = img.height;
                        obj.visible = '1';
                        obj.action = 'none';
                        obj.render(th.form);
                        th.form.enforce_conditions(true);
                        th.form.doLayout();
                        obj.activate();
                        obj.poly.push({x: Math.floor(-obj.width / 2), y: Math.floor(-obj.height / 2)});
                        obj.poly.push({x: Math.floor(+obj.width / 2), y: Math.floor(-obj.height / 2)});
                        obj.poly.push({x: Math.floor(+obj.width / 2), y: Math.floor(+obj.height / 2)});
                        obj.poly.push({x: Math.floor(-obj.width / 2), y: Math.floor(+obj.height / 2)});
                        obj.poly.push(obj.poly[0]);
                        th.touch_active_object();
                        th.paint();
                        obj.update_form();
                    };
                    img.onerror = function () {
                        Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Error loading %s'), uri));
                    };
                    img.onabort = function () {
                        Ext.Msg.alert(gt.gettext('Error'), sprintf(gt.gettext('Error loading %s'), uri));
                    };
                    img.src = uri;
                    win.destroy();
                }
            })
        ]
    });
    win.show();
};

LocObjectsEditor.add_area = function () {
    var th = this;
    th.cancel();
    var cmp = Ext.getCmp('upload-window');
    if (cmp) {
        cmp.close();
    }
    var obj = th.new_object();
    th.active_object = obj;
    obj.x = Math.floor(th.width / 2 + 0.5);
    obj.y = Math.floor(th.height / 2 + 0.5);
    obj.width = 100;
    obj.height = 100;
    obj.visible = '1';
    obj.action = 'none';
    obj.render(th.form);
    th.form.enforce_conditions(true);
    th.form.doLayout();
    obj.activate();
    obj.poly.push({x: Math.floor(-obj.width / 2), y: Math.floor(-obj.height / 2)});
    obj.poly.push({x: Math.floor(+obj.width / 2), y: Math.floor(-obj.height / 2)});
    obj.poly.push({x: Math.floor(+obj.width / 2), y: Math.floor(+obj.height / 2)});
    obj.poly.push({x: Math.floor(-obj.width / 2), y: Math.floor(+obj.height / 2)});
    obj.poly.push(obj.poly[0]);
    th.touch_active_object();
    th.paint();
    obj.update_form();
};

LocObjectsEditor.run = function() {
    this.paint(true);
    this.form.enforce_conditions(true);
    this.form.render('imagemap-form');
    this.canvas.on('dblclick', this.dblclick, this);
    this.canvas.on('mousedown', this.mouse_down, this);
    this.canvas.on('mousemove', this.mouse_move, this);
    this.canvas.on('mouseup', this.mouse_up, this);
    this.canvas.on('contextmenu', this.context_menu, this);
    Ext.get('admin-viewport').on('keydown', this.key_down, this);
};

LocObjectsEditor.point_in_object = function(pt, obj) {
    var poly = obj.poly;
    pt = {
        x: pt.x - obj.x,
        y: pt.y - obj.y
    };
    for (var c = false, i = -1, l = poly.length, j = l - 1; ++i < l; j = i) {
        ((poly[i].y <= pt.y && pt.y < poly[j].y) || (poly[j].y <= pt.y && pt.y < poly[i].y))
        && (pt.x < (poly[j].x - poly[i].x) * (pt.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)
        && (c = !c);
    }
    if (c) {
        return true;
    }
    for (var i = 0; i < poly.length; i++) {
        var vx = poly[i].x - pt.x;
        var vy = poly[i].y - pt.y;
        if (vx * vx + vy * vy < this.handler_size * this.handler_size)
            return true;
    }
    return false;
};

LocObjectsEditor.paint_handler = function(obj, pt) {
    this.ctx.save();
    if (this.active_handler == pt && this.highlighted_handler == pt) {
        this.ctx.fillStyle = '#ff8080';
        this.ctx.strokeStyle = '#804040';
    } else if (this.active_handler == pt) {
        this.ctx.fillStyle = '#ffc0c0';
        this.ctx.strokeStyle = '#804040';
    } else if (this.highlighted_handler == pt) {
        this.ctx.fillStyle = '#ffffff';
        this.ctx.strokeStyle = '#000000';
    } else {
        this.ctx.fillStyle = '#808080';
        this.ctx.strokeStyle = '#404040';
    }
    this.ctx.fillRect(obj.x + pt.x + 0.5 - this.handler_size / 2, obj.y + pt.y + 0.5 - this.handler_size / 2, this.handler_size, this.handler_size);
    this.ctx.strokeRect(obj.x + pt.x + 0.5 - this.handler_size / 2, obj.y + pt.y + 0.5 - this.handler_size / 2, this.handler_size, this.handler_size);
    this.ctx.restore();
};

LocObjectsEditor.paint_segment = function(obj, pt1, pt2) {
    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.moveTo(obj.x + pt1.x + 0.5, obj.y + pt1.y + 0.5);
    this.ctx.lineTo(obj.x + pt2.x + 0.5, obj.y + pt2.y + 0.5);
    this.ctx.strokeStyle = '#c0c0c0';
    this.ctx.lineWidth = 2;
    this.ctx.stroke();
    this.ctx.restore();
};

LocObjectsEditor.update_highlighted = function() {
    if (this.drag_handler || this.drag_object)
        return false;
    var old_highlighted_object = this.highlighted_object;
    var old_highlighted_handler = this.highlighted_handler;
    var old_highlighted_segment = this.highlighted_segment;
    this.highlighted_handler = undefined;
    this.highlighted_segment = undefined;
    this.highlighted_object = undefined;
    if (this.active_object) {
        var best_dist = undefined;
        for (var j = 0; j < this.active_object.poly.length - 1; j++) {
            var pt = this.active_object.poly[j];
            var pv = {x: pt.x + this.active_object.x - this.mouse.x, y: pt.y + this.active_object.y - this.mouse.y};
            var dist = Math.sqrt(pv.x * pv.x + pv.y * pv.y);
            if (dist < this.handler_size) {
                if (best_dist == undefined || dist < best_dist) {
                    best_dist = dist;
                    this.highlighted_handler = pt;
                    this.highlighted_object = this.active_object;
                }
            }
        }
        for (var j = 0; j < this.active_object.poly.length - 1; j++) {
            var pt1 = this.active_object.poly[j];
            pt1 = {
                x: pt1.x + this.active_object.x,
                y: pt1.y + this.active_object.y
            };
            var pt2 = this.active_object.poly[j + 1];
            pt2 = {
                x: pt2.x + this.active_object.x,
                y: pt2.y + this.active_object.y
            };
            if (this.mouse.x >= pt1.x && this.mouse.x <= pt2.x || this.mouse.x <= pt1.x && this.mouse.x >= pt2.x) {
                if (this.mouse.y >= pt1.y && this.mouse.y <= pt2.y || this.mouse.y <= pt1.y && this.mouse.y >= pt2.y) {
                    /* distance from segment (pt1, pt2) to the mouse cursor */
                    var v12 = {x: pt2.x - pt1.x, y: pt2.y - pt1.y};
                    var l12 = Math.sqrt(v12.x * v12.x + v12.y * v12.y);
                    if (l12 < 1) l12 = 1;
                    var u12 = {x: v12.x / l12, y: v12.y / l12};
                    var n12 = {x: -u12.y, y: u12.x};
                    var vm = {x: this.mouse.x - pt1.x, y: this.mouse.y - pt1.y};
                    var dist = Math.abs(vm.x * n12.x + vm.y * n12.y) + this.handler_size;
                    if (dist < this.handler_size * 1.5) {
                        if (best_dist == undefined || dist < best_dist) {
                            best_dist = dist;
                            this.highlighted_segment = j;
                            this.highlighted_handler = undefined;
                            this.highlighted_object = this.active_object;
                        }
                    }
                }
            }
        }
    }
    if (!this.highlighted_object) {
        for (var i = this.objects.length - 1; i >= 0; i--) {
            if (this.point_in_object(this.mouse, this.objects[i])) {
                this.highlighted_object = this.objects[i];
                break;
            }
        }
    }
    var modified = false;
    if (this.highlighted_handler != old_highlighted_handler) {
        this.touch_active_object();
        modified = true;
    }
    if (this.highlighted_segment != old_highlighted_segment) {
        this.touch_active_object();
        modified = true;
    }
    if (this.highlighted_object != old_highlighted_object) {
        this.touch_object(this.highlighted_object);
        this.touch_object(old_highlighted_object);
        modified = true;
    }
    return modified;
};

LocObjectsEditor.paint = function(force) {
    if (this.clip_x1 == undefined && !force)
        return;
    this.ctx.save();
    var clipping = true;
    try {
        if (G_vmlCanvasManager) {
            clipping = false;
        }
    } catch (e) {
    }
    if (clipping && !force) {
        this.ctx.beginPath();
        this.ctx.rect(this.clip_x1, this.clip_y1, this.clip_x2 - this.clip_x1 + 1, this.clip_y2 - this.clip_y1 + 1);
        this.ctx.clip();
    }
    this.ctx.clearRect(0, 0, this.width, this.height);
    for (var i = 0; i < this.objects.length; i++) {
        var object = this.objects[i];
        this.ctx.save();
        if (object.img) {
            this.ctx.drawImage(object.img, Math.floor(object.x - object.width / 2), Math.floor(object.y - object.height / 2));
        }
        this.ctx.beginPath();
        this.ctx.moveTo(object.poly[0].x + object.x + 0.5, object.poly[0].y + object.y + 0.5);
        for (var j = 1; j < object.poly.length; j++) {
            this.ctx.lineTo(object.poly[j].x + object.x + 0.5, object.poly[j].y + object.y + 0.5);
        }
        if (this.highlighted_object == object && this.active_object == object) {
            this.ctx.fillStyle = '#ff8080';
        } else if (this.active_object == object) {
            this.ctx.fillStyle = '#ffc0c0';
        } else if (this.highlighted_object == object) {
            this.ctx.fillStyle = '#ffffff';
        } else {
            this.ctx.fillStyle = '#c0c0c0';
        }
        this.ctx.globalAlpha = 0.3;
        this.ctx.lineTo(object.poly[0].x + object.x + 0.5, object.poly[0].y + object.y + 0.5);
        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.globalAlpha = 1;
        if (this.highlighted_object == object) {
            this.ctx.strokeStyle = '#000000';
        } else {
            this.ctx.strokeStyle = '#404040';
        }
        this.ctx.stroke();
        this.ctx.restore();
        /* handlers */
        if (object == this.active_object) {
            if (this.highlighted_segment != undefined) {
                var p1 = object.poly[this.highlighted_segment];
                var p2 = object.poly[this.highlighted_segment + 1];
                this.paint_segment(object, p1, p2);
            }
            for (var j = 0; j < object.poly.length - 1; j++) {
                this.paint_handler(object, object.poly[j]);
            }
        }
    }
    this.ctx.restore();
    this.clip_x1 = undefined;
    this.clip_y1 = undefined;
    this.clip_x2 = undefined;
    this.clip_y2 = undefined;
};

LocObjectsEditor.new_object = function() {
    var object = new VisualObject(++this.object_id);
    this.objects.push(object);
    return object;
};

LocObjectsEditor.dblclick = function(ev, target) {
    ev.stopEvent();
    if (ev.button == 0) {
        if (this.highlighted_object) {
            /* Send to back */
            for (var i = 0; i < this.objects.length; i++) {
                if (this.objects[i] == this.active_object) {
                    this.objects.splice(i, 1);
                    this.objects.splice(0, 0, this.active_object);
                    break;
                }
            }
            this.touch_active_object();
            this.paint();
        }
    }
};

LocObjectsEditor.mouse_down = function(ev, target) {
    ev.stopEvent();
    var page_coo = ev.getXY();
    var pt = {
        x: page_coo[0] - this.canvas.getLeft(),
        y: page_coo[1] - this.canvas.getTop()
    };
    this.mouse = pt;
    var repaint = false;
    if (this.update_highlighted()) {
        repaint = true;
    }
    if (ev.button == 0) {
        if (this.highlighted_handler) {
            /* activating handler */
            this.active_handler = this.highlighted_handler;
            this.drag_handler = {
                start_x: this.active_handler.x, start_y: this.active_handler.y,
                mouse_start_x: this.mouse.x, mouse_start_y: this.mouse.y
            };
            this.touch_active_object();
            repaint = true;
        } else if (this.highlighted_segment != undefined) {
            /* splitting segment into 2 segments */
            var polypt = {
                x: pt.x - this.active_object.x,
                y: pt.y - this.active_object.y
            };
            this.active_handler = polypt;
            this.active_object.poly.splice(this.highlighted_segment + 1, 0, polypt);
            this.drag_handler = {
                start_x: this.active_handler.x, start_y: this.active_handler.y,
                mouse_start_x: this.mouse.x, mouse_start_y: this.mouse.y
            };
            this.highlighted_segment = undefined;
            this.touch_active_object();
            repaint = true;
        } else if (this.highlighted_object) {
            this.touch_active_object();
            if (this.active_object)
                this.active_object.deactivate();
            this.active_object = this.highlighted_object;
            this.active_object.activate();
            this.active_handler = undefined;
            this.active_segment = undefined;
            this.drag_object = {
                offset_x: 0, offset_y: 0,
                mouse_last_x: this.mouse.x, mouse_last_y: this.mouse.y
            };
            this.touch_active_object();
            repaint = true;
        } else if (this.active_object) {
            this.touch_active_object();
            this.active_object.deactivate();
            this.active_object = undefined;
            this.active_handler = undefined;
            this.active_segment = undefined;
            repaint = true;
        }
    } else if (ev.button == 2) {
        this.cancel();
        repaint = true;
    }
    if (repaint) {
        this.paint();
    }
    if (!this.global_events) {
        Ext.get('admin-viewport').on('mousemove', this.mouse_move, this);
        Ext.get('admin-viewport').on('mouseup', this.mouse_up, this);
        Ext.get('admin-viewport').on('contextmenu', this.context_menu, this);
        this.global_events = true;
    }
};

LocObjectsEditor.touch_active_object = function(poly) {
    this.touch_object(this.active_object);
};

LocObjectsEditor.touch_object = function(object) {
    if (object) {
        this.touch({
            x: Math.floor(object.x - object.width / 2),
            y: Math.floor(object.y - object.height / 2)
        });
        this.touch({
            x: Math.floor(object.x + object.width / 2),
            y: Math.floor(object.y + object.height / 2)
        });
        for (var pi = 0; pi < object.poly.length; pi++) {
            this.touch({
                x: object.poly[pi].x + object.x,
                y: object.poly[pi].y + object.y
            });
        }
    }
};

LocObjectsEditor.touch = function(pt) {
    if (this.clip_x1 == undefined) {
        this.clip_x1 = pt.x;
        this.clip_x2 = pt.x;
        this.clip_y1 = pt.y;
        this.clip_y2 = pt.y;
    } else {
        if (pt.x - this.handler_size < this.clip_x1)
            this.clip_x1 = pt.x - this.handler_size;
        if (pt.x + this.handler_size > this.clip_x2)
            this.clip_x2 = pt.x + this.handler_size;
        if (pt.y - this.handler_size < this.clip_y1)
            this.clip_y1 = pt.y - this.handler_size;
        if (pt.y + this.handler_size > this.clip_y2)
            this.clip_y2 = pt.y + this.handler_size;
    }
};

LocObjectsEditor.cancel = function() {
    if (this.drag_handler) {
        this.touch_active_object();
        this.active_handler.x = this.drag_handler.start_x;
        this.active_handler.y = this.drag_handler.start_y;
        this.touch_active_object();
        this.drag_handler = undefined;
        this.active_object.update_form();
    } else if (this.drag_object) {
        this.touch_active_object();
        this.active_object.x -= this.drag_object.offset_x;
        this.active_object.y -= this.drag_object.offset_y;
        this.touch_active_object();
        this.drag_object = undefined;
        this.active_object.update_form();
    } else if (this.active_object) {
        this.touch_active_object();
        this.active_object.deactivate();
        this.active_object = undefined;
        this.active_handler = undefined;
        this.active_segment = undefined;
    }
};

LocObjectsEditor.mouse_move = function(ev, target) {
    ev.stopEvent();
    var page_coo = ev.getXY();
    var pt = {
        x: page_coo[0] - this.canvas.getLeft(),
        y: page_coo[1] - this.canvas.getTop()
    };
    this.mouse = pt;
    var repaint = false;
    if (this.update_highlighted()) {
        repaint = true;
    }
    if (this.drag_handler) {
        this.touch_active_object();
        this.active_handler.x = pt.x - this.drag_handler.mouse_start_x + this.drag_handler.start_x;
        this.active_handler.y = pt.y - this.drag_handler.mouse_start_y + this.drag_handler.start_y;
        this.touch_active_object();
        repaint = true;
        this.active_object.update_form();
    } else if (this.drag_object) {
        this.touch_active_object();
        var delta_x = pt.x - this.drag_object.mouse_last_x;
        var delta_y = pt.y - this.drag_object.mouse_last_y;
        this.drag_object.mouse_last_x = pt.x;
        this.drag_object.mouse_last_y = pt.y;
        this.drag_object.offset_x += delta_x;
        this.drag_object.offset_y += delta_y;
        this.active_object.x += delta_x;
        this.active_object.y += delta_y;
        this.touch_active_object();
        repaint = true;
        this.active_object.update_form();
    }
    if (repaint)
        this.paint();
};

LocObjectsEditor.uninstall_global_events = function() {
    if (this.global_events) {
        Ext.get('admin-viewport').un('mousemove', this.mouse_move, this);
        Ext.get('admin-viewport').un('mouseup', this.mouse_up, this);
        Ext.get('admin-viewport').un('contextmenu', this.context_menu, this);
        this.global_events = false;
    }
};

LocObjectsEditor.mouse_up = function(ev, target) {
    this.uninstall_global_events();
    ev.stopEvent();
    var page_coo = ev.getXY();
    var pt = {
        x: page_coo[0] - this.canvas.getLeft(),
        y: page_coo[1] - this.canvas.getTop()
    };
    this.mouse = pt;
    var repaint = false;
    if (this.update_highlighted()) {
        repaint = true;
    }
    if (this.drag_handler) {
        this.drag_handler = undefined;
        this.touch_active_object();
        repaint = true;
    }
    if (this.drag_object) {
        this.drag_object = undefined;
        this.touch_active_object();
        repaint = true;
    }
    if (repaint)
        this.paint();
};

LocObjectsEditor.context_menu = function(ev, target) {
    ev.stopEvent();
};

LocObjectsEditor.key_down = function(ev, target) {
    if (!this.canvas.dom || this.canvas.dom != Ext.getDom('imagemap-canvas')) {
        // editor closed. uninstalling
        Ext.get('admin-viewport').un('keydown', this.key_down, this);
        this.cleanup();
        return;
    }
    var key = ev.getKey();
    if (key == ev.ESC) {
        ev.stopEvent();
        this.cancel();
        this.paint();
    } else if (key == ev.ENTER) {
        ev.stopEvent();
        this.cancel();
        this.paint();
        this.form.custom_submit(this.form.form_cmp.url);
    } else if (key == ev.DELETE) {
        ev.stopEvent();
        if (this.active_handler) {
            /* removing vertex */
            this.touch_active_object();
            for (var i = 0; i < this.active_object.poly.length; i++) {
                if (this.active_object.poly[i] == this.active_handler) {
                    this.active_object.poly.splice(i, 1);
                    if (i == 0) {
                        /* first point removed */
                        this.active_object.poly[this.active_object.poly.length - 1] = this.active_object.poly[0];
                    }
                    this.active_handler = this.active_object.poly[i];
                    this.active_object.update_form();
                    break;
                }
            }
            if (this.active_object.poly.length < 4) {
                /* removing object */
                for (var i = 0; i < this.objects.length; i++) {
                    if (this.objects[i] == this.active_object) {
                        this.active_object.cleanup();
                        this.objects.splice(i, 1);
                        break;
                    }
                }
                this.active_object = undefined;
                this.active_handler = undefined;
                this.active_segment = undefined;
            }
            this.drag_handler = undefined;
            this.update_highlighted();
            this.paint();
        } else if (!this.active_handler && !this.highlighted_handler && this.active_object) {
            /* removing object */
            this.touch_active_object();
            for (var i = 0; i < this.objects.length; i++) {
                if (this.objects[i] == this.active_object) {
                    this.active_object.cleanup();
                    this.objects.splice(i, 1);
                    break;
                }
            }
            this.active_object = undefined;
            this.drag_handler = undefined;
            this.active_handler = undefined;
            this.active_segment = undefined;
            this.update_highlighted();
            this.paint();
        }
    }
};

wait(['admin-form', 'FileUploadField'], function() {
    loaded('locobjects-editor');
});
