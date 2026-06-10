import settings


def test_map_dimensions():
    assert len(settings.MAP) == settings.GRID_H == 10
    assert all(len(row) == settings.GRID_W == 15 for row in settings.MAP)


def test_map_only_known_terrain():
    for row in settings.MAP:
        for ch in row:
            assert ch in settings.TERRAIN


def test_units_start_on_passable_tiles():
    for u in settings.PLAYER_UNITS + settings.ENEMY_UNITS:
        x, y = u['pos']
        ch = settings.MAP[y][x]
        assert settings.TERRAIN[ch]['cost'] is not None
        assert u['cls'] in settings.CLASSES
