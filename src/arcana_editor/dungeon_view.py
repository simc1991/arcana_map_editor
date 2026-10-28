from __future__ import annotations

from dataclasses import dataclass

from .rom import MAP_HEIGHT, MAP_WIDTH

DIRECTION_NAMES = ("Nord", "Est", "Sud", "Ouest")
DIRECTION_VECTORS = ((0, -1), (1, 0), (0, 1), (-1, 0))


@dataclass(frozen=True)
class ViewCell:
    x: int
    y: int
    depth: int
    lateral: int
    value: int


def relative_position(x: int, y: int, direction: int, lateral: int, depth: int) -> tuple[int, int]:
    forward_x, forward_y = DIRECTION_VECTORS[direction % 4]
    right_x, right_y = DIRECTION_VECTORS[(direction + 1) % 4]
    return x + forward_x * depth + right_x * lateral, y + forward_y * depth + right_y * lateral


def tile_at(tiles: bytes | bytearray, x: int, y: int) -> int:
    if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT:
        return tiles[y * MAP_WIDTH + x]
    return 0


def visible_cells(tiles: bytes | bytearray, x: int, y: int, direction: int, depth: int = 5) -> tuple[ViewCell, ...]:
    cells = []
    for distance in range(depth + 1):
        for lateral in (-1, 0, 1):
            cell_x, cell_y = relative_position(x, y, direction, lateral, distance)
            cells.append(ViewCell(cell_x, cell_y, distance, lateral, tile_at(tiles, cell_x, cell_y)))
    return tuple(cells)


def move_position(tiles: bytes | bytearray, x: int, y: int, direction: int, amount: int = 1) -> tuple[int, int]:
    target_x, target_y = relative_position(x, y, direction, 0, amount)
    if tile_at(tiles, target_x, target_y) != 0:
        return target_x, target_y
    return x, y
