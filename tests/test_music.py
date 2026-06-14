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
    # 章节分区主题（每 2 章换一首，共 5 个）
    assert music.track_for('IDLE', 0) == 'map_hope'
    assert music.track_for('IDLE', 2) == 'map_valor'
    assert music.track_for('IDLE', 4) == 'map_tense'
    assert music.track_for('IDLE', 6) == 'map_storm'
    assert music.track_for('IDLE', 8) == 'map_dark'
    assert music.track_for('IDLE', 9) == 'map_dark'
    # 敌方回合：按分区的压迫变体
    assert music.track_for('IDLE', 0, enemy_phase=True) == 'enemy_light'
    assert music.track_for('IDLE', 5, enemy_phase=True) == 'enemy_mid'
    assert music.track_for('IDLE', 9, enemy_phase=True) == 'enemy_dark'
    # 试炼之塔：攻防同曲，且盖过分区主题
    assert music.track_for('IDLE', 0, tower=True) == 'tower'
    assert music.track_for('ENEMY_TURN', 0, enemy_phase=True, tower=True) == 'tower'
    assert music.track_for('TOWER_META', tower=True) == 'title'   # 大厅仍用标题曲


def test_graceful_without_audio():
    # 未 init 时 director.update 不应抛异常
    music.director.update('title')
    music.set_enabled(False)
    music.set_enabled(True)
