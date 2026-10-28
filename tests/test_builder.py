from pathlib import Path
import random
import struct

import pytest

from arcana_editor.builder import build_rom
from arcana_editor.compression import compress_hal
from arcana_editor.events import MapEvent, default_properties
from arcana_editor.project import ArcanaProject
from arcana_editor.rom import ArcanaRom, MAP_POINTER_TABLE_PC, decompress_hal, snes_lorom_to_pc

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


def test_hal_compressor_round_trips_patterns() -> None:
    samples = [
        bytes([0] * 1024),
        bytes(range(256)) * 4,
        bytes([1, 2] * 512),
        bytes((index * 17) & 0xFF for index in range(1024)),
        random.Random(42).randbytes(1024),
    ]
    for sample in samples:
        compressed = compress_hal(sample)
        decoded, consumed = decompress_hal(compressed, 0, 1025)
        assert decoded == sample
        assert consumed == len(compressed)


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_build_rom_injects_maps_and_updates_checksum(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    original = project.map_for_entry(0)[2 * 32 + 7]
    project.set_tile(0, 7, 2, original ^ 1)
    chest = project.event_at(0, 7, 2)
    assert chest is not None
    chest.properties["quantité"] = 999
    project.update_event(0, chest, 7, 2)
    stair = project.event_at(0, 15, 1)
    assert stair is not None
    stair.properties["destination_map_index"] = 1
    stair.properties["destination"] = "Balnea 2F"
    stair.properties["x_cible"] = 10
    stair.properties["y_cible"] = 11
    stair.properties["direction"] = "Est"
    project.update_event(0, stair, 15, 1)
    destination = tmp_path / "Arcana Mod.sfc"
    report = build_rom(project, destination)
    built = destination.read_bytes()
    assert len(built) == len(rom.data)
    assert report.maps_written == 14
    assert report.treasures_written >= len(rom.treasures)
    assert report.stairs_written > 100
    assert report.compressed_bytes <= report.available_bytes
    rebuilt = ArcanaRom(destination)
    rebuilt_chest = rebuilt.treasure_at(0, 7, 2)
    assert rebuilt_chest is not None and rebuilt_chest.value == 999
    rebuilt_stair = rebuilt.stair_at(0, 15, 2)
    assert rebuilt_stair is not None
    assert (rebuilt_stair.destination, rebuilt_stair.target_x, rebuilt_stair.target_y, rebuilt_stair.direction) == (0x0101, 10, 11, 2)
    assert struct.unpack_from("<H", built, 0x7FDE)[0] == report.checksum
    assert struct.unpack_from("<H", built, 0x7FDC)[0] == report.checksum ^ 0xFFFF
    assert sum(built) & 0xFFFF == report.checksum
    pointer = struct.unpack_from("<H", built, MAP_POINTER_TABLE_PC)[0]
    decoded, _ = decompress_hal(built, snes_lorom_to_pc((0x13 << 16) | pointer), 1025)
    assert decoded == bytes(project.map_for_entry(0))
    assert ROM.read_bytes() == rom.data


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_builder_allocates_new_chest_and_converts_external_exit(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    address = rom.maps[0].snes_address
    new_chest = MapEvent(address, 1, 1, 0x80, properties={
        "contenu": "Herbs", "quantité": 1, "item_id": 11, "catégorie": "Objet", "type_trésor": 1,
    })
    project.update_event(0, new_chest, 1, 1)
    external = project.event_at(0, 15, 30)
    assert external is not None
    external.properties.update(destination_map_index=1, destination="Balnea 2F", x_cible=2, y_cible=3, direction="Sud")
    project.update_event(0, external, 15, 30)
    destination = tmp_path / "Arcana Allocated.sfc"
    report = build_rom(project, destination)
    rebuilt = ArcanaRom(destination)
    allocated = rebuilt.treasure_at(0, 1, 1)
    assert allocated is not None
    assert (allocated.treasure_type, allocated.value) == (1, 11)
    converted = rebuilt.stair_at(0, 15, 29)
    assert converted is not None
    assert (converted.destination, converted.target_x, converted.target_y, converted.direction) == (0x0101, 2, 3, 4)
    assert not report.warnings
