from pathlib import Path

import pytest

from arcana_editor.events import MapEvent
from arcana_editor.items import GameItem
from arcana_editor.project import ArcanaProject
from arcana_editor.rom import ArcanaRom

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_project_round_trip_and_shared_maps(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    original = project.map_for_entry(8)[0]
    project.set_tile(8, 0, 0, original ^ 0xFF)
    assert project.map_for_entry(9)[0] == original ^ 0xFF
    destination = tmp_path / "test.arcana.json"
    project.save(destination)
    loaded = ArcanaProject.load(rom, destination)
    assert loaded.map_for_entry(8) == project.map_for_entry(8)
    assert not loaded.dirty


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_structured_event_round_trip(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    address = rom.maps[0].snes_address
    event = MapEvent(address, 1, 1, 0x80, "Coffre de test", "Visible après le boss", {"contenu": "Potion", "quantité": 2})
    project.update_event(0, event, 1, 1)
    assert project.event_at(0, 1, 1).display_name == "Coffre de test"
    destination = tmp_path / "events.arcana.json"
    project.save(destination)
    loaded = ArcanaProject.load(rom, destination)
    restored = loaded.event_at(0, 1, 1)
    assert restored is not None
    assert restored.properties["contenu"] == "Potion"
    loaded.remove_event(0, 1, 1)
    assert loaded.event_at(0, 1, 1) is None


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_custom_item_database_round_trip(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    item = GameItem(
        "Arme", project.next_item_id("Arme"), "Lame Devin", description="Arme de test",
        price=1234, resale_value=617, attack=42, magic_defense=3,
        equippable_by=["Rooks"], vendors=["Outfitter — Chapitre 1"], custom=True,
    )
    project.save_item(item)
    assert next(candidate for candidate in project.items if candidate.key == item.key).attack == 42
    destination = tmp_path / "items.arcana.json"
    project.save(destination)
    loaded = ArcanaProject.load(rom, destination)
    restored = next(candidate for candidate in loaded.items if candidate.key == item.key)
    assert restored.name == "Lame Devin"
    assert restored.price == 1234
    assert restored.vendors == ["Outfitter — Chapitre 1"]
    assert restored.equippable_by == ["Rooks"]
    loaded.remove_custom_item(restored.key)
    assert all(candidate.key != restored.key for candidate in loaded.items)
