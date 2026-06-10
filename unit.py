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
