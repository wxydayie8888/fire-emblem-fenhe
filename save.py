"""多槽存档：3 个手动槽（1/2/3）+ 1 个自动槽（auto），每槽一个 JSON 文件，
原子写入，损坏/非法/版本不符一律安全返回 None。零 pygame 依赖。

schema v6:
  章节档 {"version":6,"kind":"chapter","chapter_idx","camp_turns","seals",
          "mode","difficulty","fallen":[name...],"roster":[Unit.to_dict()...]}
  战斗档 {"version":6,"kind":"battle", ...挂起战局... + mode/difficulty/fallen}

兼容：v5 旧档可读（mode 默认 casual、difficulty 默认 normal、fallen 默认 []）。
旧单档 save.json 首次运行迁移到 槽1。
"""
import json
import os
from pathlib import Path

from settings import CHAPTERS, CLASSES, PLAYER_ROSTER
from unit import SAVE_FIELDS

from paths import user_data_dir

SAVE_VERSION = 6              # v6: 多槽 + 难度 + 经典模式(阵亡名单)
_OK_VERSIONS = (5, 6)        # v5 旧档兼容读取

MANUAL_SLOTS = (1, 2, 3)
AUTO_SLOT = 'auto'
ALL_SLOTS = (1, 2, 3, AUTO_SLOT)

_DATA_DIR = user_data_dir()
LEGACY_PATH = _DATA_DIR / 'save.json'        # 旧版单档

# 合法角色名 = 基础队伍 + 各章 join
_LEGAL_NAMES = ({s['name'] for s in PLAYER_ROSTER}
                | {j['name'] for ch in CHAPTERS for j in ch['join']})


def slot_path(slot):
    return _DATA_DIR / f'save_{slot}.json'


def _resolve(slot, path):
    return Path(path) if path is not None else slot_path(slot)


def _atomic_write(data, path):
    """原子写存档（先写 .tmp 再替换，避免写一半产生坏档）。"""
    tmp = Path(path).with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def _meta(mode, difficulty, fallen):
    return {'mode': mode if mode in ('casual', 'classic') else 'casual',
            'difficulty': difficulty if difficulty in ('normal', 'hard') else 'normal',
            'fallen': sorted(set(fallen or ()))}


def save_game(chapter_idx, roster_dicts, slot=1, *, path=None,
              camp_turns=0, seals=0, gold=0, mode='casual', difficulty='normal', fallen=()):
    """章节开局/通关存档写入指定槽。"""
    data = {'version': SAVE_VERSION, 'kind': 'chapter',
            'chapter_idx': chapter_idx, 'camp_turns': camp_turns,
            'seals': seals, 'gold': gold, 'roster': roster_dicts}
    data.update(_meta(mode, difficulty, fallen))
    _atomic_write(data, _resolve(slot, path))


def save_battle(payload, slot=1, *, path=None):
    """战斗中挂起存档。payload 见 game._battle_payload()（已含 mode/difficulty/fallen）。"""
    data = dict(payload)
    data['version'] = SAVE_VERSION
    data['kind'] = 'battle'
    data.update(_meta(data.get('mode'), data.get('difficulty'), data.get('fallen')))
    _atomic_write(data, _resolve(slot, path))


def load_game(slot=1, *, path=None):
    """读档。文件缺失/损坏/校验失败一律返回 None；成功则补齐 mode/difficulty/fallen。"""
    try:
        data = json.loads(_resolve(slot, path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not _validate(data):
        return None
    data.setdefault('kind', 'chapter')
    data.setdefault('mode', 'casual')
    data.setdefault('difficulty', 'normal')
    data.setdefault('fallen', [])
    data.setdefault('gold', 0)
    return data


def delete_save(slot=1, *, path=None):
    _resolve(slot, path).unlink(missing_ok=True)


def has_save(slot):
    return load_game(slot) is not None


def slot_summary(slot):
    """供存/读档界面显示的一行摘要。无档返回 {'slot','exists':False}。"""
    data = load_game(slot)
    if data is None:
        return {'slot': slot, 'exists': False}
    idx = data['chapter_idx']
    title = CHAPTERS[idx]['title'] if 0 <= idx < len(CHAPTERS) else '?'
    # 战斗档用 roster_meta（场上实时队伍，含升级后的等级），章节档用 roster
    roster = (data['roster'] if data['kind'] == 'chapter'
              else data.get('roster_meta') or data.get('snapshot', []))
    lead = roster[0]['name'] if roster else '?'
    lead_lv = roster[0].get('level', 1) if roster else 1
    try:
        mtime = os.path.getmtime(slot_path(slot))
    except OSError:
        mtime = 0
    return {
        'slot': slot, 'exists': True, 'kind': data['kind'],
        'chapter_idx': idx, 'chapter_title': title,
        'lead': lead, 'lead_level': lead_lv, 'roster_n': len(roster),
        'turn': data.get('turn'), 'mode': data['mode'],
        'difficulty': data['difficulty'], 'mtime': mtime,
    }


def all_summaries():
    return {slot: slot_summary(slot) for slot in ALL_SLOTS}


def latest_slot():
    """最近修改且可用的槽（标题「继续游戏」用）。无则 None。"""
    best, best_t = None, -1
    for slot in ALL_SLOTS:
        s = slot_summary(slot)
        if s['exists'] and s['mtime'] >= best_t:
            best, best_t = slot, s['mtime']
    return best


def migrate_legacy():
    """旧版单档 save.json → 槽1（仅当槽1为空且旧档可用时），幂等。"""
    try:
        if not LEGACY_PATH.exists() or has_save(1):
            return
        data = json.loads(LEGACY_PATH.read_text(encoding='utf-8'))
        if _validate(data):
            _atomic_write(data, slot_path(1))
    except (OSError, ValueError):
        pass


# ---------- 校验 ----------

def _valid_roster(roster, legal_names=True):
    """章节存档的队伍列表校验（SAVE_FIELDS、首位领主、名字合法不重复）。"""
    if not isinstance(roster, list) or not roster:
        return False
    if roster[0].get('cls') not in ('lord', 'great_lord'):   # Game.lord = roster[0]
        return False
    seen = set()
    for d in roster:
        if not isinstance(d, dict) or any(f not in d for f in SAVE_FIELDS):
            return False
        if d['cls'] not in CLASSES:
            return False
        if legal_names and d['name'] not in _LEGAL_NAMES:
            return False
        if d['name'] in seen:
            return False
        seen.add(d['name'])
        for f in SAVE_FIELDS[2:]:
            if not isinstance(d[f], int) or d[f] < 0:
                return False
    return True


def _valid_battle_unit(d, team):
    from unit import Unit
    if not isinstance(d, dict) or any(f not in d for f in Unit.BATTLE_FIELDS):
        return False
    if d['cls'] not in CLASSES or d['team'] != team:
        return False
    if d['ai'] not in ('aggro', 'guard') or not isinstance(d['boss'], bool):
        return False
    for f in ('level', 'exp', 'max_hp', 'pow', 'skl', 'spd', 'dfn',
              'x', 'y', 'hp', 'potions'):
        if not isinstance(d[f], int) or d[f] < 0:
            return False
    return True


def _valid_meta(data):
    """mode/difficulty/fallen 若存在则需合法（缺失按默认，兼容 v5）。"""
    if data.get('mode', 'casual') not in ('casual', 'classic'):
        return False
    if data.get('difficulty', 'normal') not in ('normal', 'hard'):
        return False
    fallen = data.get('fallen', [])
    return isinstance(fallen, list) and all(isinstance(n, str) for n in fallen)


def _validate(data):
    if not isinstance(data, dict) or data.get('version') not in _OK_VERSIONS:
        return False
    idx = data.get('chapter_idx')
    if not isinstance(idx, int) or not 0 <= idx < len(CHAPTERS):
        return False
    if not _valid_meta(data):
        return False
    kind = data.get('kind', 'chapter' if 'roster' in data else None)
    if kind == 'chapter':
        return _valid_roster(data.get('roster'))
    if kind == 'battle':
        if not isinstance(data.get('turn'), int) or data['turn'] < 1:
            return False
        meta = data.get('roster_meta')
        if (not isinstance(meta, list) or not meta
                or meta[0].get('cls') not in ('lord', 'great_lord')):
            return False
        if not all(_valid_battle_unit(d, 'player') for d in meta):
            return False
        if not _valid_roster(data.get('snapshot')):
            return False
        enemies = data.get('enemies')
        if not isinstance(enemies, list):
            return False
        if not all(_valid_battle_unit(d, 'enemy') for d in enemies):
            return False
        return isinstance(data.get('reinforce_used'), list) \
            and isinstance(data.get('pending_reinforce'), list)
    return False
