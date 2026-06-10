"""敌方 AI：择优攻击（期望伤害-反击风险），无目标则逼近最近敌人。零 pygame 依赖。"""
import combat
from grid import manhattan, move_range


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
        unit.ai = 'aggro'              # 驻守单位接敌后永久转为进攻
        return {'move': best[1], 'target': best[2]}

    if unit.boss or unit.ai == 'guard':
        return {'move': stay, 'target': None}
    nearest = min(foes, key=lambda f: manhattan(stay, (f.x, f.y)))
    move = min(reach, key=lambda p: (manhattan(p, (nearest.x, nearest.y)), reach[p]))
    return {'move': move, 'target': None}
