import config


def test_defaults_when_missing(tmp_path):
    cfg = config.load(path=tmp_path / 'nope.json')
    assert cfg == config.DEFAULTS
    assert cfg is not config.DEFAULTS        # 返回副本


def test_set_persists_and_reloads(tmp_path):
    p = tmp_path / 'config.json'
    config.load(path=p)
    config.set('music_vol', 3, path=p)
    config.set('text_speed', 'fast', path=p)
    again = config.load(path=p)
    assert again['music_vol'] == 3
    assert again['text_speed'] == 'fast'


def test_coerce_clamps_and_rejects(tmp_path):
    p = tmp_path / 'config.json'
    config.load(path=p)
    assert config.set('sfx_vol', 99, path=p) == 10        # 上限
    assert config.set('sfx_vol', -5, path=p) == 0         # 下限
    assert config.set('text_speed', 'turbo', path=p) == 'normal'  # 非法回退默认


def test_corrupt_file_falls_back(tmp_path):
    p = tmp_path / 'config.json'
    p.write_text('{bad json', encoding='utf-8')
    cfg = config.load(path=p)
    assert cfg == config.DEFAULTS


def test_cycle(tmp_path):
    p = tmp_path / 'config.json'
    config.load(path=p)
    config.set('music_vol', 5, path=p)
    assert config.cycle('music_vol', 1) == 6
    assert config.cycle('music_vol', -1) == 5
    config.set('confirm_end', True, path=p)
    assert config.cycle('confirm_end', 1) is False
    config.set('text_speed', 'normal', path=p)
    assert config.cycle('text_speed', 1) == 'fast'
    assert config.cycle('text_speed', 1) == 'slow'   # 循环


def test_derived(tmp_path):
    p = tmp_path / 'config.json'
    config.load(path=p)
    config.set('music_vol', 7, path=p)
    config.set('sfx_vol', 0, path=p)
    config.set('text_speed', 'fast', path=p)
    assert abs(config.music_frac() - 0.7) < 1e-6
    assert config.sfx_frac() == 0.0
    assert config.text_cps() == 60
