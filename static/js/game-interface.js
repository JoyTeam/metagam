Game.progress = new Array();
Game.dynamic_blocks = {};
Game.dynamic_block_deps = {};

Game.now = function() {
    return TimeSync.getTime() * 1000.0;
};

Game.reload = function() {
    Stream.initialized = false;
    var frm = document.createElement('form');
    frm.method = 'post';
    frm.action = '/';
    var inp = document.createElement('input');
    inp.type = 'hidden';
    inp.name = 'session';
    inp.value = Ext.util.Cookies.get('mgsess-' + Game.app);
    frm.appendChild(inp);
    Ext.getBody().dom.appendChild(frm);
    frm.submit();
};

Game.close = function() {
    Stream.initialized = false;
    document.location = 'http://' + Game.domain;
};

Game.logout = function() {
    Stream.initialized = false;
    document.location = 'http://' + Game.domain + '/auth/logout';
};

Game.msg = function(title, str, add_cls) {
    if (!this.msgCt){
        this.msgCt = Ext.DomHelper.insertFirst(document.body, {id: 'msg-div'}, true);
    }
    var m = Ext.DomHelper.append(this.msgCt, '<div class="msg' + (add_cls ? ' ' + add_cls : '') + '">' + (title ? '<h3>' + title + '</h3>' : '') + '<p>' + str + '</p></div>', true);
    m.hide();
    m.slideIn('t').pause(3).ghost('t', {remove: true});
};

Game.info = function(title, str) {
    this.msg(title, str, 'msg-info');
};

Game.error = function(title, str) {
    this.msg(title, str, 'msg-error');
};

Game.msg_info = function(pkt) {
    this.info(pkt.title, pkt.content);
};

Game.msg_error = function(pkt) {
    this.error(pkt.title, pkt.content);
};

Game.main_open = function(uri) {
    try {
        if (uri.uri)
            uri = uri.uri;
    } catch (e) {
    }
    if (uri.charAt(0) == '/') {
        uri = 'http://' + Game.domain + uri;
    }
    try {
        Game.main_frame().location.href = uri;
    } catch (e) {
        this.error(gt.gettext('Exception'), e);
    }
    return false;
};

Game.progress_stop = function(id) {
    if (this.progress[id] && this.progress[id].timer) {
        window.clearInterval(this.progress[id].timer);
        this.progress[id].timer = undefined;
    }
};

Game.progress_set = function(id, ratio) {
    this.progress_stop(id);
    this.progress_show(id, ratio);
};

Game.main_frame = function () {
    var iframe = Ext.getCmp('main-iframe');
    var win = iframe.el.dom.contentWindow || window.frames['main-iframe'];
    return win;
};

Game.dom_query = function (query) {
    var els = Ext.query(query);
    try {
        var els2 = Ext.query(query, Game.main_frame_document());
        for (var i = 0; i < els2.length; i++) {
            els.push(els2[i]);
        }
    } catch (e) {
    }
    return els;
};

Game.progress_show = function(id, ratio) {
    if (ratio < 0)
        ratio = 0;
    if (ratio > 1)
        ratio = 1;
    var progress = this.progress[id];
    if (!progress) {
        progress = {};
        this.progress[id] = progress;
    }
    progress.ratio = ratio;
    var els = Game.dom_query('.progress-' + id);
    for (var i = 0; i < els.length; i++) {
        var el = Ext.get(els[i]);
        if (el.content_width == undefined) {
            el.content_width = el.parent().getWidth(true);
        }
        if (el.content_height == undefined) {
            el.content_height = el.parent().getHeight(true);
        }
        if (el.hasClass('progress-indicator-horizontal')) {
            el.dom.style.width = Math.floor(ratio * el.content_width) + 'px';
            el.dom.style.height = el.content_height + 'px';
        }
        if (el.hasClass('progress-indicator-vertical')) {
            el.dom.style.width = el.content_width + 'px';
            el.dom.style.height = Math.floor(ratio * el.content_height) + 'px';
        }
        if (!el.hasClass(id + '-notfull')) {
            if (ratio < 1) {
                el.removeClass(id + '-full');
                el.addClass(id + '-notfull');
            }
        }
        if (!el.hasClass(id + '-full')) {
            if (ratio >= 1) {
                el.removeClass(id + '-notfull');
                el.addClass(id + '-full');
            }
        }
    }
};

Game.progress_run = function(id, start_ratio, end_ratio, time_till_end) {
    this.progress_set(start_ratio);
    if (time_till_end > 0) {
        var now = this.now();
        this.progress[id] = {
            timer: window.setInterval(this.progress_tick.createDelegate(this, [id]), 30),
            start_ratio: start_ratio,
            end_ratio: end_ratio,
            start_time: now,
            end_time: now + time_till_end
        };
    }
};

Game.progress_tick = function(id) {
    try {
        var progress = this.progress[id];
        if (progress && progress.timer) {
            var now = this.now();
            if (now >= progress.end_time) {
                this.progress_show(id, 1);
                this.progress_stop(id);
            } else {
                var ratio = (now - progress.start_time) * (progress.end_ratio - progress.start_ratio) / (progress.end_time - progress.start_time) + progress.start_ratio;
                this.progress_show(id, ratio);
            }
        }
    } catch (e) {
        this.progress_stop(id);
        this.error(gt.gettext('Exception'), e);
    }
};

Game.onLayout = function() {
    for (var id in this.progress) {
        var progress = this.progress[id];
        if (progress.ratio == undefined)
            continue;
        var els = Game.dom_query('.progress-' + id);
        for (var i = 0; i < els.length; i++) {
            var el = Ext.get(els[i]);
            if (el.content_width != undefined) {
                el.content_width = undefined;
                el.dom.style.width = '1px';
            }
            if (el.content_height != undefined) {
                el.content_height = undefined;
                el.dom.style.height = '1px';
            }
        }
        this.progress_show(id, progress.ratio);
    }
};

Game.main_frame_document = function() {
    try {
        return Ext.getCmp('main-iframe').getFrameDocument();
    } catch (e) {
        this.error(gt.gettext('Exception'), e);
    }
    return undefined;
};

Game.fixupContentEl = function(el) {
    var def = Ext.get('default-' + el.contentEl);
    if (!def) {
        Ext.Msg.alert('Missing element: default-' + el.contentEl);
        return el;
    }
    if (Ext.getDom(el.contentEl)) {
        Ext.get(def.id).remove();
        if (el.loadWidth)
            el.width = Ext.get(el.contentEl).getWidth();
        if (el.loadHeight)
            el.height = Ext.get(el.contentEl).getHeight();
    } else {
        if (el.loadWidth)
            el.width = def.getWidth();
        if (el.loadHeight)
            el.height = def.getHeight();
        def.id = el.contentEl;
        def.dom.id = el.contentEl;
    }
    return el;
};

Game.loadMargins = function(el) {
    if (!el)
        return undefined;
    el = Ext.fly(el);
    if (!el)
        return undefined;
    var margins = el.dom.style.margin;
    if (!margins)
        return undefined;
    el.dom.style.margin = '';
    return margins;
};

Game.element = function(eid, cel, el) {
    /* creating container element */
    cel = cel || {};
    cel.id = eid;
    cel.xtype = cel.xtype || 'container';
    cel.contentEl = eid;
    cel.onLayout = function(shallow, forceLayout) {
        if (shallow !== true) {
            var cmp = Ext.getCmp(eid + '-content-container');
            if (cmp)
                cmp.doLayout(false, forceLayout);
        }
    };
    cel = this.fixupContentEl(cel);
    cel.id = eid + '-container';
    if (!cel.style)
        cel.style = {};
    cel.style.height = '100%';
    Ext.get(eid).dom.style.height = '100%';
    /* creating content element */
    var content = Ext.get(eid + '-content');
    if (content.dom.tagName == 'div' || content.dom.tagName == 'DIV') {
        el = el || {};
        el.margins = content.dom.style.margin;
        /* save static content items */
        var children = new Array();
        var childNodes = content.dom.childNodes;
        for (var i = childNodes.length - 1; i >= 0; i--) {
            var node = childNodes[i];
            content.dom.removeChild(node);
            children.push(node);
        }
        el.html = content.dom.innerHTML;
        /* 'content' is the innermost container. Remove it and create a new element
         * at the same place. */
        var content_parent = content.parent();
        var insert_here = content_parent.dom.insertBefore(document.createElement('div'), content.dom);
        content.remove();
        el.id = eid + '-content';
        el.xtype = el.xtype || 'container';
        el.flex = 1;
        el.layout = el.layout || 'fit';
        insert_here.id = eid + '-content-container';
        var container_options = {
            id: eid + '-content-container',
            applyTo: insert_here,
            layout: 'vbox',
            layoutConfig: {
                align: 'stretch'
            },
            items: [el]
        };
        if (!el.no_height)
            container_options.height = '100%';
        if (el.vertical) {
            el.vertical = undefined;
            container_options.width = '100%';
            container_options.layout = 'auto';
            container_options.layoutConfig = undefined;
        }
        var container = new Ext.Container(container_options);
        /* restore static content items */
        var dom = Ext.get(eid + '-content').dom;
        for (var i = children.length - 1; i >= 0; i--) {
            dom.appendChild(children[i]);
        }
    }
    return cel;
};

Game.panel = function(id, options) {
    var cel = {};
    var el = {
        layoutConfig: {
            align: 'stretch'
        }
    };
    options = options || {};
    if (options.vertical) {
        cel.loadWidth = true;
        el.vertical = true;
        el.layout = 'vbox';
        el.height = '100%';
    } else {
        cel.loadHeight = true;
        el.layout = 'hbox';
    }
    if (options.region) {
        cel.region = options.region;
    }
    el.items = [];
    var panel_info = this.panels[id];
    if (panel_info) {
        for (var i = 0; i < panel_info.blocks.length; i++) {
            var block = panel_info.blocks[i];
            var block_el = {
                xtype: 'box',
                flex: block.flex
            };
            if (options.vertical) {
                block_el.height = block.width;
            } else {
                block_el.width = block.width;
            }
            if (block.cls) {
                block_el.cls = 'block-' + block.cls;
            }
            if (block.tp == 'empty') {
            } else if (block.tp == 'buttons') {
                block_el.html = '';
                if (this.design_root) {
                    if (options.vertical) {
                        if (block.buttons_top) {
                            block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-top.png" alt="" />';
                        }
                    } else {
                        if (block.buttons_left) {
                            block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-left.png" alt="" />';
                        }
                    }
                }
                var hints = Ext.getDom('block-hints-' + block.cls);
                hints = hints ? hints.innerHTML.split(',') : undefined;
                if (options.vertical) {
                    if (hints) {
                        block_el.height = parseInt(hints[0]) * block.buttons.length + parseInt(hints[1]);
                    } else {
                        block_el.height = 32 * block.buttons.length + 32;
                    }
                } else {
                    if (hints) {
                        block_el.width = parseInt(hints[0]) * block.buttons.length + parseInt(hints[1]);
                    } else {
                        block_el.width = 32 * block.buttons.length + 32;
                    }
                }
                for (var j = 0; j < block.buttons.length; j++) {
                    var btn = block.buttons[j];
                    block_el.html += this.render_button(btn, {
                        menu_align: options.vertical ? (options.right ? 'tr-tl' : 'tl-tr') : 'tl-bl'
                    });
                }
                if (this.design_root) {
                    if (options.vertical) {
                        if (block.buttons_bottom) {
                            block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-bottom.png" alt="" />';
                        }
                    } else {
                        if (block.buttons_right) {
                            block_el.html += '<img src="' + this.design_root + '/' + block.cls + '-right.png" alt="" />';
                        }
                    }
                }
            } else if (block.tp == 'html') {
                block_el.html = block.html;
            } else if (block.tp == 'header') {
                var cls = 'panel-header-' + (options.vertical ? 'vertical' : 'horizontal');
                block_el.html = '<div class="' + cls + '"><div class="' + cls + '-1"><div class="' + cls + '-2"><div class="' + cls + '-3"><div class="' + cls + '-4"><div class="' + cls + '-5"><div class="' + cls + '-6"><div class="' + cls + '-7"><div class="' + cls + '-8"><div class="panel-header-horizontal-margin"></div><div class="' + cls + '-content-1"><div class="' + cls + '-10"><div class="' + cls + '-11"><table class="' + cls + '-9"><tr><td class="' + cls + '-12">' + block.html + '</td></tr></table></div></div></div></div></div></div></div></div></div></div></div></div>';
            } else if (block.tp == 'progress') {
                var cls = 'progress-' + (options.vertical ? 'vertical' : 'horizontal');
                var bars;
                if (block.progress_types.length) {
                    if (options.vertical) {
                        bars = '<table class="progress-bars-vertical"><tr>';
                        var width = Math.floor(100 / block.progress_types.length);
                        for (var j = 0; j < block.progress_types.length; j++) {
                            bars += '<td class="progress-bars-vertical-td" style="width: ' + width + '%"><div class="progress-indicator progress-indicator-vertical progress-' + block.progress_types[j] + '" style="height: 0px"></div></td>';
                        }
                        bars += '</tr></table>';
                    } else {
                        bars = '<div class="progress-bars-horizontal-margin"></div><table class="progress-bars-horizontal">';
                        var height = Math.floor(100 / block.progress_types.length);
                        for (var j = 0; j < block.progress_types.length; j++) {
                            bars += '<tr style="height: ' + height + '%"><td class="progress-bars-horizontal-td"><div class="progress-indicator progress-indicator-horizontal progress-' + block.progress_types[j] + '" style="width: 0px"></div></td></tr>';
                        }
                        bars += '</table>';
                    }
                } else {
                    bars = '';
                }
                block_el.html = '<div class="' + cls + '"><div class="' + cls + '-1"><div class="' + cls + '-2"><div class="' + cls + '-3"><div class="' + cls + '-4"><div class="' + cls + '-5"><div class="' + cls + '-6"><div class="' + cls + '-7"><div class="' + cls + '-8"><div class="' + cls + '-9">' + bars + '</div></div></div></div></div></div></div></div></div></div>';
            } else {
                block_el.html = block.tp;
            }
            el.items.push(block_el);
        }
    }
    var panel = this.element('panel-' + id, cel, el);
    return panel;
};

Game.setup_cabinet_layout = function() {
    new Ext.Viewport({
        id: 'cabinet-viewport',
        layout: 'fit',
        items: this.fixupContentEl({
            xtype: 'box',
            contentEl: 'cabinet-content'
        })
    });
};

Game.get_btn_id = function() {
    if (this.btn_id != undefined)
        return ++this.btn_id;
    this.btn_id = 1;
    return 1;
};

Game.render_button = function(btn, options) {
    options = options || {};
    var att = '';
    var btn_id = this.get_btn_id();
    var classes = new Array();
    if (btn.qevent) {
        att += ' onclick="Game.qevent(\'' + btn.qevent + '\')"';
        classes.push('clickable');
    } else if (btn.onclick) {
        att += ' onclick="' + btn.onclick + '"';
        classes.push('clickable');
    } else if (btn.popup) {
        att += ' onclick="Game.popup(\'panel-btn-' + btn_id + '\', \'' + btn.popup + '\', undefined, \'' + (options.menu_align || 'tl-bl') + '\');"';
        classes.push('clickable');
    }
    classes.push('btn-' + btn.id);
    att += ' class="' + classes.join(' ') + '"';
    var img = '<img id="panel-btn-' + btn_id + '" src="' + btn.image + '" alt="" title="' + btn.title + '"' + att + ' />';
    if (btn.href && !btn.onclick) {
        img = '<a href="' + btn.href + '" target="' + btn.target + '">' + img + '</a>';
    }
    this.buttons[btn.id] = btn;
    return img;
};

Game.popup = function(btn_id, popup_id, parent_menu, align) {
    var btn_el = Ext.get(btn_id);
    if (!btn_el)
        return;
    var popup = this.popups[popup_id];
    if (!popup)
        return;
    var menu = new Ext.menu.Menu({
    });
    if (!align)
        align = 'tl-bl';
    for (var i = 0; i < popup.buttons.length; i++) {
        var btn = popup.buttons[i];
        var btn_id = 'panel-btn-' + this.get_btn_id();
        menu.addMenuItem({
            id: btn_id,
            icon: btn.image,
            text: btn.title,
            href: btn.href,
            hrefTarget: btn.target,
            hideOnClick: btn.popup ? false : true,
            listeners: {
                click: (function(btn_el, e, btn, menu, btn_id) {
                    if (btn.onclick) {
                        eval(btn.onclick);
                    } else if (btn.popup) {
                        this.popup(btn_id, btn.popup, menu, 'tl-tr');
                    } else if (btn.qevent) {
                        Game.qevent(btn.qevent);
                    }
                }).createDelegate(this, [btn, menu, btn_id], true)
            }
        });
    }
    menu.show(btn_el, align, parent_menu);
    if (!parent_menu) {
        Ext.ux.ManagedIFrame.Manager.showShims();
        menu.addListener('hide', function() {
            Ext.ux.ManagedIFrame.Manager.hideShims();
        });
    }
};

Game.refresh_layout = function() {
    Ext.getCmp('game-viewport').doLayout(false, true);
};

Game.javascript = function(pkt) {
    eval(pkt.script);
};

Game.qevent = function (ev, params) {
    if (!params) {
        params = {};
    }
    params.ev = ev;
    Ext.Ajax.request({
        url: '/quest/event',
        method: 'POST',
        params: params,
        success: function (response, opts) {
            if (response && response.getResponseHeader) {
                var res = Ext.util.JSON.decode(response.responseText);
                if (res.redirect) {
                    Game.main_open(res.redirect);
                }
            }
        }
    });
};

Game.dynamic_block = function (uuid, css, text) {
    var deps = MMOScript.dependenciesText(text);
    var block = {
        css: css,
        text: text,
        dirty: true,
        deps: deps
    };
    for (var i = 0; i < deps.length; i++) {
        var dep = deps[i];
        var depStr = dep.join('.');
        if (depStr === 't' || depStr === 'T') {
            block.time_dependent = true;
        }
        if (!this.dynamic_block_deps[depStr]) {
            this.dynamic_block_deps[depStr] = [];
        }
        this.dynamic_block_deps[depStr].push(uuid);
    }
    Game.dynamic_blocks[uuid] = block;
    Game.update_dynamic_blocks();
};

Game.update_dynamic_blocks = function () {
    var self = this;
    if (self.dynamic_blocks_timer) {
        return;
    }
    var dirty = false;
    var time = TimeSync.getTime();
    if (!time) {
        dirty = true;
    } else {
        var env;
        var charParams = {};
        var charParamsDynamic = {};
        for (var uuid in self.dynamic_blocks) {
            if (self.dynamic_blocks.hasOwnProperty(uuid)) {
                var block = self.dynamic_blocks[uuid];
                if (block.dirty) {
                    if (!env) {
                        var now = TimeSync.getTime();
                        for (var id in Characters.myparams) {
                            if (Characters.myparams.hasOwnProperty(id)) {
                                var dynval = Characters.myparams[id];
                                charParams['p_' + id] = dynval.evaluateAndForget(now);
                                if (dynval.dynamic) {
                                    charParamsDynamic['p_' + id] = true;
                                }
                                charParams.uuid = Game.character;
                                charParams.name = Game.character_name;
                            }
                        }
                        env = {
                            globs: {
                                'char': charParams
                            }
                        };
                    };
                    var newVal = MMOScript.evaluateText(block.text, env);
                    if (newVal !== block.actualValue) {
                        block.actualValue = newVal;
                        var els = Game.dom_query(block.css);
                        for (var k = 0; k < els.length; k++) {
                            els[k].innerHTML = newVal;
                        }
                    }
                    var dynamic = false;
                    if (block.time_dependent) {
                        // Expression directly depending on t
                        dynamic = true;
                    } else {
                        // Check indirect dependencies on t
                        for (var j = 0; j < block.deps.length; j++) {
                            var dep = block.deps[j];
                            if (dep[0] === 'char') {
                                if (charParamsDynamic[dep[1]]) {
                                    dynamic = true;
                                    break;
                                }
                            }
                        }
                    }
                    if (dynamic) {
                        dirty = true;
                    } else {
                        block.dirty = false;
                    }
                }
            }
        }
    }
    if (dirty) {
        self.dynamic_blocks_timer = setTimeout(function () {
            self.dynamic_blocks_timer = undefined;
            self.update_dynamic_blocks();
        }, 10);
    }
};

Game.on_myparam_update = function (param) {
    var paramStr = 'char.p_' + param;
    var deps = Game.dynamic_block_deps[paramStr];
    if (deps) {
        var dirty = false;
        for (var i = 0; i < deps.length; i++) {
            var block = Game.dynamic_blocks[deps[i]];
            block.dirty = true;
            dirty = true;
        }
        if (dirty) {
            Game.update_dynamic_blocks();
        }
    }
};

Game.activity_update = function (text) {
    if (Game.activity_timer) {
        return;
    }
    var now = TimeSync.getTime();
    if (now) {
        var ratio = Game.activity_expr.evaluateAndForget(now);
        if (Game.activity_shown) {
            Game.activity_progress(ratio);
        } else {
            Game.activity_shown = true;
            Game.activity_show(ratio, text);
        }
        if (!Game.activity_expr.dynamic) {
            Game.activity_end_timer = setTimeout(function () {
                Ext.Ajax.request({
                    url: '/quest/activity-end',
                    method: 'POST'
                });
            }, 1000);
            return;
        }
    }
    Game.activity_timer = setTimeout(function () {
        Game.activity_timer = undefined;
        Game.activity_update(text);
    }, 10);
};

Game.activity_start = function (pkt) {
    Game.activity_expr = new DynamicValue(pkt.progress_expr);
    Game.activity_expr.setTill(pkt.progress_till);
    Game.activity_update(pkt.text || '');
};

Game.activity_stop = function () {
    if (Game.activity_shown) {
        delete Game.activity_shown;
        Game.activity_hide();
    }
    if (Game.activity_timer) {
        clearTimeout(Game.activity_timer);
        delete Game.activity_timer;
    }
    if (Game.activity_end_timer) {
        clearTimeout(Game.activity_end_timer);
        delete Game.activity_end_timer;
    }
};

Game.activity_show = function (ratio, text) {
    var hints = Ext.getDom('progress-bar-hints');
    hints = hints ? hints.innerHTML.split(',') : undefined;
    var fieldsX = hints ? parseInt(hints[0]) : 100;
    var heightY = hints ? parseInt(hints[1]) : 100;
    if (!Game.activity_initialized) {
        Game.activity_initialized = true;
        var viewport = Ext.getCmp('game-viewport');
        Game.activity_cmp = new Ext.Window({
            id: 'activity-progress-win',
            width: viewport.getWidth() - fieldsX,
            height: heightY,
            header: false,
            closable: false,
            resizable: false,
            draggable: false,
            items: Game.element('activity-progress', {}, {})
        });
        var content = Ext.getCmp('activity-progress-content');
        content.add({
            id: 'activity-progress-background',
            xtype: 'box'
        });
        content.add({
            id: 'activity-progress-indicator',
            xtype: 'box',
            style: {
                position: 'relative',
                left: '0px'
            }
        });
        content.add({
            id: 'activity-progress-text-container',
            xtype: 'box',
            autoEl: 'table',
            style: {
                position: 'relative',
                left: '0px'
            }
        });
        var backgroundEl, indicatorEl, textEl;
        var resize = function () {
            /* Resize window */
            Game.activity_cmp.setSize(viewport.getWidth() - fieldsX, heightY);
            Game.activity_cmp.setPosition(Math.floor(fieldsX / 2), Math.floor((viewport.getHeight() - heightY) / 2));
            Ext.getCmp('activity-progress-container').doLayout();
            /* Get internal area dimensions */
            var activity_width = content.getWidth();
            var activity_height = content.getHeight();
            Game.activity_width = activity_width;
            /* Find elements */
            if (!backgroundEl) {
                backgroundEl = document.getElementById('activity-progress-background');
                indicatorEl = document.getElementById('activity-progress-indicator');
                textEl = document.getElementById('activity-progress-text-container');
            }
            /* Resize elements */
            backgroundEl.style.width = activity_width + 'px';
            backgroundEl.style.height = activity_height + 'px';
            indicatorEl.style.height = activity_height + 'px';
            indicatorEl.style.top = (-activity_height) + 'px';
            textEl.style.width = activity_width + 'px';
            textEl.style.height = activity_height + 'px';
            textEl.style.top = (-activity_height * 2) + 'px';
        };
        Game.activity_cmp.show();
        resize();
        viewport.on('resize', resize);
    } else {
        Game.activity_cmp.show();
    }
    Ext.getCmp('activity-progress-text-container').update('<tr><td id="activity-progress-text">' + text + '</td></tr>');
    Game.activity_progress(ratio);
};

Game.activity_progress = function (ratio) {
    var width = Math.round(Game.activity_width * ratio);
    if (width != Game.activity_last_width) {
        document.getElementById('activity-progress-indicator').style.width = width + 'px';
        Game.activity_last_width = width;
    }
};

Game.activity_hide = function () {
    Game.activity_cmp.hide();
};

wait(['timesync'], function () {
    loaded('game-interface');
});
