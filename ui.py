"""UI 组件：全部为 draw_xxx(surface, ...) 纯绘制函数。

pygame 默认字体不含中文，font() 按候选列表查找系统中文字体。
"""
import math

import pygame

from settings import CELL, GRID_H, GRID_W, INFO_H, SCREEN_W, STAT_NAMES, TERRAIN, WEAPONS

# 颜色
COL_PANEL = (28, 30, 44)
COL_PANEL_LIGHT = (44, 48, 70)
COL_BORDER = (120, 126, 160)
COL_TEXT = (235, 235, 235)
COL_DIM = (150, 150, 160)
COL_PLAYER = (90, 140, 255)
COL_ENEMY = (235, 80, 80)
COL_GOLD = (250, 210, 90)
MOVE_TILE = (80, 120, 255, 110)
ATTACK_TILE = (255, 80, 80, 110)
TARGET_TILE = (255, 60, 60, 160)

_FONT_CANDIDATES = ['PingFang SC', 'Hiragino Sans GB', 'Heiti SC', 'STHeiti',
                    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
                    'WenQuanYi Micro Hei', 'Arial Unicode MS']
_font_cache = {}
_font_path = None
_font_searched = False


def font(size):
    global _font_path, _font_searched
    if not _font_searched:
        for name in _FONT_CANDIDATES:
            _font_path = pygame.font.match_font(name)
            if _font_path:
                break
        _font_searched = True
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(_font_path, size)
    return _font_cache[size]


def _text(surf, s, size, pos, color=COL_TEXT, center=False):
    t = font(size).render(s, True, color)
    surf.blit(t, t.get_rect(center=pos) if center else pos)
    return t.get_size()


def cell_px(x, y):
    """格子坐标 -> 屏幕像素（左上角）"""
    return x * CELL, y * CELL


# --- 范围高亮 / 光标 ---

def draw_tiles(surf, tiles, color):
    tile = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    tile.fill(color)
    for (x, y) in tiles:
        surf.blit(tile, cell_px(x, y))


def draw_cursor(surf, pos, color=(255, 255, 255)):
    px, py = cell_px(*pos)
    pygame.draw.rect(surf, color, (px + 1, py + 1, CELL - 2, CELL - 2), 3, border_radius=4)


# --- 单位标记 ---

def draw_team_ring(surf, unit, px, py):
    """脚下椭圆色环标识阵营"""
    color = COL_PLAYER if unit.team == 'player' else COL_ENEMY
    rect = pygame.Rect(px + 8, py + CELL - 14, CELL - 16, 10)
    pygame.draw.ellipse(surf, color, rect, 2)


def draw_hp_bar(surf, unit, px, py):
    w = CELL - 8
    ratio = unit.hp / unit.max_hp
    color = (80, 200, 80) if ratio > 0.5 else (230, 200, 60) if ratio > 0.25 else (230, 70, 70)
    pygame.draw.rect(surf, (20, 20, 28), (px + 4, py + CELL - 6, w, 5))
    if ratio > 0:
        pygame.draw.rect(surf, color, (px + 4, py + CELL - 6, max(2, int(w * ratio)), 5))


def draw_boss_mark(surf, px, py):
    _text(surf, '★', 14, (px + CELL - 16, py + 2), COL_GOLD)


# --- 信息栏（底部） ---

def draw_info(surf, unit, terrain_ch):
    y0 = GRID_H * CELL
    pygame.draw.rect(surf, COL_PANEL, (0, y0, SCREEN_W, INFO_H))
    pygame.draw.line(surf, COL_BORDER, (0, y0), (SCREEN_W, y0), 2)
    if unit is not None:
        color = COL_PLAYER if unit.team == 'player' else COL_ENEMY
        _text(surf, unit.name, 22, (16, y0 + 10), color)
        _text(surf, f'{unit.cls_name}  Lv{unit.level}  EXP {unit.exp}', 15, (16, y0 + 42), COL_DIM)
        _text(surf, f'HP {unit.hp}/{unit.max_hp}', 17, (16, y0 + 66))
        stats = f'力量{unit.pow} 技巧{unit.skl} 速度{unit.spd} 防御{unit.dfn} 移动{unit.mov}'
        _text(surf, stats, 16, (190, y0 + 66))
        w = WEAPONS[unit.weapon]
        lo, hi = w['range']
        rng = f'{lo}' if lo == hi else f'{lo}-{hi}'
        _text(surf, f'{w["name"]}  威力{w["might"]} 命中{w["hit"]} 射程{rng}', 16, (190, y0 + 40))
    if terrain_ch is not None:
        t = TERRAIN[terrain_ch]
        cost = '不可通行' if t['cost'] is None else f'移动消耗 {t["cost"]}'
        _text(surf, t['name'], 20, (SCREEN_W - 170, y0 + 12), COL_GOLD)
        _text(surf, f'回避 +{t["avoid"]}', 15, (SCREEN_W - 170, y0 + 42), COL_DIM)
        _text(surf, cost, 15, (SCREEN_W - 170, y0 + 64), COL_DIM)
        if t['heal']:
            _text(surf, f'每回合恢复 {int(t["heal"] * 100)}% HP', 14, (SCREEN_W - 170, y0 + 84), (120, 220, 120))


def draw_help(surf):
    y0 = GRID_H * CELL
    _text(surf, '左键 选择/确认   右键 取消   E 结束回合', 13, (SCREEN_W - 460, y0 + 84), (110, 110, 125))


# --- 行动菜单 ---

def draw_menu(surf, items, sel, px, py):
    """items: [(label, enabled)]。返回各项 rect 列表（屏幕坐标）供点击判定。"""
    w, line_h = 96, 30
    h = len(items) * line_h + 8
    px = min(px, SCREEN_W - w - 4)
    py = min(py, GRID_H * CELL - h - 4)
    panel = pygame.Rect(px, py, w, h)
    pygame.draw.rect(surf, COL_PANEL, panel, border_radius=6)
    pygame.draw.rect(surf, COL_BORDER, panel, 2, border_radius=6)
    rects = []
    for i, (label, enabled) in enumerate(items):
        r = pygame.Rect(px + 4, py + 4 + i * line_h, w - 8, line_h)
        if i == sel and enabled:
            pygame.draw.rect(surf, COL_PANEL_LIGHT, r, border_radius=4)
        color = COL_TEXT if enabled else (90, 90, 100)
        _text(surf, label, 18, (r.x + 12, r.y + 5), color)
        rects.append(r)
    return rects


# --- 战斗预测 ---

def _forecast_col(surf, x, y, title, color, unit, side):
    _text(surf, title, 18, (x, y), color)
    _text(surf, f'HP {unit.hp}/{unit.max_hp}', 16, (x, y + 30))
    if side is None:
        _text(surf, '无法反击', 16, (x, y + 56), COL_DIM)
        for dy, label in ((82, '命中  --'), (108, '必杀  --')):
            _text(surf, label, 16, (x, y + dy), COL_DIM)
        return
    dmg = f'伤害  {side["dmg"]}' + (f' ×{side["count"]}' if side['count'] > 1 else '')
    _text(surf, dmg, 16, (x, y + 56), COL_GOLD if side['count'] > 1 else COL_TEXT)
    _text(surf, f'命中  {side["hit"]}', 16, (x, y + 82))
    _text(surf, f'必杀  {side["crit"]}', 16, (x, y + 108))


def draw_forecast(surf, fc, att, dfd):
    w, h = 380, 190
    x = (SCREEN_W - w) // 2
    y = (GRID_H * CELL - h) // 2
    panel = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, COL_PANEL, panel, border_radius=8)
    pygame.draw.rect(surf, COL_BORDER, panel, 2, border_radius=8)
    _text(surf, '战斗预测', 17, (x + w // 2, y + 16), COL_GOLD, center=True)
    a_color = COL_PLAYER if att.team == 'player' else COL_ENEMY
    d_color = COL_PLAYER if dfd.team == 'player' else COL_ENEMY
    _forecast_col(surf, x + 36, y + 36, att.name, a_color, att, fc['att'])
    _forecast_col(surf, x + w // 2 + 36, y + 36, dfd.name, d_color, dfd, fc['def'])
    pygame.draw.line(surf, COL_BORDER, (x + w // 2, y + 36), (x + w // 2, y + h - 36), 1)
    _text(surf, '左键/回车 确认    右键/ESC 取消', 13, (x + w // 2, y + h - 16), COL_DIM, center=True)


# --- 升级弹窗 ---

def draw_levelup(surf, unit, gains, t):
    """t: 0~1 动画进度，逐项揭示 5 项属性成长。"""
    w, h = 300, 230
    x = (SCREEN_W - w) // 2
    y = (GRID_H * CELL - h) // 2
    panel = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, COL_PANEL, panel, border_radius=8)
    pygame.draw.rect(surf, COL_GOLD, panel, 2, border_radius=8)
    _text(surf, f'{unit.name}  升级！ Lv{unit.level}', 20, (x + w // 2, y + 22), COL_GOLD, center=True)
    shown = int(t * (len(gains) + 1))
    for i, (stat, up) in enumerate(gains.items()):
        if i >= shown:
            break
        name = STAT_NAMES[stat]
        val = {'hp': unit.max_hp, 'pow': unit.pow, 'skl': unit.skl,
               'spd': unit.spd, 'dfn': unit.dfn}[stat]
        line_y = y + 52 + i * 30
        _text(surf, name, 17, (x + 60, line_y))
        _text(surf, str(val), 17, (x + 160, line_y))
        if up:
            _text(surf, '+1', 17, (x + 210, line_y), (120, 230, 120))
    _text(surf, '点击继续', 13, (x + w // 2, y + h - 16), COL_DIM, center=True)


# --- 回合横幅 / 结局 ---

def draw_banner(surf, text, t, color):
    """t: 0~1；中段停留，两端淡入淡出"""
    alpha = min(1.0, min(t, 1 - t) * 4) if 0 <= t <= 1 else 0
    h = 64
    y = (GRID_H * CELL - h) // 2
    band = pygame.Surface((SCREEN_W, h), pygame.SRCALPHA)
    band.fill((10, 12, 20, int(210 * alpha)))
    surf.blit(band, (0, y))
    t_surf = font(32).render(text, True, color)
    t_surf.set_alpha(int(255 * alpha))
    surf.blit(t_surf, t_surf.get_rect(center=(SCREEN_W // 2, y + h // 2)))


def draw_end(surf, win):
    veil = pygame.Surface((SCREEN_W, GRID_H * CELL), pygame.SRCALPHA)
    veil.fill((10, 10, 16, 170))
    surf.blit(veil, (0, 0))
    text = '胜 利 ！' if win else '败 北 …'
    color = COL_GOLD if win else (180, 180, 190)
    _text(surf, text, 52, (SCREEN_W // 2, GRID_H * CELL // 2 - 20), color, center=True)
    _text(surf, '按 R 重新开始', 18, (SCREEN_W // 2, GRID_H * CELL // 2 + 40), COL_DIM, center=True)


# --- 浮动文字（伤害/回血/MISS） ---

def draw_float_text(surf, text, px, py, t, color):
    """t: 0~1，上飘渐隐。px/py 为格子左上角像素。"""
    size = 26 if text == '必杀!' else 20
    t_surf = font(size).render(text, True, color)
    t_surf.set_alpha(int(255 * (1 - t * t)))
    rise = int(28 * t)
    surf.blit(t_surf, t_surf.get_rect(center=(px + CELL // 2, py - 4 - rise)))
