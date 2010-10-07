from mg import *
import re
import sys

class WizardConfig(CassandraObject):
    _indexes = {
        "all": [["all"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "WizardConfig-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return WizardConfig._indexes

class WizardConfigList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "WizardConfig-"
        kwargs["cls"] = WizardConfig
        CassandraObjectList.__init__(self, *args, **kwargs)

class Wizard(Module):
    "Wizard is a temporary object keeping state of interactive wizard. It can be updated step by step by a user, committed or aborted"
    def __init__(self, app, fqn, uuid=None, config=None, **kwargs):
        Module.__init__(self, app, fqn)
        if uuid is None:
            self.config = self.obj(WizardConfig)
            self.uuid = self.config.uuid
            self.new(**kwargs)
            self.config.store()
        else:
            self.uuid = uuid
            self.config = config if config else self.obj(WizardConfig, uuid)
            self.load()

    def new(self, **kwargs):
        "Configure newly created wizard. Override to set your logic"
        self.config.set("all", 1)
        self.config.set("mod", self.fqn)

    def load(self):
        "Configure wizard just loaded. Override to set your logic"
        pass

    def request(self, cmd):
        "Handle HTTP request. Override to set your logic"
        self.call("web.not_implemented")

    def finish(self):
        "Commit wizard changes. Override to set your logic"
        self.destroy()

    def abort(self):
        "Rollback wizard changes. Override to set your logic"
        self.destroy()

    def destroy(self):
        "Destroy wizard on destroy. Override to set your logic"
        self.config.remove()

re_module_path = re.compile(r'^(.+)\.(.+)$')
re_wizard_args_0 = re.compile(r'^([0-9a-f]+)$')
re_wizard_args_1 = re.compile(r'^([0-9a-f]+)/(.+)$')

class Wizards(Module):
    def register(self):
        Module.register(self)
        self.rhook("wizards.new", self.wizards_new)
        self.rhook("wizards.list", self.wizards_list)
        self.rhook("wizards.call", self.wizards_call)
        self.rhook("ext-admin-wizard.call", self.wizard_call)
        self.rhook("objclasses.list", self.objclasses_list)

    def objclasses_list(self, objclasses):
        objclasses["WizardConfig"] = (WizardConfig, WizardConfigList)

    def wizard_class(self, mod):
        app = self.app()
        m = re_module_path.match(mod)
        if not m:
            raise ModuleException("Invalid wizard name: %s" % mod)
        (module_name, class_name) = m.group(1, 2)
        module = sys.modules.get(module_name)
        app.inst.modules.add(module_name)
        if not module:
            try:
                __import__(module_name, globals(), locals(), [], -1)
                module = sys.modules.get(module_name)
            except (KeyboardInterrupt, SystemExit, TaskletExit):
                raise
            except BaseException as e:
                module = sys.modules.get(module_name)
                if module:
                    self.exception(e)
                else:
                    raise
        try:
            return module.__dict__[class_name]
        except KeyError:
            return None

    def wizards_new(self, mod, **kwargs):
        cls = self.wizard_class(mod)
        obj = cls(self.app(), mod, **kwargs)
        return obj

    def wizards_list(self):
        app = self.app()
        list = self.objlist(WizardConfigList, query_index="all", query_equal="1")
        list.load()
        wizs = []
        for config in list:
            mod = config.get("mod")
            if mod:
                cls = self.wizard_class(mod)
                if cls is not None:
                    wizs.append(cls(app, mod, config.uuid, config))
        return wizs

    def wizards_call(self, method, *args, **kwargs):
        for wiz in self.wizards_list():
            f = getattr(wiz, method, None)
            if callable(f):
                f(*args, **kwargs)

    def wizard_call(self):
        req = self.req()
        if re_wizard_args_0.match(req.args):
            uuid = req.args
            cmd = ""
        else:
            m = re_wizard_args_1.match(req.args)
            if m:
                uuid, cmd = m.groups(1, 2)
            else:
                self.call("web.not_found")
        try:
            config = self.obj(WizardConfig, uuid)
        except ObjectNotFoundException:
            self.call("web.not_found")
        mod = config.get("mod")
        if mod is None:
            self.call("web.internal_server_error")
        cls = self.wizard_class(mod)
        if cls is None:
            self.call("web.internal_server_error")
        wiz = cls(self.app(), mod, config.uuid, config)
        return wiz.request(cmd)
