from __future__ import annotations

import struct

from .rom import RomError, decompress_hal

ENEMY_TILESET_TABLE_PC = 0x231A
ENEMY_TILESET_BASE = 0x18
ENEMY_PALETTE_TABLE_PC = 0xC8001
ENEMY_PALETTE_BANK_PC = 0xC80A1
OAM_ENTRY_SIZE = 5
OAM_ENTRIES_PER_FRAME = 6
CANVAS_SIZE = 176
TRANSPARENT = (24, 32, 44)


def _snes_color(value: int) -> tuple[int, int, int]:
    return (value & 0x1F) * 8, ((value >> 5) & 0x1F) * 8, ((value >> 10) & 0x1F) * 8


def _lorom_pc(address: int) -> int:
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def enemy_palette(data: bytes, enemy_id: int) -> tuple[tuple[int, int, int], ...]:
    pointer = struct.unpack_from("<H", data, ENEMY_PALETTE_TABLE_PC + enemy_id * 2)[0]
    header = _lorom_pc((data[ENEMY_PALETTE_BANK_PC + enemy_id] << 16) | pointer)
    size = struct.unpack_from("<H", data, header + 2)[0]
    colors = struct.unpack_from(f"<{size // 2}H", data, header + 4)
    return tuple(_snes_color(value) for value in colors)


def enemy_tiles(data: bytes, enemy_id: int) -> tuple[bytes, int]:
    pointer = struct.unpack_from("<H", data, ENEMY_PALETTE_TABLE_PC + enemy_id * 2)[0]
    header = _lorom_pc((data[ENEMY_PALETTE_BANK_PC + enemy_id] << 16) | pointer)
    palette_size = struct.unpack_from("<H", data, header + 2)[0]
    gfx_offset = header + 4 + palette_size
    gfx_address = data[gfx_offset] | (data[gfx_offset + 1] << 8) | (data[gfx_offset + 2] << 16)
    offset = _lorom_pc(gfx_address)
    destination = struct.unpack_from("<H", data, offset)[0]
    decoded, _ = decompress_hal(data, offset + 2, 0x20000)
    return decoded, max(0, (destination - 0x6000) // 16)


def build_enemy_tile_buffer(data: bytes, count: int = 80) -> dict[int, bytes]:
    buffer: dict[int, bytes] = {}
    for enemy_id in range(count):
        try:
            tiles, base = enemy_tiles(data, enemy_id)
        except (RomError, IndexError, struct.error):
            continue
        for index in range(len(tiles) // 32):
            buffer.setdefault(base + index, tiles[index * 32:(index + 1) * 32])
    return buffer


def _tile_row(tile: bytes, row: int) -> tuple[int, ...]:
    plane01 = row * 2
    plane23 = 16 + row * 2
    bits = (tile[plane01], tile[plane01 + 1], tile[plane23], tile[plane23 + 1])
    return tuple(
        ((bits[0] >> (7 - column)) & 1) | (((bits[1] >> (7 - column)) & 1) << 1)
        | (((bits[2] >> (7 - column)) & 1) << 2) | (((bits[3] >> (7 - column)) & 1) << 3)
        for column in range(8)
    )


def _draw_tile(pixels: list, tile: bytes, x0: int, y0: int, palette: tuple[tuple[int, int, int], ...], hflip: bool, vflip: bool) -> None:
    for row in range(8):
        source_row = 7 - row if vflip else row
        line = _tile_row(tile, source_row)
        if hflip:
            line = line[::-1]
        y = y0 + row
        if not 0 <= y < CANVAS_SIZE:
            continue
        for column in range(8):
            x = x0 + column
            index = line[column]
            if index and 0 <= x < CANVAS_SIZE:
                pixels[y * CANVAS_SIZE + x] = palette[index] if index < len(palette) else index


def enemy_frame_table(data: bytes, enemy_id: int) -> tuple[int, ...]:
    table_address = data[ENEMY_TILESET_TABLE_PC + (ENEMY_TILESET_BASE + enemy_id) * 3:][:3]
    address = table_address[0] | (table_address[1] << 8) | (table_address[2] << 16)
    table = _lorom_pc(address)
    pointers = []
    for index in range(40):
        pointer = struct.unpack_from("<H", data, table + index * 2)[0]
        offset = _lorom_pc((0x09 << 16) | pointer)
        if not 0x8000 <= pointer < 0x10000 or offset >= len(data):
            break
        if pointer in pointers:
            break
        pointers.append(pointer)
    return tuple(pointers)


def _parse_frame_entries(data: bytes, offset: int, depth: int = 0) -> tuple[tuple[int, int, int, int, int], ...]:
    entries: list[tuple[int, int, int, int, int]] = []
    for _ in range(128):
        if offset + OAM_ENTRY_SIZE > len(data) or depth > 4:
            break
        flags, x, y, tile, attr = struct.unpack_from("<5B", data, offset)
        if flags & 0x80:
            target = (flags << 8) | (x & 0xFF)
            entries.extend(_parse_frame_entries(data, _lorom_pc((0x09 << 16) | target), depth + 1))
            break
        entries.append((flags, x if x < 0x80 else x - 0x100, y if y < 0x80 else y - 0x100, tile, attr))
        offset += OAM_ENTRY_SIZE
        if flags & 0x02:
            break
    return tuple(entries)


def enemy_frame_entries(data: bytes, enemy_id: int, frame: int = 0) -> tuple[tuple[int, int, int, int, int], ...]:
    pointers = enemy_frame_table(data, enemy_id)
    return _parse_frame_entries(data, _lorom_pc((0x09 << 16) | pointers[frame]))


def _render_frame(buffer: dict[int, bytes], palette: tuple[tuple[int, int, int], ...], entries: tuple[tuple[int, int, int, int, int], ...]) -> tuple[list, int]:
    pixels = [TRANSPARENT] * (CANVAS_SIZE * CANVAS_SIZE)
    center = CANVAS_SIZE // 2
    for flags, x, y, tile, attr in entries:
        hflip = bool(attr & 0x40)
        vflip = bool(attr & 0x80)
        x0, y0 = center + x, center + y
        if flags & 0x01:
            tilemap = ((tile, tile + 1), (tile + 0x10, tile + 0x11))
        else:
            tilemap = ((tile,),)
        if hflip:
            tilemap = tuple(row[::-1] for row in tilemap)
        if vflip:
            tilemap = tilemap[::-1]
        for block_row, row_tiles in enumerate(tilemap):
            for block_column, index in enumerate(row_tiles):
                block = buffer.get(index)
                if block:
                    _draw_tile(pixels, block, x0 + block_column * 8, y0 + block_row * 8, palette, hflip, vflip)
    drawn = sum(1 for pixel in pixels if pixel != TRANSPARENT)
    return pixels, drawn


def enemy_tile_buffer(data: bytes, enemy_id: int, shared: dict[int, bytes] | None = None) -> dict[int, bytes]:
    buffer = dict(shared) if shared is not None else build_enemy_tile_buffer(data)
    try:
        tiles, base = enemy_tiles(data, enemy_id)
    except (RomError, IndexError, struct.error):
        return buffer
    for index in range(len(tiles) // 32):
        buffer[base + index] = tiles[index * 32:(index + 1) * 32]
    return buffer


def _own_tile_buffer(data: bytes, enemy_id: int) -> dict[int, bytes]:
    try:
        tiles, base = enemy_tiles(data, enemy_id)
    except (RomError, IndexError, struct.error):
        return {}
    return {base + index: tiles[index * 32:(index + 1) * 32] for index in range(len(tiles) // 32)}


def enemy_sprite_rgb(data: bytes, enemy_id: int, frame: int | None = None, shared: dict[int, bytes] | None = None) -> bytes:
    try:
        palette = enemy_palette(data, enemy_id)
        pointers = enemy_frame_table(data, enemy_id)
    except (RomError, IndexError, struct.error):
        return b""
    own = _own_tile_buffer(data, enemy_id)
    buffers = [own]
    if shared is not None:
        merged = dict(shared)
        merged.update(own)
        buffers.append(merged)
    if frame is not None:
        try:
            entries = enemy_frame_entries(data, enemy_id, frame)
        except (IndexError, struct.error):
            return b""
        pixels, _ = _render_frame(buffers[-1], palette, entries)
        if not any(pixel != TRANSPARENT for pixel in pixels):
            return b""
    else:
        pixels = []
        order = sorted(range(len(pointers)), key=lambda index: pointers[index] >= 0xC000)
        for buffer in buffers:
            found = False
            for candidate in order:
                try:
                    candidate_pixels, drawn = _render_frame(buffer, palette, enemy_frame_entries(data, enemy_id, candidate))
                except (IndexError, struct.error):
                    continue
                if drawn:
                    pixels = candidate_pixels
                    found = True
                    break
            if found:
                break
        if not pixels:
            return b""
    rgb = bytearray()
    for r, g, b in pixels:
        rgb += bytes((r, g, b))
    header = f"P6 {CANVAS_SIZE} {CANVAS_SIZE} 255\n".encode("ascii")
    return header + bytes(rgb)
