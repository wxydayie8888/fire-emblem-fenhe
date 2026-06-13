"""单位：属性、经验、升级。纯逻辑，零 pygame 依赖。"""
import random

from settings import (CLASSES, WEAPONS, EXP_LEVEL, POTION_HEAL, POTION_USES,
                      PROMOTIONS, PROMOTE_LEVEL, WEAPON_USES)

STATS = ('hp', 'pow', 'skl', 'spd', 'dfn')
# 存档只保留可变属性；mov/weapon/growth/mounted 由职业表派生
SAVE_FIELDS = ('name', 'cls', 'level', 'exp', 'max_hp', 'pow', 'skl', 'spd', 'dfn')


class Unit:
    def __init__(self, name, cls, team, pos, boss=False, ai='aggro'):
        c = CLASSES[cls]
        self.name, self.cls, self.team = name, cls, team
        self.x, self.y = pos
        self.max_hp = c['hp']
        self.hp = c['hp']
        self.pow, self.skl, self.spd, self.dfn, self.mov = (
            c['pow'], c['skl'], c['spd'], c['dfn'], c['mov'])
        self.weapon = c['weapon']
        self.mounted = c.get('mounted', False)
        self.fly = c.get('fly', False)
        self.growth = c['growth']
        self.boss = boss
        self.ai = ai                 # 'aggro' 主动 / 'guard' 驻守
        self.level, self.exp = 1, 0
        self.potions = POTION_USES   # 伤药数量
        self.acted = False           # 本回合是否已行动
        self.uses = WEAPON_USES.get(self.weapon, 40)   # 武器耐久（章内）

    @property
    def alive(self):
        return self.hp > 0

    @property
    def broken(self):
        """武器是否破损（耐久归零）：命中/伤害下降，直到本章结束自动修复。"""
        return self.uses <= 0

    def refresh_weapon(self):
        """章首把武器耐久修复满。"""
        self.uses = WEAPON_USES.get(self.weapon, 40)

    @property
    def cls_name(self):
        return CLASSES[self.cls]['name']

    @property
    def weapon_range(self):
        return WEAPONS[self.weapon]['range']

    def skill(self):
        """职业技 dict（无则空）。"""
        return CLASSES[self.cls].get('skill', {})

    def can_heal(self):
        """能否使用治疗（修女/贤者/主教）。"""
        return CLASSES[self.cls].get('heal', False)

    def is_promoted(self):
        return CLASSES[self.cls].get('tier', 1) >= 2

    def can_promote(self):
        return (self.cls in PROMOTIONS and not self.is_promoted()
                and self.level >= PROMOTE_LEVEL)

    def promote(self):
        """转职为高级职：切换职业、叠加属性增益、回满 HP。成功返回 True。"""
        if not self.can_promote():
            return False
        adv, gains = PROMOTIONS[self.cls]
        self.apply_boost(gains)
        self.cls = adv
        c = CLASSES[adv]
        self.weapon = c['weapon']
        self.mov = c['mov']
        self.mounted = c.get('mounted', False)
        self.fly = c.get('fly', False)
        self.growth = c['growth']
        self.hp = self.max_hp
        self.refresh_weapon()        # 新武器满耐久
        return True

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

    def apply_boost(self, boost):
        """章节强化（精锐敌人/Boss）：hp 同时提升上限与当前值。"""
        for stat, add in boost.items():
            if stat == 'hp':
                self.max_hp += add
                self.hp += add
            else:
                setattr(self, stat, getattr(self, stat) + add)

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def to_dict(self):
        """序列化为存档字典（仅 SAVE_FIELDS）。"""
        return {f: getattr(self, f) for f in SAVE_FIELDS}

    @classmethod
    def from_dict(cls_, d):
        """从存档字典重建我方单位（满血、职业派生属性取自职业表）。"""
        u = cls_(d['name'], d['cls'], 'player', (0, 0))
        for f in SAVE_FIELDS[2:]:
            setattr(u, f, d[f])
        u.hp = u.max_hp
        return u

    # 战斗中挂起存档：完整还原战局所需的全部可变状态
    BATTLE_FIELDS = SAVE_FIELDS + ('team', 'x', 'y', 'hp', 'acted', 'potions',
                                   'boss', 'ai', 'uses')

    def to_battle_dict(self):
        return {f: getattr(self, f) for f in self.BATTLE_FIELDS}

    @classmethod
    def from_battle_dict(cls_, d):
        u = cls_(d['name'], d['cls'], d['team'], (d['x'], d['y']),
                 boss=d['boss'], ai=d['ai'])
        for f in SAVE_FIELDS[2:]:
            setattr(u, f, d[f])
        u.hp = d['hp']
        u.acted = d['acted']
        u.potions = d['potions']
        u.uses = d.get('uses', WEAPON_USES.get(u.weapon, 40))
        return u

    def use_potion(self):
        """喝伤药。返回实际回复量（没药或满血返回 0，不消耗）。"""
        if self.potions <= 0:
            return 0
        healed = min(POTION_HEAL, self.max_hp - self.hp)
        if healed <= 0:
            return 0
        self.potions -= 1
        self.hp += healed
        return healed
