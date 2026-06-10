from unit import Unit


def make_lord():
    return Unit('罗伊', 'lord', 'player', (2, 4))


def test_init_from_class():
    u = make_lord()
    assert (u.hp, u.max_hp, u.pow, u.mov) == (20, 20, 6, 5)
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
    assert u.max_hp == 21 and u.hp == 21 and u.pow == 7


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
