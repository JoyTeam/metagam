var TimeSync = {
    offset: undefined,
    filterSamples: 10,
    offsetSamples: []
};

function onServerTime(t)
{
    TimeSync.onServerTime(t);
}

TimeSync.onServerTime = function (t) {
    var self = this;
    var offset = t - (new Date()).getTime() / 1000.0;
    self.offsetSamples.push(offset);
    if (self.offsetSamples.length > self.filterSamples) {
        self.offsetSamples.splice(0, self.offsetSamples.length - self.filterSamples);
    }
    self.offset = undefined;
};

TimeSync.getTime = function () {
    var self = this;
    if (self.offset === undefined) {
        var samples = self.offsetSamples.sort();
        if (!samples.length) {
            return undefined;
        }
        self.offset = samples[Math.floor(samples.length / 2)];
    }
    var res = (new Date()).getTime() / 1000.0 + self.offset;
    // Do not allow for the time to decrease. It must be monotonic
    if (self.lastGetTime && res < self.lastGetTime) {
        return self.lastGetTime;
    }
    self.lastGetTime = res;
    return res;
};

loaded('timesync');
