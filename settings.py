"""全部数值常量：尺寸、地形、武器、职业、章节数据、规则参数。"""

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
    'T': {'name': '要塞', 'avoid': 20, 'cost': 1,    'heal': 0.1},
    'S': {'name': '石板', 'avoid': 0,  'cost': 1,    'heal': 0},
    'R': {'name': '城墙', 'avoid': 0,  'cost': None, 'heal': 0},
    'G': {'name': '城门', 'avoid': 10, 'cost': 1,    'heal': 0},
}

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
    'lord':     {'name': '领主',   'hp': 24, 'pow': 7,  'skl': 8,  'spd': 9,  'dfn': 7,  'mov': 5,
                 'weapon': 'sword',
                 'growth': {'hp': 70, 'pow': 45, 'skl': 50, 'spd': 55, 'dfn': 35}},
    'cavalier': {'name': '重骑士', 'hp': 24, 'pow': 8,  'skl': 6,  'spd': 7,  'dfn': 8,  'mov': 7,
                 'weapon': 'lance', 'mounted': True,
                 'growth': {'hp': 80, 'pow': 50, 'skl': 40, 'spd': 45, 'dfn': 40}},
    'archer':   {'name': '弓兵',   'hp': 20, 'pow': 7,  'skl': 9,  'spd': 7,  'dfn': 4,  'mov': 5,
                 'weapon': 'bow',
                 'growth': {'hp': 65, 'pow': 40, 'skl': 60, 'spd': 50, 'dfn': 25}},
    'mage':     {'name': '魔道士', 'hp': 18, 'pow': 9,  'skl': 7,  'spd': 8,  'dfn': 3,  'mov': 5,
                 'weapon': 'magic',
                 'growth': {'hp': 55, 'pow': 55, 'skl': 50, 'spd': 50, 'dfn': 20}},
    'myrmidon': {'name': '剑士',   'hp': 20, 'pow': 8,  'skl': 11, 'spd': 11, 'dfn': 4,  'mov': 5,
                 'weapon': 'sword',
                 'growth': {'hp': 65, 'pow': 45, 'skl': 65, 'spd': 65, 'dfn': 20}},
    # 敌方职业（不升级，无成长率）
    'fighter':  {'name': '斧战士', 'hp': 20, 'pow': 7,  'skl': 5,  'spd': 5,  'dfn': 4,  'mov': 5,
                 'weapon': 'axe', 'growth': {}},
    'soldier':  {'name': '枪兵',   'hp': 20, 'pow': 7,  'skl': 6,  'spd': 6,  'dfn': 5,  'mov': 5,
                 'weapon': 'lance', 'growth': {}},
    'e_archer': {'name': '弓兵',   'hp': 18, 'pow': 6,  'skl': 7,  'spd': 6,  'dfn': 3,  'mov': 5,
                 'weapon': 'bow', 'growth': {}},
    'e_myrm':   {'name': '剑士',   'hp': 18, 'pow': 6,  'skl': 9,  'spd': 8,  'dfn': 3,  'mov': 5,
                 'weapon': 'sword', 'growth': {}},
    'warrior':  {'name': '勇士',   'hp': 28, 'pow': 9,  'skl': 8,  'spd': 7,  'dfn': 6,  'mov': 5,
                 'weapon': 'axe', 'growth': {}},
    'shaman':   {'name': '妖术师', 'hp': 22, 'pow': 7,  'skl': 7,  'spd': 6,  'dfn': 5,  'mov': 5,
                 'weapon': 'magic', 'growth': {}},
    'general':  {'name': '重甲将军', 'hp': 30, 'pow': 9,  'skl': 6, 'spd': 4,  'dfn': 9,  'mov': 4,
                 'weapon': 'lance', 'growth': {}},
}

# --- 战役队伍（基础 4 人，菲尔第 2 章加入） ---
PLAYER_ROSTER = [
    {'name': '罗伊',   'cls': 'lord'},
    {'name': '兰斯',   'cls': 'cavalier'},
    {'name': '丽贝卡', 'cls': 'archer'},
    {'name': '莉莉娜', 'cls': 'mage'},
]

# 第1章: 芬河双桥
MAP1 = [
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
# 第2章: 迷雾森林
MAP2 = [
    "FFFPPFFFPPPFFFF",
    "FPPPPPFFPPPPFFF",
    "PPFPPPPPPPFPPFF",
    "PPFFPPPFPPFFPPF",
    "PPPPPPFFPPPPTPP",
    "PFPPPFFPPPFPPPP",
    "FFPPPPPPPPFFPPP",
    "FPPFFPFFPPPPPFF",
    "PPPFFPPFFPPFPFF",
    "PFPPPPPPPPPFFFF",
]
# 第3章: 黑铁要塞（R城墙 S石板 G城门 T王座）
MAP3 = [
    "PPFPPPPPPRRRRRR",
    "PPPPPPPPPRSSSSR",
    "PFPPPPPPPRSSSSR",
    "PPPPPMPPPRSSTSR",
    "PPPPPPPPPGSSSSR",
    "PPPPPPPPPRSSSSR",
    "PPFPPPPPPRSSSSR",
    "PPPPPMPPPRRRRRR",
    "PPFPPPPMPPPFPPP",
    "PPPPPPPPPPPFFPP",
]

CHAPTERS = [
    {
        'title': '渡河遭遇',
        'story': ['罗伊小队护送军资途经芬河，',
                  '盗贼团「黑铁牙」突然自对岸袭来。',
                  '利用河上双桥的地利击退他们！'],
        'objective': '歼灭全部敌人',
        'win': 'rout',
        'map': MAP1,
        'players': [(2, 4), (1, 5), (1, 3), (2, 6)],
        'join': [],
        'enemies': [
            {'name': '斧兵甲', 'cls': 'fighter',  'pos': (10, 4)},
            {'name': '斧兵乙', 'cls': 'fighter',  'pos': (9, 2), 'ai': 'guard'},
            {'name': '斧兵丙', 'cls': 'fighter',  'pos': (10, 7)},
            {'name': '枪兵',   'cls': 'soldier',  'pos': (11, 5)},
            {'name': '弓兵',   'cls': 'e_archer', 'pos': (12, 3), 'ai': 'guard'},
            {'name': '盖尔',   'cls': 'warrior',  'pos': (13, 8), 'boss': True},
        ],
    },
    {
        'title': '林间伏击',
        'story': ['穿越迷雾森林时，妖术师莫尔甘设下伏击。',
                  '流浪剑士菲尔挺身相助，加入了队伍。',
                  '小心森林中埋伏的刀手！'],
        'objective': '歼灭全部敌人',
        'win': 'rout',
        'map': MAP2,
        'players': [(1, 4), (0, 5), (0, 3), (1, 6)],
        'join': [{'name': '菲尔', 'cls': 'myrmidon', 'pos': (2, 5)}],
        'enemies': [
            {'name': '刀手甲', 'cls': 'e_myrm',   'pos': (5, 2),  'ai': 'guard'},
            {'name': '刀手乙', 'cls': 'e_myrm',   'pos': (8, 7),  'ai': 'guard'},
            {'name': '斧兵甲', 'cls': 'fighter',  'pos': (6, 5)},
            {'name': '斧兵乙', 'cls': 'fighter',  'pos': (9, 8)},
            {'name': '弓兵',   'cls': 'e_archer', 'pos': (10, 2), 'ai': 'guard'},
            {'name': '莫尔甘', 'cls': 'shaman',   'pos': (12, 4), 'boss': True},
        ],
    },
    {
        'title': '黑铁要塞',
        'story': ['终于抵达黑铁牙的老巢——黑铁要塞。',
                  '城门狭窄，城内守军以逸待劳。',
                  '击破首领巴尔克将军，终结这一切！'],
        'objective': '击破敌将巴尔克',
        'win': 'boss',
        'map': MAP3,
        'players': [(0, 3), (1, 4), (0, 5), (1, 2), (1, 6)],
        'join': [],
        'enemies': [
            {'name': '游兵甲', 'cls': 'fighter',  'pos': (5, 2)},
            {'name': '游兵乙', 'cls': 'e_myrm',   'pos': (6, 6)},
            {'name': '游兵丙', 'cls': 'soldier',  'pos': (4, 8)},
            {'name': '门卫',   'cls': 'soldier',  'pos': (10, 1), 'ai': 'guard'},
            {'name': '城弓手', 'cls': 'e_archer', 'pos': (11, 2), 'ai': 'guard'},
            {'name': '侍卫',   'cls': 'soldier',  'pos': (10, 5), 'ai': 'guard'},
            {'name': '妖术师', 'cls': 'shaman',   'pos': (11, 5), 'ai': 'guard'},
            {'name': '巴尔克', 'cls': 'general',  'pos': (12, 3), 'boss': True},
        ],
    },
]

# 兼容别名（测试用 Grid 默认地图）
MAP = MAP1

# --- 规则参数 ---
EXP_HIT, EXP_KILL, EXP_BOSS_KILL = 10, 40, 80   # 命中/击杀/击杀Boss 经验
EXP_LEVEL = 100
DOUBLE_SPD_GAP = 4    # 速度差≥4 追击
CRIT_MULT = 3         # 必杀三倍
POTION_HEAL = 12      # 伤药回复量
POTION_USES = 3       # 每章伤药数量

STAT_NAMES = {'hp': 'HP', 'pow': '力量', 'skl': '技巧', 'spd': '速度', 'dfn': '防御'}
