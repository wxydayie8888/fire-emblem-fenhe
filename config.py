"""玩家选项（音量/文字速度/确认/动画/自动存档）：持久化到用户数据目录，
原子写入，损坏时回退默认。零 pygame 依赖，便于单测。

对外：load() 启动调用一次；get(k)/set(k,v) 读写并即时落盘；
music_frac()/sfx_frac()/text_cps() 给渲染层用的派生值；
SCHEMA 供「选项」界面渲染（逐项 key/标签/类型）。
"""
import json
import os
from pathlib import Path

from paths import user_data_dir

CONFIG_PATH = user_data_dir() / 'config.json'

DEFAULTS = {
    'music_vol': 7,        # 0-10
    'sfx_vol': 7,          # 0-10
    'text_speed': 'normal',  # slow / normal / fast
    'confirm_end': True,   # 回合结束二次确认
    'skip_anim': False,    # 跳过战斗动作动画（自动快进）
    'autosave': True,      # 每章开始/进战自动写入「自动存档」槽
}

# 文字逐字显示速度（字/秒）
_TEXT_CPS = {'slow': 16, 'normal': 30, 'fast': 60}
TEXT_SPEED_LABELS = {'slow': '慢', 'normal': '普通', 'fast': '快'}
_TEXT_ORDER = ['slow', 'normal', 'fast']

# 「选项」界面行定义：(key, 标签, 类型)
#   vol  -> 0-10 整数（左右 ±1）
#   speed-> text_speed 三档循环
#   bool -> 开/关
SCHEMA = [
    ('music_vol', '音乐音量', 'vol'),
    ('sfx_vol', '音效音量', 'vol'),
    ('text_speed', '文字速度', 'speed'),
    ('confirm_end', '结束回合需确认', 'bool'),
    ('skip_anim', '跳过战斗动画', 'bool'),
    ('autosave', '自动存档', 'bool'),
]

_cfg = dict(DEFAULTS)


def _coerce(data):
    """把读到的 dict 收敛为合法配置：未知键忽略、缺失键补默认、类型/范围校正。"""
    out = dict(DEFAULTS)
    if isinstance(data, dict):
        for k in DEFAULTS:
            v = data.get(k, DEFAULTS[k])
            if k in ('music_vol', 'sfx_vol'):
                v = v if isinstance(v, int) else DEFAULTS[k]
                v = max(0, min(10, v))
            elif k == 'text_speed':
                v = v if v in _TEXT_CPS else DEFAULTS[k]
            else:                                   # bool
                v = bool(v)
            out[k] = v
    return out


def load(path=CONFIG_PATH):
    """启动时调用：从文件载入（缺失/损坏用默认）。返回当前配置 dict 的副本。"""
    global _cfg
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = None
    _cfg = _coerce(data)
    return dict(_cfg)


def _save(path=CONFIG_PATH):
    try:
        tmp = Path(path).with_suffix('.tmp')
        tmp.write_text(json.dumps(_cfg, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, path)
    except OSError:
        pass


def get(key):
    return _cfg.get(key, DEFAULTS.get(key))


def set(key, value, path=CONFIG_PATH):
    """写入单项并即时落盘（经 _coerce 校正）。返回校正后的值。"""
    global _cfg
    merged = dict(_cfg)
    merged[key] = value
    _cfg = _coerce(merged)
    _save(path)
    return _cfg[key]


def all(): return dict(_cfg)


def music_frac(): return _cfg['music_vol'] / 10.0


def sfx_frac(): return _cfg['sfx_vol'] / 10.0


def text_cps(): return _TEXT_CPS[_cfg['text_speed']]


def cycle(key, direction):
    """选项界面的左右调整：vol±1、speed 循环、bool 翻转。返回新值。"""
    for k, _label, kind in SCHEMA:
        if k != key:
            continue
        if kind == 'vol':
            return set(key, max(0, min(10, _cfg[key] + direction)))
        if kind == 'speed':
            i = (_TEXT_ORDER.index(_cfg[key]) + direction) % len(_TEXT_ORDER)
            return set(key, _TEXT_ORDER[i])
        if kind == 'bool':
            return set(key, not _cfg[key])
    return _cfg.get(key)


def display_value(key):
    """选项界面右侧显示的可读值。"""
    v = _cfg[key]
    for k, _label, kind in SCHEMA:
        if k == key:
            if kind == 'vol':
                return str(v)            # 条形由 UI 绘制
            if kind == 'speed':
                return TEXT_SPEED_LABELS[v]
            if kind == 'bool':
                return '开' if v else '关'
    return str(v)
