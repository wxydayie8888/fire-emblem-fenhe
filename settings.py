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
