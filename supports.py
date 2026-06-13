"""羁绊/支援：相邻同队友军提供战斗加成。纯逻辑，零 pygame 依赖。

设计：
- 任意相邻（曼哈顿=1）同队友军 → 基础加成（并肩作战）。
- 剧情 CP（SUPPORT_PAIRS）相邻 → 额外加成（更高命中/回避 + 必杀）。
- 大将「鼓舞」光环：相邻的大将额外给友军命中/回避加成。
- 各项加成封顶 CAP，避免叠加失衡。
仅对我方生效（敌方不享受）。
"""
from settings import CLASSES

GENERIC = {'hit': 5, 'avoid': 5, 'crit': 0, 'dmg': 0}       # 每名相邻友军
PAIR = {'hit': 10, 'avoid': 10, 'crit': 5, 'dmg': 0}        # 剧情 CP 额外
AURA = {'hit': 10, 'avoid': 10}                             # 相邻大将「鼓舞」额外
CAP = 30                                                    # 命中/回避封顶

# 剧情 CP（无向）：名字对 -> 关系（仅用于展示）
SUPPORT_PAIRS = {
    frozenset({'罗伊', '莉莉娜'}): '情愫',
    frozenset({'罗伊', '丽贝卡'}): '青梅竹马',
    frozenset({'罗伊', '兰斯'}):   '师徒',
    frozenset({'莉莉娜', '丽贝卡'}): '损友',
    frozenset({'菲尔', '西娅'}):   '反差',
    frozenset({'艾莉丝', '加斯'}): '袍泽',
}


def is_pair(a, b):
    return frozenset({a, b}) in SUPPORT_PAIRS


def pair_name(a, b):
    return SUPPORT_PAIRS.get(frozenset({a, b}))


def _adjacent(u, v):
    return abs(u.x - v.x) + abs(u.y - v.y) == 1


def support_bonus(unit, units):
    """返回 unit 从相邻同队友军获得的战斗加成 {hit, avoid, crit, dmg}。"""
    out = {'hit': 0, 'avoid': 0, 'crit': 0, 'dmg': 0}
    if unit.team != 'player':
        return out
    for v in units:
        if v is unit or not v.alive or v.team != unit.team:
            continue
        if not _adjacent(unit, v):
            continue
        for k in out:
            out[k] += GENERIC[k]
        if is_pair(unit.name, v.name):
            for k in out:
                out[k] += PAIR[k]
        if CLASSES[v.cls].get('skill', {}).get('aura'):     # 相邻大将「鼓舞」
            out['hit'] += AURA['hit']
            out['avoid'] += AURA['avoid']
    out['hit'] = min(out['hit'], CAP)
    out['avoid'] = min(out['avoid'], CAP)
    out['crit'] = min(out['crit'], 15)
    return out


def has_support(unit, units):
    b = support_bonus(unit, units)
    return any(b.values())
