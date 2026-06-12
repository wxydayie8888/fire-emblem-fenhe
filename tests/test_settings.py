import settings
from settings import CHAPTERS, CLASSES, PLAYER_ROSTER, TERRAIN


def test_ten_chapters():
    assert len(CHAPTERS) == 10
    for ch in CHAPTERS:
        assert ch['win'] in ('rout', 'boss', 'seize', 'defend')
        assert ch['title'] and ch['story'] and ch['objective']
        if ch['win'] == 'seize':
            assert 'goal' in ch
        if ch['win'] == 'defend':
            assert ch['hold_turns'] >= 3


def test_chapter_maps_valid():
    for ch in CHAPTERS:
        rows = ch['map']
        assert len(rows) == settings.GRID_H == 10
        assert all(len(r) == settings.GRID_W == 15 for r in rows)
        for r in rows:
            for c in r:
                assert c in TERRAIN, (ch['title'], c)


def _passable(rows, pos, cls):
    x, y = pos
    if not (0 <= x < settings.GRID_W and 0 <= y < settings.GRID_H):
        return False
    if CLASSES[cls].get('fly'):
        return True
    t = TERRAIN[rows[y][x]]
    if t['cost'] is None:
        return False
    if CLASSES[cls].get('mounted') and t.get('no_mount'):
        return False
    return True


def test_roster_grows_with_joins():
    # 第 i 章的出生点数量 = 基础 4 人 + 之前所有章节加入的同伴
    expect = len(PLAYER_ROSTER)
    for ch in CHAPTERS:
        assert len(ch['players']) == expect, ch['title']
        expect += len(ch['join'])
    assert expect == 8                      # 最终八人队伍


def test_all_positions_passable_and_distinct():
    roster = [s['cls'] for s in PLAYER_ROSTER]
    for ch in CHAPTERS:
        rows = ch['map']
        taken = set()
        for cls, pos in zip(roster, ch['players']):
            assert _passable(rows, pos, cls), (ch['title'], pos)
            assert pos not in taken
            taken.add(pos)
        for j in ch['join']:
            assert j['cls'] in CLASSES
            assert _passable(rows, j['pos'], j['cls'])
            assert j['pos'] not in taken
            taken.add(j['pos'])
        for e in ch['enemies']:
            assert e['cls'] in CLASSES
            assert _passable(rows, e['pos'], e['cls']), (ch['title'], e['name'])
            assert e['pos'] not in taken, (ch['title'], e['pos'])
            taken.add(e['pos'])
            assert e.get('ai', 'aggro') in ('aggro', 'guard')
        for turn, specs in ch.get('reinforce', {}).items():
            assert isinstance(turn, int) and turn >= 2
            for spec in specs:
                assert spec['cls'] in CLASSES
                assert _passable(rows, spec['pos'], spec['cls']), (ch['title'], spec)
        if ch['win'] == 'seize':
            gx, gy = ch['goal']
            assert TERRAIN[rows[gy][gx]]['cost'] is not None
        roster += [j['cls'] for j in ch['join']]


def test_boss_chapters_have_boss():
    for ch in CHAPTERS:
        bosses = [e for e in ch['enemies'] if e.get('boss')]
        assert bosses, ch['title']          # 每章都有 Boss
        if ch['win'] == 'boss':
            assert len(bosses) == 1


def test_cleric_and_flier_classes():
    assert CLASSES['cleric']['weapon'] == 'staff'
    assert CLASSES['pegasus'].get('fly') and CLASSES['wyvern'].get('fly')
    assert settings.WEAPONS['staff'].get('heal')
    assert settings.WEAPONS['breath']['range'] == (1, 2)


def test_new_terrains():
    assert TERRAIN['S']['cost'] == 1
    assert TERRAIN['R']['cost'] is None     # 城墙不可通行
    assert TERRAIN['G']['cost'] == 1
