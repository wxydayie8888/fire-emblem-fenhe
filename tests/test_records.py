import records


def test_default_on_missing(tmp_path):
    assert records.load(tmp_path / 'nope.json') == records.DEFAULT


def test_default_on_corrupt(tmp_path):
    p = tmp_path / 'records.json'
    p.write_text('{bad', encoding='utf-8')
    assert records.load(p) == records.DEFAULT


def test_kills_and_clears(tmp_path):
    p = tmp_path / 'records.json'
    records.add_kills(3, p)
    records.add_kills(2, p)
    r = records.add_clear(88, p)
    assert (r['clears'], r['kills'], r['best_turns']) == (1, 5, 88)
    r = records.add_clear(95, p)            # 更慢，不刷新最佳
    assert r['clears'] == 2 and r['best_turns'] == 88
    r = records.add_clear(70, p)            # 更快，刷新
    assert r['best_turns'] == 70


def test_tower_records(tmp_path):
    p = tmp_path / 'records.json'
    r = records.add_tower_run(7, 7, path=p)
    assert r['best_floor'] == 7 and r['crystals'] == 7
    r = records.add_tower_run(4, 4, path=p)          # 更低层不刷新最高，但晶核累加
    assert r['best_floor'] == 7 and r['crystals'] == 11
    r = records.set_tower_upgrades({'hp': 2}, 5, path=p)
    assert r['tower'] == {'hp': 2} and r['crystals'] == 5
    assert records.load(p)['tower'] == {'hp': 2}     # 持久化


def test_tower_upgrade_cost():
    import settings
    assert settings.tower_upgrade_cost(0) == 3
    assert settings.tower_upgrade_cost(1) == 5
    assert settings.tower_upgrade_cost(4) == 11
