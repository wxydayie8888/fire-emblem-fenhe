"""平衡性模拟：贪心 bot 自动打全战役，统计各章胜率。

用法: .venv/bin/python tools/balance_sim.py [局数=20]

bot 策略（比人类玩家弱，不会卡桥头守口、不会败北重试）：
  - 能击杀则击杀，否则打期望伤害最高且挨打最少的目标
  - 攻击站位优先选地形回避高的格子
  - 低血量(≤40%)且无击杀机会时喝药
  - 无法攻击则向最近敌人逼近
敌方完全复用游戏的 ai.plan_action。胜率是平衡性的下限参考。
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import combat as C
from ai import plan_action
from grid import Grid, manhattan, move_range
from settings import CHAPTERS, PLAYER_ROSTER
from unit import Unit


def fight(att, dfd, grid):
    dist = manhattan((att.x, att.y), (dfd.x, dfd.y))
    _, exp = C.resolve(att, dfd, dist,
                       grid.terrain(att.x, att.y)['avoid'],
                       grid.terrain(dfd.x, dfd.y)['avoid'])
    for u, amount in exp.items():
        if u.alive and u.team == 'player':
            u.gain_exp(amount)
    # 与游戏一致：被打的驻守敌人被激活
    for u in (att, dfd):
        if u.team == 'enemy' and u.alive and u.ai == 'guard':
            u.ai = 'aggro'


def best_action(u, grid, units, enemies):
    """返回 ('attack', tile, target) / ('move', tile) / ('potion',)"""
    tiles = move_range(u, grid, units)
    lo, hi = u.weapon_range
    best = None
    for e in enemies:
        for t in tiles:
            d = manhattan(t, (e.x, e.y))
            if not lo <= d <= hi:
                continue
            fc = C.forecast(u, e, d, grid.terrain(*t)['avoid'],
                            grid.terrain(e.x, e.y)['avoid'])
            deal = fc['att']['dmg'] * fc['att']['count'] * fc['att']['hit'] / 100
            take = 0
            if fc['def']:
                take = fc['def']['dmg'] * fc['def']['count'] * fc['def']['hit'] / 100
            kill = 1000 if fc['att']['dmg'] * fc['att']['count'] >= e.hp else 0
            score = kill + deal - take * 0.7 + grid.terrain(*t)['avoid'] * 0.05
            if best is None or score > best[0]:
                best = (score, t, e)
    if best and (best[0] >= 1000 or u.hp > u.max_hp * 0.4):
        return ('attack', best[1], best[2])
    if u.hp <= u.max_hp * 0.4 and u.potions > 0:
        return ('potion',)
    if best:
        return ('attack', best[1], best[2])
    target = min(enemies, key=lambda e: manhattan((u.x, u.y), (e.x, e.y)))
    tile = min(tiles, key=lambda t: manhattan(t, (target.x, target.y)))
    return ('move', tile)


def heal_phase(side, grid):
    for u in side:
        if u.alive:
            t = grid.terrain(u.x, u.y)
            if t['heal']:
                u.heal(max(1, int(u.max_hp * t['heal'])))


def sim_chapter(idx, roster, seed, max_turns=30):
    random.seed(seed)
    ch = CHAPTERS[idx]
    for j in ch['join']:
        if all(u.name != j['name'] for u in roster):
            roster.append(Unit(j['name'], j['cls'], 'player', j['pos']))
    positions = list(ch['players']) + [j['pos'] for j in ch['join']]
    for u, pos in zip(roster, positions):
        u.x, u.y = pos
        u.hp = u.max_hp
        u.potions = 3
    enemies = [Unit(e['name'], e['cls'], 'enemy', e['pos'],
                    boss=e.get('boss', False), ai=e.get('ai', 'aggro'))
               for e in ch['enemies']]
    units = roster + enemies
    grid = Grid(ch['map'])
    lord = roster[0]

    def won():
        alive_e = [e for e in enemies if e.alive]
        if not alive_e:
            return True
        return ch['win'] == 'boss' and not any(e.boss for e in alive_e)

    for turn in range(1, max_turns + 1):
        for u in [x for x in roster if x.alive]:
            if won():
                return turn, None
            act = best_action(u, grid, units, [e for e in enemies if e.alive])
            if act[0] == 'attack':
                u.x, u.y = act[1]
                fight(u, act[2], grid)
            elif act[0] == 'potion':
                u.use_potion()
            else:
                u.x, u.y = act[1]
            if not lord.alive:
                return None, '阵亡'
        if won():
            return turn, None
        heal_phase(roster, grid)
        for e in [x for x in enemies if x.alive]:
            if not e.alive:
                continue
            act = plan_action(e, grid, units)
            e.x, e.y = act['move']
            if act['target'] is not None and act['target'].alive:
                fight(e, act['target'], grid)
            if not lord.alive:
                return None, '阵亡'
        heal_phase(enemies, grid)
    return None, '超时'


def run(n=20):
    results = {0: [], 1: [], 2: []}
    reasons = {0: {}, 1: {}, 2: {}}
    full_wins = 0
    for seed in range(n):
        roster = [Unit(s['name'], s['cls'], 'player', (0, 0)) for s in PLAYER_ROSTER]
        ok = True
        for idx in range(3):
            r, why = sim_chapter(idx, roster, seed * 100 + idx)
            results[idx].append(r)
            if r is None:
                reasons[idx][why] = reasons[idx].get(why, 0) + 1
                ok = False
                break
        if ok:
            full_wins += 1
    for idx in range(3):
        runs = results[idx]
        wins = [r for r in runs if r is not None]
        rate = len(wins) / len(runs) * 100 if runs else 0
        avg = f'  平均{sum(wins)/len(wins):.1f}回合' if wins else '  （全败）'
        why = f'  败因{reasons[idx]}' if reasons[idx] else ''
        print(f'第{idx+1}章: 尝试{len(runs)} 胜率{rate:.0f}%{avg}{why}')
    print(f'全战役通关率(bot不重试): {full_wins}/{n} = {full_wins/n*100:.0f}%')


if __name__ == '__main__':
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
