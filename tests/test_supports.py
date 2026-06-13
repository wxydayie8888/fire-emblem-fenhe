import supports
from unit import Unit


def at(name, cls, pos, team='player'):
    return Unit(name, cls, team, pos)


def test_no_bonus_when_isolated():
    roy = at('罗伊', 'lord', (5, 5))
    b = supports.support_bonus(roy, [roy])
    assert b == {'hit': 0, 'avoid': 0, 'crit': 0, 'dmg': 0}


def test_generic_adjacent_ally():
    roy = at('罗伊', 'lord', (5, 5))
    ally = at('加斯', 'knight', (5, 6))           # 相邻、非剧情CP
    b = supports.support_bonus(roy, [roy, ally])
    assert b['hit'] == supports.GENERIC['hit']
    assert b['avoid'] == supports.GENERIC['avoid']


def test_story_pair_stronger():
    roy = at('罗伊', 'lord', (5, 5))
    lil = at('莉莉娜', 'mage', (5, 6))            # 罗伊×莉莉娜 是剧情CP
    b = supports.support_bonus(roy, [roy, lil])
    assert b['hit'] > supports.GENERIC['hit']
    assert b['crit'] >= 5


def test_only_adjacent_counts():
    roy = at('罗伊', 'lord', (5, 5))
    far = at('莉莉娜', 'mage', (5, 8))            # 距离3，不相邻
    assert supports.support_bonus(roy, [roy, far])['hit'] == 0


def test_enemy_gets_no_support():
    e = at('敌', 'fighter', (5, 5), team='enemy')
    e2 = at('敌2', 'soldier', (5, 6), team='enemy')
    assert supports.support_bonus(e, [e, e2])['hit'] == 0


def test_great_lord_aura_stacks():
    great = at('罗伊', 'lord', (5, 5)); great.level = 12; great.promote()
    assert great.cls == 'great_lord'
    ally = at('加斯', 'knight', (5, 6))
    b = supports.support_bonus(ally, [ally, great])
    # 普通相邻 + 大将鼓舞光环
    assert b['avoid'] >= supports.GENERIC['avoid'] + 10


def test_bonus_capped():
    roy = at('罗伊', 'lord', (5, 5))
    allies = [roy,
              at('莉莉娜', 'mage', (5, 4)),
              at('丽贝卡', 'archer', (5, 6)),
              at('兰斯', 'cavalier', (4, 5)),
              at('菲尔', 'myrmidon', (6, 5))]
    b = supports.support_bonus(roy, allies)
    assert b['hit'] <= supports.CAP and b['avoid'] <= supports.CAP
