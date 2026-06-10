# 火焰纹章单关战棋 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 pygame 实现一关完整可玩的火焰纹章风格战棋（武器三角/地形/经验升级，DawnLike 素材）。

**Architecture:** 逻辑与渲染严格分离——`settings/unit/combat/grid/ai` 为零 pygame 依赖的纯逻辑层（pytest 覆盖），`assets/ui/game/main` 为渲染与交互层（手动游玩 + 截图验收）。game.py 用状态机驱动回合流程。

**Tech Stack:** Python 3.11+、pygame、pytest；素材 DawnLike v1.81（CC-BY）。

**注（视图层代码）：** Task 7–9 的精灵坐标必须在下载素材后查看图集才能确定，因此这三个任务给出完整的接口签名、状态表与关键代码片段，具体像素坐标在执行时对照图集填写，并以截图验收。

---

### Task 1: 项目骨架 + 素材下载脚本

**Files:**
- Create: `requirements.txt`, `CREDITS.txt`, `tools/fetch_assets.py`

- [x] **Step 1: 写 requirements 与致谢文件**

`requirements.txt`:
```
pygame>=2.5
pytest>=8
```

`CREDITS.txt`:
```
本游戏美术素材使用 DawnLike v1.81 (16x16 Universal Rogue-like tileset)
作者: DragonDePlatino
调色板: DawnBringer
来源: https://opengameart.org/content/dawnlike-16x16-universal-rogue-like-tileset-v181
许可: CC-BY 4.0
```

- [x] **Step 2: 写 tools/fetch_assets.py**

```python
"""一键下载 DawnLike 素材包到 assets/ 目录。"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://opengameart.org/sites/default/files/DawnLike_5.zip"
ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "assets"


def main():
    DEST.mkdir(exist_ok=True)
    print(f"正在下载 {URL} ...")
    try:
        data = urllib.request.urlopen(URL, timeout=60).read()
    except Exception as e:
        print(f"下载失败: {e}\n请手动下载 {URL} 并解压到 {DEST}/")
        sys.exit(1)
    print(f"下载完成 ({len(data) // 1024} KB)，正在解压 ...")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DEST)
    # 找到包含 Objects/Floor.png 的基准目录，确认解压成功
    hits = list(DEST.rglob("Objects/Floor.png"))
    if not hits:
        print("解压后未找到关键文件 Objects/Floor.png，素材可能已损坏")
        sys.exit(1)
    print(f"素材就绪: {hits[0].parent.parent}")


if __name__ == "__main__":
    main()
```

- [x] **Step 3: 安装依赖并运行下载脚本**

Run: `python3 -m pip install -r requirements.txt && python3 tools/fetch_assets.py`
Expected: 输出「素材就绪: .../assets/...」；`assets/` 下出现 Characters/、Objects/、GUI/ 等目录

- [x] **Step 4: 记录素材目录结构（执行时）**

Run: `find assets -name "*.png" | head -40`
把人物图集（如 Characters/Player0.png、Warrior0.png）和地形图集（Objects/Floor.png、Tree0.png 等）的实际路径记下来，Task 7 要用。

- [x] **Step 5: Commit**

```bash
git add requirements.txt CREDITS.txt tools/fetch_assets.py
git commit -m "feat: 项目骨架与素材下载脚本"
```

---

### Task 2: settings.py — 全部数值常量

**Files:**
- Create: `settings.py`
- Test: `tests/test_settings.py`

- [x] **Step 1: 写失败测试**

`tests/test_settings.py`:
```python
import settings


def test_map_dimensions():
    assert len(settings.MAP) == settings.GRID_H == 10
    assert all(len(row) == settings.GRID_W == 15 for row in settings.MAP)


def test_map_only_known_terrain():
    for row in settings.MAP:
        for ch in row:
            assert ch in settings.TERRAIN


def test_units_start_on_passable_tiles():
    for u in settings.PLAYER_UNITS + settings.ENEMY_UNITS:
        x, y = u['pos']
        ch = settings.MAP[y][x]
        assert settings.TERRAIN[ch]['cost'] is not None
        assert u['cls'] in settings.CLASSES
```

- [x] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/ -v`
Expected: FAIL（ModuleNotFoundError: settings）

- [x] **Step 3: 写 settings.py**

```python
"""全部数值常量：尺寸、地形、地图、武器、职业、阵容、规则参数。"""

# --- 尺寸 ---
TILE = 16          # 素材原始像素
SCALE = 3
CELL = TILE * SCALE                  # 48px 格子
GRID_W, GRID_H = 15, 10
INFO_H = 100                         # 底部信息栏高度
SCREEN_W = GRID_W * CELL             # 720
SCREEN_H = GRID_H * CELL + INFO_H    # 580
FPS = 60

# --- 地形: 回避加成 / 移动消耗(None=不可通行) / 回合回血比例 ---
TERRAIN = {
    'P': {'name': '平原', 'avoid': 0,  'cost': 1,    'heal': 0},
    'F': {'name': '森林', 'avoid': 20, 'cost': 2,    'heal': 0},
    'M': {'name': '山地', 'avoid': 30, 'cost': 3,    'heal': 0, 'no_mount': True},
    'W': {'name': '水域', 'avoid': 0,  'cost': None, 'heal': 0},
    'B': {'name': '桥',   'avoid': 0,  'cost': 1,    'heal': 0},
    'T': {'name': '要塞', 'avoid': 20, 'cost': 1,    'heal': 0.2},
}

# 15x10：竖向河流(x7-8)，两座桥(y4 / y7)，西部我方+要塞，东部森林山地+敌方要塞
MAP = [
    "PPPFPPPWWPPPPMM",
    "PPFFFPPWWPPPMMM",
    "PPPFPPPWWPPPPMM",
    "PPPPPPPWWPPFFPP",
    "PPPPPPPBBPPFFPP",
    "PPTPPPPWWPPPPPP",
    "PFPPPPPWWPPPPPP",
    "FFPPPPPBBPPPMPP",
    "PPPPPPPWWPPMMTP",
    "PPPPPPPWWPPPMPP",
]

# --- 武器 ---
WEAPONS = {
    'sword': {'name': '剑',   'might': 5, 'hit': 90, 'crit': 0, 'range': (1, 1)},
    'lance': {'name': '枪',   'might': 7, 'hit': 80, 'crit': 0, 'range': (1, 1)},
    'axe':   {'name': '斧',   'might': 8, 'hit': 70, 'crit': 0, 'range': (1, 1)},
    'bow':   {'name': '弓',   'might': 6, 'hit': 85, 'crit': 0, 'range': (2, 2)},
    'magic': {'name': '魔法', 'might': 8, 'hit': 85, 'crit': 5, 'range': (1, 2)},
}
WEAPON_BEATS = {'sword': 'axe', 'axe': 'lance', 'lance': 'sword'}  # 剑克斧 斧克枪 枪克剑
TRIANGLE_DMG, TRIANGLE_HIT = 1, 15

# --- 职业: 初始属性 + 成长率(%) ---
# 属性键: hp/pow(力量)/skl(技巧)/spd(速度)/dfn(防御)/mov(移动)
CLASSES = {
    'lord':     {'name': '领主',   'hp': 20, 'pow': 6,  'skl': 8, 'spd': 9, 'dfn': 5, 'mov': 5,
                 'weapon': 'sword',
                 'growth': {'hp': 70, 'pow': 45, 'skl': 50, 'spd': 55, 'dfn': 30}},
    'cavalier': {'name': '重骑士', 'hp': 22, 'pow': 7,  'skl': 6, 'spd': 7, 'dfn': 8, 'mov': 7,
                 'weapon': 'lance', 'mounted': True,
                 'growth': {'hp': 80, 'pow': 50, 'skl': 40, 'spd': 45, 'dfn': 40}},
    'archer':   {'name': '弓兵',   'hp': 18, 'pow': 6,  'skl': 9, 'spd': 7, 'dfn': 4, 'mov': 5,
                 'weapon': 'bow',
                 'growth': {'hp': 65, 'pow': 40, 'skl': 60, 'spd': 50, 'dfn': 25}},
    'mage':     {'name': '魔道士', 'hp': 16, 'pow': 7,  'skl': 7, 'spd': 8, 'dfn': 2, 'mov': 5,
                 'weapon': 'magic',
                 'growth': {'hp': 55, 'pow': 55, 'skl': 50, 'spd': 50, 'dfn': 20}},
    # 敌方职业（不升级，无成长率）
    'fighter':  {'name': '斧战士', 'hp': 22, 'pow': 8,  'skl': 5, 'spd': 5, 'dfn': 4, 'mov': 5,
                 'weapon': 'axe', 'growth': {}},
    'soldier':  {'name': '枪兵',   'hp': 20, 'pow': 7,  'skl': 6, 'spd': 6, 'dfn': 6, 'mov': 5,
                 'weapon': 'lance', 'growth': {}},
    'e_archer': {'name': '弓兵',   'hp': 18, 'pow': 6,  'skl': 7, 'spd': 6, 'dfn': 3, 'mov': 5,
                 'weapon': 'bow', 'growth': {}},
    'warrior':  {'name': '勇士',   'hp': 30, 'pow': 10, 'skl': 8, 'spd': 7, 'dfn': 9, 'mov': 5,
                 'weapon': 'axe', 'growth': {}},
}

# --- 阵容 ---
PLAYER_UNITS = [
    {'name': '罗伊',   'cls': 'lord',     'pos': (2, 4)},
    {'name': '兰斯',   'cls': 'cavalier', 'pos': (1, 5)},
    {'name': '丽贝卡', 'cls': 'archer',   'pos': (1, 3)},
    {'name': '莉莉娜', 'cls': 'mage',     'pos': (2, 6)},
]
ENEMY_UNITS = [
    {'name': '斧兵甲', 'cls': 'fighter',  'pos': (10, 4)},
    {'name': '斧兵乙', 'cls': 'fighter',  'pos': (9, 2)},
    {'name': '斧兵丙', 'cls': 'fighter',  'pos': (10, 7)},
    {'name': '枪兵',   'cls': 'soldier',  'pos': (11, 5)},
    {'name': '弓兵',   'cls': 'e_archer', 'pos': (12, 3)},
    {'name': '盖尔',   'cls': 'warrior',  'pos': (13, 8), 'boss': True},
]

# --- 规则参数 ---
EXP_HIT, EXP_KILL, EXP_BOSS_KILL = 10, 30, 60   # 命中/击杀/击杀Boss 经验
EXP_LEVEL = 100
DOUBLE_SPD_GAP = 4    # 速度差≥4 追击
CRIT_MULT = 3         # 必杀三倍

STAT_NAMES = {'hp': 'HP', 'pow': '力量', 'skl': '技巧', 'spd': '速度', 'dfn': '防御'}
```

- [x] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/ -v`
Expected: 3 passed

- [x] **Step 5: Commit**

```bash
git add settings.py tests/test_settings.py
git commit -m "feat: 数值常量与地图数据"
```

---

### Task 3: unit.py — 单位/经验/升级

**Files:**
- Create: `unit.py`
- Test: `tests/test_unit.py`

- [x] **Step 1: 写失败测试**

`tests/test_unit.py`:
```python
from unit import Unit


def make_lord():
    return Unit('罗伊', 'lord', 'player', (2, 4))


def test_init_from_class():
    u = make_lord()
    assert (u.hp, u.max_hp, u.pow, u.mov) == (20, 20, 6, 5)
    assert u.weapon == 'sword' and u.alive and not u.mounted


def test_gain_exp_no_levelup():
    u = make_lord()
    assert u.gain_exp(40) == []
    assert u.exp == 40 and u.level == 1


def test_levelup_all_stats_with_max_growth():
    u = make_lord()
    gains = u.gain_exp(100, rng=lambda: 0.0)   # rng=0 → 全部成长
    assert u.level == 2 and u.exp == 0
    assert gains == [{'hp': 1, 'pow': 1, 'skl': 1, 'spd': 1, 'dfn': 1}]
    assert u.max_hp == 21 and u.hp == 21 and u.pow == 7


def test_levelup_no_stats_with_min_growth():
    u = make_lord()
    gains = u.gain_exp(110, rng=lambda: 0.999)  # rng~1 → 全不成长
    assert u.level == 2 and u.exp == 10
    assert gains == [{'hp': 0, 'pow': 0, 'skl': 0, 'spd': 0, 'dfn': 0}]


def test_double_levelup():
    u = make_lord()
    gains = u.gain_exp(200, rng=lambda: 0.0)
    assert u.level == 3 and len(gains) == 2
```

- [x] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_unit.py -v`
Expected: FAIL（ModuleNotFoundError: unit）

- [x] **Step 3: 写 unit.py**

```python
"""单位：属性、经验、升级。纯逻辑，零 pygame 依赖。"""
import random

from settings import CLASSES, WEAPONS, EXP_LEVEL

STATS = ('hp', 'pow', 'skl', 'spd', 'dfn')


class Unit:
    def __init__(self, name, cls, team, pos, boss=False):
        c = CLASSES[cls]
        self.name, self.cls, self.team = name, cls, team
        self.x, self.y = pos
        self.max_hp = c['hp']
        self.hp = c['hp']
        self.pow, self.skl, self.spd, self.dfn, self.mov = (
            c['pow'], c['skl'], c['spd'], c['dfn'], c['mov'])
        self.weapon = c['weapon']
        self.mounted = c.get('mounted', False)
        self.growth = c['growth']
        self.boss = boss
        self.level, self.exp = 1, 0
        self.acted = False           # 本回合是否已行动

    @property
    def alive(self):
        return self.hp > 0

    @property
    def cls_name(self):
        return CLASSES[self.cls]['name']

    @property
    def weapon_range(self):
        return WEAPONS[self.weapon]['range']

    def gain_exp(self, amount, rng=random.random):
        """增加经验，满 EXP_LEVEL 升级（可连升）。返回每次升级的成长 dict 列表。"""
        if not self.growth:
            return []
        self.exp += amount
        gains = []
        while self.exp >= EXP_LEVEL:
            self.exp -= EXP_LEVEL
            gains.append(self.level_up(rng))
        return gains

    def level_up(self, rng=random.random):
        self.level += 1
        result = {}
        for stat in STATS:
            up = 1 if rng() * 100 < self.growth.get(stat, 0) else 0
            result[stat] = up
            if not up:
                continue
            if stat == 'hp':
                self.max_hp += 1
                self.hp += 1
            else:
                setattr(self, stat, getattr(self, stat) + 1)
        return result

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)
```

- [x] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_unit.py -v`
Expected: 5 passed

- [x] **Step 5: Commit**

```bash
git add unit.py tests/test_unit.py
git commit -m "feat: 单位与经验升级系统"
```

---

### Task 4: combat.py — 战斗结算

**Files:**
- Create: `combat.py`
- Test: `tests/test_combat.py`

- [x] **Step 1: 写失败测试**

`tests/test_combat.py`:
```python
import combat
from unit import Unit


def lord(**kw):
    u = Unit('剑士', 'lord', 'player', (0, 0))
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def fighter(**kw):
    u = Unit('斧兵', 'fighter', 'enemy', (1, 0))
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def test_triangle():
    assert combat.triangle('sword', 'axe') == (1, 15)    # 剑克斧
    assert combat.triangle('axe', 'sword') == (-1, -15)
    assert combat.triangle('sword', 'lance') == (-1, -15)
    assert combat.triangle('sword', 'sword') == (0, 0)
    assert combat.triangle('bow', 'axe') == (0, 0)        # 弓不参与三角


def test_damage_with_triangle():
    # 剑lord打斧fighter: 6力+5威力+1克制-4防 = 8
    assert combat.calc_damage(lord(), fighter()) == 8
    # 反向: 8力+8威力-1被克-5防 = 10
    assert combat.calc_damage(fighter(), lord()) == 10


def test_damage_floor_zero():
    assert combat.calc_damage(lord(pow=0), fighter(dfn=99)) == 0


def test_hit_clamped():
    # lord: 90+8*2+15 - (5*2+0) = 111 → 100
    assert combat.calc_hit(lord(), fighter(), 0) == 100
    assert combat.calc_hit(lord(skl=0), fighter(spd=99), 30) == 0


def test_double():
    assert combat.can_double(lord(), fighter())            # 9 vs 5
    assert not combat.can_double(lord(spd=8), fighter())   # 差3不追击


def test_counter_range():
    assert combat.in_range(fighter(), 1)
    assert not combat.in_range(fighter(), 2)   # 斧打不到2格 → 弓手安全


def test_forecast_no_counter_for_bow():
    archer = Unit('弓手', 'archer', 'player', (0, 0))
    f = combat.forecast(archer, fighter(), 2, 0, 0)
    assert f['def'] is None
    assert f['att']['count'] == 1


def test_resolve_kill_and_exp():
    a, d = lord(), fighter(hp=5)
    events, exp = combat.resolve(a, d, 1, 0, 0, rng=lambda: 0.0)
    # rng=0: 必中+必杀 8*3=24 ≥ 5HP，一击毙命，无反击
    assert not d.alive and len(events) == 1
    assert events[0]['crit'] and events[0]['dmg'] == 24
    assert exp[a] == 10 + 30   # 命中+击杀


def test_resolve_counter_and_double():
    a = lord(spd=20)                  # 必定追击
    d = fighter(hp=99, spd=1)
    hits = iter([0.5, 0.99, 0.5, 0.99, 0.5, 0.99])  # 全命中不必杀
    events, exp = combat.resolve(a, d, 1, 0, 0, rng=lambda: next(hits))
    # 顺序: 攻方→守方反击→攻方追击
    actors = [e['actor'] for e in events]
    assert actors == [a, d, a]
    assert exp[a] == 20   # 两次命中

def test_enemy_gains_no_exp():
    a, d = fighter(), lord(hp=99)
    _, exp = combat.resolve(a, d, 1, 0, 0, rng=lambda: 0.5)
    assert a not in exp
```

- [x] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_combat.py -v`
Expected: FAIL（ModuleNotFoundError: combat）

- [x] **Step 3: 写 combat.py**

```python
"""战斗结算纯逻辑：克制、伤害、命中、追击、必杀、经验。零 pygame 依赖。"""
import random

from settings import (WEAPONS, WEAPON_BEATS, TRIANGLE_DMG, TRIANGLE_HIT,
                      DOUBLE_SPD_GAP, CRIT_MULT, EXP_HIT, EXP_KILL, EXP_BOSS_KILL)


def triangle(att_w, def_w):
    """武器三角 → (伤害修正, 命中修正)"""
    if WEAPON_BEATS.get(att_w) == def_w:
        return TRIANGLE_DMG, TRIANGLE_HIT
    if WEAPON_BEATS.get(def_w) == att_w:
        return -TRIANGLE_DMG, -TRIANGLE_HIT
    return 0, 0


def calc_damage(att, dfd):
    d, _ = triangle(att.weapon, dfd.weapon)
    return max(0, att.pow + WEAPONS[att.weapon]['might'] + d - dfd.dfn)


def calc_hit(att, dfd, def_avoid_bonus):
    """def_avoid_bonus: 守方所站地形的回避加成"""
    _, h = triangle(att.weapon, dfd.weapon)
    hit = (WEAPONS[att.weapon]['hit'] + att.skl * 2 + h
           - (dfd.spd * 2 + def_avoid_bonus))
    return max(0, min(100, hit))


def calc_crit(att):
    return WEAPONS[att.weapon]['crit'] + att.skl // 2


def in_range(unit, dist):
    lo, hi = WEAPONS[unit.weapon]['range']
    return lo <= dist <= hi


def can_double(a, b):
    return a.spd - b.spd >= DOUBLE_SPD_GAP


def forecast(att, dfd, dist, att_avoid, def_avoid):
    """战斗预测（不掷骰）。def 侧为 None 表示无法反击。"""
    res = {'att': {'dmg': calc_damage(att, dfd),
                   'hit': calc_hit(att, dfd, def_avoid),
                   'crit': calc_crit(att),
                   'count': 2 if can_double(att, dfd) else 1},
           'def': None}
    if in_range(dfd, dist):
        res['def'] = {'dmg': calc_damage(dfd, att),
                      'hit': calc_hit(dfd, att, att_avoid),
                      'crit': calc_crit(dfd),
                      'count': 2 if can_double(dfd, att) else 1}
    return res


def resolve(att, dfd, dist, att_avoid, def_avoid, rng=random.random):
    """结算一场战斗（就地扣血）。

    返回 (events, exp_gains):
      events: [{'actor','target','dmg','hit','crit'}] 按时间顺序
      exp_gains: {玩家单位: 获得经验}
    """
    order = [(att, dfd, def_avoid)]
    if in_range(dfd, dist):
        order.append((dfd, att, att_avoid))
    if can_double(att, dfd):
        order.append((att, dfd, def_avoid))
    elif in_range(dfd, dist) and can_double(dfd, att):
        order.append((dfd, att, att_avoid))

    events, exp = [], {}
    for actor, target, t_avoid in order:
        if not (actor.alive and target.alive):
            continue
        hit = rng() * 100 < calc_hit(actor, target, t_avoid)
        crit = bool(hit) and rng() * 100 < calc_crit(actor)
        dmg = calc_damage(actor, target) * (CRIT_MULT if crit else 1) if hit else 0
        target.hp = max(0, target.hp - dmg)
        events.append({'actor': actor, 'target': target,
                       'dmg': dmg, 'hit': hit, 'crit': crit})
        if actor.team == 'player' and hit:
            exp[actor] = exp.get(actor, 0) + EXP_HIT
            if not target.alive:
                exp[actor] += EXP_BOSS_KILL if target.boss else EXP_KILL
    return events, exp
```

- [x] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_combat.py -v`
Expected: 10 passed

- [x] **Step 5: Commit**

```bash
git add combat.py tests/test_combat.py
git commit -m "feat: 战斗结算（三角克制/追击/必杀/经验）"
```

---

### Task 5: grid.py — 地图与范围计算

**Files:**
- Create: `grid.py`
- Test: `tests/test_grid.py`

- [x] **Step 1: 写失败测试**

`tests/test_grid.py`:
```python
from grid import Grid, move_range, attack_tiles, manhattan
from unit import Unit

# 5x4 测试地图: 中间一道河，右上有山
TEST_MAP = [
    "PPWPM",
    "PPWPP",
    "PFBPP",
    "PPWPP",
]


def g():
    return Grid(TEST_MAP)


def test_terrain_lookup():
    assert g().terrain(2, 0)['cost'] is None      # 水
    assert g().terrain(1, 2)['cost'] == 2          # 森林
    assert g().terrain(4, 0).get('no_mount')       # 山


def test_move_range_costs_and_water():
    u = Unit('u', 'lord', 'player', (0, 2))        # mov 5
    r = move_range(u, g(), [u])
    assert (0, 2) in r                              # 原地
    assert (2, 2) in r                              # 桥可走
    assert (2, 0) not in r and (2, 1) not in r      # 水不可走
    assert (3, 2) in r                              # 过桥
    # 森林耗2: 从(0,2)直走到(1,2)耗2
    assert r[(1, 2)] == 2


def test_mounted_cannot_enter_mountain():
    u = Unit('u', 'cavalier', 'player', (3, 0))    # mov 7, 骑马
    r = move_range(u, g(), [u])
    assert (4, 0) not in r
    foot = Unit('f', 'lord', 'player', (3, 0))
    assert (4, 0) in move_range(foot, g(), [foot])


def test_enemy_blocks_path_ally_blocks_stop():
    u = Unit('u', 'lord', 'player', (0, 0))
    enemy = Unit('e', 'fighter', 'enemy', (1, 0))
    ally = Unit('a', 'archer', 'player', (0, 1))
    r = move_range(u, g(), [u, enemy, ally])
    assert (1, 0) not in r          # 敌人占的格不可停
    assert (0, 1) not in r          # 友军占的格不可停
    # 友军可穿过: (0,1)被友军占，但(0,2)可达
    assert (0, 2) in r


def test_attack_tiles_ring():
    tiles = attack_tiles((2, 2), (2, 2), g())       # 弓: 只打2格
    assert (2, 0) in tiles and (4, 2) in tiles and (3, 3) in tiles
    assert (2, 1) not in tiles and (2, 2) not in tiles


def test_manhattan():
    assert manhattan((0, 0), (3, 4)) == 7
```

- [x] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_grid.py -v`
Expected: FAIL（ModuleNotFoundError: grid）

- [x] **Step 3: 写 grid.py**

```python
"""地图、地形与范围计算（Dijkstra 移动范围 / 曼哈顿攻击范围）。零 pygame 依赖。"""
import heapq

import settings
from settings import TERRAIN


class Grid:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else settings.MAP
        self.h = len(self.rows)
        self.w = len(self.rows[0])

    def terrain(self, x, y):
        return TERRAIN[self.rows[y][x]]

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def cost(self, x, y, unit):
        """unit 进入 (x,y) 的移动消耗；None=不可进入"""
        t = self.terrain(x, y)
        if t['cost'] is None:
            return None
        if unit.mounted and t.get('no_mount'):
            return None
        return t['cost']


def neighbors(x, y):
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def move_range(unit, grid, units):
    """Dijkstra 可达范围。返回 {格子: 已耗移动力}。
    敌方单位阻挡通行；任何存活单位占据的格子不能作为落点（自身除外）。"""
    occupied = {(u.x, u.y): u for u in units if u.alive}
    start = (unit.x, unit.y)
    dist = {start: 0}
    pq = [(0, start)]
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if d > dist[(x, y)]:
            continue
        for nx, ny in neighbors(x, y):
            if not grid.in_bounds(nx, ny):
                continue
            c = grid.cost(nx, ny, unit)
            if c is None:
                continue
            blocker = occupied.get((nx, ny))
            if blocker is not None and blocker.team != unit.team:
                continue                     # 敌人挡路，不可穿过
            nd = d + c
            if nd <= unit.mov and nd < dist.get((nx, ny), float('inf')):
                dist[(nx, ny)] = nd
                heapq.heappush(pq, (nd, (nx, ny)))
    return {p: d for p, d in dist.items() if p == start or p not in occupied}


def attack_tiles(pos, weapon_range, grid):
    """从 pos 出发、射程 (lo,hi) 内的所有格子（曼哈顿距离）。"""
    lo, hi = weapon_range
    out = set()
    for dx in range(-hi, hi + 1):
        for dy in range(-hi, hi + 1):
            d = abs(dx) + abs(dy)
            if lo <= d <= hi:
                x, y = pos[0] + dx, pos[1] + dy
                if grid.in_bounds(x, y):
                    out.add((x, y))
    return out


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
```

- [x] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_grid.py -v`
Expected: 6 passed

- [x] **Step 5: Commit**

```bash
git add grid.py tests/test_grid.py
git commit -m "feat: 地图与移动/攻击范围计算"
```

---

### Task 6: ai.py — 敌方 AI

**Files:**
- Create: `ai.py`
- Test: `tests/test_ai.py`

- [x] **Step 1: 写失败测试**

`tests/test_ai.py`:
```python
from ai import plan_action
from grid import Grid
from unit import Unit

PLAIN = ["PPPPPPPP"] * 6


def test_attacks_reachable_target():
    g = Grid(PLAIN)
    e = Unit('斧', 'fighter', 'enemy', (3, 3))
    p = Unit('主', 'lord', 'player', (5, 3), )
    act = plan_action(e, g, [e, p])
    assert act['target'] is p
    # 落点必须与目标相邻（斧射程1）
    mx, my = act['move']
    assert abs(mx - 5) + abs(my - 3) == 1


def test_prefers_kill():
    g = Grid(PLAIN)
    e = Unit('斧', 'fighter', 'enemy', (3, 3))
    healthy = Unit('壮', 'cavalier', 'player', (1, 3))
    dying = Unit('残', 'mage', 'player', (5, 3))
    dying.hp = 2
    act = plan_action(e, g, [e, healthy, dying])
    assert act['target'] is dying


def test_moves_toward_nearest_when_out_of_reach():
    g = Grid(["PPPPPPPPPPPPPP"] * 4)
    e = Unit('斧', 'fighter', 'enemy', (0, 0))
    p = Unit('主', 'lord', 'player', (13, 3))
    act = plan_action(e, g, [e, p])
    assert act['target'] is None
    mx, my = act['move']
    assert (mx - 0) + (my - 0) == 5      # 用满5移动力逼近


def test_boss_stays_put():
    g = Grid(PLAIN)
    boss = Unit('B', 'warrior', 'enemy', (3, 3), boss=True)
    far = Unit('主', 'lord', 'player', (7, 5))
    act = plan_action(boss, g, [boss, far])
    assert act == {'move': (3, 3), 'target': None}
    near = Unit('近', 'lord', 'player', (3, 4))
    act = plan_action(boss, g, [boss, far, near])
    assert act['move'] == (3, 3) and act['target'] is near
```

- [x] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_ai.py -v`
Expected: FAIL（ModuleNotFoundError: ai）

- [x] **Step 3: 写 ai.py**

```python
"""敌方 AI：择优攻击（期望伤害-反击风险），无目标则逼近最近敌人。零 pygame 依赖。"""
import combat
from grid import attack_tiles, manhattan, move_range


def plan_action(unit, grid, units):
    """返回 {'move': (x, y), 'target': Unit 或 None}。
    Boss 不移动，只攻击当前射程内目标。"""
    foes = [u for u in units if u.alive and u.team != unit.team]
    stay = (unit.x, unit.y)
    if not foes:
        return {'move': stay, 'target': None}

    reach = {stay: 0} if unit.boss else move_range(unit, grid, units)

    best = None   # (score, move, target)
    for pos in reach:
        for foe in foes:
            d = manhattan(pos, (foe.x, foe.y))
            if not combat.in_range(unit, d):
                continue
            dmg = combat.calc_damage(unit, foe)
            hit = combat.calc_hit(unit, foe, grid.terrain(foe.x, foe.y)['avoid'])
            score = dmg * hit / 100 + (50 if dmg >= foe.hp else 0)
            if combat.in_range(foe, d):       # 会吃反击 → 扣分
                c_dmg = combat.calc_damage(foe, unit)
                c_hit = combat.calc_hit(foe, unit, grid.terrain(*pos)['avoid'])
                score -= c_dmg * c_hit / 100 * 0.5
            if best is None or score > best[0]:
                best = (score, pos, foe)
    if best is not None:
        return {'move': best[1], 'target': best[2]}

    if unit.boss:
        return {'move': stay, 'target': None}
    nearest = min(foes, key=lambda f: manhattan(stay, (f.x, f.y)))
    move = min(reach, key=lambda p: (manhattan(p, (nearest.x, nearest.y)), reach[p]))
    return {'move': move, 'target': None}
```

- [x] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/ -v`
Expected: 全部通过（settings/unit/combat/grid/ai 累计 ~25 个用例）

- [x] **Step 5: Commit**

```bash
git add ai.py tests/test_ai.py
git commit -m "feat: 敌方AI（择优攻击/逼近/Boss守点）"
```

---

### Task 7: assets.py — 素材加载与精灵映射

**Files:**
- Create: `assets.py`

视图层任务：精灵坐标必须对照真实图集确定，本任务定义机制与接口，坐标在执行时填写。

- [x] **Step 1: 写 assets.py 框架**

接口（game/ui 只通过这三个函数拿图）：
- `load() -> None` — 启动时调用；定位素材基准目录（`assets/` 下递归找含 `Objects/Floor.png` 的目录），缺失时 `raise SystemExit("素材未就绪，请先运行: python3 tools/fetch_assets.py")`
- `terrain_sprite(ch: str) -> pygame.Surface | None` — 地形字符 → 48px 表面（None 则用 settings 中配色画纯色块）
- `unit_sprite(cls: str, team: str) -> pygame.Surface` — 职业 → 48px 人物表面；找不到映射时回退为带职业首字的色块（蓝=我方 红=敌方），**保证不崩溃**

内部实现要点：
```python
_SHEETS = {}   # path -> Surface 缓存

def _cut(sheet_path, col, row):
    """从图集切 16x16 并 scale 到 48x48，带缓存；文件不存在返回 None"""

# 职业 → (图集相对路径, 列, 行)；坐标执行时对照图集填写
UNIT_SPRITES = {
    'lord':     ('Characters/Player0.png', 0, 0),
    'cavalier': ('Characters/Player0.png', 0, 0),
    # ... 执行时从 Characters/ 下的 Player/Warrior/Humanoid 图集中
    #     为 8 个职业各选一个造型迥异的精灵
}
TERRAIN_SPRITES = {
    'P': ..., 'F': ..., 'M': ..., 'W': ..., 'B': ..., 'T': ...,
    # 执行时从 Objects/Floor.png、Tree0.png、Wall.png 等图集选取
}
```

- [x] **Step 2: 写精灵预览模式**

`python3 assets.py` 直接运行时：开窗口把 8 个职业精灵 + 6 种地形并排渲染并标注名称，用于人工核对坐标。

- [x] **Step 3: 执行时对照图集填坐标**

用 Read 工具直接查看 assets/ 下的 PNG 图集，为每个职业/地形挑选坐标；运行预览模式截图核对：8 个职业造型可区分、地形可辨认。

- [x] **Step 4: Commit**

```bash
git add assets.py
git commit -m "feat: DawnLike 素材加载与精灵映射"
```

---

### Task 8: ui.py — 界面组件

**Files:**
- Create: `ui.py`

- [x] **Step 1: 中文字体加载（关键，pygame 默认字体不支持中文）**

```python
import pygame

_FONT_CANDIDATES = ['PingFang SC', 'Hiragino Sans GB', 'Heiti SC', 'STHeiti',
                    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
                    'WenQuanYi Micro Hei', 'Arial Unicode MS']
_cache = {}

def font(size):
    if size not in _cache:
        path = None
        for name in _FONT_CANDIDATES:
            path = pygame.font.match_font(name)
            if path:
                break
        _cache[size] = pygame.font.Font(path, size)   # path=None 时退化为默认字体
    return _cache[size]
```

- [x] **Step 2: 实现 UI 组件（全部为 `draw_xxx(surface, ...)` 纯绘制函数）**

| 组件 | 签名 | 内容 |
|------|------|------|
| 范围高亮 | `draw_tiles(surf, tiles, color)` | 半透明色块：移动=蓝(80,120,255,110)，攻击=红(255,80,80,110) |
| 选中光标 | `draw_cursor(surf, pos)` | 选中格白色描边框 |
| HP 条 | `draw_hp_bar(surf, unit, px, py)` | 单位脚下 44×5px，绿>50% 黄>25% 红，底色深灰 |
| 信息栏 | `draw_info(surf, unit, terrain)` | 底部 100px：左侧悬停单位（名/职业/HP/力技速防/等级经验），右侧地形（名称/回避/移动耗） |
| 行动菜单 | `draw_menu(surf, items, sel, px, py)` | 纵向菜单（攻击/待机），高亮选中项；返回各项 rect 供点击判定 |
| 战斗预测 | `draw_forecast(surf, fc, att, dfd)` | 居中面板两列：双方 名字/HP/伤害×次数/命中%/必杀%；无法反击显示「--」 |
| 升级弹窗 | `draw_levelup(surf, unit, gains, t)` | 居中面板：「升级！」+ 五项属性逐条显示 +1（t 为 0~1 进度，逐项揭示） |
| 回合横幅 | `draw_banner(surf, text, t)` | 全宽深色横带 +大字（玩家回合/敌方回合），t 控制淡入淡出 |
| 结局画面 | `draw_end(surf, win)` | 「胜利！」金色 /「败北…」灰色 + 「按 R 重新开始」 |
| 浮动伤害 | `draw_float_text(surf, text, px, py, t, color)` | 战斗中伤害数字上飘渐隐；MISS 灰色、必杀黄色大字 |

- [x] **Step 3: Commit**

```bash
git add ui.py
git commit -m "feat: UI组件（中文字体/菜单/预测框/升级弹窗）"
```

---

### Task 9: game.py 状态机 + main.py 入口

**Files:**
- Create: `game.py`, `main.py`

- [x] **Step 1: game.py 状态机**

状态表（`self.state`）：

| 状态 | 进入条件 | 可做操作 | 离开 |
|------|---------|---------|------|
| `IDLE` | 玩家回合默认 | 左键选我方未行动单位→`MOVE`；悬停看信息；E 键结束回合 | |
| `MOVE` | 选中单位 | 显示移动+攻击范围；左键可达格→移动→`MENU`；右键/ESC 取消 | |
| `MENU` | 移动完成 | 菜单：攻击（射程内有敌→`TARGET`）/待机（→`IDLE`，单位 acted）；取消则退回原位 | |
| `TARGET` | 选了攻击 | 高亮射程内敌人；点敌人→`FORECAST`；取消→`MENU` | |
| `FORECAST` | 选了目标 | 显示预测框；左键/回车确认→`COMBAT`；右键/ESC 取消 | |
| `COMBAT` | 确认攻击 | 播放战斗事件队列（每事件 ~500ms：攻击方位移突进+伤害数字+HP条扣减）；完毕发经验 | 有升级→`LEVELUP`，否则回 `IDLE`/触发敌方回合 |
| `LEVELUP` | 有单位升级 | 升级弹窗动画 ~2s，点击跳过 | 回 `IDLE` |
| `ENEMY_TURN` | 我方全员行动完或按 E | 逐个敌人：plan_action→滑动移动动画→攻击（复用 COMBAT 队列） | 全部行动完→玩家回合，回合数+1，要塞回血 |
| `END` | 胜负判定 | 胜利/失败画面；R 重开（重建 Game） | |

关键实现要求：
- 回合开始：站要塞的存活单位回 `ceil(max_hp * 0.2)` HP（飘绿色数字）
- 每次战斗结算后立即判定胜负：敌全灭→胜利；主角（`PLAYER_UNITS[0]` 创建的 lord）死亡或我方全灭→失败
- 弓手（射程 2-2）选攻击时：若移动后无 2 格目标，菜单里「攻击」置灰
- 所有「取消」操作链完整：右键/ESC 在每个状态都能退回上一步，移动可还原原位置
- 敌方回合每个动作之间留 300ms 间隔，玩家能看清发生了什么

- [x] **Step 2: main.py 入口**

```python
"""火焰纹章风格战棋 — 入口。操作: 左键选择/确认 右键取消 E结束回合 R重开"""
import pygame

import assets
import settings
from game import Game


def main():
    pygame.init()
    pygame.display.set_caption("火焰纹章·单关演示")
    screen = pygame.display.set_mode((settings.SCREEN_W, settings.SCREEN_H))
    assets.load()
    clock = pygame.time.Clock()
    game = Game()
    running = True
    while running:
        dt = clock.tick(settings.FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle(event)
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
```

- [x] **Step 3: 全量测试 + 启动冒烟**

Run: `python3 -m pytest tests/ -v && python3 main.py`
Expected: 测试全过；窗口打开，地图/单位渲染正常，能完成一次「选人→移动→攻击→结算→敌方回合」循环

- [x] **Step 4: 截图验收**

对照清单：移动范围蓝色高亮、预测框数值与公式一致、克制方向正确（剑打斧 +15 命中）、升级弹窗出现、敌方回合 AI 主动过桥进攻、要塞回血。

- [x] **Step 5: Commit**

```bash
git add game.py main.py
git commit -m "feat: 游戏状态机与主循环，整关可玩"
```

---

### Task 10: 收尾 — README 与最终验收

**Files:**
- Create: `README.md`

- [x] **Step 1: 写 README.md**

内容：游戏截图、安装步骤（pip install → fetch_assets → main.py）、操作说明（左键/右键/E/R）、规则速查（武器三角/地形表/经验）、致谢与许可。

- [x] **Step 2: 最终验收**

Run: `python3 -m pytest tests/ -v`
Expected: 全部通过
手动完整游玩一局打到胜利结局；再故意送掉主角验证失败结局。

- [x] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README 与操作说明"
```

---

## Self-Review 记录

- **规格覆盖**：胜负条件(T9)、玩法循环(T9)、战斗公式(T4)、三角(T4)、射程(T4/T5)、地形六种(T2/T5)、经验升级(T3)、阵容(T2)、AI(T6)、素材+授权(T1/T7)、错误处理(T1/T7)、测试策略(T2-T6/T9-T10) — 全覆盖
- **类型一致性**：属性键统一 `hp/pow/skl/spd/dfn/mov`；`Unit.weapon_range`=(lo,hi)；`resolve` 返回 (events, exp_gains)；`plan_action` 返回 {'move','target'} — 各任务间一致
- **已知留白（有意为之）**：Task 7 精灵坐标、Task 8/9 的渲染细节代码——必须对照真实图集与运行效果迭代，计划中以接口契约+验收清单锁定行为
