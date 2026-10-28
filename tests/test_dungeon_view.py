from arcana_editor.dungeon_view import move_position, relative_position, tile_at, visible_cells


def test_relative_position_for_each_direction() -> None:
    assert relative_position(10, 10, 0, 0, 2) == (10, 8)
    assert relative_position(10, 10, 1, 0, 2) == (12, 10)
    assert relative_position(10, 10, 2, 1, 2) == (9, 12)
    assert relative_position(10, 10, 3, -1, 2) == (8, 11)


def test_movement_respects_walls() -> None:
    tiles = bytearray(32 * 32)
    tiles[10 * 32 + 10] = 0x30
    tiles[9 * 32 + 10] = 0x30
    assert move_position(tiles, 10, 10, 0) == (10, 9)
    assert move_position(tiles, 10, 10, 1) == (10, 10)
    assert tile_at(tiles, -1, 0) == 0


def test_visible_cells_cover_corridor() -> None:
    tiles = bytearray([0x30] * (32 * 32))
    cells = visible_cells(tiles, 16, 16, 0, depth=3)
    assert len(cells) == 12
    assert cells[0].depth == 0
    assert cells[-1].depth == 3
