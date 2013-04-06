var soundManagerLoaded;

var Sound = {
    soundQueue: [],
    musicQueue: [],
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
            for (var i = 0; i < Sound.soundQueue.length; i++) {
                var snd = Sound.soundQueue[i];
                if (snd.playing) {
                    snd.sound.stop();
                }
            }
            Sound.soundQueue = [];
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
    Sound.soundQueue.push(snd);
};

Sound.startPlay = function (snd) {
    snd.playing = true;
    snd.sound.play({
        volume: snd.volume,
        onfinish: function () {
            for (var i = 0; i < Sound.soundQueue.length; i++) {
                if (Sound.soundQueue[i].id === snd.id) {
                    Sound.soundQueue.splice(i, 1);
                    break;
                }
            }
            Sound.checkQueue();
        }
    });
};

Sound.checkQueue = function () {
    var firstWaiting;
    for (var i = 0; i < Sound.soundQueue.length; i++) {
        var snd = Sound.soundQueue[i];
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

Sound.music = function (pkt) {
    var sound = soundManager.getSoundById(pkt.id);
    var playSound = function () {
        pkt.sound = sound;
        for (var i = 0; i < Sound.musicQueue.length; i++) {
            var m = Sound.musicQueue[i];
            if (m.sound === pkt.sound) {
                /* The same music is already being played */
                if (m.stopping) {
                    m.sound.stop();
                    Sound.musicQueue.splice(i, 1);
                    break;
                } else {
                    return;
                }
            }
        }
        if (pkt.fade < 10) {
            pkt.volumeMult = 1.0;
            Sound.stopMusic();
            Sound.enqueueMusic(pkt);
            Sound.startMusic(pkt);
        } else {
            for (var i = 0; i < Sound.musicQueue.length; i++) {
                Sound.musicQueue[i].stopping = true;
            }
            pkt.volumeMult = 0.0;
            Sound.enqueueMusic(pkt);
            Sound.startMusic(pkt);
            Sound.startCrossfader(pkt.fade);
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

Sound.stopMusic = function () {
    for (var i = 0; i < Sound.musicQueue.length; i++) {
        Sound.musicQueue[i].sound.stop();
    }
    Sound.musicQueue = [];
};

Sound.enqueueMusic = function (music) {
    music.id = ++Sound.lastid;
    Sound.musicQueue.push(music);
};

Sound.startMusic = function (music) {
    music.sound.play({
        volume: Math.floor(music.volume * music.volumeMult),
        onfinish: function () {
            if (music.stopping) {
                for (var i = 0; i < Sound.musicQueue.length; i++) {
                    if (Sound.musicQueue[i].id === music.id) {
                        Sound.musicQueue.splice(i, 1);
                        break;
                    }
                }
            } else {
                Sound.startMusic(music);
            }
        }
    });
};

Sound.startCrossfader = function (interval) {
    if (Sound.crossfader) {
        return;
    }
    Sound.crossfader = setInterval(function () {
        var cont = false;
        for (var i = 0; i < Sound.musicQueue.length; i++) {
            var music = Sound.musicQueue[i];
            if (music.stopping) {
                music.volumeMult -= 0.1;
                if (music.volumeMult > 0) {
                    music.sound.setVolume(Math.floor(music.volume * music.volumeMult));
                    cont = true;
                } else {
                    music.sound.stop();
                    Sound.musicQueue.splice(i, 1);
                    i--;
                }
            } else {
                if (music.volumeMult < 1) {
                    music.volumeMult += 0.1;
                    if (music.volumeMult > 1) {
                        music.volumeMult = 1;
                    } else {
                        cont = true;
                    }
                    music.sound.setVolume(Math.floor(music.volume * music.volumeMult));
                }
            }
        }
        if (!cont) {
            Sound.stopCrossfader();
        }
    }, Math.floor(interval / 10) || 1);
};

Sound.stopCrossfader = function () {
    if (Sound.crossfader) {
        clearInterval(Sound.crossfader);
        delete Sound.crossfader;
    }
};
