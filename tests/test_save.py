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
        {'version': save.SAVE_VERSION, 'chapter_idx': 9, 'roster': roster_dicts()},   # 章节越界
        {'version': save.SAVE_VERSION, 'chapter_idx': 0, 'roster': []},               # 空队伍
        {'version': save.SAVE_VERSION, 'chapter_idx': 0,
         'roster': roster_dicts()[1:]},                                               # 首位不是领主
    ]
    bad_cls = roster_dicts()
    bad_cls[1]['cls'] = 'dragon'                                                      # 非法职业
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
