class ParametrizedObject(object):
    def __init__(self, cls):
        self._param_cls = cls

    def _invalidate(self):
        try:
            delattr(self, "_param_cache")
        except AttributeError:
            pass

    def _param(self, key, handle_exceptions=True):
        param = self.call("%s.param" % self._param_cls, key)
        if not param:
            return None, None
        try:
            cache = self._param_cache
        except AttributeError:
            cache = {}
            self._param_cache = cache
        try:
            return param, cache[key]
        except KeyError:
            # 'param-value' handles cache storing automatically
            return param, self.call("%s.param-value" % self._param_cls, self, key, handle_exceptions)

    def _param_eval(self, key, handle_exceptions=True):
        param, value = self._param(key, handle_exceptions)
        value = self.call("script.evaluate-dynamic", value)
        return param, value

    def param(self, key, handle_exceptions=True):
        param, value = self._param_eval(key, handle_exceptions)
        return value

    def param_dyn(self, key, handle_exceptions=True):
        param, value = self._param(key, handle_exceptions)
        return type(value) is list

    def param_html(self, key, handle_exceptions=True):
        param, value = self._param_eval(key, handle_exceptions)
        if param is None:
            return None
        return self.call("%s.param-html" % self._param_cls, param, value)

    def set_param(self, key, val):
        return self.call("%s.set-param" % self._param_cls, self, key, val)
