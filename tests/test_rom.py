from pathlib import Path

import pytest

from arcana_editor.rom import ArcanaRom, KNOWN_CRC32, MAP_COUNT, RomError, decompress_hal, snes_lorom_to_pc

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


def test_lorom_conversion() -> None:
    assert snes_lorom_to_pc(0x008000) == 0
    assert snes_lorom_to_pc(0x138000) == 0x98000
    assert snes_lorom_to_pc(0x13EBF6) == 0x9EBF6
    with pytest.raises(RomError):
        snes_lorom_to_pc(0x130000)


def test_decompress_commands() -> None:
    stream = bytes([
        0x02, 1, 2, 3,
        0x22, 7,
        0x41, 8, 9,
        0x62, 10,
        0x83, 0, 0,
        0xFF,
    ])
    output, consumed = decompress_hal(stream, 0)
    assert output == bytes([1, 2, 3, 7, 7, 7, 8, 9, 8, 9, 10, 11, 12, 1, 2, 3, 7])
    assert consumed == len(stream)


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_arcana_rom_and_maps() -> None:
    rom = ArcanaRom(ROM)
    assert rom.info.crc32 == KNOWN_CRC32
    assert rom.info.is_known_dump
    assert len(rom.maps) == MAP_COUNT
    assert len(rom.unique_maps()) == 14
    assert len(rom.stairs) > 400
    balnea_stair = rom.stair_at(0, 15, 2)
    assert balnea_stair is not None
    assert rom.stair_properties(balnea_stair)["destination_map_index"] == 1
    assert all(len(rom.read_map(index)) == 1024 for index in range(MAP_COUNT))
