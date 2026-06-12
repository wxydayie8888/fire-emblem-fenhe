"""战绩记忆：通关周目数、累计击破、最佳通关回合。损坏时安全归零。零 pygame 依赖。"""
import json
from pathlib import Path

from paths import user_data_dir

RECORDS_PATH = user_data_dir() / 'records.json'
DEFAULT = {'clears': 0, 'kills': 0, 'best_turns': None}


def load(path=RECORDS_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        out = dict(DEFAULT)
        for k in DEFAULT:
            if k in data:
                out[k] = data[k]
        if not isinstance(out['clears'], int) or not isinstance(out['kills'], int):
            return dict(DEFAULT)
        if out['best_turns'] is not None and not isinstance(out['best_turns'], int):
            return dict(DEFAULT)
        return out
    except (OSError, ValueError):
        return dict(DEFAULT)


def _save(data, path):
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def add_kills(n, path=RECORDS_PATH):
    r = load(path)
    r['kills'] += n
    _save(r, path)
    return r


def add_clear(camp_turns, path=RECORDS_PATH):
    """通关一周目。返回更新后的战绩。"""
    r = load(path)
    r['clears'] += 1
    if r['best_turns'] is None or camp_turns < r['best_turns']:
        r['best_turns'] = camp_turns
    _save(r, path)
    return r
