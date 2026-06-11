"""DawnLike 素材加载与精灵映射。

对外接口：
  load()                    启动时调用，定位素材目录（缺失时中文报错退出）
  unit_sprite(cls, frame)   职业 -> 48x48 人物表面（两帧 idle 动画）
  terrain_sprite(ch, frame) 地形字符 -> 48x48 地形表面
任何图块缺失都回退为纯色块渲染，保证不崩溃。
"""
from pathlib import Path

import pygame

from settings import TILE, CELL

ROOT = Path(__file__).resolve().parent
_asset_dir = None
_sheets = {}      # 相对路径 -> Surface（原始尺寸）
_unit_cache = {}
_terrain_cache = {}

# 职业 -> (Characters 图集基名, 列, 行)；基名后缀 0/1 为两帧动画
UNIT_SPRITES = {
    'lord':     ('Player', 4, 0),      # 金发挥剑战士
    'cavalier': ('Humanoid', 3, 13),   # 灰马铠甲骑士
    'archer':   ('Player', 2, 3),      # 绿衣持弓猎手
    'mage':     ('Player', 3, 4),      # 尖帽持杖法师
    'fighter':  ('Player', 0, 12),     # 绿皮兽人
    'soldier':  ('Player', 2, 12),     # 蓝甲兽人
    'e_archer': ('Humanoid', 4, 8),    # 持弓猎人
    'warrior':  ('Player', 6, 12),     # 红纹萨满兽人(Boss)
    'myrmidon': ('Humanoid', 0, 4),    # 银盔绿衣剑士(菲尔)
    'e_myrm':   ('Player', 2, 4),      # 黑衣刀手
    'shaman':   ('Player', 7, 3),      # 红袍妖术师
    'general':  ('Player', 5, 3),      # 黑甲将军
}

# 地形底层图块 (sheet, col, row)；{f} 会替换为动画帧号(0/1)
TERRAIN_BASE = {
    'P': ('Objects/Floor.png', 8, 7),     # 草地
    'F': ('Objects/Floor.png', 8, 7),
    'M': ('Objects/Floor.png', 8, 7),
    'T': ('Objects/Floor.png', 8, 7),
    'W': ('Objects/Pit{f}.png', 1, 15),   # 蓝色波纹水面（两帧动画）
    'B': ('Objects/Pit{f}.png', 1, 15),   # 桥下也是水
    'S': ('Objects/Floor.png', 1, 7),     # 灰砖石板
    'R': ('Objects/Wall.png', 1, 6),      # 灰砖城墙
    'G': ('Objects/Floor.png', 1, 7),     # 城门下是石板
}
# 地形叠加装饰；'B' 按 variant 区分左右桥头
TERRAIN_OVERLAY = {
    'F': ('Objects/Tree0.png', 3, 3),     # 绿树
    'M': ('Objects/Hill0.png', 1, 7),     # 雪顶山峰
    'T': ('Objects/Map0.png', 8, 13),     # 白色城堡
    'B0': ('Objects/Floor.png', 11, 19),  # 木桥左端
    'B1': ('Objects/Floor.png', 13, 19),  # 木桥右端
    'G': ('Objects/Door0.png', 0, 1),     # 灰色双门
}

FALLBACK_COLORS = {
    'P': (96, 160, 80), 'F': (40, 110, 60), 'M': (130, 120, 110),
    'W': (70, 120, 200), 'B': (160, 120, 70), 'T': (150, 140, 160),
    'S': (130, 130, 140), 'R': (90, 90, 100), 'G': (110, 95, 80),
}


# 原创像素立绘（tools/gen_portraits.py 生成），按角色名索引
PORTRAIT_FILES = {'罗伊': 'roy', '兰斯': 'lance', '丽贝卡': 'rebecca',
                  '莉莉娜': 'lilina', '菲尔': 'fir', '盖尔': 'gale',
                  '莫尔甘': 'morgan', '巴尔克': 'balk'}
_portraits = {}


def load():
    """定位素材目录并载入立绘。必须在 pygame.display 初始化后调用。"""
    global _asset_dir
    hits = list((ROOT / 'assets').rglob('Objects/Floor.png'))
    if not hits:
        raise SystemExit('素材未就绪，请先运行: python3 tools/fetch_assets.py')
    _asset_dir = hits[0].parent.parent
    for name, fname in PORTRAIT_FILES.items():
        path = ROOT / 'assets' / 'portraits' / f'{fname}.png'
        try:
            _portraits[name] = pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            pass                       # 缺图时调用方回退到地图精灵


def portrait(name):
    """角色立绘（48x48）。无此角色立绘返回 None。"""
    return _portraits.get(name)


def _sheet(rel):
    if rel not in _sheets:
        try:
            _sheets[rel] = pygame.image.load(str(_asset_dir / rel)).convert_alpha()
        except (pygame.error, FileNotFoundError, TypeError):
            _sheets[rel] = None
    return _sheets[rel]


def _cut(rel, col, row):
    """从图集切 16x16 放大到 48x48；失败返回 None。"""
    sheet = _sheet(rel)
    if sheet is None:
        return None
    x, y = col * TILE, row * TILE
    if x + TILE > sheet.get_width() or y + TILE > sheet.get_height():
        return None
    part = sheet.subsurface((x, y, TILE, TILE))
    return pygame.transform.scale(part, (CELL, CELL))


def unit_sprite(cls, frame=0):
    """职业精灵（frame 0/1 两帧）。无映射/缺图时回退为色块+职业首字。"""
    key = (cls, frame)
    if key in _unit_cache:
        return _unit_cache[key]
    surf = None
    if cls in UNIT_SPRITES:
        base, col, row = UNIT_SPRITES[cls]
        surf = _cut(f'Characters/{base}{frame % 2}.png', col, row)
    if surf is None:
        from settings import CLASSES
        surf = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        pygame.draw.rect(surf, (90, 90, 120), (6, 6, CELL - 12, CELL - 12), border_radius=8)
        font = pygame.font.Font(None, 24)
        ch = CLASSES.get(cls, {}).get('name', '?')[0]
        t = font.render(ch, True, (255, 255, 255))
        surf.blit(t, t.get_rect(center=(CELL // 2, CELL // 2)))
    _unit_cache[key] = surf
    return surf


def terrain_sprite(ch, frame=0, variant=0):
    """地形表面（底层+装饰已合成）。缺图回退纯色块。
    frame: 水面动画帧(0/1)；variant: 桥的左(0)/右(1)端。"""
    key = (ch, frame % 2, variant)
    if key in _terrain_cache:
        return _terrain_cache[key]
    surf = pygame.Surface((CELL, CELL))
    surf.fill(FALLBACK_COLORS.get(ch, (60, 60, 60)))
    if ch in TERRAIN_BASE:
        rel, col, row = TERRAIN_BASE[ch]
        base = _cut(rel.format(f=frame % 2), col, row)
        if base is not None:
            surf.blit(base, (0, 0))
    over_key = f'B{variant}' if ch == 'B' else ch
    if over_key in TERRAIN_OVERLAY:
        rel, col, row = TERRAIN_OVERLAY[over_key]
        over = _cut(rel.format(f=frame % 2), col, row)
        if over is not None:
            surf.blit(over, (0, 0))
    _terrain_cache[key] = surf
    return surf


def _preview():
    """python3 assets.py — 渲染全部精灵/地形到 /tmp/fe_assets_preview.png 供核对。"""
    import settings
    pygame.init()
    pygame.display.set_mode((1, 1))
    load()
    classes = list(UNIT_SPRITES)
    terrains = list(TERRAIN_BASE)
    w = max(len(classes), len(terrains)) * (CELL + 44)
    surf = pygame.Surface((w, 2 * (CELL + 40) + 20))
    surf.fill((40, 40, 50))
    font = pygame.font.Font(None, 18)
    for i, cls in enumerate(classes):
        x = i * (CELL + 44) + 10
        surf.blit(unit_sprite(cls), (x, 10))
        surf.blit(font.render(cls, True, (255, 255, 0)), (x, 10 + CELL + 4))
    for i, ch in enumerate(terrains):
        x = i * (CELL + 44) + 10
        y = CELL + 50
        surf.blit(terrain_sprite(ch), (x, y))
        name = settings.TERRAIN[ch]['name']
        surf.blit(font.render(ch, True, (255, 255, 0)), (x, y + CELL + 4))
    out = '/tmp/fe_assets_preview.png'
    pygame.image.save(surf, out)
    print('预览已保存:', out)


if __name__ == '__main__':
    _preview()
