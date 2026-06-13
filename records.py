"""战绩记忆：通关周目、累计击破、最佳回合，以及试炼之塔的最高层 / 晶核 / 永久强化。
损坏时安全归零。零 pygame 依赖。"""
import json
from pathlib import Path

from paths import user_data_dir

RECORDS_PATH = user_data_dir() / 'records.json'
# best_floor: 试炼之塔最高层；crystals: 试炼晶核（元货币）；tower: 永久强化等级 {key:lv}
DEFAULT = {'clears': 0, 'kills': 0, 'best_turns': None,
           'best_floor': 0, 'crystals': 0, 'tower': {}}


def _fresh():
    r = dict(DEFAULT)
    r['tower'] = {}
    return r


def load(path=RECORDS_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return _fresh()
    out = _fresh()
    for k in DEFAULT:
        if k in data:
            out[k] = data[k]
    if not all(isinstance(out[k], int) for k in ('clears', 'kills', 'best_floor', 'crystals')):
        return _fresh()
    if out['best_turns'] is not None and not isinstance(out['best_turns'], int):
        return _fresh()
    if not isinstance(out['tower'], dict):
        out['tower'] = {}
    return out


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


def add_tower_run(floor, crystals_gained, path=RECORDS_PATH):
    """结束一次试炼之塔：更新最高层并发放晶核。返回更新后的战绩。"""
    r = load(path)
    r['best_floor'] = max(r['best_floor'], floor)
    r['crystals'] += crystals_gained
    _save(r, path)
    return r


def set_tower_upgrades(tower, crystals, path=RECORDS_PATH):
    """写入永久强化等级与剩余晶核（购买后）。返回更新后的战绩。"""
    r = load(path)
    r['tower'] = dict(tower)
    r['crystals'] = crystals
    _save(r, path)
    return r
