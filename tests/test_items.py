from pathlib import Path

import pytest

from arcana_editor.items import read_item_catalog
from arcana_editor.rom import ArcanaRom

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_catalog_is_decoded_from_rom() -> None:
    rom = ArcanaRom(ROM)
    assert rom.items == read_item_catalog(rom.data)
    assert len(rom.items) == 145
    categories = {item.category for item in rom.items}
    assert categories == {"Objet", "Arme", "Armure", "Bouclier", "Accessoire", "Carte", "Monnaie"}
    assert rom.items[0].name == "Gold"
    assert rom.items[1].name == "Return Ring"
    assert any(item.name == "Water of Life" and item.item_id == 2 for item in rom.items)
    assert any(item.name == "Crystal Sword" and item.category == "Arme" for item in rom.items)
    dagger = next(item for item in rom.items if item.name == "Dagger")
    assert dagger.price == 100
    assert dagger.resale_value == 50
    assert dagger.attack == 20
    assert dagger.equippable_by == ["Rooks", "Teefa", "Salah", "Darwin", "Axs"]
    crystal_sword = next(item for item in rom.items if item.name == "Crystal Sword")
    assert crystal_sword.attack == 230
    assert crystal_sword.equippable_by == ["Rooks"]
    magic_shield = next(item for item in rom.items if item.name == "Magic Shield")
    assert magic_shield.defense == 160
    assert magic_shield.magic_defense == 35
    assert magic_shield.equippable_by == ["Salah"]
    assert any(item.name == "Call Amulet" and item.category == "Carte" for item in rom.items)
    treasure = rom.treasure_at(0, 7, 2)
    assert treasure is not None
    assert rom.treasure_properties(treasure)["contenu"] == "Gold"
    assert rom.treasure_properties(treasure)["quantité"] == 300


def test_catalog_display_and_keys() -> None:
    data = bytearray(0x40000)
    data[0x2EE9A + 20:0x2EE9A + 40] = b"Test Item          \x00"
    catalog = read_item_catalog(bytes(data))
    assert catalog[0].key == "Monnaie:00"
    assert catalog[1].key == "Objet:01"
    assert "Test Item" in catalog[1].display
