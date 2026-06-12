"""章节存档：JSON 单档，原子写入，损坏/非法时安全返回 None。零 pygame 依赖。

schema:
  {"version": 1, "chapter_idx": 0, "roster": [Unit.to_dict()...]}
"""
import json
import os
from pathlib import Path

from settings import CHAPTERS, CLASSES, PLAYER_ROSTER
from unit import SAVE_FIELDS

SAVE_VERSION = 4      # v4: 支持战斗中挂起存档（kind: chapter / battle）
SAVE_PATH = Path(__file__).resolve().parent / 'save.json'

# 合法角色名 = 基础队伍 + 各章 join
_LEGAL_NAMES = ({s['name'] for s in PLAYER_ROSTER}
                | {j['name'] for ch in CHAPTERS for j in ch['join']})


def _atomic_write(data, path):
    """原子写存档（先写 .tmp 再替换，避免写一半产生坏档）。"""
    tmp = Path(path).with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def save_game(chapter_idx, roster_dicts, camp_turns=0, path=SAVE_PATH):
    """章节开局/通关存档。"""
    _atomic_write({'version': SAVE_VERSION, 'kind': 'chapter',
                   'chapter_idx': chapter_idx, 'camp_turns': camp_turns,
                   'roster': roster_dicts}, path)


def save_battle(payload, path=SAVE_PATH):
    """战斗中挂起存档。payload 见 game.save_battle_state()。"""
    data = dict(payload)
    data['version'] = SAVE_VERSION
    data['kind'] = 'battle'
    _atomic_write(data, path)


def load_game(path=SAVE_PATH):
    """读档。文件缺失/损坏/校验失败一律返回 None。"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if _validate(data) else None


def delete_save(path=SAVE_PATH):
    Path(path).unlink(missing_ok=True)


def _valid_roster(roster, legal_names=True):
    """章节存档的队伍列表校验（SAVE_FIELDS、首位领主、名字合法不重复）。"""
    if not isinstance(roster, list) or not roster:
        return False
    if roster[0].get('cls') != 'lord':          # Game.lord = roster[0] 的硬依赖
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


def _validate(data):
    if not isinstance(data, dict) or data.get('version') != SAVE_VERSION:
        return False
    idx = data.get('chapter_idx')
    if not isinstance(idx, int) or not 0 <= idx < len(CHAPTERS):
        return False
    kind = data.get('kind')
    if kind == 'chapter':
        return _valid_roster(data.get('roster'))
    if kind == 'battle':
        if not isinstance(data.get('turn'), int) or data['turn'] < 1:
            return False
        meta = data.get('roster_meta')
        if not isinstance(meta, list) or not meta or meta[0].get('cls') != 'lord':
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
