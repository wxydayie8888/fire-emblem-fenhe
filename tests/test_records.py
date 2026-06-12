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
    assert r == {'clears': 1, 'kills': 5, 'best_turns': 88}
    r = records.add_clear(95, p)            # 更慢，不刷新最佳
    assert r['clears'] == 2 and r['best_turns'] == 88
    r = records.add_clear(70, p)            # 更快，刷新
    assert r['best_turns'] == 70
