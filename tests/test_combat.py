import combat
from unit import Unit


def lord(**kw):
    u = Unit('剑士', 'lord', 'player', (0, 0))
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def fighter(**kw):
    u = Unit('斧兵', 'fighter', 'enemy', (1, 0))
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def test_triangle():
    assert combat.triangle('sword', 'axe') == (1, 15)    # 剑克斧
    assert combat.triangle('axe', 'sword') == (-1, -15)
    assert combat.triangle('sword', 'lance') == (-1, -15)
    assert combat.triangle('sword', 'sword') == (0, 0)
    assert combat.triangle('bow', 'axe') == (0, 0)        # 弓不参与三角


def test_damage_with_triangle():
    # 剑lord打斧fighter: 7力+5威力+1克制-4防 = 9
    assert combat.calc_damage(lord(), fighter()) == 9
    # 反向: 7力+8威力-1被克-7防 = 7
    assert combat.calc_damage(fighter(), lord()) == 7


def test_damage_floor_zero():
    assert combat.calc_damage(lord(pow=0), fighter(dfn=99)) == 0


def test_hit_clamped():
    # lord: 90+8*2+15 - (5*2+0) = 111 → 100
    assert combat.calc_hit(lord(), fighter(), 0) == 100
    assert combat.calc_hit(lord(skl=0), fighter(spd=99), 30) == 0


def test_double():
    assert combat.can_double(lord(), fighter())            # 9 vs 5
    assert not combat.can_double(lord(spd=8), fighter())   # 差3不追击


def test_counter_range():
    assert combat.in_range(fighter(), 1)
    assert not combat.in_range(fighter(), 2)   # 斧打不到2格 → 弓手安全


def test_forecast_no_counter_for_bow():
    archer = Unit('弓手', 'archer', 'player', (0, 0))
    f = combat.forecast(archer, fighter(), 2, 0, 0)
    assert f['def'] is None
    assert f['att']['count'] == 1


def test_resolve_kill_and_exp():
    a, d = lord(), fighter(hp=5)
    events, exp = combat.resolve(a, d, 1, 0, 0, rng=lambda: 0.0)
    # rng=0: 必中+必杀 9*3=27 ≥ 5HP，一击毙命，无反击
    assert not d.alive and len(events) == 1
    assert events[0]['crit'] and events[0]['dmg'] == 27
    assert exp[a] == 10 + 40   # 命中+击杀


def test_resolve_counter_and_double():
    a = lord(spd=20)                  # 必定追击
    d = fighter(hp=99, spd=1)
    hits = iter([0.5, 0.99, 0.5, 0.99, 0.5, 0.99])  # 全命中不必杀
    events, exp = combat.resolve(a, d, 1, 0, 0, rng=lambda: next(hits))
    # 顺序: 攻方→守方反击→攻方追击
    actors = [e['actor'] for e in events]
    assert actors == [a, d, a]
    assert exp[a] == 20   # 两次命中


def test_enemy_gains_no_exp():
    a, d = fighter(), lord(hp=99)
    _, exp = combat.resolve(a, d, 1, 0, 0, rng=lambda: 0.5)
    assert a not in exp


def test_breath_weapon_range():
    dragon = Unit('邪龙', 'dragon', 'enemy', (0, 0), boss=True)
    assert combat.in_range(dragon, 1) and combat.in_range(dragon, 2)
    assert not combat.in_range(dragon, 3)
    assert combat.calc_damage(dragon, Unit('R', 'lord', 'player', (1, 0))) > 0
