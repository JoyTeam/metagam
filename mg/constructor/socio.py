from mg.constructor import *
import cStringIO
import re

re_del = re.compile('^del\/(\S+)$')

class Socio(ConstructorModule):
    def register(self):
        self.rhook("headmenu-admin-sociointerface.buttons", self.headmenu_buttons)
        self.rhook("ext-admin-sociointerface.buttons", self.admin_sociointerface_buttons, priv="design")
        self.rhook("menu-admin-socio.index", self.menu_socio_index)
        self.rhook("web.setup_design", self.web_setup_design)
        self.rhook("socio.render-form", self.render_form)

    def render_form(self, vars):
        design = self.design("sociointerface")
        return self.call("design.parse", design, "form.html", None, vars)

    def blocks(self):
        blocks = []
        self.call("socio.button-blocks", blocks)
        return blocks

    def generated_buttons(self):
        buttons = []
        self.call("sociointerface.buttons", buttons)
        buttons.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
        return buttons

    def buttons_layout(self):
        layout = self.conf("sociointerface.buttons-layout")
        if layout is not None:
            return layout
        # Loading available blocks
        blocks = {}
        for blk in self.blocks():
            blocks[blk["id"]] = blk
        # Default button layout
        layout = {}
        for btn in self.generated_buttons():
            block_id = btn["block"]
            blk = blocks.get(block_id)
            if blk:
                btn_list = layout.get(block_id)
                if btn_list is None:
                    btn_list = []
                    layout[block_id] = btn_list
                lbtn = btn.copy()
                btn_list.append(lbtn)
        for block_id, btn_list in layout.iteritems():
            btn_list.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
        return layout

    def headmenu_buttons(self, args):
        if args:
            layout = self.buttons_layout()
            for block_id, btn_list in layout.iteritems():
                for btn in btn_list:
                    if btn["id"] == args:
                        return [htmlescape(self.call("script.unparse-text", btn["title"])), "sociointerface/buttons"]
            return [self._("Button editor"), "sociointerface/buttons"]
        return self._("Socio interface buttons")

    def admin_sociointerface_buttons(self):
        req = self.req()
        if req.args == "new":
            return self.button_editor(None)
        m = re_del.match(req.args)
        if m:
            button_id = m.group(1)
            # Removing button from the layout
            layout = self.buttons_layout()
            for block_id, btn_list in layout.items():
                for btn in btn_list:
                    if btn["id"] == button_id:
                        btn_list = [ent for ent in btn_list if ent["id"] != button_id]
                        if btn_list:
                            layout[block_id] = btn_list
                        else:
                            del layout[block_id]
            config = self.app().config_updater()
            config.set("sociointerface.buttons-layout", layout)
            config.store()
            self.call("admin.redirect", "sociointerface/buttons")
        if req.args:
            # Buttons in the layout
            for block_id, btn_list in self.buttons_layout().iteritems():
                for btn in btn_list:
                    if btn["id"] == req.args:
                        return self.button_editor(btn)
            # Unused buttons
            for btn in self.generated_buttons():
                if btn["id"] == req.args:
                    return self.button_editor(btn)
            self.call("admin.redirect", "sociointerface/buttons")
        vars = {
            "NewButton": self._("New button"),
            "Button": self._("Button"),
            "Action": self._("Action"),
            "Order": self._("Order"),
            "Editing": self._("Editing"),
            "Deletion": self._("Deletion"),
            "delete": self._("delete"),
            "ConfirmDelete": self._("Are you sure want to delete this button?"),
            "NA": self._("n/a"),
        }
        # Loading list of socio interfaces
        # Every such block is marked as 'valid'
        valid_blocks = {}
        vars["blocks"] = []
        for block in self.blocks():
            show_block = {
                "title": self._("Button block: %s") % htmlescape(block.get("title")),
                "buttons": []
            }
            vars["blocks"].append(show_block)
            valid_blocks[block["id"]] = show_block
        # Looking at the buttons layout and assigning buttons to the interfaces
        # Remebering assigned buttons
        assigned_buttons = {}
        generated = set([btn["id"] for btn in self.generated_buttons()])
        for block_id, btn_list in self.buttons_layout().iteritems():
            show_block = valid_blocks.get(block_id)
            if show_block:
                for btn in btn_list:
                    if btn["id"] in generated or btn.get("manual"):
                        show_btn = btn.copy()
                        assigned_buttons[btn["id"]] = show_btn
                        show_block["buttons"].append(show_btn)
                        show_btn["edit"] = self._("edit")
        # Loading full list of generated buttons and showing missing buttons
        # as unused
        unused_buttons = []
        for btn in self.generated_buttons():
            if not btn["id"] in assigned_buttons:
                show_btn = btn.copy()
                assigned_buttons[btn["id"]] = show_btn
                unused_buttons.append(show_btn)
                show_btn["edit"] = self._("show")
        # Preparing buttons to rendering
        for btn in assigned_buttons.values():
            btn["title"] = htmlescape(self.call("script.unparse-text", btn.get("title")))
            if btn.get("href"):
                btn["action"] = self._("href///<strong>{0}</strong>").format(btn["href"])
            elif btn.get("onclick"):
                btn["action"] = btn["onclick"]
            btn["may_delete"] = True
        # Rendering unused buttons
        if unused_buttons:
            unused_buttons.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            vars["blocks"].append({
                "title": self._("Unused buttons"),
                "buttons": unused_buttons,
                "hide_order": True,
                "hide_deletion": True,
            })
        self.call("admin.response_template", "admin/sociointerface/buttons.html", vars)

    def button_editor(self, button):
        req = self.req()
        layout = self.buttons_layout()
        if req.ok():
            errors = {}
            if button:
                button_id = button["id"]
                # Removing button from the layout
                for block_id, btn_list in layout.items():
                    for btn in btn_list:
                        if btn["id"] == button["id"]:
                            btn_list = [ent for ent in btn_list if ent["id"] != button["id"]]
                            if btn_list:
                                layout[block_id] = btn_list
                            else:
                                del layout[block_id]
                manual = button.get("manual")
            else:
                button_id = uuid4().hex
                manual = True
            # Trying to find button prototype in generated buttons
            user = True
            if button:
                for btn in self.generated_buttons():
                    if btn["id"] == button["id"]:
                        prototype = btn
                        user = False
                        break
            # Input parameters
            block = req.param("v_block")
            order = intz(req.param("order"))
            action = req.param("v_action")
            href = req.param("href")
            target = req.param("v_target")
            onclick = req.param("onclick")
            # Creating new button
            char = self.character(req.user())
            btn = {
                "id": button_id,
                "order": order,
                "title": self.call("script.admin-text", "title", errors, globs={"char": char}),
                "condition": self.call("script.admin-expression", "condition", errors, globs={"char": char}) if req.param("condition").strip() else None,
                "left": True if req.param("left") else False,
            }
            if manual:
                btn["manual"] = True
            # Button action
            if action == "javascript":
                if not onclick:
                    errors["onclick"] = self._("Specify JavaScript action")
                else:
                    btn["onclick"] = onclick
            elif action == "href":
                if not href:
                    errors["href"] = self._("Specify URL")
                elif target != "_blank" and not href.startswith("/"):
                    errors["href"] = self._("Ingame URL must be relative (start with '/' symbol)")
                else:
                    btn["href"] = href
                    btn["target"] = target
            elif action == "search":
                btn["search"] = True
            else:
                errors["v_action"] = self._("Select an action")
            # Button block
            if not block:
                errors["v_block"] = self._("Select interface where to place the button")
            else:
                btn_list = layout.get(block)
                if not btn_list:
                    btn_list = []
                    layout[block] = btn_list
                btn_list.append(btn)
                btn_list.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
            # Storing button
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config = self.app().config_updater()
            config.set("sociointerface.buttons-layout", layout)
            config.store()
            self.call("web.response_json", {"success": True, "redirect": "sociointerface/buttons"})
        else:
            if button:
                block = button.get("block")
                order = button["order"]
                title = button.get("title")
                condition = button.get("condition")
                user = False
                for block_id, btn_list in layout.iteritems():
                    for btn in btn_list:
                        if btn["id"] == button["id"]:
                            block = block_id
                            break
                href = button.get("href")
                onclick = button.get("onclick")
                left = button.get("left")
                if onclick:
                    action = "javascript"
                    target = "_self"
                elif button.get("search"):
                    action = "search"
                    target = "_self"
                else:
                    action = "href"
                    target = button.get("target")
                # Valid blocks
                if block:
                    valid_block = False
                    for blk in self.blocks():
                        if blk["id"] == block:
                            valid_block = True
                            break
                    if not valid_block:
                        block = ""
            else:
                block = ""
                order = 50
                title = []
                user = True
                href = ""
                onclick = ""
                target = "_self"
                action = "href"
                left = False
                condition = None
        blocks = []
        for blk in self.blocks():
            blocks.append((blk["id"], blk.get("title") or blk["id"]))
        fields = [
            {"name": "block", "type": "combo", "label": self._("Socio interface"), "values": blocks, "value": block},
            {"name": "order", "label": self._("Sort order"), "value": order, "inline": True},
            {"name": "left", "label": self._("Show on the left side"), "checked": left, "type": "checkbox"},
            {"name": "condition", "label": self._("Condition (when to show the link)") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", condition) if condition else None},
            {"name": "title", "label": self._("Link text") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-text", title)},
            {"type": "combo", "name": "action", "label": self._("Button action"), "value": action, "values": [("href", self._("Open hyperlink")), ("javascript", self._("Execute JavaScript")), ("search", self._("Search box"))]},
            {"name": "href", "label": self._("Link href"), "value": href, "condition": "[[action]]=='href'"},
            {"type": "combo", "name": "target", "label": self._("Target frame"), "value": target, "values": [("_self", self._("Current window")), ("_blank", self._("New window"))], "condition": "[[action]]=='href'", "inline": True},
            {"name": "onclick", "label": self._("Javascript onclick"), "value": onclick, "condition": "[[action]]=='javascript'"},
        ]
        self.call("admin.form", fields=fields)

    def menu_socio_index(self, menu):
        req = self.req()
        if req.has_access("design"):
            menu.append({"id": "sociointerface/buttons", "text": self._("Buttons editor"), "leaf": True, "order": 4})

    def web_setup_design(self, vars):
        req = self.req()
        block = None
        if req.group == "socio" and req.hook == "image":
            pass
        elif req.group == "forum" or req.group == "socio" or req.group == "news":
            vars["title_suffix"] = " - %s" % self.app().project.get("title_short")
            block = "forum"
        elif req.group == "library":
            block = "library"
        topmenu = []
        uri = req.uri()
        if block:
            user = req.user()
            char = self.character(user) if user else None
            generated = set([btn["id"] for btn in self.generated_buttons()])
            layout = self.buttons_layout().get(block)
            if layout:
                for btn in layout:
                    if btn.get("manual") or btn["id"] in generated:
                        try:
                            if not btn.get("condition") or self.call("script.evaluate-expression", btn["condition"], {"char": char}, description=self._("Socio top menu")):
                                ent = {
                                    "html": self.call("script.evaluate-text", btn["title"], {"char": char}, description=self._("Socio top menu"))
                                }
                                if btn.get("search"):
                                    ent["search"] = True
                                elif btn.get("href"):
                                    if btn["href"] != uri:
                                        ent["href"] = btn["href"]
                                        ent["target"] = btn["target"]
                                elif btn.get("onclick"):
                                    ent["onclick"] = btn["onclick"]
                                if btn.get("left"):
                                    ent["left"] = True
                                topmenu.append(ent)
                        except ScriptError as e:
                            self.call("exception.report", e)
        if len(topmenu):
            topmenu_left = []
            topmenu_right = []
            for ent in topmenu:
                if ent.get("left"):
                    topmenu_left.append(ent)
                else:
                    topmenu_right.append(ent)
            vars["topmenu"] = []
            if len(topmenu_left):
                vars["topmenu"].append({
                    "id": "left",
                    "items": topmenu_left
                })
                topmenu_left[-1]["lst"] = True
            if len(topmenu_right):
                vars["topmenu"].append({
                    "id": "right",
                    "items": topmenu_right
                })
                topmenu_right[-1]["lst"] = True
