from pathlib import Path

import pytest

from arcana_editor.encounters import chapter_for_map, read_encounter_groups
from arcana_editor.rom import ArcanaRom

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


def test_map_chapter_mapping() -> None:
    assert chapter_for_map(0) == 1
    assert chapter_for_map(2) == 2
    assert chapter_for_map(5) == 3
    assert chapter_for_map(8) == 4
    assert chapter_for_map(22) == 5


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_encounter_groups_are_decoded_from_rom() -> None:
    rom = ArcanaRom(ROM)
    assert rom.encounter_groups == read_encounter_groups(rom.data)
    assert len(rom.encounter_groups) == 52
    chapter_one = rom.encounters_for_map(0)
    assert len(chapter_one) == 8
    assert chapter_one[0].group_id == 0
    assert chapter_one[0].zone == 0x0A
    assert chapter_one[0].enemy_names == ("Slime", "Goblin", "Hound", "Saurian", "Gurgeon")
    assert "Groupe $0" in chapter_one[0].display
    assert len(rom.encounters_for_map(22)) == 13
