var Characters = {
    params: {},
    names: {}
};

Characters.set_params = function (id, params) {
    this.params[id] = params;
    this.names[params.name] = id;
};

Character.params = function (id) {
    return this.params[id];
};

Character.params_by_name = function (name) {
    var id = this.names[name];
    if (!id)
        return undefined;
    return this.params[id];
};

loaded('characters');
