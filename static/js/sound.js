var soundManagerLoaded;

var Sound = {
    queue: [],
    lastid: 0
};

Sound.initialized = function () {
    if (Sound.loaded) {
        return;
    }
    Sound.loaded = true;
    Stream.stream_handler('sound', Sound);
    loaded('sound');
}

wait(['realplexor-stream', 'soundmanager2'], function () {
    soundManager.setup({
        url: '/st-mg/sound-swf',
        flashVersion: 9,
        ontimeout: Sound.initialized,
        onready: Sound.initialized
    });
});

Sound.play = function (pkt) {
    var sound = soundManager.getSoundById(pkt.id);
    var playSound = function () {
        pkt.sound = sound;
        if (pkt.mode === 'stop') {
            for (var i = 0; i < Sound.queue.length; i++) {
                var snd = Sound.queue[i];
                if (snd.playing) {
                    snd.sound.stop();
                }
            }
            Sound.queue = [];
            Sound.enqueue(pkt);
            Sound.startPlay(pkt);
        } else if (pkt.mode === 'wait') {
            Sound.enqueue(pkt);
            Sound.checkQueue();
        } else {
            Sound.enqueue(pkt);
            Sound.startPlay(pkt);
        }
    };
    if (sound) {
        playSound();
    } else {
        sound = soundManager.createSound({
            id: pkt.id,
            url: pkt.url,
            autoLoad: true,
            autoPlay: false,
            onload: playSound
        });
    }
};

Sound.enqueue = function (snd) {
    snd.id = ++Sound.lastid;
    Sound.queue.push(snd);
};

Sound.startPlay = function (snd) {
    snd.playing = true;
    snd.sound.play({
        volume: (snd.volume === undefined) ? 50 : snd.volume,
        onfinish: function () {
            for (var i = 0; i < Sound.queue.length; i++) {
                if (Sound.queue[i].id === snd.id) {
                    Sound.queue.splice(i, 1);
                    break;
                }
            }
            Sound.checkQueue();
        }
    });
};

Sound.checkQueue = function () {
    var firstWaiting;
    for (var i = 0; i < Sound.queue.length; i++) {
        var snd = Sound.queue[i];
        if (snd.playing) {
            return;
        }
        if (!snd.playing && snd.mode === 'wait' && !firstWaiting) {
            firstWaiting = snd;
        }
    }
    if (firstWaiting) {
        Sound.startPlay(firstWaiting);
    }
};
