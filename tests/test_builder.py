from pathlib import Path
import random
import struct

import pytest

from arcana_editor.builder import build_rom
from arcana_editor.compression import compress_hal
from arcana_editor.encounters import EncounterGroup
from arcana_editor.events import MapEvent, default_properties
from arcana_editor.project import ArcanaProject
from arcana_editor.rom import ArcanaRom, MAP_POINTER_TABLE_PC, RomError, decompress_hal, snes_lorom_to_pc

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


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_builder_injects_items_shops_and_encounters(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    dagger = next(item for item in project.items if item.name == "Dagger")
    project.save_item(dagger.clone(
        name="Dagger Plus", price=250, attack=25, defense=0,
        equippable_by=["Rooks"], vendors=["Outfitter — Chapitre 1", "Outfitter — Chapitre 2"],
    ), dagger.key)
    source_group = next(group for group in project.encounter_groups if group.chapter == 1)
    project.save_encounter_group(EncounterGroup(1, source_group.group_id, 7, (5, 5, 9), (), source_group.flags))
    destination = tmp_path / "Arcana Items.sfc"
    report = build_rom(project, destination)
    assert report.items_written > 100
    assert report.shop_slots_written >= 80
    assert report.encounters_written == len(rom.encounter_groups)
    rebuilt = ArcanaRom(destination)
    edited = next(item for item in rebuilt.items if item.name == "Dagger Plus")
    assert edited.price == 250
    assert edited.attack == 25
    assert edited.equippable_by == ["Rooks"]
    assert edited.vendors == ["Outfitter — Chapitre 1", "Outfitter — Chapitre 2"]
    rebuilt_group = next(group for group in rebuilt.encounter_groups if group.chapter == 1 and group.group_id == source_group.group_id)
    assert rebuilt_group.zone == 7
    assert rebuilt_group.enemy_ids == (5, 5, 9)


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_builder_injects_enemy_stats(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    slime = project.enemies[0]
    project.save_enemy(slime.clone(
        name="Mega Slime", hp=250, exp=99, gp=123, level=9,
        strength=77, race=3, element=5, spell=4, attack_animation=20,
    ), slime.key)
    destination = tmp_path / "Arcana Enemies.sfc"
    report = build_rom(project, destination)
    assert report.enemies_written == 79
    rebuilt = ArcanaRom(destination)
    edited = rebuilt.enemies[0]
    assert edited.name == "Mega Slime"
    assert (edited.hp, edited.exp, edited.gp, edited.level, edited.strength) == (250, 99, 123, 9, 77)
    assert (edited.race, edited.element, edited.spell, edited.attack_animation) == (3, 5, 4, 20)


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_builder_injects_spell_stats(tmp_path: Path) -> None:
    from arcana_editor.spells import Spell
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    project.save_spell(Spell(1, "Storm Bolt", accuracy=200, power=999, element=5))
    destination = tmp_path / "Arcana Spells.sfc"
    report = build_rom(project, destination)
    assert report.spells_written == 91
    rebuilt = ArcanaRom(destination)
    edited = rebuilt.spells[1]
    assert edited.name == "Storm Bolt"
    assert (edited.accuracy, edited.power, edited.element) == (200, 999, 5)


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_ips_patch_contains_differences(tmp_path: Path) -> None:
    from arcana_editor.patches import build_ips_patch
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    slime = project.enemies[0]
    project.save_enemy(slime.clone(name="Patched", hp=77), slime.key)
    destination = tmp_path / "Arcana Patch.sfc"
    build_rom(project, destination)
    patch = build_ips_patch(rom.data, destination.read_bytes())
    assert patch.startswith(b"PATCH")
    assert patch.endswith(b"EOF")
    rebuilt = rom.data[:]
    destination_bytes = destination.read_bytes()
    changed = [i for i in range(len(rebuilt)) if rebuilt[i] != destination_bytes[i]]
    assert len(patch) >= 5
    assert changed


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_builder_injects_enemy_sprite(tmp_path: Path) -> None:
    from arcana_editor.sprites import image_to_enemy_tiles

    class FakeImage:
        def width(self) -> int:
            return 32

        def height(self) -> int:
            return 16

        def get(self, x: int, y: int) -> tuple[int, int, int]:
            return (64, 192, 96) if x < 16 else (32, 96, 192)

    tiles, palette, width, height = image_to_enemy_tiles(FakeImage())
    assert width == 32 and height == 16
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    slime = project.enemies[0]
    project.save_enemy(slime.clone(
        sprite_tiles=tiles.hex(),
        sprite_palette=b"".join(int(v).to_bytes(2, "little") for v in palette).hex(),
        sprite_w=width, sprite_h=height,
    ), slime.key)
    destination = tmp_path / "Arcana Sprite.sfc"
    report = build_rom(project, destination)
    assert report.enemies_written == 79
    assert destination.read_bytes() != rom.data


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_builder_rejects_invalid_item_data(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    herbs = next(item for item in project.items if item.key == "Objet:0B")
    project.save_item(herbs.clone(name="Un nom beaucoup trop long pour le ROM"), herbs.key)
    with pytest.raises(RomError):
        build_rom(project, tmp_path / "bad.sfc")
