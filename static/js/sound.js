var soundManagerLoaded;

var Sound = {
    soundQueue: [],
    musicQueue: [],
    lastid: 0,
    initFailed: 0
};

Sound.initialize = function () {
    soundManager.setup({
        url: '/st/sound-swf/',
        onready: function () {
            try { debug_log('Sound initialization completed'); } catch (e) {}
            Sound.initialized();
        }
    });
    Stream.stream_handler('sound', Sound);
    setTimeout(function () {
        if (!Sound.loaded) {
            try { debug_log('Sound initialization not finished yet. Starting game interface'); } catch (e) {}
            Sound.initialized();
        }
    }, 3000);
};

Sound.initialized = function () {
    if (Sound.loaded) {
        return;
    }
    Sound.loaded = true;
    loaded('sound');
};

wait(['realplexor-stream'], function () {
    Sound.initialize();
});

Sound.play = function (pkt) {
    if (!Sound.sound_volume) {
        return;
    }
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
        volume: Math.floor(snd.volume * Sound.sound_volume / 100),
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
    if (!Sound.music_volume) {
        return;
    }
    var toLoad = 0;
    var playSound = function () {
        /* If one of tracks is currently being played, don't do anything */
        var newIds = [];
        var isPlaying = false;
        for (var id in pkt.playlist) {
            if (pkt.playlist.hasOwnProperty(id)) {
                newIds.push(id)
                for (var j = 0; j < Sound.musicQueue.length; j++) {
                    var m = Sound.musicQueue[j];
                    if (!m.stopping && m.code === id) {
                        isPlaying = true;
                    }
                }
            }
        }
        Sound.playlist = newIds;
        if (!isPlaying) {
            Sound.nextTrack(newIds, pkt.volume, pkt.fade);
        }
    };
    var waiting = false;
    for (var id in pkt.playlist) {
        if (pkt.playlist.hasOwnProperty(id)) {
            var sound = soundManager.getSoundById(id);
            if (!sound || !sound.loadHandled) {
                (function (id, sound) {
                    toLoad++;
                    soundManager.destroySound(id);
                    sound = soundManager.createSound({
                        id: id,
                        url: pkt.playlist[id],
                        autoLoad: true,
                        autoPlay: false,
                        onload: function () {
                            sound.loadHandled = true;
                            toLoad--;
                            if (toLoad == 0 && waiting) {
                                playSound();
                            }
                        }
                    });
                })(id, sound);
            }
        }
    }
    if (!toLoad) {
        playSound();
    } else {
        waiting = true;
    }
};

Sound.nextTrack = function (ids, volume, fade) {
    /* Select a track */
    var id;
    if (ids.length) {
        id = ids[Math.floor(Math.random() * ids.length)];
    }
    /* Mark all tracks stopping */
    var crossfader = false;
    if (fade >= 10) {
        for (var i = 0; i < Sound.musicQueue.length; i++) {
            var m = Sound.musicQueue[i];
            m.stopping = true;
            if (m.code === id && m.stopping) {
                /* The same music is already being played but stopping now */
                m.sound.stop();
                Sound.musicQueue.splice(i, 1);
                i--;
            } else {
                crossfader = true;
            }
        }
    } else {
        Sound.stopMusic();
    }
    /* Start new track */
    if (id) {
        var sound = soundManager.getSoundById(id);
        var m = {
            code: id,
            sound: sound,
            fade: fade,
            volume: volume
        };
        if (fade < 10) {
            m.volumeMult = 1.0;
            Sound.enqueueMusic(m);
            Sound.startMusic(m);
        } else {
            m.volumeMult = 0.0;
            Sound.enqueueMusic(m);
            Sound.startMusic(m);
            crossfader = true;
        }
    }
    /* Start crossfader */
    if (crossfader) {
        Sound.startCrossfader(fade);
    } else {
        Sound.stopCrossfader();
    }
};

Sound.updateMusic = function () {
    for (var i = 0; i < Sound.musicQueue.length; i++) {
        var music = Sound.musicQueue[i];
        music.sound.setVolume(Math.floor(music.volume * music.volumeMult * Sound.music_volume / 100));
    }
};

Sound.stopMusic = function () {
    for (var i = 0; i < Sound.musicQueue.length; i++) {
        var music = Sound.musicQueue[i];
        music.stopping = true;
        Sound.musicQueue[i].sound.stop();
    }
    Sound.musicQueue = [];
};

Sound.enqueueMusic = function (music) {
    music.id = ++Sound.lastid;
    Sound.musicQueue.push(music);
};

Sound.startMusic = function (music) {
    var cmd = {
        volume: Math.floor(music.volume * music.volumeMult * Sound.music_volume / 100)
    };
    var canRepeatTheSame = false;
    var nextTrackSelected;
    var nextTrack = function () {
        /* Avoid double triggering on onPosition and onFinish */
        if (nextTrackSelected) {
            return;
        }
        if (music.stopping) {
            return;
        }
        nextTrackSelected = true;
        if (music.stopping || canRepeatTheSame) {
            for (var i = 0; i < Sound.musicQueue.length; i++) {
                if (Sound.musicQueue[i].id === music.id) {
                    var m = Sound.musicQueue[i];
                    m.stopping = true;
                    m.sound.stop();
                    Sound.musicQueue.splice(i, 1);
                    break;
                }
            }
        }
        /* Select next track */
        var ids = [];
        for (var i = 0; i < Sound.playlist.length; i++) {
            if (Sound.playlist[i] != music.code || canRepeatTheSame) {
                ids.push(Sound.playlist[i]);
            }
        }
        Sound.nextTrack(ids, music.volume, music.fade);
    };
    if (Sound.playlist && (Sound.playlist.length > 1) && music.sound.duration > music.fade) {
        soundManager.onPosition(music.code, music.sound.duration - music.fade, nextTrack);
    } else {
        canRepeatTheSame = true;
    }
    cmd.onfinish = nextTrack;
    music.sound.play(cmd);
};

Sound.startCrossfader = function (interval) {
    if (Sound.crossfader) {
        Sound.stopCrossfader();
    }
    Sound.crossfader = setInterval(function () {
        var cont = false;
        for (var i = 0; i < Sound.musicQueue.length; i++) {
            var music = Sound.musicQueue[i];
            if (music.stopping) {
                music.volumeMult -= 0.1;
                if (music.volumeMult > 0) {
                    music.sound.setVolume(Math.floor(music.volume * music.volumeMult * Sound.music_volume / 100));
                    cont = true;
                } else {
                    music.stopping = true;
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
                    music.sound.setVolume(Math.floor(music.volume * music.volumeMult * Sound.music_volume / 100));
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

Sound.settings = function (pkt) {
    Sound.music_volume = pkt.music;
    Sound.sound_volume = pkt.sound;
    if (pkt.music) {
        Sound.updateMusic();
    } else {
        Sound.stopMusic();
    }
};
