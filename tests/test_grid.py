from grid import Grid, move_range, attack_tiles, manhattan
from unit import Unit

# 5x4 测试地图: 中间一道河(x2)，(2,2)是桥，右上有山
TEST_MAP = [
    "PPWPM",
    "PPWPP",
    "PFBPP",
    "PPWPP",
]


def g():
    return Grid(TEST_MAP)


def test_terrain_lookup():
    assert g().terrain(2, 0)['cost'] is None      # 水
    assert g().terrain(1, 2)['cost'] == 2          # 森林
    assert g().terrain(4, 0).get('no_mount')       # 山


def test_move_range_costs_and_water():
    u = Unit('u', 'lord', 'player', (0, 2))        # mov 5
    r = move_range(u, g(), [u])
    assert (0, 2) in r                              # 原地
    assert (2, 2) in r                              # 桥可走
    assert (2, 0) not in r and (2, 1) not in r      # 水不可走
    assert (3, 2) in r                              # 过桥
    # 森林耗2: 从(0,2)直走到(1,2)耗2
    assert r[(1, 2)] == 2


def test_mounted_cannot_enter_mountain():
    u = Unit('u', 'cavalier', 'player', (3, 0))    # mov 7, 骑马
    r = move_range(u, g(), [u])
    assert (4, 0) not in r
    foot = Unit('f', 'lord', 'player', (3, 0))
    assert (4, 0) in move_range(foot, g(), [foot])


def test_enemy_blocks_path_ally_blocks_stop():
    u = Unit('u', 'lord', 'player', (0, 0))
    enemy = Unit('e', 'fighter', 'enemy', (1, 0))
    ally = Unit('a', 'archer', 'player', (0, 1))
    r = move_range(u, g(), [u, enemy, ally])
    assert (1, 0) not in r          # 敌人占的格不可停
    assert (0, 1) not in r          # 友军占的格不可停
    # 友军可穿过: (0,1)被友军占，但(0,2)可达
    assert (0, 2) in r


def test_attack_tiles_ring():
    tiles = attack_tiles((2, 2), (2, 2), g())       # 弓: 只打2格
    assert (2, 0) in tiles and (4, 2) in tiles and (3, 3) in tiles
    assert (2, 1) not in tiles and (2, 2) not in tiles


def test_manhattan():
    assert manhattan((0, 0), (3, 4)) == 7
