import settings
from settings import CHAPTERS, CLASSES, PLAYER_ROSTER, TERRAIN


def test_three_chapters():
    assert len(CHAPTERS) == 3
    for ch in CHAPTERS:
        assert ch['win'] in ('rout', 'boss')
        assert ch['title'] and ch['story'] and ch['objective']


def test_chapter_maps_valid():
    for ch in CHAPTERS:
        rows = ch['map']
        assert len(rows) == settings.GRID_H == 10
        assert all(len(r) == settings.GRID_W == 15 for r in rows)
        for r in rows:
            for c in r:
                assert c in TERRAIN


def _passable(rows, pos, cls):
    x, y = pos
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
        assert len(ch['players']) == expect
        expect += len(ch['join'])


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
            assert _passable(rows, e['pos'], e['cls'])
            assert e['pos'] not in taken
            taken.add(e['pos'])
            assert e.get('ai', 'aggro') in ('aggro', 'guard')
        roster += [j['cls'] for j in ch['join']]


def test_boss_chapters_have_boss():
    for ch in CHAPTERS:
        bosses = [e for e in ch['enemies'] if e.get('boss')]
        assert bosses, ch['title']          # 每章都有 Boss
        if ch['win'] == 'boss':
            assert len(bosses) == 1


def test_new_terrains():
    assert TERRAIN['S']['cost'] == 1
    assert TERRAIN['R']['cost'] is None     # 城墙不可通行
    assert TERRAIN['G']['cost'] == 1
