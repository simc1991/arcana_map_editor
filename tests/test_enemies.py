from pathlib import Path

import pytest

from arcana_editor.enemies import read_enemies
from arcana_editor.rom import ArcanaRom

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_enemies_are_decoded_from_rom() -> None:
    rom = ArcanaRom(ROM)
    assert rom.enemies == read_enemies(rom.data)
    assert len(rom.enemies) == 79
    slime = rom.enemies[0]
    assert slime.name == "Slime"
    assert slime.hp == 3
    assert slime.exp == 1
    assert slime.gp == 4
    assert slime.level == 1
    boss = rom.enemies[78]
    assert boss.name == "Rimsala"
    assert boss.hp == 1500
    assert boss.level == 40


def test_enemy_key_and_display() -> None:
    from arcana_editor.enemies import Enemy
    enemy = Enemy(5, "Hound", hp=10)
    assert enemy.key == "05"
    assert "$05" in enemy.display and "Hound" in enemy.display
