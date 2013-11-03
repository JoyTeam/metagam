import mg

class TimeSync(mg.Module):
    def register(self):
        self.rhook("gameinterface.render", self.gameinterface_render)

    def gameinterface_render(self, character, vars, design):
        req = self.req()
        vars["js_modules"].add("timesync")
