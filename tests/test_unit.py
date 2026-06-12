from unit import Unit


def make_lord():
    return Unit('罗伊', 'lord', 'player', (2, 4))


def test_init_from_class():
    u = make_lord()
    assert (u.hp, u.max_hp, u.pow, u.mov) == (24, 24, 7, 5)
    assert u.weapon == 'sword' and u.alive and not u.mounted


def test_gain_exp_no_levelup():
    u = make_lord()
    assert u.gain_exp(40) == []
    assert u.exp == 40 and u.level == 1


def test_levelup_all_stats_with_max_growth():
    u = make_lord()
    gains = u.gain_exp(100, rng=lambda: 0.0)   # rng=0 → 全部成长
    assert u.level == 2 and u.exp == 0
    assert gains == [{'hp': 1, 'pow': 1, 'skl': 1, 'spd': 1, 'dfn': 1}]
    assert u.max_hp == 25 and u.hp == 25 and u.pow == 8


def test_levelup_no_stats_with_min_growth():
    u = make_lord()
    gains = u.gain_exp(110, rng=lambda: 0.999)  # rng~1 → 全不成长
    assert u.level == 2 and u.exp == 10
    assert gains == [{'hp': 0, 'pow': 0, 'skl': 0, 'spd': 0, 'dfn': 0}]


def test_double_levelup():
    u = make_lord()
    gains = u.gain_exp(200, rng=lambda: 0.0)
    assert u.level == 3 and len(gains) == 2


def test_enemy_no_growth_no_levelup():
    e = Unit('斧兵', 'fighter', 'enemy', (0, 0))
    assert e.gain_exp(500) == []
    assert e.level == 1


def test_heal_caps_at_max():
    u = make_lord()
    u.hp = 15
    u.heal(99)
    assert u.hp == u.max_hp


def test_potion_heals_and_consumes():
    u = make_lord()
    u.hp = 5
    assert u.potions == 3
    assert u.use_potion() == 12        # 回复量
    assert u.hp == 17 and u.potions == 2


def test_potion_caps_at_max_hp():
    u = make_lord()
    u.hp = 15
    assert u.use_potion() == 9         # 只回到满血
    assert u.hp == u.max_hp


def test_potion_empty_returns_zero():
    u = make_lord()
    u.hp = 5
    u.potions = 0
    assert u.use_potion() == 0
    assert u.hp == 5


def test_to_dict_only_save_fields():
    u = make_lord()
    u.gain_exp(140, rng=lambda: 0.0)   # Lv2 全成长, exp 40
    d = u.to_dict()
    assert d == {'name': '罗伊', 'cls': 'lord', 'level': 2, 'exp': 40,
                 'max_hp': 25, 'pow': 8, 'skl': 9, 'spd': 10, 'dfn': 8}


def test_from_dict_roundtrip():
    u = make_lord()
    u.gain_exp(250, rng=lambda: 0.0)
    u.hp = 3                            # 受伤状态不应被存档保留
    r = Unit.from_dict(u.to_dict())
    assert r.to_dict() == u.to_dict()
    assert r.hp == r.max_hp             # 读档满血
    assert r.team == 'player'
    # 职业派生属性来自职业表，不来自存档
    assert r.mov == 5 and r.weapon == 'sword' and r.growth


def test_flying_class_flag():
    peg = Unit('艾莉丝', 'pegasus', 'player', (0, 0))
    assert peg.fly
    assert not make_lord().fly


def test_cleric_cannot_attack_but_heals():
    import combat
    thea = Unit('西娅', 'cleric', 'player', (0, 0))
    assert not combat.can_attack(thea)
    assert combat.can_attack(make_lord())
    assert combat.heal_amount(thea) == 10 + thea.pow
