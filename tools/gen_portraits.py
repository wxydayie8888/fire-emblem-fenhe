"""参数化像素立绘生成器：为八位角色绘制 48×48 原创胸像。

用法: SDL_VIDEODRIVER=dummy .venv/bin/python tools/gen_portraits.py
输出: assets/portraits/<拼音>.png + /tmp/fe_portraits_preview.png（4x 预览）

统一脸部几何保证风格一致；发型/护甲/表情/特征参数塑造个体辨识度。
"""
import os
import sys
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame

W = H = 48
OUT = ROOT / 'assets' / 'portraits'

# 通用色
OUTLINE = (44, 32, 38)
SKIN = (236, 188, 148)
SKIN_SH = (203, 148, 110)
SKIN_HL = (250, 214, 178)
WHITE = (240, 240, 235)


def srf():
    return pygame.Surface((W, H), pygame.SRCALPHA)


def ell(s, color, rect):
    pygame.draw.ellipse(s, color, rect)


def rect(s, color, r):
    pygame.draw.rect(s, color, r)


def poly(s, color, pts):
    pygame.draw.polygon(s, color, pts)


def px(s, color, x, y):
    if 0 <= x < W and 0 <= y < H:
        s.set_at((x, y), color)


def hline(s, color, x0, x1, y):
    for x in range(x0, x1 + 1):
        px(s, color, x, y)


# ---------- 基础部件 ----------

def draw_head(s, skin=SKIN, skin_sh=SKIN_SH, jaw='normal'):
    """脸 + 脖子 + 耳朵。jaw: normal/wide(壮汉)/slim(少女)"""
    if jaw == 'wide':
        ell(s, skin, (14, 6, 20, 14))               # 圆顶光头
        rect(s, skin, (14, 13, 20, 14))
        poly(s, skin, [(14, 27), (33, 27), (31, 31), (24, 33), (17, 31)])
        ell(s, skin_sh, (15, 7, 6, 4))              # 头顶反光过渡
        ell(s, skin, (16, 7, 5, 3))
    elif jaw == 'slim':
        ell(s, skin, (15, 9, 18, 18))
        poly(s, skin, [(16, 22), (32, 22), (29, 28), (24, 31), (19, 28)])
    else:
        ell(s, skin, (15, 9, 18, 19))
        poly(s, skin, [(16, 23), (32, 23), (29, 29), (24, 32), (19, 29)])
    # 左侧阴影
    poly(s, skin_sh, [(16, 22), (19, 22), (20, 28), (24, 31), (24, 32), (19, 29), (16, 23)])
    # 脖子与耳朵
    rect(s, skin_sh, (21, 30, 7, 5))
    rect(s, skin, (14, 19, 2, 5))
    rect(s, skin, (33, 19, 2, 5))


def draw_eyes(s, iris, style='normal', y=20):
    """style: normal/sharp(锐利)/glow(发光)/dot(豆豆眼)"""
    if style == 'glow':
        rect(s, iris, (18, y, 3, 2))
        rect(s, iris, (27, y, 3, 2))
        px(s, WHITE, 19, y)
        px(s, WHITE, 28, y)
        return
    # 眼白 + 虹膜 + 上缘线
    rect(s, WHITE, (18, y, 4, 3))
    rect(s, WHITE, (27, y, 4, 3))
    rect(s, iris, (19, y, 2, 3))
    rect(s, iris, (28, y, 2, 3))
    px(s, OUTLINE, 19, y + 1)
    px(s, OUTLINE, 28, y + 1)
    hline(s, OUTLINE, 18, 21, y - 1)
    hline(s, OUTLINE, 27, 30, y - 1)
    if style == 'sharp':            # 上挑眼角
        px(s, OUTLINE, 17, y)
        px(s, OUTLINE, 31, y)


def draw_brows(s, color, style='flat', y=17):
    if style == 'angry':
        for i in range(4):
            px(s, color, 18 + i, y + (i // 2))
            px(s, color, 30 - i, y + (i // 2))
    else:
        hline(s, color, 18, 21, y)
        hline(s, color, 27, 30, y)


def draw_mouth(s, style='flat'):
    if style == 'smile':
        hline(s, OUTLINE, 22, 26, 27)
        px(s, OUTLINE, 21, 26)
        px(s, OUTLINE, 27, 26)
    elif style == 'grim':
        hline(s, OUTLINE, 21, 26, 27)
    elif style == 'sneer':
        hline(s, OUTLINE, 21, 25, 27)
        px(s, OUTLINE, 26, 26)
        px(s, (180, 180, 175), 24, 28)   # 露齿
    else:
        hline(s, OUTLINE, 22, 25, 27)
    px(s, SKIN_SH, 24, 24)               # 鼻
    px(s, SKIN_SH, 24, 23)


def draw_torso(s, base, sh, hl, style='plate'):
    """胸口与肩。style: plate重甲/cloak披风/robe法袍/leather皮甲/tunic布衣"""
    rect(s, base, (12, 36, 24, 12))                      # 躯干
    poly(s, base, [(12, 36), (8, 42), (8, 48), (12, 48)])    # 左肩斜面
    poly(s, base, [(36, 36), (40, 42), (40, 48), (36, 48)])  # 右肩斜面
    rect(s, sh, (12, 44, 24, 4))
    if style == 'plate':
        ell(s, hl, (6, 34, 12, 9))      # 大肩甲
        ell(s, hl, (30, 34, 12, 9))
        ell(s, sh, (8, 36, 8, 5))
        ell(s, sh, (32, 36, 8, 5))
        rect(s, hl, (22, 36, 4, 12))    # 中央条
    elif style == 'cloak':
        poly(s, hl, [(8, 38), (16, 34), (16, 48), (8, 48)])   # 披风搭左肩
        rect(s, sh, (20, 38, 8, 2))     # 领口扣
        px(s, (250, 210, 90), 24, 39)   # 金扣
    elif style == 'robe':
        poly(s, hl, [(20, 34), (28, 34), (26, 48), (22, 48)])  # 中央饰带
        hline(s, (250, 210, 90), 21, 27, 36)                   # 金边
    elif style == 'leather':
        poly(s, sh, [(12, 36), (24, 48), (20, 48), (12, 41)])  # 斜背带
        px(s, hl, 15, 38)
        px(s, hl, 17, 40)
    # tunic: 素色不加饰


# ---------- 发型 ----------

def hair_spiky(s, c, d):
    """少年短发（刺猬头）"""
    ell(s, c, (13, 4, 22, 12))
    poly(s, c, [(13, 10), (35, 10), (35, 16), (33, 13), (30, 16), (27, 12),
                (24, 16), (21, 12), (18, 16), (15, 13), (13, 16)])
    for x, y in ((15, 4), (20, 2), (26, 2), (31, 4)):
        poly(s, c, [(x, y + 4), (x + 2, y), (x + 4, y + 4)])
    poly(s, d, [(13, 10), (16, 10), (15, 14), (13, 15)])


def hair_crop(s, c, d, stubble=None):
    """利落短发 + 可选胡茬"""
    ell(s, c, (14, 5, 20, 10))
    rect(s, c, (14, 10, 20, 4))
    poly(s, d, [(14, 12), (17, 12), (16, 15), (14, 15)])
    poly(s, d, [(34, 12), (31, 12), (32, 15), (34, 15)])
    if stubble:
        for x in range(18, 31, 2):
            px(s, stubble, x, 29)
        for x in range(19, 30, 2):
            px(s, stubble, x, 30)


def hair_ponytail(s, c, d):
    """高马尾"""
    ell(s, c, (14, 5, 20, 11))
    rect(s, c, (14, 10, 3, 8))
    rect(s, c, (31, 10, 3, 8))
    poly(s, c, [(30, 6), (38, 2), (40, 10), (37, 20), (34, 26), (36, 14)])  # 马尾束
    poly(s, d, [(36, 6), (38, 12), (35, 22), (36, 12)])
    hline(s, d, 15, 18, 9)
    px(s, (250, 210, 90), 33, 7)   # 发绳


def hair_long(s, c, d):
    """垂肩长发"""
    ell(s, c, (13, 4, 22, 12))
    rect(s, c, (13, 10, 4, 22))
    rect(s, c, (31, 10, 4, 22))
    poly(s, c, [(13, 30), (17, 32), (17, 36), (12, 36)])
    poly(s, c, [(35, 30), (31, 32), (31, 36), (36, 36)])
    poly(s, d, [(13, 12), (15, 12), (14, 30), (13, 30)])
    hline(s, d, 16, 20, 8)


def hair_tied(s, c, d):
    """束起的长发（剑士）"""
    ell(s, c, (14, 4, 20, 11))
    rect(s, c, (14, 9, 2, 10))
    rect(s, c, (32, 9, 2, 10))
    poly(s, c, [(22, 3), (26, 3), (25, 0), (23, 0)])           # 发髻
    poly(s, c, [(32, 14), (36, 18), (35, 30), (32, 26)])       # 侧后垂发
    poly(s, d, [(34, 18), (35, 24), (33, 28), (34, 20)])
    hline(s, d, 16, 19, 8)


def hair_bald(s, c, d):
    """光头 + 络腮胡"""
    poly(s, d, [(14, 22), (16, 30), (20, 34), (24, 35), (28, 34), (32, 30),
                (34, 22), (34, 28), (30, 34), (24, 37), (18, 34), (14, 28)])
    rect(s, d, (19, 27, 11, 7))      # 浓密下巴胡
    rect(s, d, (14, 22, 2, 6))       # 鬓角
    rect(s, d, (33, 22, 2, 6))
    hline(s, (120, 88, 62), 21, 27, 29)   # 胡须高光纹理
    hline(s, (120, 88, 62), 20, 28, 32)
    px(s, c, 17, 8)                  # 头顶反光
    px(s, c, 19, 7)
    px(s, c, 21, 6)


def hood(s, c, d):
    """兜帽（遮上半脸）"""
    ell(s, c, (11, 2, 26, 16))
    poly(s, c, [(11, 10), (37, 10), (35, 22), (31, 16), (17, 16), (13, 22)])
    rect(s, c, (12, 8, 4, 28))
    rect(s, c, (32, 8, 4, 28))
    poly(s, d, [(17, 16), (31, 16), (29, 19), (19, 19)])   # 帽沿阴影
    rect(s, d, (12, 20, 3, 16))
    poly(s, c, [(22, 0), (26, 0), (25, 4), (23, 4)])       # 帽尖


def helm_scar(s):
    """巴尔克的疤：自右眉上方斜划过脸颊"""
    for x, y in ((30, 13), (29, 15), (29, 16), (28, 18), (28, 19), (27, 21), (27, 23)):
        px(s, (205, 115, 96), x, y)
        px(s, (170, 88, 76), x + 1, y)


# ---------- 角色配置 ----------

def paint_roy(s):
    draw_head(s)
    draw_torso(s, (52, 120, 70), (38, 92, 54), (76, 160, 96), 'cloak')
    rect(s, (180, 186, 200), (19, 33, 10, 4))            # 锁甲领
    hair_spiky(s, (196, 60, 44), (150, 38, 32))
    draw_brows(s, (150, 38, 32))
    draw_eyes(s, (60, 110, 180))
    draw_mouth(s, 'flat')


def paint_lance(s):
    draw_head(s)
    draw_torso(s, (96, 110, 138), (70, 82, 106), (140, 152, 178), 'plate')
    hair_crop(s, (104, 76, 52), (78, 56, 38), stubble=(120, 95, 70))
    draw_brows(s, (78, 56, 38))
    draw_eyes(s, (90, 80, 60), 'sharp')
    draw_mouth(s, 'grim')


def paint_rebecca(s):
    draw_head(s, jaw='slim')
    draw_torso(s, (140, 100, 60), (108, 76, 44), (172, 130, 84), 'leather')
    poly(s, (110, 80, 50), [(34, 36), (40, 30), (41, 32), (36, 39)])   # 背后弓梢
    hair_ponytail(s, (70, 150, 70), (48, 112, 50))
    draw_brows(s, (48, 112, 50))
    draw_eyes(s, (70, 140, 80))
    draw_mouth(s, 'smile')


def paint_lilina(s):
    draw_head(s, jaw='slim')
    draw_torso(s, (180, 60, 56), (140, 42, 40), (214, 96, 80), 'robe')
    hair_long(s, (140, 90, 190), (104, 62, 150))
    draw_brows(s, (104, 62, 150))
    draw_eyes(s, (150, 90, 200))
    draw_mouth(s, 'smile')
    px(s, (250, 210, 90), 14, 6)     # 发饰
    px(s, (250, 210, 90), 15, 5)


def paint_fir(s):
    draw_head(s, jaw='slim')
    draw_torso(s, (70, 100, 170), (50, 74, 132), (100, 134, 204), 'tunic')
    rect(s, (200, 205, 215), (21, 34, 7, 3))             # 护喉
    hair_tied(s, (208, 212, 222), (160, 165, 182))
    draw_brows(s, (160, 165, 182))
    draw_eyes(s, (90, 110, 160), 'sharp')
    draw_mouth(s, 'flat')


def paint_gale(s):
    draw_head(s, skin=(222, 168, 126), skin_sh=(186, 130, 92), jaw='wide')
    draw_torso(s, (130, 92, 58), (100, 68, 42), (160, 120, 80), 'leather')
    poly(s, (120, 120, 128), [(30, 30), (42, 38), (40, 42), (29, 34)])  # 扛斧柄
    poly(s, (168, 170, 178), [(38, 30), (46, 36), (42, 42), (36, 36)])  # 斧刃
    hair_bald(s, (236, 188, 148), (88, 60, 40))
    draw_brows(s, (88, 60, 40), 'angry', 16)
    draw_eyes(s, (120, 70, 40), 'sharp', 19)
    px(s, (250, 190, 70), 35, 22)    # 金耳环
    px(s, (250, 190, 70), 35, 23)


def paint_morgan(s):
    draw_head(s, skin=(214, 196, 188), skin_sh=(178, 156, 150))
    draw_torso(s, (84, 60, 120), (62, 42, 92), (110, 82, 152), 'robe')
    hood(s, (84, 60, 120), (58, 40, 88))
    draw_eyes(s, (200, 90, 230), 'glow')
    draw_mouth(s, 'sneer')
    px(s, OUTLINE, 26, 26)                       # 加深冷笑嘴角
    for x, y in ((9, 40), (8, 37), (10, 34), (7, 43), (11, 30),         # 暗紫魔雾(両侧)
                 (39, 41), (40, 38), (38, 35), (41, 44), (37, 31)):
        px(s, (170, 100, 230), x, y)
        px(s, (120, 60, 180), x, y + 1)


def paint_balk(s):
    draw_head(s, skin=(224, 176, 140), skin_sh=(188, 138, 104))
    draw_torso(s, (62, 64, 76), (44, 46, 56), (96, 100, 116), 'plate')
    rect(s, (200, 70, 60), (22, 33, 4, 3))               # 红色领巾
    hair_crop(s, (168, 170, 176), (128, 130, 140), stubble=(150, 152, 158))
    draw_brows(s, (128, 130, 140), 'angry')
    draw_eyes(s, (80, 84, 96), 'sharp')
    draw_mouth(s, 'grim')
    helm_scar(s)


CHARS = [
    ('罗伊',   'roy',     paint_roy),
    ('兰斯',   'lance',   paint_lance),
    ('丽贝卡', 'rebecca', paint_rebecca),
    ('莉莉娜', 'lilina',  paint_lilina),
    ('菲尔',   'fir',     paint_fir),
    ('盖尔',   'gale',    paint_gale),
    ('莫尔甘', 'morgan',  paint_morgan),
    ('巴尔克', 'balk',    paint_balk),
]


def outline(src):
    """外轮廓 1px 描边"""
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    mask = pygame.mask.from_surface(src, 8)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for x, y in mask.outline():
            px(out, OUTLINE, x + dx, y + dy)
    out.blit(src, (0, 0))
    return out


def main():
    pygame.init()
    pygame.display.set_mode((64, 64))
    OUT.mkdir(parents=True, exist_ok=True)
    font = pygame.font.Font(None, 22)
    scale = 4
    sheet = pygame.Surface((len(CHARS) * (W * scale + 12) + 12, H * scale + 44))
    sheet.fill((28, 30, 44))
    for i, (cname, pinyin, painter) in enumerate(CHARS):
        s = srf()
        painter(s)
        s = outline(s)
        pygame.image.save(s, str(OUT / f'{pinyin}.png'))
        big = pygame.transform.scale(s, (W * scale, H * scale))
        x = 12 + i * (W * scale + 12)
        sheet.blit(big, (x, 8))
        sheet.blit(font.render(pinyin, True, (250, 210, 90)), (x, H * scale + 16))
    pygame.image.save(sheet, '/tmp/fe_portraits_preview.png')
    print(f'已生成 {len(CHARS)} 张立绘 → {OUT}')
    print('预览: /tmp/fe_portraits_preview.png')


if __name__ == '__main__':
    main()
