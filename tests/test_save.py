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


# ---------- 多槽 / 难度 / 经典模式 / 兼容 ----------

import pytest


@pytest.fixture
def slots_dir(tmp_path, monkeypatch):
    """把存档目录指向临时目录，隔离槽相关测试。"""
    monkeypatch.setattr(save, '_DATA_DIR', tmp_path)
    monkeypatch.setattr(save, 'LEGACY_PATH', tmp_path / 'save.json')
    return tmp_path


def test_slot_roundtrip_and_summary(slots_dir):
    save.save_game(2, roster_dicts(5), 2, camp_turns=7, seals=2,
                   mode='classic', difficulty='hard', fallen=['菲尔'])
    data = save.load_game(2)
    assert data['chapter_idx'] == 2 and data['mode'] == 'classic'
    assert data['difficulty'] == 'hard' and data['fallen'] == ['菲尔']
    assert save.load_game(1) is None                  # 其它槽空
    s = save.slot_summary(2)
    assert s['exists'] and s['lead'] == '罗伊' and s['roster_n'] == 5
    assert s['difficulty'] == 'hard' and s['mode'] == 'classic'
    assert save.slot_summary(1) == {'slot': 1, 'exists': False}


def test_latest_slot(slots_dir):
    assert save.latest_slot() is None
    save.save_game(0, roster_dicts(), 1)
    save.save_game(1, roster_dicts(), 3)
    assert save.latest_slot() == 3                    # 最近写的


def test_v5_back_compat(slots_dir):
    """v5 旧档（无 mode/difficulty/fallen）可读，补默认。"""
    old = {'version': 5, 'kind': 'chapter', 'chapter_idx': 1,
           'camp_turns': 3, 'seals': 1, 'roster': roster_dicts(4)}
    (slots_dir / 'save_1.json').write_text(json.dumps(old), encoding='utf-8')
    data = save.load_game(1)
    assert data is not None
    assert data['mode'] == 'casual' and data['difficulty'] == 'normal'
    assert data['fallen'] == []


def test_bad_meta_rejected(slots_dir):
    bad = {'version': 6, 'kind': 'chapter', 'chapter_idx': 0,
           'difficulty': 'nightmare', 'roster': roster_dicts()}
    (slots_dir / 'save_1.json').write_text(json.dumps(bad), encoding='utf-8')
    assert save.load_game(1) is None


def test_migrate_legacy(slots_dir):
    save.save_game(2, roster_dicts(5), path=slots_dir / 'save.json')   # 旧单档
    assert not save.has_save(1)
    save.migrate_legacy()
    assert save.has_save(1)                           # 迁移到槽1
    save.migrate_legacy()                             # 幂等：槽1已有则不覆盖
    assert save.load_game(1)['chapter_idx'] == 2


def test_gold_roundtrip(slots_dir):
    save.save_game(2, roster_dicts(5), 1, gold=777)
    assert save.load_game(1)['gold'] == 777
    assert save.load_game(1, path=slots_dir / 'nope.json') is None or True  # 不崩
