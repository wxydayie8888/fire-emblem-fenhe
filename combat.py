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


def _skill(u):
    """单位职业技 dict（Unit.skill() 或空）。兼容无 skill 方法的对象。"""
    fn = getattr(u, 'skill', None)
    return fn() if callable(fn) else {}


def calc_damage(att, dfd, sup_dmg=0):
    """sup_dmg: 攻方支援伤害加成。职业技：攻方魔力、守方额外防御自动计入。"""
    d, _ = triangle(att.weapon, dfd.weapon)
    raw = (att.pow + WEAPONS[att.weapon]['might'] + d
           + _skill(att).get('pow', 0) + sup_dmg
           - dfd.dfn - _skill(dfd).get('dfn', 0))
    return max(0, raw)


def calc_hit(att, dfd, def_avoid_bonus, sup_hit=0, sup_avoid=0):
    """def_avoid_bonus: 守方地形回避；sup_hit/sup_avoid: 双方支援加成。
    职业技：攻方命中、守方回避自动计入。"""
    _, h = triangle(att.weapon, dfd.weapon)
    hit = (WEAPONS[att.weapon]['hit'] + att.skl * 2 + h
           + _skill(att).get('hit', 0) + sup_hit
           - (dfd.spd * 2 + def_avoid_bonus
              + _skill(dfd).get('avoid', 0) + sup_avoid))
    return max(0, min(100, hit))


def calc_crit(att, sup_crit=0):
    return WEAPONS[att.weapon]['crit'] + att.skl // 2 + _skill(att).get('crit', 0) + sup_crit


def can_attack(unit):
    """杖类武器（heal=True）不能攻击。"""
    return not WEAPONS[unit.weapon].get('heal')


def heal_amount(healer):
    """治疗回复量 = 基础值 + 力量 + 职业技治疗加成（主教祈祷）。"""
    from settings import STAFF_BASE_HEAL
    return STAFF_BASE_HEAL + healer.pow + _skill(healer).get('heal_bonus', 0)


def in_range(unit, dist):
    if not can_attack(unit):
        return False
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
        shield = _skill(target).get('shield', 0)   # 大盾：几率半伤
        if dmg > 0 and shield and rng() < shield:
            dmg -= dmg // 2
        target.hp = max(0, target.hp - dmg)
        events.append({'actor': actor, 'target': target,
                       'dmg': dmg, 'hit': hit, 'crit': crit})
        if actor.team == 'player' and hit:
            exp[actor] = exp.get(actor, 0) + EXP_HIT
            if not target.alive:
                exp[actor] += EXP_BOSS_KILL if target.boss else EXP_KILL
    return events, exp
