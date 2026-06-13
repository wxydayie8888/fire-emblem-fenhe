import music


def test_midi_parsing():
    assert music._midi('C4') == 60
    assert music._midi('A4') == 69
    assert music._midi('C0') == 12
    assert music._midi('F#3') == 54
    assert music._midi('Bb4') == 70
    assert music._midi('G2') == 43


def test_freq_reference():
    assert abs(music._mtof(69) - 440.0) < 0.01      # A4 = 440Hz
    assert abs(music._mtof(60) - 261.63) < 0.1       # C4


def test_song_library_well_formed():
    songs = music._songs()
    assert len(songs) >= 8
    for name, s in songs.items():
        assert s['tempo'] > 0 and s['beats'] > 0
        for instr, vol, pattern in s['tracks']:
            assert instr in music.TIMBRES, (name, instr)
            assert 0 < vol <= 1
            total = sum(beats for _, beats in pattern)
            assert total == s['beats'], (name, instr, total, s['beats'])
            for token, beats in pattern:
                if token != 'R':
                    for note in token.split('+'):
                        music._midi(note)             # 不抛异常即合法


def test_track_for_mapping():
    assert music.track_for('TITLE') == 'title'
    assert music.track_for('CODEX') == 'title'
    assert music.track_for('CINEMA') is None          # AI 交响乐单独处理
    assert music.track_for('INTRO') == 'story'
    assert music.track_for('DIALOGUE') == 'story'
    assert music.track_for('END') == 'defeat'
    assert music.track_for('CLEAR') == 'victory'
    # 章节情绪分幕
    assert music.track_for('IDLE', 0) == 'map_hope'    # 第1幕
    assert music.track_for('IDLE', 2) == 'map_hope'
    assert music.track_for('IDLE', 4) == 'map_tense'   # 第2幕
    assert music.track_for('IDLE', 6) == 'map_tense'
    assert music.track_for('IDLE', 8) == 'map_dark'    # 第3幕
    assert music.track_for('IDLE', 9) == 'map_dark'
    # 敌方回合
    assert music.track_for('IDLE', 0, enemy_phase=True) == 'enemy'


def test_graceful_without_audio():
    # 未 init 时 director.update 不应抛异常
    music.director.update('title')
    music.set_enabled(False)
    music.set_enabled(True)
