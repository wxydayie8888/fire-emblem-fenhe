"""章节存档：JSON 单档，原子写入，损坏/非法时安全返回 None。零 pygame 依赖。

schema:
  {"version": 1, "chapter_idx": 0, "roster": [Unit.to_dict()...]}
"""
import json
import os
from pathlib import Path

from settings import CHAPTERS, CLASSES, PLAYER_ROSTER
from unit import SAVE_FIELDS

SAVE_VERSION = 1
SAVE_PATH = Path(__file__).resolve().parent / 'save.json'

# 合法角色名 = 基础队伍 + 各章 join
_LEGAL_NAMES = ({s['name'] for s in PLAYER_ROSTER}
                | {j['name'] for ch in CHAPTERS for j in ch['join']})


def save_game(chapter_idx, roster_dicts, path=SAVE_PATH):
    """原子写存档（先写 .tmp 再替换，避免写一半产生坏档）。"""
    data = {'version': SAVE_VERSION, 'chapter_idx': chapter_idx, 'roster': roster_dicts}
    tmp = Path(path).with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def load_game(path=SAVE_PATH):
    """读档。文件缺失/损坏/校验失败一律返回 None。"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if _validate(data) else None


def delete_save(path=SAVE_PATH):
    Path(path).unlink(missing_ok=True)


def _validate(data):
    if not isinstance(data, dict) or data.get('version') != SAVE_VERSION:
        return False
    idx = data.get('chapter_idx')
    if not isinstance(idx, int) or not 0 <= idx < len(CHAPTERS):
        return False
    roster = data.get('roster')
    if not isinstance(roster, list) or not roster:
        return False
    if roster[0].get('cls') != 'lord':          # Game.lord = roster[0] 的硬依赖
        return False
    seen = set()
    for d in roster:
        if not isinstance(d, dict) or any(f not in d for f in SAVE_FIELDS):
            return False
        if d['cls'] not in CLASSES or d['name'] not in _LEGAL_NAMES:
            return False
        if d['name'] in seen:
            return False
        seen.add(d['name'])
        for f in SAVE_FIELDS[2:]:
            if not isinstance(d[f], int) or d[f] < 0:
                return False
    return True
