from ai import plan_action
from grid import Grid
from unit import Unit

PLAIN = ["PPPPPPPP"] * 6


def test_attacks_reachable_target():
    g = Grid(PLAIN)
    e = Unit('斧', 'fighter', 'enemy', (3, 3))
    p = Unit('主', 'lord', 'player', (5, 3))
    act = plan_action(e, g, [e, p])
    assert act['target'] is p
    # 落点必须与目标相邻（斧射程1）
    mx, my = act['move']
    assert abs(mx - 5) + abs(my - 3) == 1


def test_prefers_kill():
    g = Grid(PLAIN)
    e = Unit('斧', 'fighter', 'enemy', (3, 3))
    healthy = Unit('壮', 'cavalier', 'player', (1, 3))
    dying = Unit('残', 'mage', 'player', (5, 3))
    dying.hp = 2
    act = plan_action(e, g, [e, healthy, dying])
    assert act['target'] is dying


def test_moves_toward_nearest_when_out_of_reach():
    g = Grid(["PPPPPPPPPPPPPP"] * 4)
    e = Unit('斧', 'fighter', 'enemy', (0, 0))
    p = Unit('主', 'lord', 'player', (13, 3))
    act = plan_action(e, g, [e, p])
    assert act['target'] is None
    mx, my = act['move']
    assert (mx - 0) + (my - 0) == 5      # 用满5移动力逼近


def test_boss_stays_put():
    g = Grid(PLAIN)
    boss = Unit('B', 'warrior', 'enemy', (3, 3), boss=True)
    far = Unit('主', 'lord', 'player', (7, 5))
    act = plan_action(boss, g, [boss, far])
    assert act == {'move': (3, 3), 'target': None}
    near = Unit('近', 'lord', 'player', (3, 4))
    act = plan_action(boss, g, [boss, far, near])
    assert act['move'] == (3, 3) and act['target'] is near
