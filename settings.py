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
    'staff': {'name': '杖',   'might': 0, 'hit': 0,  'crit': 0, 'range': (1, 1), 'heal': True},
    'breath': {'name': '吐息', 'might': 12, 'hit': 90, 'crit': 0, 'range': (1, 2)},
    'light': {'name': '光魔', 'might': 7, 'hit': 90, 'crit': 8, 'range': (1, 2)},  # 主教用
}
STAFF_BASE_HEAL = 10   # 治疗量 = 基础 + 力量
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
    'cleric':   {'name': '修女',   'hp': 18, 'pow': 5,  'skl': 7,  'spd': 8,  'dfn': 3,  'mov': 5,
                 'weapon': 'staff', 'heal': True,
                 'growth': {'hp': 55, 'pow': 40, 'skl': 50, 'spd': 55, 'dfn': 25}},
    'pegasus':  {'name': '天马骑士', 'hp': 20, 'pow': 7, 'skl': 8,  'spd': 11, 'dfn': 5,  'mov': 7,
                 'weapon': 'lance', 'fly': True,
                 'growth': {'hp': 60, 'pow': 45, 'skl': 55, 'spd': 60, 'dfn': 30}},
    'knight':   {'name': '重甲兵', 'hp': 26, 'pow': 9,  'skl': 6,  'spd': 4,  'dfn': 11, 'mov': 4,
                 'weapon': 'lance',
                 'growth': {'hp': 80, 'pow': 50, 'skl': 35, 'spd': 25, 'dfn': 55}},
    # --- 高级职（转职目标；属性由 promote() 按 PROMOTIONS 增益叠加，下列 base 仅供参考）---
    'great_lord': {'name': '大将', 'hp': 30, 'pow': 10, 'skl': 11, 'spd': 12, 'dfn': 11, 'mov': 6,
                   'weapon': 'sword', 'tier': 2, 'skill': {'name': '鼓舞', 'aura': True},
                   'growth': {'hp': 75, 'pow': 50, 'skl': 55, 'spd': 60, 'dfn': 40}},
    'paladin':  {'name': '圣骑士', 'hp': 30, 'pow': 11, 'skl': 8,  'spd': 9,  'dfn': 11, 'mov': 8,
                 'weapon': 'lance', 'mounted': True, 'tier': 2,
                 'skill': {'name': '坚韧', 'hit': 12, 'dfn': 1},
                 'growth': {'hp': 85, 'pow': 55, 'skl': 45, 'spd': 50, 'dfn': 45}},
    'sniper':   {'name': '神射手', 'hp': 26, 'pow': 11, 'skl': 14, 'spd': 11, 'dfn': 6,  'mov': 6,
                 'weapon': 'bow', 'tier': 2, 'skill': {'name': '狙击', 'crit': 15},
                 'growth': {'hp': 70, 'pow': 45, 'skl': 65, 'spd': 55, 'dfn': 30}},
    'sage':     {'name': '贤者', 'hp': 24, 'pow': 13, 'skl': 11, 'spd': 11, 'dfn': 6,  'mov': 6,
                 'weapon': 'magic', 'heal': True, 'tier': 2,
                 'skill': {'name': '魔导', 'pow': 2},
                 'growth': {'hp': 60, 'pow': 60, 'skl': 55, 'spd': 55, 'dfn': 25}},
    'swordmaster': {'name': '剑圣', 'hp': 26, 'pow': 11, 'skl': 16, 'spd': 16, 'dfn': 7, 'mov': 6,
                    'weapon': 'sword', 'tier': 2, 'skill': {'name': '必杀', 'crit': 20},
                    'growth': {'hp': 70, 'pow': 50, 'skl': 70, 'spd': 70, 'dfn': 25}},
    'bishop':   {'name': '主教', 'hp': 24, 'pow': 11, 'skl': 10, 'spd': 11, 'dfn': 6,  'mov': 6,
                 'weapon': 'light', 'heal': True, 'tier': 2,
                 'skill': {'name': '祈祷', 'heal_bonus': 5},
                 'growth': {'hp': 60, 'pow': 50, 'skl': 55, 'spd': 55, 'dfn': 30}},
    'falcon':   {'name': '天马将军', 'hp': 28, 'pow': 11, 'skl': 12, 'spd': 15, 'dfn': 9, 'mov': 8,
                 'weapon': 'lance', 'fly': True, 'tier': 2,
                 'skill': {'name': '疾风', 'avoid': 15},
                 'growth': {'hp': 65, 'pow': 50, 'skl': 60, 'spd': 65, 'dfn': 35}},
    'marshal':  {'name': '将军', 'hp': 34, 'pow': 13, 'skl': 8,  'spd': 5,  'dfn': 16, 'mov': 5,
                 'weapon': 'lance', 'tier': 2, 'skill': {'name': '大盾', 'shield': 0.5},
                 'growth': {'hp': 85, 'pow': 55, 'skl': 40, 'spd': 30, 'dfn': 60}},
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
    'e_knight': {'name': '帝国重甲', 'hp': 24, 'pow': 8, 'skl': 5, 'spd': 4,  'dfn': 10, 'mov': 4,
                 'weapon': 'lance', 'growth': {}},
    'wyvern':   {'name': '龙骑士', 'hp': 24, 'pow': 9,  'skl': 7,  'spd': 8,  'dfn': 8,  'mov': 7,
                 'weapon': 'lance', 'fly': True, 'growth': {}},
    'assassin': {'name': '刺客',   'hp': 20, 'pow': 7,  'skl': 12, 'spd': 12, 'dfn': 4,  'mov': 6,
                 'weapon': 'sword', 'growth': {}},
    'dark_mage': {'name': '暗魔道士', 'hp': 20, 'pow': 8, 'skl': 7, 'spd': 7, 'dfn': 4,  'mov': 5,
                  'weapon': 'magic', 'growth': {}},
    'pirate':   {'name': '海盗',   'hp': 22, 'pow': 8,  'skl': 5,  'spd': 6,  'dfn': 4,  'mov': 5,
                 'weapon': 'axe', 'growth': {}},
    'dragon':   {'name': '邪龙',   'hp': 52, 'pow': 13, 'skl': 9,  'spd': 5,  'dfn': 12, 'mov': 4,
                 'weapon': 'breath', 'growth': {}},
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

# 第4章: 风雪驿道
MAP4 = [
    "MMFFPPPFFFPPFMM",
    "MFPPPPPPPPPPFFM",
    "FPPFPPPPPFPPPFF",
    "PPPPPPFFPPPPPPP",
    "PPPPPPPPPPTPPPP",
    "PPFPPPPPPPPPFPP",
    "FPPPPFFPPPPPPFF",
    "FFPPPPPPPFPPPFF",
    "MFFPPPPPPPPFFFM",
    "MMFFPPPFFPPFMMM",
]
# 第5章: 河港（南侧大水域，东侧城门 G 为占领点）
MAP5 = [
    "PPFFPPPPPFFPPPP",
    "PPPPPPFPPPPPFPP",
    "FPPPPPPPPPPPPPF",
    "PPPFPPSSSSSPPPP",
    "PPPPPPSWWSSPFPP",
    "FPPSSSSWWSSSSPP",
    "PPPSWWWWWWWWSGP",
    "PPSSWWWWWWWWSSP",
    "PSSWWWWWWWWWWSS",
    "SSWWWWWWWWWWWWS",
]
# 第6章: 风暴山道（西侧要塞群驻防，东侧增援涌入）
MAP6 = [
    "MMMMFFPPFFMMMMM",
    "MMFFPPPPPFFMMMM",
    "MTPPPPFPPPPFFMM",
    "PPPPFPPPPFPPPMM",
    "PTPPPPPFPPPPPPP",
    "PPPPFPPPPPFPPPP",
    "PTPPPPPFPPPPFMM",
    "PPPPFPPPPPPFFMM",
    "MMFFPPPFFPPFMMM",
    "MMMMFPPPFFMMMMM",
]
# 第7章: 王都内城（中央王座密室，南侧开口）
MAP7 = [
    "SSSSSSSSSSSSSSS",
    "SRRSSPPPPSSRRSS",
    "SRSSPPFPPSSSRSS",
    "SSSPPPPPPPSSSSS",
    "SPPPPRRRPPPPPSS",
    "SPPPPRTRPPPPPSS",
    "SSSPPRPRPPPSSSS",
    "SRSSPPPPPSSSRSS",
    "SRRSSPPPPSSRRSS",
    "SSSSSSSSSSSSSSS",
]
# 第8章: 溃堤之战（双桥大河，背后有海盗伏兵）
MAP8 = [
    "PPFPPPWWPPPFPMM",
    "PPPPPPWWPPPPPMM",
    "FPPPPPBBPPFPPPM",
    "PPPFPPWWPPPPPPP",
    "PPPPPPWWPFFPPPP",
    "PPFPPPWWPPPPTPP",
    "PPPPPPWWPPFPPPP",
    "PFPPPPBBPPPPPPP",
    "PPPPPPWWPPPFPPM",
    "PPFPPPWWPPPPPMM",
]
# 第9章: 灰烬祭坛（柱廊大殿，北端祭坛）
MAP9 = [
    "RRRRRRSTSRRRRRR",
    "RSSSSSSSSSSSSSR",
    "RSRSRSSSSSRSRSR",
    "RSSSSSSSSSSSSSR",
    "RSRSSSRRSSSRSSR",
    "RSSSSSSSSSSSSSR",
    "RSRSRSSSSSRSRSR",
    "RSSSSSSSSSSSSSR",
    "RSSSSSSSSSSSSSR",
    "RRRRRSSSSSRRRRR",
]
# 第10章: 龙巢（火山环谷，东侧龙座）
MAP10 = [
    "MMMMMFPPPFMMMMM",
    "MMFFPPPPPPPFFMM",
    "MFPPPPFPPFPPPFM",
    "MPPTPPPPPPPTPPM",
    "FPPPPPPPPPPTPPF",
    "PPFPPPFPPPPPPPM",
    "MPPPPPPPPFPPPMM",
    "MFPPTPPPPPPTPFM",
    "MMFPPPPFPPPPFMM",
    "MMMMFFPPPFFMMMM",
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
            {'name': '斧兵丙', 'cls': 'fighter',  'pos': (10, 7), 'ai': 'guard'},
            {'name': '枪兵',   'cls': 'soldier',  'pos': (11, 5)},
            {'name': '弓兵',   'cls': 'e_archer', 'pos': (12, 3), 'ai': 'guard'},
            {'name': '盖尔',   'cls': 'warrior',  'pos': (13, 8), 'boss': True},
        ],
    },
    {
        'title': '林间伏击',
        'ambient': {'weather': 'leaves'},
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
    {
        'title': '风雪驿道',
        'ambient': {'weather': 'snow', 'tint': (150, 180, 255, 26)},
        'story': ['带着密函北上王都的途中，驿道飘起了细雪。',
                  '帝国残党的巡逻队封锁了道路——',
                  '修女西娅正被他们围在驿站中。'],
        'objective': '歼灭全部敌人',
        'win': 'rout',
        'map': MAP4,
        'players': [(1, 4), (1, 3), (2, 3), (2, 5), (1, 5)],
        'join': [{'name': '西娅', 'cls': 'cleric', 'pos': (2, 4)}],
        'enemies': [
            {'name': '巡逻兵甲', 'cls': 'fighter',  'pos': (6, 2)},
            {'name': '巡逻兵乙', 'cls': 'soldier',  'pos': (8, 3)},
            {'name': '哨弓手',   'cls': 'e_archer', 'pos': (9, 5),  'ai': 'guard'},
            {'name': '巡逻兵丙', 'cls': 'fighter',  'pos': (7, 7)},
            {'name': '驿站卫兵', 'cls': 'soldier',  'pos': (11, 6), 'ai': 'guard'},
            {'name': '道森',     'cls': 'e_knight', 'pos': (10, 4), 'boss': True,
             'boost': {'hp': 8, 'pow': 1}},
        ],
        'reinforce': {3: [{'name': '追兵甲', 'cls': 'fighter', 'pos': (13, 1)},
                          {'name': '追兵乙', 'cls': 'fighter', 'pos': (13, 8)}]},
    },
    {
        'title': '夺取河港',
        'enemy_boost': {'hp': 2},
        'story': ['要过芬河下游，只能经由海盗盘踞的河港。',
                  '天马骑士艾莉丝从王都突围而来，带来噩耗：',
                  '王城已被渗透。「先夺下城门，向南突围！」'],
        'objective': '罗伊抵达港口城门',
        'win': 'seize',
        'goal': (13, 6),
        'map': MAP5,
        'players': [(1, 0), (0, 1), (1, 2), (2, 1), (1, 1), (2, 2)],
        'join': [{'name': '艾莉丝', 'cls': 'pegasus', 'pos': (0, 3)}],
        'enemies': [
            {'name': '海盗甲',   'cls': 'pirate',   'pos': (5, 2)},
            {'name': '海盗乙',   'cls': 'pirate',   'pos': (8, 1)},
            {'name': '码头弓手', 'cls': 'e_archer', 'pos': (7, 3),  'ai': 'guard'},
            {'name': '刀手',     'cls': 'e_myrm',   'pos': (11, 2)},
            {'name': '守门兵',   'cls': 'soldier',  'pos': (10, 4), 'ai': 'guard'},
            {'name': '海盗丙',   'cls': 'pirate',   'pos': (12, 5), 'ai': 'guard'},
            {'name': '加洛',     'cls': 'warrior',  'pos': (12, 7), 'boss': True,
             'boost': {'hp': 6, 'pow': 1}},
        ],
        'reinforce': {4: [{'name': '飞龙佣兵', 'cls': 'wyvern', 'pos': (14, 9)}],
                      6: [{'name': '飞龙佣兵', 'cls': 'wyvern', 'pos': (0, 9)}]},
    },
    {
        'title': '风暴山道',
        'ambient': {'weather': 'leaves', 'tint': (140, 150, 170, 22)},
        'enemy_boost': {'hp': 2, 'pow': 1},
        'story': ['通往王都的最后隘口，狂风夹着碎石呼啸。',
                  '佣兵龙骑士团受雇截杀——数量太多了。',
                  '「守住要塞群，撑过风暴！」'],
        'objective': '坚守 8 回合',
        'win': 'defend',
        'hold_turns': 8,
        'map': MAP6,
        'players': [(1, 2), (1, 4), (1, 6), (2, 3), (2, 5), (3, 4), (2, 4)],
        'join': [],
        'enemies': [
            {'name': '山贼斧兵', 'cls': 'fighter',  'pos': (9, 3)},
            {'name': '佣兵枪手', 'cls': 'soldier',  'pos': (10, 5)},
            {'name': '崖上弓手', 'cls': 'e_archer', 'pos': (10, 2), 'ai': 'guard'},
            {'name': '龙骑兵甲', 'cls': 'wyvern',   'pos': (12, 4)},
            {'name': '游刀手',   'cls': 'e_myrm',   'pos': (9, 7)},
            {'name': '薇拉',     'cls': 'wyvern',   'pos': (14, 4), 'boss': True,
             'boost': {'hp': 10, 'dfn': 2}},
        ],
        'reinforce': {3: [{'name': '增援斧兵', 'cls': 'fighter', 'pos': (14, 3)},
                          {'name': '龙骑兵乙', 'cls': 'wyvern',  'pos': (14, 5)}],
                      5: [{'name': '增援枪兵', 'cls': 'soldier', 'pos': (14, 3)},
                          {'name': '龙骑兵丙', 'cls': 'wyvern',  'pos': (14, 6)}],
                      7: [{'name': '增援斧兵', 'cls': 'fighter', 'pos': (14, 3)},
                          {'name': '增援弓手', 'cls': 'e_archer', 'pos': (14, 5)}]},
    },
    {
        'title': '王都疑云',
        'enemy_boost': {'hp': 4, 'pow': 1},
        'story': ['王都的街道安静得可怕——卫队已被假面刺客接管。',
                  '被革职的重甲兵加斯拦住一行人：',
                  '「王座厅是陷阱。要走，就从我的盾后走。」'],
        'objective': '击破敌将雷文',
        'win': 'boss',
        'map': MAP7,
        'players': [(6, 8), (5, 8), (7, 8), (8, 8), (6, 7), (5, 7), (7, 7)],
        'join': [{'name': '加斯', 'cls': 'knight', 'pos': (8, 7)}],
        'enemies': [
            {'name': '暗巷刺客', 'cls': 'assassin',  'pos': (2, 3)},
            {'name': '暗巷刺客', 'cls': 'assassin',  'pos': (12, 3)},
            {'name': '教团术士', 'cls': 'dark_mage', 'pos': (4, 2),  'ai': 'guard'},
            {'name': '教团术士', 'cls': 'dark_mage', 'pos': (10, 6), 'ai': 'guard'},
            {'name': '叛变卫兵', 'cls': 'e_knight',  'pos': (6, 3),  'ai': 'guard'},
            {'name': '王座卫兵', 'cls': 'e_knight',  'pos': (6, 6),  'ai': 'guard'},
            {'name': '巡街弓手', 'cls': 'e_archer',  'pos': (2, 6)},
            {'name': '雷文',     'cls': 'assassin',  'pos': (6, 5),  'boss': True,
             'boost': {'hp': 14, 'pow': 2, 'dfn': 3}},
        ],
        'reinforce': {4: [{'name': '影刺客', 'cls': 'assassin', 'pos': (0, 0)},
                          {'name': '影刺客', 'cls': 'assassin', 'pos': (14, 0)}]},
    },
    {
        'title': '溃堤之战',
        'enemy_boost': {'hp': 4, 'pow': 1, 'dfn': 1},
        'story': ['教团炸开了芬河大堤，要把追兵连同河谷一起埋葬。',
                  '叛将克鲁格率残军在对岸列阵。',
                  '「渡河，在洪水漫过平原之前结束这一切！」'],
        'objective': '歼灭全部敌人',
        'win': 'rout',
        'map': MAP8,
        'players': [(1, 3), (2, 4), (1, 5), (2, 6), (1, 4), (2, 3), (1, 6), (2, 5)],
        'join': [],
        'enemies': [
            {'name': '叛军重甲', 'cls': 'e_knight',  'pos': (9, 2),  'ai': 'guard'},
            {'name': '叛军枪兵', 'cls': 'soldier',   'pos': (10, 3)},
            {'name': '叛军斧兵', 'cls': 'fighter',   'pos': (9, 6)},
            {'name': '叛军弓手', 'cls': 'e_archer',  'pos': (10, 1), 'ai': 'guard'},
            {'name': '随军术士', 'cls': 'dark_mage', 'pos': (10, 7), 'ai': 'guard'},
            {'name': '飞龙斥候', 'cls': 'wyvern',    'pos': (12, 4)},
            {'name': '河盗',     'cls': 'pirate',    'pos': (4, 8)},
            {'name': '克鲁格',   'cls': 'general',   'pos': (12, 5), 'boss': True,
             'boost': {'hp': 8, 'dfn': 1}},
        ],
        'reinforce': {3: [{'name': '河盗伏兵', 'cls': 'pirate', 'pos': (0, 9)},
                          {'name': '河盗伏兵', 'cls': 'pirate', 'pos': (0, 0)}],
                      5: [{'name': '飞龙游骑', 'cls': 'wyvern',  'pos': (14, 0)},
                          {'name': '叛军增援', 'cls': 'soldier', 'pos': (14, 7)}]},
    },
    {
        'title': '灰烬祭坛',
        'ambient': {'weather': 'ash', 'tint': (120, 70, 160, 30)},
        'enemy_boost': {'hp': 6, 'pow': 2, 'dfn': 1},
        'story': ['祭坛深处烛火如林，大祭司沃尔甘立于高台。',
                  '「莫尔甘的死，不过是仪式的一部分。」',
                  '邪龙的封印已现裂痕——阻止他，就在此刻！'],
        'objective': '击破大祭司沃尔甘',
        'win': 'boss',
        'map': MAP9,
        'players': [(7, 8), (6, 8), (8, 8), (5, 8), (9, 8), (6, 9), (7, 9), (8, 9)],
        'join': [],
        'enemies': [
            {'name': '教团术士', 'cls': 'dark_mage', 'pos': (3, 2),  'ai': 'guard'},
            {'name': '教团术士', 'cls': 'dark_mage', 'pos': (11, 2), 'ai': 'guard'},
            {'name': '祭坛刺客', 'cls': 'assassin',  'pos': (5, 4)},
            {'name': '祭坛刺客', 'cls': 'assassin',  'pos': (9, 4)},
            {'name': '殿前重甲', 'cls': 'e_knight',  'pos': (6, 1),  'ai': 'guard'},
            {'name': '殿前重甲', 'cls': 'e_knight',  'pos': (8, 1),  'ai': 'guard'},
            {'name': '司仪妖术师', 'cls': 'shaman',  'pos': (7, 3),  'ai': 'guard'},
            {'name': '雷文',     'cls': 'assassin',  'pos': (7, 5),
             'boost': {'hp': 10, 'pow': 1}},
            {'name': '沃尔甘',   'cls': 'dark_mage', 'pos': (7, 0),  'boss': True,
             'boost': {'hp': 16, 'pow': 2, 'dfn': 4}},
        ],
        'reinforce': {3: [{'name': '暗影信徒', 'cls': 'dark_mage', 'pos': (5, 9)},
                          {'name': '暗影信徒', 'cls': 'dark_mage', 'pos': (9, 9)}],
                      5: [{'name': '影刺客', 'cls': 'assassin', 'pos': (1, 1)},
                          {'name': '影刺客', 'cls': 'assassin', 'pos': (13, 1)}]},
    },
    {
        'title': '屠龙·终章',
        'ambient': {'weather': 'embers', 'tint': (255, 110, 40, 26)},
        'enemy_boost': {'hp': 6, 'pow': 2, 'dfn': 2},
        'story': ['火山口的龙巢，空气灼热得扭曲。',
                  '千年邪龙法夫尼尔睁开了燃烧的双眼。',
                  '「为了芬河，为了所有人——上吧！」'],
        'objective': '讨伐邪龙法夫尼尔',
        'win': 'boss',
        'map': MAP10,
        'players': [(1, 3), (2, 4), (1, 5), (2, 3), (2, 5), (1, 4), (3, 4), (2, 6)],
        'join': [],
        'enemies': [
            {'name': '护龙术士', 'cls': 'dark_mage', 'pos': (5, 2),  'ai': 'guard'},
            {'name': '护龙术士', 'cls': 'dark_mage', 'pos': (9, 6),  'ai': 'guard'},
            {'name': '龙巢飞龙', 'cls': 'wyvern',    'pos': (8, 2)},
            {'name': '龙巢飞龙', 'cls': 'wyvern',    'pos': (8, 7)},
            {'name': '狂信刺客', 'cls': 'assassin',  'pos': (6, 5)},
            {'name': '龙前重甲', 'cls': 'e_knight',  'pos': (10, 3), 'ai': 'guard'},
            {'name': '献祭妖术师', 'cls': 'shaman',  'pos': (12, 3), 'ai': 'guard'},
            {'name': '龙前重甲', 'cls': 'e_knight',  'pos': (10, 5), 'ai': 'guard'},
            {'name': '法夫尼尔', 'cls': 'dragon',    'pos': (11, 4), 'boss': True,
             'boost': {'hp': 8, 'pow': 1, 'dfn': 1}},
        ],
        'reinforce': {4: [{'name': '盘旋飞龙', 'cls': 'wyvern', 'pos': (14, 0)},
                          {'name': '盘旋飞龙', 'cls': 'wyvern', 'pos': (14, 9)}],
                      6: [{'name': '暗影信徒', 'cls': 'dark_mage', 'pos': (5, 9)},
                          {'name': '狂信刺客', 'cls': 'assassin',  'pos': (9, 9)}]},
    },
]

# 兼容别名（测试用 Grid 默认地图）
MAP = MAP1

# --- 转职：基础职 -> (高级职, 属性增益) ---
PROMOTIONS = {
    'lord':     ('great_lord',  {'hp': 6, 'pow': 3, 'skl': 2, 'spd': 2, 'dfn': 4}),
    'cavalier': ('paladin',     {'hp': 6, 'pow': 3, 'skl': 1, 'spd': 1, 'dfn': 3}),
    'archer':   ('sniper',      {'hp': 5, 'pow': 3, 'skl': 4, 'spd': 2, 'dfn': 2}),
    'mage':     ('sage',        {'hp': 5, 'pow': 4, 'skl': 3, 'spd': 2, 'dfn': 3}),
    'myrmidon': ('swordmaster', {'hp': 5, 'pow': 3, 'skl': 4, 'spd': 4, 'dfn': 2}),
    'cleric':   ('bishop',      {'hp': 5, 'pow': 5, 'skl': 3, 'spd': 2, 'dfn': 3}),
    'pegasus':  ('falcon',      {'hp': 6, 'pow': 3, 'skl': 3, 'spd': 3, 'dfn': 3}),
    'knight':   ('marshal',     {'hp': 7, 'pow': 4, 'skl': 2, 'spd': 1, 'dfn': 5}),
}
PROMOTE_LEVEL = 10          # 达到此等级可转职
SEAL_NAME = '转职证'

# --- 规则参数 ---
EXP_HIT, EXP_KILL, EXP_BOSS_KILL = 10, 40, 80   # 命中/击杀/击杀Boss 经验
EXP_LEVEL = 100
DOUBLE_SPD_GAP = 4    # 速度差≥4 追击
CRIT_MULT = 3         # 必杀三倍
POTION_HEAL = 12      # 伤药回复量
POTION_USES = 3       # 每章伤药数量

STAT_NAMES = {'hp': 'HP', 'pow': '力量', 'skl': '技巧', 'spd': '速度', 'dfn': '防御'}
