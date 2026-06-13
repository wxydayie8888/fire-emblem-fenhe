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


def promoted(base, **kw):
    from unit import Unit
    u = Unit('x', base, 'player', (0, 0))
    u.level = 12
    u.promote()
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def test_skill_crit_bonuses():
    sm = promoted('myrmidon')          # 剑圣 必杀+20
    base = sm.skl // 2 + combat.WEAPONS[sm.weapon]['crit']
    assert combat.calc_crit(sm) == base + 20
    sn = promoted('archer')            # 神射手 必杀+15
    assert combat.calc_crit(sn) == sn.skl // 2 + combat.WEAPONS['bow']['crit'] + 15


def test_skill_hit_and_avoid():
    from unit import Unit
    # 圣骑士命中+12：与同 skl 的未转职重骑士(同为枪、无技能)对照
    pal = promoted('cavalier', skl=8)
    plain = Unit('对照', 'cavalier', 'player', (0, 0)); plain.skl = 8
    f = fighter()
    assert combat.calc_hit(pal, f, 0) == min(100, combat.calc_hit(plain, f, 0) + 12)
    # 天马将军回避+15：与同 spd 的未转职天马(同为枪、无技能)对照
    fal = promoted('pegasus')
    plain_peg = Unit('对照', 'pegasus', 'player', (0, 0)); plain_peg.spd = fal.spd
    atk = fighter(skl=20)
    assert combat.calc_hit(atk, fal, 0) == max(0, combat.calc_hit(atk, plain_peg, 0) - 15)


def test_skill_sage_power_and_defender_dfn():
    sage = promoted('mage')            # 贤者 魔力+2
    f = fighter(dfn=0)
    dmg = combat.calc_damage(sage, f)
    assert dmg == sage.pow + combat.WEAPONS['magic']['might'] + 2     # 魔法不吃三角


def test_skill_bishop_heal_bonus():
    bishop = promoted('cleric')        # 主教 祈祷 治疗+5
    from settings import STAFF_BASE_HEAL
    assert combat.heal_amount(bishop) == STAFF_BASE_HEAL + bishop.pow + 5


def test_skill_great_shield_halves_damage():
    from unit import Unit
    marshal = promoted('knight')       # 将军 大盾 50% 半伤
    atk = Unit('弓手', 'archer', 'player', (0, 0)); atk.pow = 30   # 弓 2 格，将军无法反击
    marshal.hp = marshal.max_hp
    full = combat.calc_damage(atk, marshal)
    assert full > 2
    seq = iter([0.0, 0.99, 0.0])       # 命中 / 不必杀 / 大盾触发
    combat.resolve(atk, marshal, 2, 0, 0, rng=lambda: next(seq))
    assert marshal.max_hp - marshal.hp == full - full // 2     # 半伤


# ---------- 特效武器 ----------

def archer(**kw):
    u = Unit('弓兵', 'archer', 'player', (0, 0))
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def pegasus(**kw):
    u = Unit('飞兵', 'pegasus', 'enemy', (2, 0))
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def test_effective_bow_vs_flier():
    a, p = archer(), pegasus()
    base = a.pow + 6                                   # 弓威力6，无三角
    assert combat.is_effective(a, p)                   # 弓克飞行
    assert combat.calc_damage(a, p) == max(0, base * 3 - p.dfn)
    # 反向：飞兵(枪)打弓兵不特效
    assert not combat.is_effective(p, a)


def test_effective_light_and_lord_vs_dragon():
    from unit import Unit
    dragon = Unit('邪龙', 'dragon', 'enemy', (3, 0))
    bishop = Unit('主教', 'bishop', 'player', (0, 0))   # 光魔
    roy = Unit('罗伊', 'lord', 'player', (0, 0))         # 圣剑
    myrm = Unit('剑客', 'myrmidon', 'player', (0, 0))    # 普通剑
    assert combat.is_effective(bishop, dragon)
    assert combat.is_effective(roy, dragon)             # 领主圣剑克龙
    assert not combat.is_effective(myrm, dragon)        # 普通剑不克


def test_non_flier_not_effective():
    assert not combat.is_effective(archer(), fighter())  # 弓对步兵无特效


def test_forecast_carries_effective():
    fc = combat.forecast(archer(), pegasus(), dist=2, att_avoid=0, def_avoid=0)
    assert fc['att']['effective'] is True


# ---------- 武器耐久（破损惩罚）----------

def test_broken_weapon_penalty():
    a, f = lord(), fighter(dfn=0, spd=20)       # 高速避免命中被钳到 100
    a.uses = 5
    full = combat.calc_damage(a, f)
    full_hit = combat.calc_hit(a, f, 0)
    assert full_hit < 100                        # 未触顶，便于验证 -25
    a.uses = 0
    assert a.broken
    assert combat.calc_damage(a, f) == full - 3          # 伤害-3
    assert combat.calc_hit(a, f, 0) == full_hit - 25      # 命中-25


# ---------- 天气命中 ----------

def test_weather_hit_penalty():
    a, f = lord(), fighter(spd=20)
    base = combat.calc_hit(a, f, 0, weather=0)
    assert combat.calc_hit(a, f, 0, weather=10) == max(0, base - 10)
    fc = combat.forecast(a, f, 1, 0, 0, weather=10)
    assert fc['att']['hit'] == max(0, base - 10)
