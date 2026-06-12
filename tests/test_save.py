import json

import save
from unit import Unit


def roster_dicts(n=4):
    base = [('罗伊', 'lord'), ('兰斯', 'cavalier'), ('丽贝卡', 'archer'),
            ('莉莉娜', 'mage'), ('菲尔', 'myrmidon')]
    return [Unit(name, cls, 'player', (0, 0)).to_dict() for name, cls in base[:n]]


def test_roundtrip(tmp_path):
    p = tmp_path / 'save.json'
    save.save_game(1, roster_dicts(5), path=p)
    data = save.load_game(path=p)
    assert data['chapter_idx'] == 1
    assert len(data['roster']) == 5
    assert data['roster'][0]['name'] == '罗伊'


def test_load_missing_returns_none(tmp_path):
    assert save.load_game(path=tmp_path / 'nope.json') is None


def test_load_corrupt_returns_none(tmp_path):
    p = tmp_path / 'save.json'
    p.write_text('{not valid json!!', encoding='utf-8')
    assert save.load_game(path=p) is None


def test_load_wrong_version_returns_none(tmp_path):
    p = tmp_path / 'save.json'
    save.save_game(0, roster_dicts(), path=p)
    data = json.loads(p.read_text(encoding='utf-8'))
    data['version'] = 99
    p.write_text(json.dumps(data), encoding='utf-8')
    assert save.load_game(path=p) is None


def test_load_invalid_rejected(tmp_path):
    p = tmp_path / 'save.json'
    cases = [
        {'version': save.SAVE_VERSION, 'chapter_idx': 99, 'roster': roster_dicts()},  # 章节越界
        {'version': save.SAVE_VERSION, 'chapter_idx': 0, 'roster': []},               # 空队伍
        {'version': save.SAVE_VERSION, 'chapter_idx': 0,
         'roster': roster_dicts()[1:]},                                               # 首位不是领主
    ]
    bad_cls = roster_dicts()
    bad_cls[1]['cls'] = 'slime'                                                       # 非法职业
    cases.append({'version': save.SAVE_VERSION, 'chapter_idx': 0, 'roster': bad_cls})
    bad_field = roster_dicts()
    del bad_field[2]['spd']                                                           # 缺字段
    cases.append({'version': save.SAVE_VERSION, 'chapter_idx': 0, 'roster': bad_field})
    bad_name = roster_dicts()
    bad_name[3]['name'] = '路人甲'                                                     # 非法名字
    cases.append({'version': save.SAVE_VERSION, 'chapter_idx': 0, 'roster': bad_name})
    for data in cases:
        p.write_text(json.dumps(data), encoding='utf-8')
        assert save.load_game(path=p) is None, data


def test_delete_idempotent(tmp_path):
    p = tmp_path / 'save.json'
    save.save_game(0, roster_dicts(), path=p)
    save.delete_save(path=p)
    assert not p.exists()
    save.delete_save(path=p)        # 再删不报错


def battle_payload():
    lord = Unit('罗伊', 'lord', 'player', (2, 4))
    enemy = Unit('斧兵', 'fighter', 'enemy', (10, 4))
    return {
        'chapter_idx': 5, 'turn': 4, 'boss_quote_shown': True,
        'camp_turns': 21, 'reinforce_used': [3],
        'pending_reinforce': [],
        'roster_meta': [lord.to_battle_dict()],
        'snapshot': [lord.to_dict()],
        'enemies': [enemy.to_battle_dict()],
    }


def test_battle_save_roundtrip(tmp_path):
    p = tmp_path / 'save.json'
    save.save_battle(battle_payload(), path=p)
    data = save.load_game(path=p)
    assert data and data['kind'] == 'battle'
    assert data['turn'] == 4 and data['chapter_idx'] == 5
    assert data['enemies'][0]['cls'] == 'fighter'


def test_battle_save_validation(tmp_path):
    p = tmp_path / 'save.json'
    bad = battle_payload()
    bad['enemies'][0]['cls'] = 'slime'
    save.save_battle(bad, path=p)
    assert save.load_game(path=p) is None        # 非法职业拒绝
    bad2 = battle_payload()
    bad2['roster_meta'][0]['cls'] = 'mage'        # 首位非领主
    save.save_battle(bad2, path=p)
    assert save.load_game(path=p) is None


def test_chapter_save_still_works(tmp_path):
    p = tmp_path / 'save.json'
    save.save_game(1, roster_dicts(5), path=p)
    data = save.load_game(path=p)
    assert data['kind'] == 'chapter'
